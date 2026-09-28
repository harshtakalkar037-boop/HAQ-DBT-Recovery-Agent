"""HAQ specialist agents: KHOJ (evidence), NIDAAN (diagnosis), YOJNA (planner),
NYAYA (policy enforcement), KARM (documents), SATYAPAN (verification),
ANUSARAN (follow-up). Each agent is a pure function over the case document —
the orchestrator owns sequencing, sleeps and event emission."""
from __future__ import annotations
from .core import (
    CAUSES, STEPS, STEP_ORDER, run_policy_engine, current_plan, build_plan_steps,
)
from .docs_templates import render_document, DOC_SPECS
from .extract import extract_from_document, build_identity_graph, interpret_narrative

# ------------------------------------------------------------------ signal matching
SIGNAL_MAP = {
    "SIG_NAME_MISMATCH_DOCS": lambda ctx: ctx["name_mismatch"],
    "SIG_PFMS_VALIDATION_FAILED": lambda ctx: "ACCOUNT_VALIDATION_FAILED" in ctx["codes"],
    "SIG_BANK_B06": lambda ctx: "B06" in ctx["codes"] or "NAME_MISMATCH_BANK" in ctx["codes"],
    "SIG_MAPPER_INACTIVE": lambda ctx: bool({"MAPPER_INACTIVE", "MAPPER_DISABLED"} & ctx["codes"]),
    "SIG_MAPPER_NOT_SEEDED": lambda ctx: "MAPPER_NOT_SEEDED" in ctx["codes"],
    "SIG_BANK_ACCOUNT_CLOSED": lambda ctx: "ACCOUNT_CLOSED" in ctx["codes"],
    "SIG_BANK_DORMANT": lambda ctx: bool({"ACCOUNT_DORMANT", "ACCOUNT_INOPERATIVE"} & ctx["codes"]),
    "SIG_ACCOUNT_RECENT_ACTIVITY": lambda ctx: "ACCOUNT_RECENT_ACTIVITY" in ctx["flags"],
    "SIG_APBS_RETURNED": lambda ctx: "PAYMENT_RETURNED_APBS" in ctx["codes"],
    "SIG_MULTIPLE_MAPPINGS": lambda ctx: "MULTIPLE_MAPPINGS" in ctx["codes"],
    "SIG_SCHEME_CREDITED_ELSEWHERE": lambda ctx: "CREDITED_ELSEWHERE" in ctx["codes"],
    "SIG_IFSC_INVALID": lambda ctx: ("IFSC_UNMAPPED" in ctx["codes"] or "INVALID_IFSC" in ctx["codes"]
                                     or ctx["ifsc_flag"]),
    "SIG_EKYC_PENDING": lambda ctx: "EKYC_PENDING" in ctx["codes"],
    "SIG_PENSION_SCHEME": lambda ctx: ctx["is_pension"],
    "SIG_LIFE_CERT_PENDING": lambda ctx: "LIFE_CERT_PENDING" in ctx["codes"],
    "SIG_SCHEME_PENDING": lambda ctx: "SCHEME_NOT_RELEASED" in ctx["codes"],
}


def _ctx(case: dict) -> dict:
    ig = (case.get("extraction") or {}).get("identity_graph") or {}
    codes = {e["code"] for e in case.get("evidence") or []}
    ifsc_flag = any("IFSC" in (e.get("message") or "").upper() for e in case.get("evidence") or [])
    return {
        "codes": codes,
        "flags": set(case.get("evidence_flags") or []),
        "name_mismatch": any(m.get("field") == "name" for m in ig.get("mismatches") or []),
        "is_pension": bool((case.get("beneficiary") or {}).get("is_pension")),
        "ifsc_flag": ifsc_flag,
    }


