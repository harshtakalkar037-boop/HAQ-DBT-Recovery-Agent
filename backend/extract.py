"""SAMVAAD layer: multilingual narrative understanding, document extraction,
identity graph construction, and the optional LLM reasoner.

Hybrid principle (spec §18):
- This module does document understanding + messy-language interpretation.
- Deterministic parsers own the extracted fields. Nothing here invents government
  rules — those live in rules/*.json.
- If GROQ_API_KEY or GEMINI_API_KEY is set, the LLM polish layer is used for
  narrative summaries; otherwise deterministic phrase builders (demo-safe offline).
"""
from __future__ import annotations
import os, re
from datetime import datetime
from .core import compare_names, normalize_name

# ---------------------------------------------------------------- narrative
SCHEME_KEYWORDS = {
    "pension": ["pension", "पेंशन", "budhi", "बुढ़ा", "dadi", "दादी", "nanaji", "NSAP", "vidhwa", "विधवा"],
    "scholarship": ["scholarship", "छात्रवृत्ति", "scholar", "NSP", "post matric", "post-matric", "fees", "फीस", "college"],
    "pmkisan": ["pm kisan", "pm-kisan", "pmkisan", "किसान", "kisan", "khet", "installment", "kist", "किस्त", "farmer"],
    "mgnrega": ["mgnrega", "narega", "मनरेगा", "wage", "majdoor", "मजदूर", "shram"],
}
MONTH_WORDS = r"(?:mahine|mahina|months?|महीने|महीना)"
RELATIONS = {"dadi": "grandmother", "दादी": "grandmother", "nani": "grandmother", "dadaji": "grandfather",
             "papa": "father", "पापा": "father", "maa": "mother", "माँ": "mother", "bhai": "brother",
             "mera": "self", "मेरा": "self", "my": "self", "mai": "self", "main": "self"}

