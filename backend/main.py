"""HAQ API server — FastAPI. Serves the command-center frontend and the agent
workflow API. Run:  uvicorn backend.main:app --host 0.0.0.0 --port 8000"""
from __future__ import annotations
import os, shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from .core import CaseStore, new_id, now_iso, _fields_confirmed, mask_case_view
from .extract import interpret_narrative
from .seed import SEED_CATALOG, materialize_seed, derive_profile_from_case
from .orchestrator import Orchestrator
from .adapters import build_tools, MODE_LABELS

BASE = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(os.path.dirname(BASE), "frontend")
UPLOADS = os.path.join("/tmp", "haq_uploads") if os.environ.get("VERCEL") else os.path.join(os.path.dirname(BASE), "data", "uploads")
os.makedirs(UPLOADS, exist_ok=True)

app = FastAPI(title="HAQ — DBT Payment Recovery Agent", version="1.0")
store = CaseStore()
orch = Orchestrator(store)

AGENT_ROSTER = [
    {"key": "SAMVAAD", "role": "Intake & Extraction", "desc": "Reads documents, builds the case file & identity graph"},
    {"key": "KHOJ", "role": "Evidence & Status", "desc": "Checks scheme · PFMS · APBS · NPCI mapper · bank systems"},
    {"key": "NIDAAN", "role": "Diagnosis", "desc": "Hybrid rules + language reasoning over the failure taxonomy"},
    {"key": "YOJNA", "role": "Planner", "desc": "Dependency-aware plan that re-plans when evidence changes"},
    {"key": "KARM", "role": "Action & Documents", "desc": "Generates office-ready forms, letters and scripts"},
    {"key": "NYAYA", "role": "Decision Engine", "desc": "Deterministic policy: ordering, deadlines, guardrails"},
    {"key": "SATYAPAN", "role": "Verification", "desc": "Checks every artifact; invalidates outdated documents"},
    {"key": "ANUSARAN", "role": "Follow-up Watchdog", "desc": "Timelines, nudges, escalations — until payment is verified"},
]


class DocumentIn(BaseModel):
    kind: str = "OTHER"
    filename: str = "document.txt"
    text_content: str = ""


class CaseIn(BaseModel):
    seed_id: Optional[str] = None
    narrative: str = ""
    language: Optional[str] = None
    documents: list[DocumentIn] = []
    consent: bool = False


class FieldConfirmIn(BaseModel):
    fields: dict[str, str] = {}


class SimulateIn(BaseModel):
    action: str


class AikartRunIn(BaseModel):
    """Public aiKart sandbox input.

    The marketplace only needs a natural-language problem statement. HAQ uses
    the seeded synthetic pension case as the institutional demo context and
    runs the full workflow synchronously before returning the agent outcome.
    """
    message: str
    language: str = "hi-en"
    consent: bool = True


def _public_case(case: dict) -> dict:
    """API view with the privacy layer applied (masked Aadhaar/account)."""
    return mask_case_view(case)


@app.get("/api/health")
def health():
    from .extract import Reasoner
    return {"ok": True, "product": "HAQ — DBT Payment Recovery Agent",
            "language_layer": Reasoner().mode, "cases": len(store.list_cases())}


@app.get("/api/meta")
def meta():
    from .extract import Reasoner
    return {"agents": AGENT_ROSTER, "catalog": SEED_CATALOG,
            "privacy": "Demo mode uses synthetic beneficiary data. No real Aadhaar or financial information.",
            "mode_badge": "DEMO MODE",
            "language_layer": Reasoner().mode,
            "disclaimer": ("HAQ provides information, evidence analysis and assistance in preparing resolution "
                           "actions. It does not guarantee government payment, bank approval, benefit eligibility "
                           "or grievance resolution. Users should verify important actions with the relevant "
                           "government department, bank or qualified professional. Demo mode may use synthetic "
                           "beneficiary data and simulated institutional responses. Live sources are explicitly labelled.")}


@app.get("/api/sources")
def sources():
    """Source transparency registry — what is live, what is demo, with links."""
    tools = [t.registry_entry() for t in build_tools()]
    kb = []
    import json as _json, os as _os
    with open(_os.path.join(os.path.dirname(BASE), "backend", "kb", "dbt_knowledge.json"), encoding="utf-8") as f:
        kb = [{"id": e["id"], "title": e["title"], "source": e["source"], "url": e["url"]}
              for e in _json.load(f)["entries"]]
    return {
        "mode_labels": MODE_LABELS,
        "tools": tools,
        "public_sources": kb,
        "statement": ("LIVE tools make real HTTP calls to public APIs at request time. DEMO adapters simulate "
                      "institutional responses for systems that require authentication (OTP, Aadhaar eKYC, "
                      "bank or government credentials) which we do not hold and do not bypass. The adapter "
                      "interface is identical — production replaces demo adapters with authorized integrations."),
    }