# ------------------------------------------------------------------ KHOJ
def khoj_investigate(case: dict, tools: list, emit) -> list[dict]:
    """KHOJ: decide which tools this case needs, call them for real, and build the
    evidence chain. Every call is a genuine backend tool invocation."""
    from .adapters import select_tools
    chosen = select_tools(case, tools)
    emit("KHOJ", "START",
         f"Planning evidence gathering — {len(chosen)} tool(s) selected for this case "
         f"({', '.join(t.key for t in chosen)})", status="START")
    evidence = []
    for tool in chosen:
        emit("KHOJ", "TOOL_CALL",
             f"🔧 Tool Call · {tool.key} — {tool.title} · {tool.description}",
             status="WORK", source=tool.key,
             extra={"mode": tool.mode, "tool": tool.key})
        result = tool.run(case)          # REAL invocation (live HTTP / KB retrieval / demo adapter)
        ev = result.to_evidence(len(evidence) + 1)
        evidence.append(ev)
        mark = {"OK": "✓", "FAIL": "✕", "WARN": "●"}[ev["status"]]
        emit("KHOJ", "TOOL_RESULT",
             f"{mark} {ev['source_label']} — {ev['code']} · {ev['mode_label']} · {ev['retrieved_at']} · {ev['message']}",
             status=ev["status"], source=ev["tool"],
             extra={"mode": ev["mode"], "tool": ev["tool"], "source_url": ev.get("source_url"),
                    "retrieved_at": ev["retrieved_at"], "confidence": ev.get("confidence")})
    case["evidence"] = evidence
    return evidence


def khoj_sufficiency(case: dict, emit) -> bool:
    """KHOJ's decision: do we have enough evidence for NIDAAN to reason over?"""
    ev = case.get("evidence") or []
    pipeline_hits = [e for e in ev if e.get("tool") in
                     ("SCHEME_STATUS", "PFMS_STATUS", "APBS_STATUS", "NPCI_MAPPER", "BANK_CBS")]
    failures = [e for e in pipeline_hits if e["status"] == "FAIL"]
    enough = len(pipeline_hits) >= 3 and (failures or (case.get("extraction") or {}).get("identity_graph", {}).get("mismatches"))
    note = (f"{len(ev)} evidence items collected ({len(failures)} failure signal(s), "
            f"{len(pipeline_hits)} pipeline stage(s) checked) — ")
    note += "KHOJ has collected enough evidence for NIDAAN." if enough else \
        "evidence is thin — NIDAAN will flag uncertainty and ask for more documents."
    emit("KHOJ", "DONE", note, status="DONE" if enough else "WARN")
    return enough


