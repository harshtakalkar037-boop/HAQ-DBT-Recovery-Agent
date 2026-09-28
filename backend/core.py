"""HAQ core: case memory (SQLite), identity-graph utilities, rules loading, NYAYA fact model."""
from __future__ import annotations
import json, os, re, sqlite3, threading, uuid
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")
RULES_DIR = os.path.join(BASE_DIR, "rules")
os.makedirs(DATA_DIR, exist_ok=True)

_lock = threading.RLock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


# ---------------------------------------------------------------- rules loading
def load_json(name: str) -> dict:
    with open(os.path.join(RULES_DIR, name), encoding="utf-8") as f:
        return json.load(f)

TAXONOMY = load_json("taxonomy.json")
PLAYBOOKS = load_json("playbooks.json")
POLICY = load_json("policy.json")

STEPS = PLAYBOOKS["steps"]
STEP_ORDER = PLAYBOOKS["step_order_index"]
CAUSE_PLAYBOOKS = PLAYBOOKS["cause_playbooks"]
CAUSES = TAXONOMY["causes"]


# ---------------------------------------------------------------- identity graph
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE = re.compile(r"\s+")

def normalize_name(name: str) -> str:
    """Normalize Indian names for comparison: upper, strip punct, collapse spaces,
    join single-token spelling variants like 'SHANTA BAI' <-> 'SHANTABAI'."""
    s = (name or "").upper()
    s = _PUNCT.sub(" ", s)
    s = _SPACE.sub(" ", s).strip()
    return s

def compact_name(name: str) -> str:
    return normalize_name(name).replace(" ", "")

def name_tokens(name: str) -> list[str]:
    return normalize_name(name).split()

def compare_names(a: str, b: str) -> dict:
    """Compare two name strings. Returns {match: bool, type: str, detail: str}."""
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return {"match": False, "type": "missing", "detail": "One of the name fields is empty."}
    if na == nb:
        return {"match": True, "type": "exact", "detail": "Normalized names match exactly."}
    if compact_name(a) == compact_name(b):
        return {"match": True, "type": "spacing_variant", "detail": "Only spacing differs — still flagged for B06 safety."}
    ta, tb = name_tokens(a), name_tokens(b)
    # initials expansion: "SHANTABAI D PAWAR" vs "SHANTABAI DAGDU PAWAR"
    initials_ok = len(ta) == len(tb)
    token_detail = []
    if initials_ok:
        for x, y in zip(ta, tb):
            if x == y:
                continue
            if len(x) == 1 and y.startswith(x):
                token_detail.append(f"'{x}' is an initial of '{y}'")
                continue
            if len(y) == 1 and x.startswith(y):
                token_detail.append(f"'{y}' is an initial of '{x}'")
                continue
            if x[:4] == y[:4]:
                token_detail.append(f"'{x}' vs '{y}' — spelling variant")
                continue
            initials_ok = False
            break
    if initials_ok:
        return {"match": False, "type": "initial_or_spelling", "detail": "; ".join(token_detail) or "Token-level differences"}
    if set(ta) & set(tb):
        return {"match": False, "type": "partial", "detail": f"Tokens {sorted(set(ta) ^ set(tb))} differ between records."}
    return {"match": False, "type": "different", "detail": "Names do not correspond."}


def mask_aadhaar(a: str) -> str:
    digits = "".join(ch for ch in (a or "") if ch.isdigit())
    return ("XXXX XXXX " + digits[-4:]) if len(digits) >= 12 else "XXXX XXXX XXXX"


def mask_account(a: str) -> str:
    digits = "".join(ch for ch in (a or "") if ch.isdigit())
    return ("XXXX" + digits[-4:]) if len(digits) >= 4 else "XXXX"


def mask_case_view(case: dict) -> dict:
    """Privacy layer: mask sensitive fields in the API view. Documents generated
    for official submission keep the account number (the beneficiary needs it on
    the form); the interface never shows it unnecessarily."""
    import copy
    view = copy.deepcopy(case)
    b = view.get("beneficiary") or {}
    if b.get("aadhaar"):
        b["aadhaar"] = mask_aadhaar(b["aadhaar"])
        b["aadhaar_masked"] = True
    if b.get("account_number"):
        b["account_number"] = mask_account(b["account_number"])
        b["account_masked"] = True
    for f in ((view.get("extraction") or {}).get("fields") or {}).values():
        if "aadhaar" in str(f.get("value", "")) and len("".join(c for c in str(f.get("value", "")) if c.isdigit())) >= 12:
            f["value"] = mask_aadhaar(f["value"])
    exf = (view.get("extraction") or {}).get("fields") or {}
    if "aadhaar" in exf:
        exf["aadhaar"]["value"] = mask_aadhaar(exf["aadhaar"].get("value", ""))
    if "account_number" in exf:
        exf["account_number"]["value"] = mask_account(exf["account_number"].get("value", ""))
    for d in view.get("documents_generated") or []:
        fu = d.get("fields_used") or {}
        if fu.get("account_number"):
            fu["account_number"] = mask_account(fu["account_number"])
    return view


