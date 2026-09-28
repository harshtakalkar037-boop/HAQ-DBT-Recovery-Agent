"""KHOJ tool layer — REAL tools first, honest demo adapters second.

GovPortalAdapter architecture (production-ready):

    GovTool (interface)
      ├── LIVE tools         — real public APIs / sources, no auth required
      │     ├── IfscLookupTool       (Razorpay public IFSC directory — RBI-licensed banks)
      │     └── PincodeLookupTool    (postalpincode.in — India Post public data)
      ├── PUBLIC SOURCE tool — retrieval over curated official/public guidance (kb/dbt_knowledge.json)
      └── DEMO tools         — controlled realistic institutional responses
            (SchemeStatus · PFMS · APBS · NPCI Mapper · Bank CBS)

Rules enforced here:
* We NEVER fake a live call. If a live source fails, the result mode is
  UNAVAILABLE with an honest message — never a simulated success.
* Every result carries: mode (LIVE / PUBLIC SOURCE / DEMO / UNAVAILABLE),
  source, source_url, retrieved_at (IST), confidence.
* Beneficiary-level status for scheme/mapper/bank systems requires OTP/Aadhaar/
  institutional credentials we do not have — those stay DEMO adapters behind the
  same interface, ready to be replaced by authorized integrations.
"""
from __future__ import annotations
import json, os
from abc import ABC, abstractmethod
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def now_ist() -> str:
    return datetime.now(IST).strftime("%d %b %Y · %H:%M IST")


class ToolResult:
    def __init__(self, tool: str, title: str, mode: str, status: str, code: str,
                 message: str, detail: str = "", data: dict | None = None,
                 source: str = "", source_url: str = "", confidence: float = 0.8,
                 urn: str | None = None, raw: dict | None = None):
        self.tool = tool
        self.title = title
        self.mode = mode          # LIVE | PUBLIC | DEMO | UNAVAILABLE
        self.status = status      # OK | FAIL | WARN
        self.code = code
        self.message = message
        self.detail = detail
        self.data = data or {}
        self.source = source
        self.source_url = source_url
        self.confidence = confidence
        self.urn = urn
        self.raw = raw or {}
        self.retrieved_at = now_ist()

    def to_evidence(self, idx: int) -> dict:
        return {
            "id": f"EV-{idx:02d}",
            "tool": self.tool,
            "source": self.tool,
            "source_label": self.title,
            "check": self.code,
            "status": self.status,
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
            "mode": self.mode,
            "mode_label": MODE_LABELS.get(self.mode, self.mode),
            "source_url": self.source_url,
            "retrieved_at": self.retrieved_at,
            "confidence": self.confidence,
            "urn": self.urn,
            "raw": self.raw,
        }


MODE_LABELS = {
    "LIVE": "🟢 LIVE SOURCE",
    "PUBLIC": "🟢 PUBLIC SOURCE",
    "DEMO": "🟡 DEMO / SIMULATED",
    "UNAVAILABLE": "🟠 SOURCE UNAVAILABLE",
}


class GovTool(ABC):
    key = "BASE"
    title = "Base tool"
    mode = "DEMO"
    description = ""
    source = ""
    source_url = ""

    @abstractmethod
    def applicable(self, case: dict) -> bool:
        """Should KHOJ call this tool for this case?"""

    @abstractmethod
    def run(self, case: dict) -> ToolResult:
        ...

    def registry_entry(self) -> dict:
        return {"key": self.key, "title": self.title, "mode": self.mode,
                "mode_label": MODE_LABELS[self.mode], "description": self.description,
                "source": self.source, "source_url": self.source_url}