# ------------------------------------------------------------------ NIDAAN
def nidaan_diagnose(case: dict, emit, version: int = 1) -> dict:
    ctx = _ctx(case)
    scores, matched = {}, {}
    for code, cause in CAUSES.items():
        total, sigs = 0, []
        for sig in cause["signals"]:
            pred = SIGNAL_MAP.get(sig["id"])
            try:
                hit = bool(pred and pred(ctx))
            except Exception:
                hit = False
            if hit:
                total += sig["weight"]
                sigs.append({"id": sig["id"], "text": sig["text"], "weight": sig["weight"]})
        scores[code], matched[code] = total, sigs

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], CAUSES[kv[0]]["severity"] != "CRITICAL"))
    ranked = [(c, s) for c, s in ranked if s > 0] or [("OTHER", 1)]
    root_code, root_score = ranked[0]
    sec_code, sec_score = ranked[1] if len(ranked) > 1 else (None, 0)

    override_note = None
    # ---- deterministic override rules (documented, not LLM) ----
    if root_code == "CLOSED_MAPPED_ACCOUNT" and "ACCOUNT_RECENT_ACTIVITY" in ctx["flags"]:
        root_code = "DORMANT_MAPPED_ACCOUNT"
        override_note = ("OVERRIDE RULE R-DORMANT-01: the account was reported closed, but new passbook evidence "
                         "shows customer activity after the alleged closure date. A live account with long inactivity "
                         "is DORMANT — reactivatable — not CLOSED. Diagnosis revised.")
        root_score += 3
    # de-duplicate root/secondary after overrides
    if sec_code == root_code:
        sec_code = next((c for c, s in ranked[1:] if c != root_code and s > 0), None)
        sec_score = scores.get(sec_code, 0) if sec_code else 0
    if root_code != "NAME_MISMATCH" and sec_code != "NAME_MISMATCH" and ctx["name_mismatch"] \
            and root_code in ("DORMANT_MAPPED_ACCOUNT", "CLOSED_MAPPED_ACCOUNT"):
        sec_code = "NAME_MISMATCH"
        sec_score = scores.get(sec_code, 0)
    additional = [c for c, s in ranked[2:] if s > 0 and c not in (root_code, sec_code)][:2]
    watch = []
    if ctx["is_pension"] and "LIFE_CERTIFICATE_PENDING" not in (root_code, sec_code):
        watch.append({"code": "LIFE_CERTIFICATE_PENDING",
                      "label": CAUSES["LIFE_CERTIFICATE_PENDING"]["label"],
                      "reason": "Pension schemes require an annual life certificate before 30 November — a separate stoppage risk."})

    denom = root_score + 0.6 * max(sec_score, 1)
    confidence = round(min(0.95, max(0.62, root_score / denom)), 2)
    if override_note:
        confidence = 0.88

    evidence_cited = [
        {"source": e["source_label"], "code": e["code"], "message": e["message"], "status": e["status"]}
        for e in case.get("evidence", [])[:5]
    ]
    for m in (case.get("extraction") or {}).get("identity_graph", {}).get("mismatches", []):
        lk = m['left'].get('kind') or m['left'].get('doc', 'doc')
        rk = m['right'].get('kind') or m['right'].get('doc', 'doc')
        evidence_cited.append({
            "source": f"Identity graph ({lk} vs {rk})",
            "code": "NAME_MISMATCH_DOCS" if m.get("field") == "name" else "FIELD_CONFLICT",
            "message": f"{m['left'].get('value')} ≠ {m['right'].get('value')} — {m.get('detail', '')}",
            "status": "FAIL",
        })

    diagnosis = {
        "version": version,
        "root_cause_code": root_code,
        "root_cause_label": CAUSES[root_code]["label"],
        "root_cause_label_hi": CAUSES[root_code]["label_hi"],
        "root_cause_ref": CAUSES[root_code]["code_ref"],
        "secondary_cause_code": sec_code,
        "secondary_cause_label": CAUSES[sec_code]["label"] if sec_code else None,
        "additional_causes": additional,
        "watch_items": watch,
        "confidence": confidence,
        "confidence_basis": f"root signal score {root_score} vs secondary {sec_score} (deterministic weights from rules/taxonomy.json)",
        "matched_signals": matched.get(root_code, []) + matched.get(sec_code or "", []),
        "evidence": evidence_cited,
        "rules_applied": [
            "Taxonomy scoring: rules/taxonomy.json signal weights",
            "Override R-DORMANT-01 (closed vs dormant)" if override_note else "No overrides fired",
            "Evidence-first rule: every cause must cite matched signals",
        ],
        "override_note": override_note,
        "explanation": "",
    }
    from .extract import Reasoner
    diagnosis["explanation"] = Reasoner().diagnosis_explanation(diagnosis, case.get("narrative_analysis") or {}, evidence_cited)
    case["diagnosis"] = diagnosis
    if not case.get("diagnosis_history"):
        case["diagnosis_history"] = []
    case["diagnosis_history"].append({"version": version, "root": root_code, "secondary": sec_code,
                                      "confidence": confidence, "override_note": override_note})
    return diagnosis


# ------------------------------------------------------------------ YOJNA
def yojna_plan(case: dict, emit, trigger: str = "INITIAL") -> dict:
    diag = case.get("diagnosis") or {}
    # Only root + secondary causes drive the playbook. Additional causes are
    # displayed as "also observed" signals but must not pollute the action plan.
    cause_codes = [c for c in [diag.get("root_cause_code"), diag.get("secondary_cause_code")] if c]
    policy = run_policy_engine(case)
    steps = build_plan_steps(cause_codes, case, policy)

    plans = case.setdefault("plans", [])
    version = len(plans) + 1
    for p in plans:
        if not p.get("superseded"):
            p["superseded"] = True
            p["superseded_by"] = version
            p["superseded_reason"] = ("New evidence changed the resolution plan" if trigger == "NEW_EVIDENCE"
                                      else "Re-planned")
    changed_keys = {"added": [], "removed": [], "reordered": []}
    if plans:
        old = {s["key"] for s in plans[-1]["steps"] if s["status"] != "REPLACED"}
        new = {s["key"] for s in steps}
        changed_keys = {"added": sorted(new - old), "removed": sorted(old - new), "reordered": sorted(old & new)}

    rationale = {
        "causes_addressed": cause_codes,
        "causes_also_observed": diag.get("additional_causes") or [],
        "policy_rules_fired": policy["fired"],
        "guardrails": policy["guardrails"],
        "ordering": "NYAYA step_order_index + dependency ordering (name correction → seeding → mapper verify → re-process → escalation)",
        "note": (diag.get("override_note") if trigger == "NEW_EVIDENCE" else
                 "Plan built from playbook union of active causes; blocked steps listed with reasons."),
        "changed_steps": changed_keys,
    }
    from .core import now_iso, POLICY
    plan = {
        "version": version,
        "trigger": trigger,
        "created_at": now_iso(),
        "steps": steps,
        "rationale": rationale,
        "escalation_ladder": POLICY["escalation_ladder"],
    }
    plans.append(plan)
    return plan


