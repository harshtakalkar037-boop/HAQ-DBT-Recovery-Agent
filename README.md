# HAQ हक़ — The DBT Payment Recovery Agent

> **“Mera sarkari paisa kyun nahi aaya?”**
> HAQ doesn't answer this question. It **owns the case** — investigating, diagnosing, planning, drafting paperwork, verifying its own work, re-planning when evidence changes, and following up until the money is verified.

Built for **BHARAT AGENTIC 2026** (12-hour Agentic AI hackathon).

---

## What it does

An ordinary Indian beneficiary (pensioner, farmer, student) hasn't received a Direct Benefit Transfer payment. They describe the problem in Hindi/English/Hinglish and upload whatever they have — Aadhaar, passbook, failure SMS, scheme letter. HAQ then runs a **stateful multi-agent workflow**:

```
USER → SAMVAAD → KHOJ → NIDAAN → YOJNA → KARM → SATYAPAN → ANUSARAN → USER
                        NEW EVIDENCE ↳ SATYAPAN → NIDAAN → YOJNA (RE-PLAN) → KARM → SATYAPAN
```

| Agent | Role | What it actually does |
|---|---|---|
| **SAMVAAD** | Intake & Extraction | Understands Hinglish narratives, parses documents, builds a **Case File + Identity Graph**, flags name/account mismatches (e.g. `SHANTA BAI DAGDU PAWAR` ≠ `SHANTABAI D. PAWAR`). Never blind-trusts extraction. |
| **KHOJ** | Evidence & Status | Checks 5 systems through a **GovSystemAdapter** layer: Scheme Portal · PFMS · APBS · NPCI Mapper · Bank CBS. Assembles one evidence chain. |
| **NIDAAN** | Diagnosis | Hybrid scoring over the deterministic failure taxonomy (rules/taxonomy.json) + documented override rules (closed→dormant). Outputs structured root/secondary causes with confidence + cited evidence. |
| **YOJNA** | Planner | Dependency-ordered plan (name correction **before** re-seeding, mapper verify **before** re-processing). **Re-plans when new evidence arrives.** |
| **KARM** | Action & Documents | Generates office-ready artifacts from **fixed templates** (never LLM-invented forms): Aadhaar Seeding Request (Annexure I), KYC name correction, non-payment certificate, re-processing request, CPGRAMS grievance, RTI draft, Hindi bank-counter script, WhatsApp update. |
| **NYAYA** | Decision Engine | Deterministic policy: ordering, blocking (B06 rule), deadlines, escalation ladder, guardrails. The LLM has **no authority** over these rules. |
| **SATYAPAN** | Verification | Checks every artifact before release (fields, identity, URN, authority, plan version). **Invalidates** outdated documents after re-planning. Detects material change in new evidence. |
| **ANUSARAN** | Follow-up Watchdog | Case timeline (TODAY → TOMORROW → +2d → +7d → +15d → +30d), escalations, simulated WhatsApp nudges. **Closes the case only on a verified credit.** |

## The golden demo (the re-planning moment)

1. Shantabai Pawar, 67, Nashik — pension stopped for 3 months. Grandson files the case in Hinglish + 4 documents.
2. SAMVAAD detects the **name mismatch** across Aadhaar / passbook / scheme letter.
3. KHOJ's evidence chain: Scheme ✓ released → PFMS ✓ processed → APBS ✕ returned → NPCI ✕ inactive → Bank ✕ "closed".
4. NIDAAN: `CLOSED_MAPPED_ACCOUNT` (primary) + `NAME_MISMATCH` (secondary).
5. YOJNA plans v1: close/withdraw from old account → correct name → re-seed → verify mapper → re-process → escalate.
6. **New evidence arrives** — a second passbook page showing a ₹500 withdrawal 4 months ago.
7. SATYAPAN: *"MATERIAL CHANGE — the account cannot be closed; it is DORMANT."*
8. NIDAAN revises via **override rule R-DORMANT-01** → `DORMANT_MAPPED_ACCOUNT`.
9. YOJNA emits **PLAN v2** — `OLD_ACCOUNT_ACTION` **removed**, `REACTIVATE_DORMANT_ACCOUNT` **added**.
10. KARM **invalidates** all 9 v1 documents with reasons, regenerates the v2 pack; SATYAPAN verifies it.
11. ANUSARAN updates the timeline — **HAQ WATCHDOG ACTIVE** until the payment is verified.

## Quick start

```bash
cd haq
pip install -r requirements.txt
./run.sh                       # or: python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
# open http://localhost:8000
```

Optional live LLM polish layer (never required — demo runs fully offline):

```bash
export GROQ_API_KEY=...        # or GEMINI_API_KEY
```

## Architecture