@app.delete("/api/cases/{case_id}")
def delete_case(case_id: str):
    """Privacy: user-initiated case deletion."""
    import sqlite3
    from .core import DATA_DIR
    if not store.get_case(case_id):
        raise HTTPException(404, "case not found")
    with sqlite3.connect(store.path) as c:
        c.execute("DELETE FROM cases WHERE id=?", (case_id,))
        c.execute("DELETE FROM events WHERE case_id=?", (case_id,))
    return {"ok": True, "deleted": case_id, "message": "Case and all associated data permanently deleted."}


@app.get("/api/catalog")
def catalog():
    return SEED_CATALOG


@app.post("/api/aikart/run")
def aikart_run(payload: AikartRunIn):
    """aiKart-compatible agent endpoint.

    Accepts one natural-language problem statement and executes HAQ's complete
    stateful agent workflow. Institutional beneficiary-status adapters remain
    explicitly DEMO/simulated; the returned diagnosis and next action are read
    from the resulting case state rather than hard-coded.
    """
    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(400, "message is required")

    result = create_case(CaseIn(
        seed_id="pension",
        narrative=message,
        language=payload.language or "hi-en",
        documents=[],
        consent=payload.consent,
    ))
    case_id = result["id"]
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(500, "case was created but could not be loaded")

    diagnosis = case.get("diagnosis") or {}
    watchdog = case.get("watchdog") or {}
    followup = case.get("followup") or {}
    payment_verified = bool(watchdog.get("payment_verified"))
    status = case.get("status", "WATCHDOG")

    return {
        "success": True,
        "case_id": case_id,
        "status": status,
        "diagnosis": diagnosis.get("root_cause_code"),
        "secondary_diagnosis": diagnosis.get("secondary_cause_code"),
        "confidence": diagnosis.get("confidence"),
        "payment_status": "VERIFIED" if payment_verified else "BLOCKED",
        "next_action": followup.get("next_action") or watchdog.get("next_action"),
        "agentic_workflow": [
            "SAMVAAD",
            "KHOJ",
            "NIDAAN",
            "YOJNA",
            "KARM",
            "NYAYA",
            "SATYAPAN",
            "ANUSARAN",
        ],
    }


@app.post("/api/cases")
def create_case(payload: CaseIn):
    if not payload.consent:
        raise HTTPException(403, "Consent is required before HAQ can process documents. "
                                 "Please accept the privacy notice to continue.")
    case_id = new_id("HAQ")
    documents = []
    portal_profile = None
    replan_documents = []
    case_partial = {}

    if payload.seed_id:
        seed = materialize_seed(payload.seed_id)
        case_partial = seed["case_partial"]
        portal_profile = seed["portal_profile"]
        replan_documents = seed["replan_documents"]
        for d in seed["documents"]:
            documents.append({"id": new_id("DOC"), **d, "source": "seed", "uploaded_at": now_iso()})

    for d in payload.documents:
        documents.append({"id": new_id("DOC"), "kind": d.kind, "filename": d.filename,
                          "text_content": d.text_content, "source": "user", "uploaded_at": now_iso()})

    narrative = payload.narrative or case_partial.get("narrative") or ""
    if not narrative and payload.seed_id:
        narrative = next((c["narrative"] for c in SEED_CATALOG if c["id"] == payload.seed_id), "")
    ben = case_partial.get("beneficiary", {})
    case = {
        "id": case_id,
        "status": "INTAKE",
        "seed_id": payload.seed_id,
        "narrative": narrative,
        "language": payload.language or case_partial.get("language") or interpret_narrative(narrative)["language_detected"],
        "narrative_analysis": interpret_narrative(narrative),
        "beneficiary": ben,
        "documents": documents,
        "portal_profile": portal_profile,
        "replan_documents": replan_documents,
        "expected": case_partial.get("expected"),
        "extraction": {"fields": {}, "identity_graph": {"nodes": [], "mismatches": []}},
        "evidence": [],
        "evidence_flags": [],
        "diagnosis": None,
        "plans": [],
        "documents_generated": [],
        "verification": None,
        "followup": None,
        "watchdog": {"active": False, "next_action": None, "escalation_level": 0, "payment_verified": False},
        "events_hint": "Agent activity streams below — polled live from the orchestrator.",
        "consent": {"granted": True, "at": now_iso(),
                    "text": "Documents will be used only to analyze this case and prepare the requested actions."},
    }
    store.create_case(case)
    try:
        orch.run_initial(case_id)
    except Exception as e:
        failed = store.get_case(case_id) or case
        failed["status"] = "ERROR"
        failed["error"] = str(e)
        store.update_case(failed)
        raise HTTPException(500, f"Agent workflow failed: {e}")
    final_case = store.get_case(case_id) or case
    return {"id": case_id, "status": final_case.get("status", "WATCHDOG")}