def refresh_step_statuses(case: dict) -> dict:
    """NYAYA continuous enforcement: recompute blocks and unblock dependents."""
    plan = current_plan(case)
    if not plan:
        return {}
    policy = run_policy_engine(case, plan)
    done = {s["key"] for s in plan["steps"] if s["status"] == "DONE"}
    for s in plan["steps"]:
        if s["status"] in ("DONE", "REPLACED", "SKIPPED"):
            continue
        key = s["key"]
        if key in policy["blocks"] or key in policy["soft_blocks"]:
            s["status"] = "BLOCKED"
            s["blocked_reason"] = policy["blocks"].get(key) or policy["soft_blocks"].get(key)
            continue
        deps = s["depends_on"]
        if deps and not all(d in done for d in deps):
            s["status"] = "PENDING"
            s["blocked_reason"] = None
            continue
        s["status"] = "READY"
        s["blocked_reason"] = None
        if key in policy["deadlines"] and not s.get("deadline_overridden"):
            s["deadline_days"] = policy["deadlines"][key]["days"]
            s["deadline_overridden"] = True
    return policy


# ------------------------------------------------------------------ KARM
def karm_generate(case: dict, plan: dict, emit) -> list[dict]:
    from .core import now_iso
    docs = case.setdefault("documents_generated", [])
    current_keys = {s["key"] for s in plan["steps"] if s["status"] != "REPLACED"}
    current_types = {s["doc_type"] for s in plan["steps"] if s.get("doc_type")} | {
        "BANK_COUNTER_SCRIPT", "WHATSAPP_UPDATE"}
    # invalidate docs belonging to replaced/removed steps
    for d in docs:
        if d["status"] in ("VERIFIED", "DRAFT"):
            if d.get("step_key") and d["step_key"] not in current_keys:
                d["status"] = "INVALIDATED"
                d["invalidated_reason"] = ("Resolution plan changed after new evidence — this document belongs to a "
                                           "replaced action and must not be submitted.")
            elif d["type"] in current_types and d["plan_version"] < plan["version"]:
                d["status"] = "INVALIDATED"
                d["invalidated_reason"] = f"Superseded by plan v{plan['version']} — use the regenerated version."

    generated = []
    step_by_key = {s["key"]: s for s in plan["steps"]}
    for s in plan["steps"]:
        if s["status"] == "REPLACED" or not s.get("doc_type"):
            continue
        if any(d["type"] == s["doc_type"] and d["plan_version"] == plan["version"] for d in docs):
            continue
        rec = render_document(s["doc_type"], case, s, plan["version"])
        rec.update({"id": f"DOC-{len(docs)+1:03d}", "status": "DRAFT", "checks": [], "created_at": now_iso(),
                    "invalidated_reason": None})
        docs.append(rec)
        generated.append(rec)
    for dtype in ("BANK_COUNTER_SCRIPT", "WHATSAPP_UPDATE"):
        if any(d["type"] == dtype and d["plan_version"] == plan["version"] for d in docs):
            continue
        rec = render_document(dtype, case, None, plan["version"])
        rec.update({"id": f"DOC-{len(docs)+1:03d}", "status": "DRAFT", "checks": [], "created_at": now_iso(),
                    "invalidated_reason": None})
        docs.append(rec)
        generated.append(rec)
    case["documents_generated"] = docs
    return generated