def interpret_narrative(text: str) -> dict:
    t = (text or "").lower()
    has_devanagari = bool(re.search(r"[\u0900-\u097F]", text or ""))
    has_english = bool(re.search(r"[a-zA-Z]{3,}", text or ""))
    romanized_hindi = any(w in t for w in (" nahi ", " hai ", " meri ", " mera ", " kyun ", " paisa ",
                                          " mahine ", " karao ", " theek ", " ruki ", " aayi ", " dijiye",
                                          " madad ", " bank ", " kripya ", " liye "))
    if has_devanagari and not has_english:
        language = "hi"
    elif has_english and (has_devanagari or romanized_hindi):
        language = "hi-en"
    elif has_english:
        language = "en"
    else:
        language = "hi"
    schemes = [k for k, words in SCHEME_KEYWORDS.items() if any(w.lower() in t for w in words)]
    m = re.search(rf"(\d+|do|teen|char|chaar|paanch|do|two|three|four|five)\s*{MONTH_WORDS}", t)
    months = None
    if m:
        words = {"do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "two": 2, "three": 3, "four": 4, "five": 5}
        v = m.group(1)
        months = words.get(v) or int(v) if v.isdigit() else words.get(v)
    person = next((v for k, v in RELATIONS.items() if k in t), "self")
    return {
        "language_detected": language,
        "intent": "PAYMENT_NOT_RECEIVED",
        "scheme_hints": schemes,
        "affected_person": person,
        "duration_months": months,
        "raw": text,
    }


# ---------------------------------------------------------------- extraction
_DATE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
_AADHAAR = re.compile(r"\b(\d{4}\s\d{4}\s\d{4})\b")
_URN = re.compile(r"URN[:\s]*([0-9A-Z]{8,})", re.I)
_IFSC = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")
_ACCT = re.compile(r"(?:A/c\s*No\.?|Account\s*No\.?)[:\s]*([0-9]{6,})", re.I)
_NAME = re.compile(r"(?i:A/c Name|Name|Beneficiary(?:\s+Name)?)[:\s]+([A-Z][A-Z .]{4,})")
_DOB = re.compile(r"(?:DOB|Date of Birth)[:\s]*(\d{2}/\d{2}/\d{4})", re.I)
_BENID = re.compile(r"Beneficiary ID[:\s]*([A-Z0-9/–\-]+)", re.I)
_APPID = re.compile(r"Application ID[:\s]*([A-Z0-9]+)", re.I)
_SCHEME = re.compile(r"Scheme[:\s]*(.+)", re.I)
_AMOUNT = re.compile(r"(?:Rs\.?|₹)\s*([\d,]+)", re.I)

TXN_KEYWORDS = ("WDL", "WITHDRAW", "DEP CASH", "CASH DEP", "DEPOSIT")
FAIL_KEYWORDS = ("FAIL", "RETURN", "INVALID", "NOT SEEDED", "NOT SEED", "INACTIVE", "DORMANT",
                 "CLOSED", "REJECTED", "COULD NOT", "ON HOLD", "PENDING", "विफल", "लौट")


def _parse_date(d: str) -> datetime | None:
    try:
        return datetime.strptime(d, "%d/%m/%Y")
    except ValueError:
        return None


def extract_from_document(doc: dict) -> dict:
    """Deterministic parser over messy document text. Returns fields + flags.
    Never invents values: if a field is absent it is absent."""
    text = doc.get("text_content") or ""
    fields: dict[str, dict] = {}

    def put(key, value, pattern_label, confidence=0.9):
        if value:
            fields[key] = {"value": value.strip(), "pattern": pattern_label, "confidence": confidence, "confirmed": confidence >= 0.8}

    m = _NAME.search(text)
    if m:
        raw = m.group(1).strip()
        raw = re.sub(r"\s+", " ", raw)
        put("name", raw, "name-label")
    m = _DOB.search(text)
    if m: put("dob", m.group(1), "dob-label")
    m = _AADHAAR.search(text)
    if m: put("aadhaar", m.group(1), "aadhaar-12-digit", 0.95)
    m = _ACCT.search(text)
    if m: put("account_number", m.group(1), "account-label")
    m = _IFSC.search(text)
    if m: put("ifsc", m.group(1), "ifsc-pattern")
    m = _URN.search(text)
    if m: put("urn", m.group(1), "urn-label", 0.95)
    m = _BENID.search(text)
    if m: put("beneficiary_id", m.group(1), "beneficiary-id-label", 0.95)
    m = _APPID.search(text)
    if m: put("application_id", m.group(1), "application-id-label", 0.95)
    m = _SCHEME.search(text)
    if m: put("scheme_mentioned", m.group(1), "scheme-label", 0.8)

    dates = [d for d in _DATE.findall(text)]
    amounts = _AMOUNT.findall(text)
    flags: list[str] = []
    flag_details: list[str] = []

    if doc.get("kind") == "PASSBOOK":
        txn_lines = [ln for ln in text.splitlines() if any(k in ln.upper() for k in TXN_KEYWORDS)]
        txn_dates = []
        for ln in txn_lines:
            for d in _DATE.findall(ln):
                dt = _parse_date(d)
                if dt:
                    txn_dates.append((dt, ln.strip()))
        if txn_dates:
            latest = max(txn_dates, key=lambda x: x[0])
            # activity in the recent window (after 2025-01-01) proves the account is alive
            if latest[0] >= datetime(2025, 1, 1):
                flags.append("ACCOUNT_RECENT_ACTIVITY")
                flag_details.append(f"Passbook shows customer activity on {latest[0].strftime('%d/%m/%Y')}: “{latest[1]}”")

    fail_lines = [ln.strip() for ln in text.splitlines() if any(k in ln.upper() for k in FAIL_KEYWORDS)]
    ocr_unreadable = (not text.strip()) or (not fields)
    return {
        "kind": doc.get("kind"),
        "filename": doc.get("filename"),
        "fields": fields,
        "dates_found": dates,
        "amounts_found": amounts,
        "failure_lines": fail_lines[:6],
        "flags": flags,
        "flag_details": flag_details,
        "ocr_unreadable": ocr_unreadable,
    }


def build_identity_graph(doc_extractions: list[dict]) -> dict:
    nodes, mismatches = [], []
    name_values = []
    for ex in doc_extractions:
        node_id = ex.get("filename") or ex.get("kind")
        nodes.append({"id": node_id, "kind": ex["kind"], "fields": ex["fields"]})
        nv = (ex["fields"].get("name") or {}).get("value")
        if nv:
            name_values.append({"doc": node_id, "kind": ex["kind"], "value": nv})
    for i in range(len(name_values)):
        for j in range(i + 1, len(name_values)):
            a, b = name_values[i], name_values[j]
            cmp = compare_names(a["value"], b["value"])
            if cmp["type"] != "exact":
                mismatches.append({
                    "field": "name",
                    "left": {"doc": a["doc"], "kind": a["kind"], "value": a["value"], "normalized": normalize_name(a["value"])},
                    "right": {"doc": b["doc"], "kind": b["kind"], "value": b["value"], "normalized": normalize_name(b["value"])},
                    "type": cmp["type"],
                    "detail": cmp["detail"],
                    "rule": "RULE: Normalized identity fields must match exactly across Aadhaar / bank / scheme records (B06).",
                })
    # account / aadhaar consistency
    def collect(key):
        vals = {}
        for ex in doc_extractions:
            v = (ex["fields"].get(key) or {}).get("value")
            if v:
                vals.setdefault(v, []).append(ex["kind"])
        return vals
    for key in ("account_number", "aadhaar", "ifsc"):
        vals = collect(key)
        if len(vals) > 1:
            mismatches.append({
                "field": key,
                "left": {"doc": "multiple", "value": list(vals.keys())[0]},
                "right": {"doc": "multiple", "value": list(vals.keys())[1]},
                "type": "field_conflict",
                "detail": f"Conflicting {key} values across documents: {list(vals.keys())}",
                "rule": f"RULE: {key} must be identical across documents.",
            })
    return {"nodes": nodes, "name_values": name_values, "mismatches": mismatches}


# ---------------------------------------------------------------- LLM polish (optional)
class Reasoner:
    """Language-layer assistant. Uses a live LLM if keys exist; otherwise falls back
    to deterministic phrasing. NEVER used for taxonomy, ordering, deadlines or rules."""

    def __init__(self):
        self.groq_key = os.environ.get("GROQ_API_KEY")
        self.gemini_key = os.environ.get("GEMINI_API_KEY")

    @property
    def mode(self) -> str:
        if self.groq_key:
            return "LIVE (Groq)"
        if self.gemini_key:
            return "LIVE (Gemini)"
        return "DEMO (deterministic language layer)"

    def _llm(self, system: str, user: str) -> str | None:
        try:
            import requests
            if self.groq_key:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.groq_key}"},
                    json={"model": "llama-3.3-70b-versatile",
                          "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                          "temperature": 0.2, "max_tokens": 400},
                    timeout=20,
                )
                return r.json()["choices"][0]["message"]["content"]
        except Exception:
            return None
        return None

    def diagnosis_explanation(self, diagnosis: dict, narrative: dict, evidence: list[dict]) -> str:
        root = diagnosis.get("root_cause_label", diagnosis.get("root_cause_code"))
        sec = diagnosis.get("secondary_cause_label") or "—"
        ev = " · ".join(e["message"][:90] for e in evidence[:3])
        base = (f"Payment is stuck because: {root}. Secondary issue: {sec}. "
                f"This is based on {len(evidence)} checked signals — {ev}.")
        out = self._llm(
            "You explain Indian DBT payment failures to a beneficiary in simple Hindi-English. Max 60 words.",
            base)
        return out or base

    def whatsapp_update(self, case: dict, plan_summary: str) -> str:
        name = (case.get("beneficiary") or {}).get("name", "लाभार्थी").split()[0]
        return (f"नमस्ते! HAQ अपडेट — {name} जी का मामला:\n"
                f"स्थिति: {plan_summary}\n"
                f"अगला कदम तय समय पर। पैसा आने तक HAQ WATCHDOG चालू रहेगा। — HAQ टीम (डेमो)")