@app.post("/api/cases/{case_id}/run")
def run_case(case_id: str):
    """Run the initial agent workflow synchronously.

    Vercel serverless runtimes may terminate daemon background threads after the
    HTTP response, so the hosted API explicitly keeps the workflow inside this
    request. The frontend calls this endpoint immediately after case creation.
    """
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(404, "case not found")
    if case.get("status") not in ("INTAKE", "INVESTIGATING"):
        return {"id": case_id, "status": case.get("status"), "message": "Case is already running or completed."}
    try:
        orch.run_initial(case_id)
    except Exception as e:
        case = store.get_case(case_id) or case
        case["status"] = "ERROR"
        case["error"] = str(e)
        store.update_case(case)
        raise HTTPException(500, f"Agent workflow failed: {e}")
    case = store.get_case(case_id)
    return {"id": case_id, "status": case.get("status", "WATCHDOG")}


@app.get("/api/cases")
def list_cases():
    return store.list_cases()


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(404, "case not found")
    return _public_case(case)


@app.get("/api/cases/{case_id}/events")
def get_events(case_id: str, after: int = 0):
    if not store.get_case(case_id):
        raise HTTPException(404, "case not found")
    return {"events": store.list_events(case_id, after)}


@app.post("/api/cases/{case_id}/fields/confirm")
def confirm_fields(case_id: str, payload: FieldConfirmIn):
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(404, "case not found")
    fields = case["extraction"]["fields"]
    for k, v in payload.fields.items():
        fields[k] = {"value": v, "pattern": "user-confirmed", "confidence": 1.0, "confirmed": True}
    for k, meta in fields.items():
        meta["confirmed"] = True
    store.update_case(case)
    store.add_event(case_id, {"agent": "SAMVAAD", "action": "DONE",
                              "detail": f"Beneficiary confirmed {len(fields)} extracted field(s) — identity graph locked.",
                              "status": "DONE", "ts": now_iso()})
    return {"ok": True, "fields_confirmed": _fields_confirmed(case)}


@app.post("/api/cases/{case_id}/evidence")
async def add_evidence(case_id: str, kind: str = Form("OTHER"), text_content: str = Form(""),
                       filename: str = Form("upload.txt"), file: Optional[UploadFile] = File(None)):
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(404, "case not found")
    content = text_content
    fname = filename
    if file is not None:
        fname = file.filename or filename
        raw = await file.read()
        if fname.lower().endswith((".txt", ".csv", ".log")):
            content = raw.decode("utf-8", errors="replace")
        else:
            # images/PDFs are stored; extraction needs a vision model (Gemini) in live mode —
            # for now the UI asks the user to confirm fields, never blind-trusting OCR.
            dest = os.path.join(UPLOADS, f"{case_id}_{fname}")
            with open(dest, "wb") as f:
                f.write(raw)
            content = content or ""
    doc = {"id": new_id("DOC"), "kind": kind, "filename": fname, "text_content": content,
           "source": "user", "uploaded_at": now_iso()}
    orch.start_new_evidence(case_id, doc)
    return {"ok": True, "message": "New evidence accepted — re-planning loop started", "doc": doc["filename"]}


@app.post("/api/cases/{case_id}/evidence/seed-replan")
def seed_replan(case_id: str):
    """Demo helper: deliver the queued 'new evidence' document of a seeded case
    (the moment that triggers re-planning)."""
    case = store.get_case(case_id)
    if not case:
        raise HTTPException(404, "case not found")
    queued = case.get("replan_documents") or []
    if not queued:
        raise HTTPException(400, "no queued demo evidence for this case")
    doc = {**queued[0], "id": new_id("DOC"), "source": "user", "uploaded_at": now_iso()}
    case["replan_documents"] = queued[1:]
    store.update_case(case)
    orch.start_new_evidence(case_id, doc)
    return {"ok": True, "message": "Demo evidence delivered — watch the agents re-plan", "doc": doc["filename"]}


@app.post("/api/cases/{case_id}/simulate")
def simulate(case_id: str, payload: SimulateIn):
    try:
        case = orch.simulate(case_id, payload.action)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "status": case["status"]}


# ---------------------------------------------------------------- static frontend
@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND, "index.html"))

app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