# ------------------------------------------------------------------ SATYAPAN
def satyapan_verify_documents(case: dict, plan: dict, emit) -> dict:
    from .core import _fields_confirmed
    results = []
    fields_ok = _fields_confirmed(case)
    ex_fields = (case.get("extraction") or {}).get("fields") or {}
    name_src = None
    for f, meta in ((case.get("extraction") or {}).get("fields") or {}).items():
        if f == "name":
            name_src = meta.get("value")
    for d in case.get("documents_generated") or []:
        if d["status"] == "INVALIDATED":
            results.append({"doc": d["id"], "title": d["title"], "status": "INVALIDATED",
                            "checks": [{"name": "plan version", "pass": False, "detail": d["invalidated_reason"]}]})
            continue
        if d["plan_version"] != plan["version"]:
            continue
        checks = []
        bag = d.get("fields_used") or {}
        missing = [r for r in d["required_fields"] if not bag.get(r) or str(bag.get(r)).startswith("[")]
        checks.append({"name": "Required fields complete", "pass": not missing,
                       "detail": "All required fields populated" if not missing else f"Missing: {missing}"})
        name_match = (not name_src) or (bag.get("name") == name_src)
        checks.append({"name": "Beneficiary identity consistent", "pass": name_match,
                       "detail": f"Document name matches confirmed identity: {bag.get('name')}" if name_match
                       else f"Document name '{bag.get('name')}' ≠ case identity '{name_src}'"})
        acct = (case.get("beneficiary") or {}).get("account_number")
        acct_ok = (not acct) or (bag.get("account_number") == acct) or d["type"] in ("CPGRAMS_GRIEVANCE", "RTI_APPLICATION", "WHATSAPP_UPDATE")
        checks.append({"name": "Account information consistent", "pass": acct_ok,
                       "detail": f"a/c ••{str(acct)[-4:]}" if acct_ok else "Account number mismatch"})
        urn_src = next((e.get("urn") for e in case.get("evidence") or [] if e.get("urn")), None)
        urn_ok = (not urn_src) or (bag.get("urn") == urn_src) or bag.get("urn") == "[URN]"
        if d["type"] in ("PAYMENT_REPROCESSING_REQUEST", "CPGRAMS_GRIEVANCE", "RTI_APPLICATION", "OLD_BRANCH_LETTER"):
            urn_ok = (not urn_src) or (bag.get("urn") == urn_src)
        checks.append({"name": "URN consistent", "pass": urn_ok,
                       "detail": f"URN {bag.get('urn')}" if urn_ok else "URN mismatch between document and evidence"})
        checks.append({"name": "Correct authority addressed", "pass": bool(d.get("authority")),
                       "detail": f"Addressed to: {d['authority']}"})
        checks.append({"name": "Matches current plan (v%d)" % plan["version"], "pass": d["plan_version"] == plan["version"],
                       "detail": f"Generated under plan v{d['plan_version']}"})
        step = next((s for s in plan["steps"] if s["key"] == d.get("step_key")), None)
        attached = {doc.get("kind") for doc in case.get("documents") or []}
        req = {"AADHAAR", "PASSBOOK"}
        have_req = bool(attached & req)
        checks.append({"name": "Required attachments available", "pass": have_req,
                       "detail": f"Attached document kinds: {', '.join(sorted(attached)) or 'none'}"
                       + (" · carry Aadhaar copy + passbook when submitting" if have_req else " · attach Aadhaar copy and passbook")})
        checks.append({"name": "Completion condition defined", "pass": bool(step and step.get("completion_condition")) if step else True,
                       "detail": (step or {}).get("completion_condition", "Informational document")})
        unconfirmed = [r for r in d["required_fields"]
                       if r in ex_fields and not (ex_fields[r] or {}).get("confirmed")]
        checks.append({"name": "Required fields confirmed", "pass": not unconfirmed,
                       "detail": "All extracted fields used in this document are confirmed" if not unconfirmed
                       else f"Unconfirmed fields: {unconfirmed} — beneficiary must confirm before release"})
        all_pass = all(c["pass"] for c in checks)
        d["checks"] = checks
        d["status"] = "VERIFIED" if all_pass else "DRAFT"
        results.append({"doc": d["id"], "title": d["title"], "status": d["status"], "checks": checks})
    summary = {
        "total": len(results),
        "verified": sum(1 for r in results if r["status"] == "VERIFIED"),
        "draft": sum(1 for r in results if r["status"] == "DRAFT"),
        "invalidated": sum(1 for r in results if r["status"] == "INVALIDATED"),
        "results": results,
        "fields_confirmed": fields_ok,
    }
    case["verification"] = summary
    return summary


def satyapan_material_change(case: dict, previous_diagnosis: dict | None, new_flags: list[str]) -> dict:
    """Detect whether new evidence changes the resolution picture (SATYAPAN's job
    in the re-planning loop)."""
    prev_root = (previous_diagnosis or {}).get("root_cause_code")
    reasons = []
    if "ACCOUNT_RECENT_ACTIVITY" in new_flags and prev_root == "CLOSED_MAPPED_ACCOUNT":
        reasons.append("New passbook page shows customer activity AFTER the alleged closure date — "
                       "the account cannot be closed. Status must be revised to DORMANT.")
    if prev_root and prev_root not in ("NAME_MISMATCH",) and "ACCOUNT_RECENT_ACTIVITY" not in new_flags:
        ig = (case.get("extraction") or {}).get("identity_graph") or {}
        new_name_pairs = [m for m in ig.get("mismatches") or [] if m.get("field") == "name"]
        if new_name_pairs and not previous_diagnosis.get("secondary_cause_code") == "NAME_MISMATCH":
            reasons.append("New document introduces a name inconsistency across records (B06 risk).")
    return {"changed": bool(reasons), "reasons": reasons}