# ---------------------------------------------------------------- case store
class CaseStore:
    """Persistent case memory. A case is a JSON document; events are append-only."""

    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(DATA_DIR, "haq.db")
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with _lock, self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS cases(
                id TEXT PRIMARY KEY, data TEXT NOT NULL, created_at TEXT, updated_at TEXT)""")
            c.execute("""CREATE TABLE IF NOT EXISTS events(
                seq INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL,
                data TEXT NOT NULL, ts TEXT)""")
            c.execute("CREATE INDEX IF NOT EXISTS idx_events_case ON events(case_id, seq)")

    def create_case(self, case: dict) -> dict:
        case["created_at"] = now_iso()
        case["updated_at"] = case["created_at"]
        with _lock, self._conn() as c:
            c.execute("INSERT INTO cases(id, data, created_at, updated_at) VALUES (?,?,?,?)",
                      (case["id"], json.dumps(case, ensure_ascii=False), case["created_at"], case["updated_at"]))
        return case

    def get_case(self, case_id: str) -> dict | None:
        with _lock, self._conn() as c:
            row = c.execute("SELECT data FROM cases WHERE id=?", (case_id,)).fetchone()
        return json.loads(row["data"]) if row else None

    def update_case(self, case: dict) -> dict:
        case["updated_at"] = now_iso()
        with _lock, self._conn() as c:
            c.execute("UPDATE cases SET data=?, updated_at=? WHERE id=?",
                      (json.dumps(case, ensure_ascii=False), case["updated_at"], case["id"]))
        return case

    def list_cases(self) -> list[dict]:
        with _lock, self._conn() as c:
            rows = c.execute("SELECT id, data, created_at, updated_at FROM cases ORDER BY updated_at DESC").fetchall()
        out = []
        for r in rows:
            d = json.loads(r["data"])
            out.append({
                "id": d["id"], "status": d.get("status"), "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "beneficiary": d.get("beneficiary", {}).get("name"),
                "scheme": d.get("beneficiary", {}).get("scheme"),
                "root_cause": (d.get("diagnosis") or {}).get("root_cause_code"),
                "watchdog_active": (d.get("watchdog") or {}).get("active", False),
                "narrative": d.get("narrative", "")[:110],
            })
        return out

    def add_event(self, case_id: str, event: dict) -> dict:
        event["ts"] = event.get("ts") or now_iso()
        with _lock, self._conn() as c:
            cur = c.execute("INSERT INTO events(case_id, data, ts) VALUES (?,?,?)",
                            (case_id, json.dumps(event, ensure_ascii=False), event["ts"]))
            event["seq"] = cur.lastrowid
        return event

    def list_events(self, case_id: str, after: int = 0) -> list[dict]:
        with _lock, self._conn() as c:
            rows = c.execute("SELECT seq, data FROM events WHERE case_id=? AND seq>? ORDER BY seq",
                             (case_id, after)).fetchall()
        out = []
        for r in rows:
            e = json.loads(r["data"])
            e["seq"] = r["seq"]
            out.append(e)
        return out


# ---------------------------------------------------------------- NYAYA facts + rule engine
class Facts:
    """Deterministic fact model the policy rules evaluate against."""

    def __init__(self, case: dict):
        plan = current_plan(case)
        self.cause_active = {
            code: False for code in CAUSES
        }
        diag = case.get("diagnosis") or {}
        for code in [diag.get("root_cause_code"), diag.get("secondary_cause_code")]:
            if code:
                self.cause_active[code] = True
        for extra in diag.get("additional_causes") or []:
            self.cause_active[extra] = True
        self.step_status = {}
        self.step_owner = {}
        if plan:
            for s in plan["steps"]:
                self.step_status[s["key"]] = s["status"]
                self.step_owner[s["key"]] = s["owner"]
        self.scheme_is_pension = bool((case.get("beneficiary") or {}).get("is_pension"))
        self.has_urn = bool(_find_urn(case))
        self.fields_confirmed = _fields_confirmed(case)
        self.evidence_flag = {}
        for f in case.get("evidence_flags") or []:
            self.evidence_flag[f] = True
        self.cause_set = [c for c, v in self.cause_active.items() if v]

    def get(self, fact: str, arg: str | None = None):
        if fact == "cause_active":
            return self.cause_active.get(arg, False)
        if fact == "step_status":
            return self.step_status.get(arg, "MISSING")
        if fact == "step_owner":
            return self.step_owner.get(arg)
        if fact == "scheme_is_pension":
            return self.scheme_is_pension
        if fact == "has_urn":
            return self.has_urn
        if fact == "fields_confirmed":
            return self.fields_confirmed
        if fact == "evidence_flag":
            return self.evidence_flag.get(arg, False)
        if fact == "cause_set":
            return self.cause_set
        return None


def _find_urn(case: dict) -> str | None:
    for d in case.get("documents") or []:
        f = d.get("fields") or {}
        if f.get("urn"):
            return f["urn"]
    for e in case.get("evidence") or []:
        if e.get("urn"):
            return e["urn"]
    return None

def _fields_confirmed(case: dict) -> bool:
    ex = case.get("extraction") or {}
    fields = ex.get("fields") or {}
    values = list(fields.values()) if isinstance(fields, dict) else fields
    if not values:
        return False
    return all(f.get("confirmed") for f in values)


def eval_condition(cond: dict, facts: Facts) -> bool:
    val = facts.get(cond["fact"], cond.get("arg"))
    op, target = cond["op"], cond["value"]
    if op == "==":
        return val == target
    if op == "!=":
        return val != target
    if op == "overlaps":
        return bool(set(val or []) & set(target))
    if op == "in":
        return val in target
    raise ValueError(f"unknown op {op}")


def eval_rule(rule: dict, facts: Facts) -> bool:
    block = rule["if"]
    if "all" in block:
        return all(eval_condition(c, facts) for c in block["all"])
    if "any" in block:
        return any(eval_condition(c, facts) for c in block["any"])
    return eval_condition(block, facts)


def run_policy_engine(case: dict, plan: dict | None = None) -> dict:
    """Evaluate all NYAYA rules. Returns {fired: [...], blocks: {step: reason},
    soft_blocks: {step: reason}, deadlines: {step: {days, reason}}, guardrails: [...],
    ensure_steps: [...]}."""
    facts = Facts(case)
    result = {"fired": [], "blocks": {}, "soft_blocks": {}, "deadlines": {}, "guardrails": [], "ensure_steps": []}
    for rule in sorted(POLICY["rules"], key=lambda r: r["priority"]):
        try:
            fired = eval_rule(rule, facts)
        except Exception:
            fired = False
        if fired:
            result["fired"].append({"id": rule["id"], "label": rule["label"]})
            for eff in rule["then"]:
                a = eff["action"]
                if a == "block_step":
                    result["blocks"][eff["step"]] = eff["reason"]
                elif a == "soft_block":
                    result["soft_blocks"][eff["step"]] = eff["reason"]
                elif a == "set_deadline":
                    result["deadlines"][eff["step"]] = {"days": eff["days"], "reason": eff.get("reason", "")}
                elif a == "guardrail":
                    result["guardrails"].append(eff["text"])
                elif a == "ensure_step":
                    result["ensure_steps"].append({"step": eff["step"], "reason": eff.get("reason", "")})
    return result


# ---------------------------------------------------------------- plan helpers
def current_plan(case: dict) -> dict | None:
    plans = case.get("plans") or []
    for p in reversed(plans):
        if not p.get("superseded"):
            return p
    return plans[-1] if plans else None


def build_plan_steps(cause_codes: list[str], case: dict, policy_result: dict) -> list[dict]:
    """Union playbooks of all active causes -> dependency-ordered plan steps.
    Ordering: step_order_index topological-ish sort, NYAYA blocks applied."""
    keys: list[str] = []
    for code in cause_codes:
        for k in CAUSE_PLAYBOOKS.get(code, CAUSE_PLAYBOOKS["OTHER"]):
            if k not in keys:
                keys.append(k)
    for extra in policy_result.get("ensure_steps") or []:
        if extra["step"] not in keys:
            keys.append(extra["step"])
    # always schedule non-payment certificate for pension arrears recovery
    if (case.get("beneficiary") or {}).get("is_pension") and "NON_PAYMENT_CERTIFICATE" not in keys:
        keys.insert(0, "NON_PAYMENT_CERTIFICATE")
    keys.sort(key=lambda k: (STEP_ORDER.get(k, 9), k))
    # NOTE: dependencies are trimmed to steps that actually apply (in the playbook
    # union). We deliberately do NOT drag in unrelated steps via dependency closure —
    # that would pollute the plan and hide the v1→v2 diff during re-planning.

    steps = []
    for k in keys:
        defn = STEPS[k]
        deps = [d for d in defn["depends_on"] if d in keys]
        status = "READY"
        blocked_reason = None
        if k in policy_result["blocks"]:
            status = "BLOCKED"
            blocked_reason = policy_result["blocks"][k]
        elif k in policy_result["soft_blocks"]:
            status = "BLOCKED"
            blocked_reason = policy_result["soft_blocks"][k]
        elif deps:
            status = "PENDING"
        deadline = policy_result["deadlines"].get(k, {}).get("days", defn["deadline_days"])
        steps.append({
            "key": k,
            "action": defn["action"],
            "action_hi": defn["action_hi"],
            "owner": defn["owner"],
            "depends_on": deps,
            "deadline_days": deadline,
            "required_docs": defn["required_docs"],
            "doc_type": defn["doc_type"],
            "notes": defn["notes"],
            "completion_condition": defn.get("completion_condition", "Action acknowledged by the responsible party."),
            "status": status,
            "blocked_reason": blocked_reason,
            "done_at": None,
        })
    # unblock dependents whose deps are all DONE (none at creation)
    return steps
