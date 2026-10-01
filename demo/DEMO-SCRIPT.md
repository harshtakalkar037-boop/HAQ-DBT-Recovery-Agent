# HAQ — 3-Minute Golden Demo Script (for judges)

**Case:** Shantabai Pawar, 67, Nashik — old-age pension stopped for 3 months.
**Narrative (Hinglish):** “Meri dadi Shantabai ki purani pension teen mahine se nahi aayi hai…”

---

### 0:00 — Open & file the case
Home screen: the question **“Mera sarkari paisa kyun nahi aaya?”** → click **▶ Run the Golden Demo**.
Press **⚑ Open Case & Start Investigation**. The Command Center opens — the agent board is live.

### 0:10 — SAMVAAD works
- Extraction cards stream: fields pulled from Aadhaar, passbook, SMS, scheme letter.
- **RED ALERT: NAME MISMATCH DETECTED** — `SHANTA BAI DAGDU PAWAR` (Aadhaar) vs `SHANTABAI D. PAWAR` (bank) with the B06 rule shown.
- Point at the **Identity Graph** in the Case File tab. *“OCR is never blindly trusted — fields are confirmed before use.”*

### 0:35 — KHOJ investigates the pipeline
Evidence chain lights up node by node (all badges **DEMO / CACHED**):
Scheme Portal ✓ released → PFMS ✓ processed → APBS ✕ returned (code 25) → NPCI Mapper ✕ INACTIVE → Bank ✕ “account closed”.
*“Five systems, one evidence chain — this is where the money died.”*

### 0:55 — NIDAAN diagnoses (evidence-first)
Diagnosis tab: root **`CLOSED_MAPPED_ACCOUNT`** (80%) + secondary **`NAME_MISMATCH`** + watch item **life certificate (30 Nov)**.
Every conclusion has cited evidence + taxonomy signals + rules used.

### 1:15 — YOJNA plans + NYAYA blocks
Plan tab: **PLAN v1** — 9 dependency-ordered steps. Two steps show **NYAYA BLOCK** badges:
seeding is blocked *because name correction must come first (B06)*. *“The rules engine — not the LLM — decides this.”*

### 1:35 — ⭐ THE RE-PLANNING MOMENT
Press the amber button: **📥 Deliver new evidence (demo: passbook page 2)**.
- SAMVAAD extracts the new page → **SATYAPAN ALERT: MATERIAL CHANGE** — a ₹500 withdrawal 4 months ago. *“The account is not closed — it is DORMANT.”*
- NIDAAN revises via override rule R-DORMANT-01 → **`DORMANT_MAPPED_ACCOUNT` (88%)**.
- YOJNA screams: **PLAN v2 — REMOVED → `OLD_ACCOUNT_ACTION` · ADDED → `REACTIVATE_DORMANT_ACCOUNT`**.
- KARM strikes through all 9 v1 documents — **✕ INVALIDATED — “resolution plan changed after new evidence”** — and regenerates the v2 pack.
*“This is not a chatbot. A chatbot cannot say ‘my earlier plan was wrong, here is the new one.’”*

### 2:10 — KARM + SATYAPAN
Open the Documents tab — click **Aadhaar Seeding Request (Annexure I)**: a filled, print-ready form carrying her name *as per Aadhaar*, account, scheme and URN. Also: KYC name correction letter, non-payment certificate, re-processing request, CPGRAMS draft, RTI draft, **Hindi bank-counter script**.
Verification tab: every check ✓ (fields complete · identity consistent · URN consistent · correct authority · plan version). *“9 invalidated, 8 verified — nothing stale ships.”*

### 2:40 — ANUSARAN arms the watchdog
Follow-up tab: **🛡 HAQ WATCHDOG ACTIVE** + timeline: TODAY (action pack) → TOMORROW (bank visit) → +2d (mapper verify) → +7d (re-process follow-up) → +15d (CPGRAMS auto-prepared) → +30d (RTI) → **closes only when the payment is verified**.
Optional finish: press **₹ Payment received — verify & close** → the case closes with a verified-credit stamp.

### 3:00 — One-line close
> “HAQ investigated five systems, found the real cause, caught its own wrong diagnosis when new evidence arrived, replaced the plan, invalidated its own paperwork, and is now following up until a grandmother's pension actually lands. That is agency.”

---
**Backup tips:** the Live Agent Feed tab shows all events if the flow moves too fast; every seeded case is deterministic — re-run freely; `payment_received` is the clean closing beat.