# ============================================================ LIVE tools
class IfscLookupTool(GovTool):
    """REAL public API: Razorpay's public IFSC directory (RBI-licensed bank IFSCs).
    Validates the branch code, detects invalid/unmapped IFSCs — the exact defect
    behind many 'bank not mapped' failures. No auth required."""

    key = "IFSC_LOOKUP"
    title = "IFSC directory lookup"
    mode = "LIVE"
    description = "Validates the bank branch code against the public IFSC directory (live HTTP call)."
    source = "Public IFSC directory (Razorpay IFSC API — RBI-licensed banks)"
    source_url = "https://ifsc.razorpay.com/"
    API = "https://ifsc.razorpay.com/{ifsc}"

    def applicable(self, case: dict) -> bool:
        return bool(_case_ifsc(case))

    def run(self, case: dict) -> ToolResult:
        import requests
        ifsc = _case_ifsc(case)
        url = self.API.format(ifsc=ifsc)
        try:
            r = requests.get(url, timeout=6)
        except Exception as e:
            return ToolResult(self.key, self.title, "UNAVAILABLE", "WARN", "SOURCE_UNAVAILABLE",
                              f"IFSC directory temporarily unavailable ({type(e).__name__}). "
                              "HAQ will continue using the available evidence.",
                              detail="This was a real network call that did not succeed — no simulated data was substituted.",
                              source=self.source, source_url=self.source_url, confidence=0.0)
        if r.status_code == 200:
            d = r.json()
            return ToolResult(
                self.key, self.title, "LIVE", "OK", "IFSC_VALID",
                f"IFSC {ifsc} is valid — {d.get('BANK', '')} , {d.get('BRANCH', '')}, {d.get('CITY', '')}.",
                detail=f"NEFT {'yes' if d.get('NEFT') else 'no'} · RTGS {'yes' if d.get('RTGS') else 'no'} · "
                       f"UPI {'yes' if d.get('UPI') else 'no'} · MICR {d.get('MICR') or '—'}",
                data={"bank": d.get("BANK"), "branch": d.get("BRANCH"), "city": d.get("CITY"),
                      "district": d.get("DISTRICT"), "state": d.get("STATE")},
                source=self.source, source_url=url, confidence=0.95, raw=d)
        return ToolResult(
            self.key, self.title, "LIVE", "FAIL", "IFSC_INVALID",
            f"IFSC {ifsc} NOT FOUND in the public IFSC directory — likely invalid or merged away "
            "(bank mergers re-issue IFSCs). This alone can block DBT routing.",
            detail="Live lookup returned 404. Fix: obtain the current IFSC of your branch and update the scheme record.",
            source=self.source, source_url=url, confidence=0.95)


class PincodeLookupTool(GovTool):
    """REAL public API: India Post public pincode directory. Confirms the
    beneficiary's district/state used for the correct scheme office/authority."""

    key = "PINCODE_LOOKUP"
    title = "Postal pincode directory"
    mode = "LIVE"
    description = "Resolves the beneficiary's area to district/state for correct office addressing (live HTTP call)."
    source = "India Post public pincode directory (postalpincode.in)"
    source_url = "https://api.postalpincode.in/"
    API = "https://api.postalpincode.in/pincode/{pin}"

    def applicable(self, case: dict) -> bool:
        return bool(_case_pincode(case))

    def run(self, case: dict) -> ToolResult:
        import requests
        pin = _case_pincode(case)
        url = self.API.format(pin=pin)
        payload = None
        try:
            for attempt in (1, 2):
                try:
                    r = requests.get(url, timeout=8)
                    payload = r.json()
                    break
                except Exception as e:
                    if attempt == 2:
                        raise e
        except Exception as e:
            return ToolResult(self.key, self.title, "UNAVAILABLE", "WARN", "SOURCE_UNAVAILABLE",
                              f"Pincode directory temporarily unavailable ({type(e).__name__}). "
                              "HAQ will continue using the available evidence.",
                              source=self.source, source_url=self.source_url, confidence=0.0)
        try:
            rec = payload[0]
            if rec.get("Status") == "Success" and rec.get("PostOffice"):
                po = rec["PostOffice"][0]
                return ToolResult(
                    self.key, self.title, "LIVE", "OK", "PINCODE_VALID",
                    f"Pincode {pin} resolves to {po.get('Block') or po.get('Name')}, "
                    f"{po.get('District')}, {po.get('State')} — used to address the correct district office.",
                    detail=f"{len(rec['PostOffice'])} post offices in this pincode.",
                    data={"district": po.get("District"), "state": po.get("State"), "block": po.get("Block")},
                    source=self.source, source_url=url, confidence=0.9)
        except Exception:
            pass
        return ToolResult(self.key, self.title, "LIVE", "WARN", "PINCODE_UNRESOLVED",
                          f"Pincode {pin} could not be resolved. Address the scheme office using the district "
                          "shown on the scheme letter.",
                          source=self.source, source_url=url, confidence=0.4)