# ------------------------------------------------------------------ ANUSARAN
def anusaran_followup(case: dict, plan: dict, emit) -> dict:
    from .core import now_iso
    steps = plan["steps"]
    timeline = []
    n_docs = len([d for d in case.get("documents_generated") or [] if d["status"] != "INVALIDATED"
                  and d["plan_version"] == plan["version"]])
    timeline.append({"id": "TL-0", "when": "TODAY", "title": f"Action pack ready — {n_docs} documents generated & verified",
                     "detail": "Print the pack and carry the bank-counter script.", "status": "DONE", "kind": "MILESTONE"})

    def first(pred):
        return next((s for s in steps if pred(s) and s["status"] != "REPLACED"), None)

    bank_step = first(lambda s: s["owner"] in ("USER_AT_BANK", "USER_AT_CSC") and s["status"] != "DONE")
    if bank_step:
        carry = [d["title"] for d in case.get("documents_generated") or []
                 if d.get("step_key") == bank_step["key"] and d["status"] != "INVALIDATED"]
        timeline.append({"id": "TL-1", "when": "TOMORROW", "title": f"Bank/office visit — {bank_step['action']}",
                         "detail": ("Carry: " + ", ".join(carry)) if carry else "Carry Aadhaar + passbook + printed letters.",
                         "status": "SCHEDULED", "kind": "USER_ACTION", "step_key": bank_step["key"]})
    verify = first(lambda s: s["key"] == "VERIFY_MAPPER")
    if verify:
        timeline.append({"id": "TL-2", "when": "+2 DAYS", "title": "HAQ verifies NPCI mapper ('Enabled for DBT')",
                         "detail": "Watchdog re-checks BASE status and unblocks the re-processing request.",
                         "status": "SCHEDULED", "kind": "AGENT_ACTION", "step_key": verify["key"]})
    reproc = first(lambda s: s["key"] == "REPROCESS_REQUEST")
    if reproc:
        timeline.append({"id": "TL-3", "when": "+7 DAYS", "title": "Follow-up: payment re-processing at scheme office",
                         "detail": f"Quote URN references. {reproc['notes']}",
                         "status": "SCHEDULED", "kind": "FOLLOWUP", "step_key": reproc["key"]})
    cpgrams = first(lambda s: s["key"] == "ESCALATE_CPGRAMS")
    if cpgrams:
        timeline.append({"id": "TL-4", "when": "+15 DAYS", "title": "CPGRAMS grievance auto-prepared if unresolved",
                         "detail": "Escalation ladder level 4. Draft is ready in the document pack.",
                         "status": "SCHEDULED", "kind": "ESCALATION", "step_key": cpgrams["key"]})
    rti = first(lambda s: s["key"] == "ESCALATE_RTI")
    if rti:
        timeline.append({"id": "TL-5", "when": "+30 DAYS", "title": "RTI application ready to file",
                         "detail": "Escalation ladder level 5 — asks which account received each credit and why.",
                         "status": "SCHEDULED", "kind": "ESCALATION", "step_key": rti["key"]})
    timeline.append({"id": "TL-9", "when": "UNTIL CREDIT", "title": "PAYMENT RECEIVED → CASE CLOSES",
                     "detail": "The case stays OPEN until HAQ verifies the credit. Nothing is closed on promises.",
                     "status": "SCHEDULED", "kind": "WATCHDOG"})

    next_action = next((s["action"] for s in steps if s["status"] == "READY"), None) or \
                  next((s["action"] for s in steps if s["status"] == "PENDING"), "Waiting for evidence")
    followup = {
        "timeline": timeline,
        "created_at": now_iso(),
        "next_action": next_action,
    }
    case["followup"] = followup
    case["watchdog"] = {
        "active": True,
        "next_action": next_action,
        "escalation_level": 0,
        "payment_verified": False,
        "started_at": now_iso(),
    }
    return followup
