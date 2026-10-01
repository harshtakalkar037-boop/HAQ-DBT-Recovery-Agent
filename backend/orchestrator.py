"""Stateful workflow orchestration.

USER -> SAMVAAD -> KHOJ -> NIDAAN -> YOJNA -> KARM -> SATYAPAN -> ANUSARAN -> USER
NEW EVIDENCE -> SATYAPAN (detect) -> NIDAAN -> YOJNA (RE-PLAN) -> KARM -> SATYAPAN -> ANUSARAN

Runs in a background thread per case; every stage emits events the frontend polls
so judges SEE the agents working. Small sleeps make the workflow legible."""
from __future__ import annotations
import threading, time
from .core import CaseStore, now_iso
from .extract import extract_from_document, build_identity_graph, interpret_narrative
from .adapters import build_tools
from . import agents as ag
from .seed import materialize_seed, derive_profile_from_case

PAUSE = 0.55  # seconds between agent stages — demo legibility


class Orchestrator:
    def __init__(self, store: CaseStore):
        self.store = store
        self.tools = build_tools()
        self._locks: dict[str, threading.Lock] = {}

    # ------------------------------------------------------------- plumbing
    def _emit(self, case_id: str, agent: str, action: str, detail: str, *,
              status: str = "WORK", source: str | None = None, extra: dict | None = None):
        ev = {"agent": agent, "action": action, "detail": detail, "status": status,
              "source": source, "ts": now_iso()}
        if extra:
            ev.update(extra)
        return self.store.add_event(case_id, ev)

    def _emit_fn(self, case_id: str):
        """Emitter for agent functions: emit(agent, action, detail, status=..., extra=...)."""
        def emit(agent: str, action: str, detail: str, *, status: str = "WORK",
                 source: str | None = None, extra: dict | None = None):
            return self._emit(case_id, agent, action, detail, status=status, source=source, extra=extra)
        return emit

    def _get(self, case_id: str) -> dict:
        case = self.store.get_case(case_id)
        if not case:
            raise KeyError(case_id)
        return case

    def _save(self, case: dict) -> dict:
        return self.store.update_case(case)

    def _lock_for(self, case_id: str) -> threading.Lock:
        if case_id not in self._locks:
            self._locks[case_id] = threading.Lock()
        return self._locks[case_id]

    # ------------------------------------------------------------- SAMVAAD
    def _samvaad(self, case: dict, new_docs: list[dict] | None = None) -> None:
        cid = case["id"]
        all_docs = case.get("documents") or []
        fresh_ids = {id(d) for d in (new_docs or [])} or {id(d) for d in all_docs}
        docs_to_announce = new_docs if new_docs is not None else all_docs
        self._emit(cid, "SAMVAAD", "START",
                   f"Reading {len(all_docs)} document(s) + beneficiary narrative "
                   f"({case.get('narrative_analysis', {}).get('language_detected', 'hi-en')})…",
                   status="START")
        extractions = []
        for d in all_docs:
            if not d.get("extraction"):
                d["extraction"] = extract_from_document(d)
            extractions.append(d["extraction"])
            if id(d) in fresh_ids or d in docs_to_announce:
                n = len(d["extraction"]["fields"])
                self._emit(cid, "SAMVAAD", "WORK",
                           f"Extracted {n} field(s) from {d['filename']} ({d['kind']})",
                           extra={"doc": d["filename"]})
                time.sleep(PAUSE * 0.5)

        # merge fields with document-kind precedence: AADHAAR > PASSBOOK > SCHEME_LETTER > SMS
        precedence = {"AADHAAR": 0, "PASSBOOK": 1, "SCHEME_LETTER": 2, "SMS": 3, "OTHER": 4}
        merged: dict[str, dict] = {}
        for extr in sorted(extractions, key=lambda e: precedence.get(e["kind"], 5)):
            for k, v in extr["fields"].items():
                if k not in merged:
                    merged[k] = dict(v, source_doc=extr["filename"], source_kind=extr["kind"])
        case.setdefault("extraction", {})
        case["extraction"]["fields"] = merged
        ig = build_identity_graph(extractions)
        case["extraction"]["identity_graph"] = ig

        flags, flag_details = [], []
        for extr in extractions:
            for f in extr["flags"]:
                if f not in flags:
                    flags.append(f)
            flag_details += extr["flag_details"]
        case["evidence_flags"] = flags
        case["evidence_flag_details"] = flag_details

        for m in ig["mismatches"]:
            if m["field"] != "name":
                continue
            involved = any(d.get("filename") in (m["left"].get("doc"), m["right"].get("doc"))
                           for d in docs_to_announce)
            already = any(e.get("detail", "").find(m["left"]["value"][:12]) >= 0 and e["agent"] == "SAMVAAD"
                          and e["action"] == "ALERT" for e in self.store.list_events(cid))
            if (new_docs is None or involved) and not already:
                self._emit(cid, "SAMVAAD", "ALERT",
                           f"NAME MISMATCH DETECTED — {m['left']['kind']}: “{m['left']['value']}” vs "
                           f"{m['right']['kind']}: “{m['right']['value']}”",
                           status="ALERT", extra={"rule": m["rule"]})
                time.sleep(PAUSE * 0.4)
        for det in flag_details:
            self._emit(cid, "SAMVAAD", "ALERT", f"NEW EVIDENCE SIGNAL — {det}", status="ALERT")

        # honest failure states — never silently proceed
        unreadable = [d for d in all_docs if (d.get("extraction") or {}).get("ocr_unreadable")
                      and d.get("text_content", "") == ""]
        if unreadable:
            names = ", ".join(d["filename"] for d in unreadable)
            self._emit(cid, "SAMVAAD", "ALERT",
                       f"OCR UNREADABLE — We couldn't confidently read {names}. Please retake the photo or type the key fields.",
                       status="ALERT", extra={"needs_input": True,
                                              "banner": "We couldn't confidently read one of your documents."})
            case["needs_input"] = {
                "kind": "ocr_unreadable",
                "message": "We couldn't confidently read this document. Please retake the photo or type the key details.",
                "docs": [d["filename"] for d in unreadable],
            }
        conflicts = [m for m in ig["mismatches"] if m.get("type") == "field_conflict"]
        if conflicts:
            self._emit(cid, "SAMVAAD", "ALERT",
                       "CONFLICTING EVIDENCE — conflicting account/identity fields across documents. "
                       "We need one more piece of information before proceeding.",
                       status="ALERT", extra={"needs_input": True,
                                              "banner": "Conflicting evidence detected — one more document needed."})
            case["needs_input"] = {
                "kind": "conflict",
                "message": "Conflicting evidence detected. We need one more piece of information before proceeding.",
                "conflicts": [c["detail"] for c in conflicts],
            }

        n_fields = len(merged)
        n_mis = len(ig["mismatches"])
        self._emit(cid, "SAMVAAD", "DONE",
                   f"{n_fields} fields extracted · identity graph built · {n_mis} inconsistency flag(s)",
                   status="DONE")

    # ------------------------------------------------------------- full pipeline
    def run_initial(self, case_id: str) -> None:
        with self._lock_for(case_id):
            case = self._get(case_id)
            case["status"] = "INVESTIGATING"
            self._save(case)
            self._samvaad(case)
            time.sleep(PAUSE)

            self._emit(case_id, "KHOJ", "START",
                       "Investigating where the payment broke — selecting tools for this case…", status="START")
            profile = case.get("portal_profile") or derive_profile_from_case(case)
            case["portal_profile"] = profile
            emit = self._emit_fn(case_id)
            ag.khoj_investigate(case, self.tools, emit)
            ag.khoj_sufficiency(case, emit)
            chain = " → ".join(
                {"OK": "✓", "FAIL": "✕", "WARN": "●"}[e["status"]] + " " + e["source_label"].split(" —")[0]
                for e in case["evidence"][:5])
            self._emit(case_id, "KHOJ", "WORK", f"Evidence chain: {chain}", status="WORK")
            self._emit(case_id, "KHOJ", "DONE",
                       "Evidence chain complete — required payment-path sources checked.", status="DONE")
            self._save(case)
            time.sleep(PAUSE)

            self._emit(case_id, "NIDAAN", "START", "Scoring the failure taxonomy against the evidence…", status="START")
            diag = ag.nidaan_diagnose(case, self._emit, version=1)
            self._emit(case_id, "NIDAAN", "DONE",
                       f"ROOT CAUSE: {diag['root_cause_code']} · secondary: {diag['secondary_cause_code'] or '—'} "
                       f"· confidence {diag['confidence']:.0%}", status="DONE",
                       extra={"diagnosis": {"root": diag["root_cause_code"], "secondary": diag["secondary_cause_code"],
                                            "confidence": diag["confidence"]}})
            self._save(case)
            time.sleep(PAUSE)

            self._emit(case_id, "YOJNA", "START", "Building a dependency-aware resolution plan…", status="START")
            plan = ag.yojna_plan(case, self._emit, trigger="INITIAL")
            ag.refresh_step_statuses(case)
            n_blocked = sum(1 for s in plan["steps"] if s["status"] == "BLOCKED")
            self._emit(case_id, "YOJNA", "DONE",
                       f"PLAN v{plan['version']} — {len(plan['steps'])}-step plan created "
                       f"({n_blocked} step(s) correctly blocked by NYAYA rules)", status="DONE",
                       extra={"plan_version": plan["version"]})
            self._save(case)
            time.sleep(PAUSE)

            self._emit(case_id, "KARM", "START", "Generating the action pack from fixed templates…", status="START")
            generated = ag.karm_generate(case, plan, self._emit)
            for d in generated:
                self._emit(case_id, "KARM", "WORK", f"Drafted: {d['title']} → {d['authority']}",
                           extra={"doc_id": d["id"]})
                time.sleep(PAUSE * 0.35)
            self._emit(case_id, "KARM", "DONE", f"{len(generated)} document(s) generated", status="DONE")
            self._save(case)
            time.sleep(PAUSE)

            self._emit(case_id, "SATYAPAN", "START", "Verifying every artifact before release…", status="START")
            summary = ag.satyapan_verify_documents(case, plan, self._emit)
            for r in summary["results"]:
                mark = {"VERIFIED": "✓", "DRAFT": "●", "INVALIDATED": "✕"}[r["status"]]
                failed = [c["name"] for c in r["checks"] if not c["pass"]]
                self._emit(case_id, "SATYAPAN", "WORK",
                           f"{mark} {r['title']} — {r['status']}" + (f" · issues: {', '.join(failed)}" if failed else ""),
                           extra={"doc_id": r["doc"]})
                time.sleep(PAUSE * 0.3)
            self._emit(case_id, "SATYAPAN", "DONE",
                       f"{summary['verified']} verified · {summary['draft']} draft · {summary['invalidated']} invalidated",
                       status="DONE")
            self._save(case)
            time.sleep(PAUSE)

            self._emit(case_id, "ANUSARAN", "START", "Arming the follow-up watchdog…", status="START")
            fu = ag.anusaran_followup(case, plan, self._emit)
            for t in fu["timeline"]:
                self._emit(case_id, "ANUSARAN", "WORK", f"{t['when']} — {t['title']}")
                time.sleep(PAUSE * 0.25)
            case["status"] = "WATCHDOG"
            self._save(case)
            self._emit(case_id, "ANUSARAN", "DONE",
                       "HAQ WATCHDOG ACTIVE — case stays open until the payment is verified.", status="DONE")

    # ------------------------------------------------------------- replan loop
    def run_new_evidence(self, case_id: str, doc: dict) -> None:
        with self._lock_for(case_id):
            case = self._get(case_id)
            prev_diag = dict(case.get("diagnosis") or {})
            case.setdefault("documents", []).append(doc)
            case["status"] = "REPLANNING"
            self._save(case)
            self._emit(case_id, "SAMVAAD", "START", f"NEW EVIDENCE received: {doc['filename']} — extracting…", status="START")
            self._samvaad(case, new_docs=[doc])
            time.sleep(PAUSE)

            change = ag.satyapan_material_change(case, prev_diag, doc.get("extraction", {}).get("flags", []))
            if change["changed"]:
                for r in change["reasons"]:
                    self._emit(case_id, "SATYAPAN", "ALERT",
                               f"MATERIAL CHANGE — {r}", status="ALERT",
                               extra={"banner": "New evidence changed the resolution plan."})
                    time.sleep(PAUSE * 0.5)
            else:
                self._emit(case_id, "SATYAPAN", "DONE", "New evidence reviewed — no material change to the plan.",
                           status="DONE")

            self._emit(case_id, "NIDAAN", "START", "Re-diagnosing with the enriched evidence base…", status="START")
            old_root = prev_diag.get("root_cause_code")
            diag = ag.nidaan_diagnose(case, self._emit, version=(prev_diag.get("version", 1) + 1))
            self._emit(case_id, "NIDAAN", "DONE",
                       f"Diagnosis v{diag['version']}: {diag['root_cause_code']} (was {old_root}) · "
                       f"confidence {diag['confidence']:.0%}", status="DONE",
                       extra={"diagnosis": {"root": diag["root_cause_code"], "secondary": diag["secondary_cause_code"],
                                            "confidence": diag["confidence"]}})
            self._save(case)
            time.sleep(PAUSE)

            self._emit(case_id, "YOJNA", "START", "RE-PLANNING: reevaluating every action against the new situation…",
                       status="START")
            plan = ag.yojna_plan(case, self._emit, trigger="NEW_EVIDENCE")
            ag.refresh_step_statuses(case)
            changed = plan["rationale"]["changed_steps"]
            diff = []
            if changed.get("removed"):
                diff.append("REMOVED → " + ", ".join(changed["removed"]))
            if changed.get("added"):
                diff.append("ADDED → " + ", ".join(changed["added"]))
            self._emit(case_id, "YOJNA", "ALERT",
                       f"PLAN v{plan['version']} — NEW EVIDENCE CHANGED THE RESOLUTION PLAN. "
                       + (" · ".join(diff) if diff else "steps re-ordered"),
                       status="ALERT", extra={"plan_version": plan["version"], "banner": "New evidence changed the resolution plan."})
            self._save(case)
            time.sleep(PAUSE)

            self._emit(case_id, "KARM", "START", "Invalidating outdated documents and regenerating the action pack…",
                       status="START")
            generated = ag.karm_generate(case, plan, self._emit)
            for d in case.get("documents_generated") or []:
                if d["status"] == "INVALIDATED" and d.get("invalidated_reason"):
                    self._emit(case_id, "KARM", "ALERT",
                               f"OLD DOCUMENT ✕ INVALIDATED — {d['title']}", status="ALERT",
                               extra={"doc_id": d["id"], "reason": d["invalidated_reason"]})
                    time.sleep(PAUSE * 0.3)
            for d in generated:
                self._emit(case_id, "KARM", "WORK", f"Drafted (v{plan['version']}): {d['title']}", extra={"doc_id": d["id"]})
                time.sleep(PAUSE * 0.3)
            self._emit(case_id, "KARM", "DONE", f"{len(generated)} document(s) regenerated for plan v{plan['version']}",
                       status="DONE")
            self._save(case)
            time.sleep(PAUSE)

            self._emit(case_id, "SATYAPAN", "START", "Verifying the regenerated pack…", status="START")
            summary = ag.satyapan_verify_documents(case, plan, self._emit)
            self._emit(case_id, "SATYAPAN", "DONE",
                       f"{summary['verified']} verified · {summary['draft']} draft · {summary['invalidated']} invalidated",
                       status="DONE")
            self._save(case)
            time.sleep(PAUSE)

            fu = ag.anusaran_followup(case, plan, self._emit)
            case["status"] = "WATCHDOG"
            self._save(case)
            self._emit(case_id, "ANUSARAN", "DONE",
                       f"Timeline updated. WATCHDOG ACTIVE — next: {fu['next_action']}", status="DONE",
                       extra={"banner": "Timeline updated after re-planning."})

    # ------------------------------------------------------------- simulations
    def simulate(self, case_id: str, action: str) -> dict:
        with self._lock_for(case_id):
            case = self._get(case_id)
            plan = next((p for p in reversed(case.get("plans") or []) if not p.get("superseded")), None)
            if not plan:
                raise ValueError("no plan")
            if action == "bank_visit_done":
                n = 0
                for s in plan["steps"]:
                    if s["owner"] in ("USER_AT_BANK", "USER_AT_CSC") and s["status"] in ("READY", "PENDING", "BLOCKED"):
                        s["status"] = "DONE"
                        s["done_at"] = now_iso()
                        n += 1
                ag.refresh_step_statuses(case)
                self._emit(case_id, "ANUSARAN", "DONE",
                           f"User completed {n} office action(s). NYAYA unblocked dependent steps.", status="DONE")
            elif action == "mapper_verified":
                for s in plan["steps"]:
                    if s["key"] == "VERIFY_MAPPER":
                        s["status"] = "DONE"
                        s["done_at"] = now_iso()
                ag.refresh_step_statuses(case)
                self._emit(case_id, "KHOJ", "DONE",
                           "NPCI mapper re-check: 'Enabled for DBT' ✓ — payment re-processing now unblocked.", status="DONE")
            elif action == "cpgrams_filed":
                for s in plan["steps"]:
                    if s["key"] == "ESCALATE_CPGRAMS":
                        s["status"] = "DONE"
                        s["done_at"] = now_iso()
                ag.refresh_step_statuses(case)
                self._emit(case_id, "ANUSARAN", "DONE", "CPGRAMS grievance filed — tracking number recorded.",
                           status="DONE")
            elif action == "payment_received":
                case["watchdog"]["payment_verified"] = True
                case["watchdog"]["active"] = False
                case["status"] = "CLOSED"
                for t in case.get("followup", {}).get("timeline", []):
                    if t["kind"] == "WATCHDOG":
                        t["status"] = "DONE"
                self._emit(case_id, "SATYAPAN", "DONE",
                           "PAYMENT VERIFIED in the beneficiary account ✓ — CASE CLOSED. "
                           "HAQ closes cases only on verified credits, never on promises.", status="DONE")
            else:
                raise ValueError(f"unknown action {action}")
            self._save(case)
            return case

    # ------------------------------------------------------------- threading wrappers
    def start_initial(self, case: dict) -> threading.Thread:
        t = threading.Thread(target=self.run_initial, args=(case["id"],), daemon=True)
        t.start()
        return t

    def start_new_evidence(self, case_id: str, doc: dict) -> threading.Thread:
        t = threading.Thread(target=self.run_new_evidence, args=(case_id, doc), daemon=True)
        t.start()
        return t