```
frontend/          index.html · styles.css · app.js   (case command center, polls agent events)
backend/
  main.py          FastAPI — REST + static serving · consent gate · case deletion · source registry
  orchestrator.py  Stateful workflow engine (threads + event stream)
  agents.py        KHOJ · NIDAAN · YOJNA · KARM · SATYAPAN · ANUSARAN
  extract.py       SAMVAAD: narrative understanding, document parsing, identity graph, LLM adapter
  adapters.py      GovTool interface → LIVE tools · PUBLIC docs retrieval · DEMO adapters
  docs_templates.py KARM document factory (fixed templates, slot validation)
  core.py          Case memory (SQLite), identity utils, NYAYA rules engine, privacy masking
  rules/           taxonomy.json · playbooks.json · policy.json   ← source of truth
  kb/              dbt_knowledge.json — curated public guidance with real source URLs
  seed.py          3 demo cases with synthetic data + realistic portal profiles
data/              haq.db (persistent case memory — reopen and continue any case)
```

### Source transparency (never faked)

| Tool | Mode | What it really does |
|---|---|---|
| `IFSC_LOOKUP` | 🟢 LIVE | Real HTTP call to the public IFSC directory — validates branch codes, detects merged/invalid IFSCs |
| `PINCODE_LOOKUP` | 🟢 LIVE | Real HTTP call to India Post's public pincode directory — resolves district/state |
| `DBT_PUBLIC_DOCS` | 🟢 PUBLIC | Retrieval over the curated corpus of official/public DBT guidance (URLs shown) |
| `SCHEME_STATUS` · `PFMS_STATUS` · `APBS_STATUS` · `NPCI_MAPPER` · `BANK_CBS` | 🟡 DEMO | Beneficiary-level status requires OTP/Aadhaar/institutional credentials — simulated behind the same adapter interface, ready for authorized integrations |

If a live source fails, the result is marked **🟠 SOURCE UNAVAILABLE** with "HAQ will continue using the available evidence" — never a simulated success.

### Privacy & consent

Consent gate before processing · masked Aadhaar (`XXXX XXXX 1234`) and account (`XXXX4521`) in the UI · **Delete My Case** endpoint · Privacy Center, Sources page and disclaimer in the product · no secrets in frontend or logs.

### Hybrid AI principle (enforced)

- **LLM / language layer** *(optional, pluggable)*: messy-document understanding, Hinglish interpretation, explanations, drafting into fixed templates.
- **Deterministic layer** *(always)*: failure taxonomy, dependency ordering, deadlines, escalation, validation, document correctness. **NYAYA is the source of truth** — the LLM never invents government rules.
- **Evidence-first UI**: every conclusion displays its evidence and the rule that fired.

### Honesty in demo mode

- All government responses come from **MockAdapters**, labelled **DEMO / CACHED** in the UI. `LiveGovAdapter` is stubbed for production APIs (PFMS, NPCI, scheme portals).
- All beneficiary data is **synthetic**. No real Aadhaar or financial information is used anywhere.

## Demo cases

| Case | Story | Root cause (v1) | Re-plan trigger |
|---|---|---|---|
| **pension** ★ | Shantabai Pawar, 67 — pension stopped 3 months | `CLOSED_MAPPED_ACCOUNT` + `NAME_MISMATCH` | passbook page 2 → `DORMANT_MAPPED_ACCOUNT` |
| **scholarship** | Priya Wagh, 18 — NSP instalment bounced | `NAME_MISMATCH` + `ACCOUNT_VALIDATION_FAILED` | — |
| **pmkisan** | Ramesh Yadav, 57 — instalment missing | `AADHAAR_NOT_SEEDED` + `EKYC_PENDING` | — |

## API surface

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/cases` | Create case (seed or custom) → starts the agent pipeline |
| GET | `/api/cases/{id}` | Full case state (case memory) |
| GET | `/api/cases/{id}/events?after=N` | Agent event stream (incremental) |
| POST | `/api/cases/{id}/evidence` | New evidence (upload) → **re-planning loop** |
| POST | `/api/cases/{id}/evidence/seed-replan` | Demo: deliver queued evidence (golden moment) |
| POST | `/api/cases/{id}/fields/confirm` | Confirm extracted fields before document release |
| POST | `/api/cases/{id}/simulate` | `bank_visit_done` · `mapper_verified` · `payment_received` |

## Why this is genuinely agentic

- **Multi-step, stateful workflow** with persistent case memory — reopen any case and continue.
- **Real work product**: office-ready, institution-addressed documents with populated fields.
- **Verification loop**: artifacts are checked and can be **invalidated**; nothing is blindly emitted.
- **Adaptation**: new evidence changes the diagnosis **and** the plan, visibly (`PLAN v1 → PLAN v2`).
- **Follow-up over time**: the watchdog holds the case open with deadlines and an escalation ladder — the part no chatbot and no human helper sustains.