class PublicDocsTool(GovTool):
    """PUBLIC SOURCE: retrieval over the curated corpus of official/public DBT
    guidance (backend/kb/dbt_knowledge.json) with source URLs shown in the UI.
    This is how KHOJ 'searches/retrieves' process knowledge without pretending to
    scrape authenticated portals."""

    key = "DBT_PUBLIC_DOCS"
    title = "DBT public guidance retrieval"
    mode = "PUBLIC"
    description = "Retrieves relevant official/public DBT process guidance with source links."
    source = "Curated corpus of official/public sources (DBT Mission, NPCI, UIDAI, PFMS, CPGRAMS, RTI)"
    source_url = "https://dbtbharat.gov.in/"

    def __init__(self):
        with open(os.path.join(BASE_DIR, "kb", "dbt_knowledge.json"), encoding="utf-8") as f:
            self.kb = json.load(f)["entries"]

    def applicable(self, case: dict) -> bool:
        return True

    def run(self, case: dict) -> ToolResult:
        diag = case.get("diagnosis") or {}
        text = " ".join([
            case.get("narrative", ""),
            " ".join(str(v.get("value", "")) for v in (case.get("extraction", {}).get("fields") or {}).values()),
            diag.get("root_cause_code") or "",
            " ".join(e.get("code", "") + " " + e.get("message", "") for e in case.get("evidence") or []),
        ]).lower()
        tags_hit, best = [], None
        for entry in self.kb:
            hits = [t for t in entry["tags"] if t.lower() in text]
            if hits and (best is None or len(hits) > len(tags_hit)):
                best, tags_hit = entry, hits
        if not best:
            best = next(e for e in self.kb if e["id"] == "KB-DBT-01")
            tags_hit = ["pipeline"]
        return ToolResult(
            self.key, self.title, "PUBLIC", "OK", "GUIDANCE_FOUND",
            f"Retrieved public guidance: “{best['title']}” (matched: {', '.join(tags_hit[:4])}).",
            detail=best["content"][:400] + ("…" if len(best["content"]) > 400 else ""),
            data={"kb_id": best["id"], "kb_title": best["title"], "url": best["url"], "source": best["source"]},
            source=best["source"], source_url=best["url"], confidence=0.85)


# ============================================================ DEMO tools
class DemoTool(GovTool):
    mode = "DEMO"

    def __init__(self, key, title, profile_key, description):
        self.key, self.title, self.profile_key, self.description = key, title, profile_key, description
        self.source = title
        self.source_url = ""

    def applicable(self, case: dict) -> bool:
        return True

    def run(self, case: dict) -> ToolResult:
        profile = case.get("portal_profile") or {}
        sig = dict(profile.get(self.profile_key, {}))
        replan = profile.get("replan_updates", {}).get(self.profile_key)
        if replan and case.get("evidence_flags"):
            sig.update(replan)
        return ToolResult(
            self.key, self.title, "DEMO", sig.get("status", "WARN"), sig.get("code", "UNKNOWN"),
            sig.get("message", "No simulated signal available."),
            detail=sig.get("detail", "") + " · Simulated institutional response (beneficiary-level status "
                    "on this system requires authentication we do not hold — production plugs an authorized adapter here).",
            data=sig.get("raw", {}), source=self.title, source_url="", confidence=0.75,
            urn=sig.get("urn"), raw=sig.get("raw", {}))


def build_tools() -> list[GovTool]:
    return [
        DemoTool("SCHEME_STATUS", "Scheme Portal (NSAP / NSP / PM-KISAN)", "scheme_portal",
                 "Beneficiary payment status on the scheme portal."),
        DemoTool("PFMS_STATUS", "PFMS — Public Financial Management System", "pfms",
                 "Payment batch processing status."),
        DemoTool("APBS_STATUS", "APBS — Aadhaar Payment Bridge", "apbs",
                 "Credit routing / return status."),
        DemoTool("NPCI_MAPPER", "NPCI Aadhaar Mapper (BASE)", "npci_mapper",
                 "Which bank account the Aadhaar is seeded to for DBT."),
        DemoTool("BANK_CBS", "Bank CBS — Core Banking System", "bank",
                 "Account status and credit outcome at the bank."),
        IfscLookupTool(),
        PincodeLookupTool(),
        PublicDocsTool(),
    ]


PIPELINE_ORDER = [("SCHEME_STATUS", "SCHEME"), ("PFMS_STATUS", "PFMS / TREASURY"),
                  ("APBS_STATUS", "APBS"), ("NPCI_MAPPER", "NPCI MAPPER"), ("BANK_CBS", "BANK")]


def select_tools(case: dict, tools: list[GovTool]) -> list[GovTool]:
    """KHOJ's tool-selection decision: what evidence does THIS case need?"""
    return [t for t in tools if t.applicable(case)]


def _case_ifsc(case: dict) -> str | None:
    f = (case.get("extraction") or {}).get("fields") or {}
    v = (f.get("ifsc") or {}).get("value") or (case.get("beneficiary") or {}).get("ifsc")
    return v.strip().upper() if v else None


def _case_pincode(case: dict) -> str | None:
    import re
    blob = " ".join(str(d.get("text_content", "")) for d in case.get("documents") or [])
    m = re.search(r"\b(4\d{5})\b", blob) or re.search(r"\b(\d{6})\b", blob)
    return m.group(1) if m else None
