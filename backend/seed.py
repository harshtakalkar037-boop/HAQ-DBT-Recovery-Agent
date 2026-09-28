"""Seeded demo cases with synthetic beneficiary data and realistic portal profiles.
All personal data is FICTIONAL (demo mode)."""
from __future__ import annotations

SEED_CATALOG = [
    {
        "id": "pension",
        "title": "GOLDEN DEMO — Grandmother's pension stopped for 3 months",
        "title_hi": "दादी की पेंशन 3 महीने से रुकी है",
        "person": "Shantabai Pawar, 67 — Nashik, Maharashtra",
        "scheme": "Old Age Pension (NSAP-IGNOAPS + State share)",
        "blurb": "Name mismatch + dormant mapped account + returned instalments. Includes the NEW-EVIDENCE re-planning moment.",
        "narrative": "Meri dadi Shantabai ki purani pension teen mahine se nahi aayi hai. Gram panchayat ne likha hai paisa bank se laut gaya. Bank wale bolte hain department se poochho. Kripya madad kijiye — dadi ka ilaaj ka paisa chahiye.",
    },
    {
        "id": "scholarship",
        "title": "Student scholarship bounced — Account Validation Failed",
        "title_hi": "छात्रवृत्ति का पैसा नहीं आया",
        "person": "Priya Wagh, 18 — Kolhapur, Maharashtra",
        "scheme": "Post-Matric Scholarship (NSP / PFMS)",
        "blurb": "PFMS Account Validation Failed — name + IFSC problems after a bank merger.",
        "narrative": "Mera naam Priya hai. Meri post-matric scholarship ki pehli instalment nahi aayi. NSP portal par likha hai Account Validation Failed. College ka nodal officer bolta hai bank se theek karao.",
    },
    {
        "id": "pmkisan",
        "title": "PM-KISAN instalment missing — Aadhaar not seeded",
        "title_hi": "पीएम-किसान की किस्त नहीं आई",
        "person": "Ramesh Yadav, 57 — Latur, Maharashtra",
        "scheme": "PM-KISAN Samman Nidhi",
        "blurb": "UID never enabled for DBT + pending eKYC. Classic mapper failure.",
        "narrative": "Mera naam Ramesh Yadav hai. PM-KISAN ki kist mujhe nahi mili, baaki gaon walon ko mil gayi. SMS aaya tha aadhaar not seeded. Bank ka chakkar lagake thak gaya hoon.",
    },
]


def _aadhaar_text(name, dob, aadhaar, address):
    return (
        "GOVERNMENT OF INDIA\n"
        "Unique Identification Authority of India\n"
        "आधार / AADHAAR\n"
        f"Name: {name}\n"
        f"DOB: {dob}\n"
        "Gender: F\n"
        f"Aadhaar No: {aadhaar}\n"
        f"Address: {address}\n"
        "Synthetic demo document — not a real Aadhaar card.\n"
    )


def materialize_seed(seed_id: str) -> dict:
    """Returns {case_partial, documents, portal_profile, replan_documents}."""
    if seed_id == "pension":
        return {
            "case_partial": {
                "seed_id": "pension",
                "language": "hi-en",
                "beneficiary": {
                    "name": "SHANTA BAI DAGDU PAWAR",
                    "aadhaar": "4321 6543 2109",
                    "dob": "12/07/1958",
                    "state": "Maharashtra",
                    "district": "Nashik",
                    "scheme": "Old Age Pension (NSAP-IGNOAPS + State share)",
                    "scheme_key": "NSAP_IGNOAPS",
                    "is_pension": True,
                    "language": "hi",
                    "bank": "Bank of Maharashtra, Sinnar Branch",
                    "account_number": "6031224521",
                    "ifsc": "MAHB0001234",
                    "beneficiary_id": "MH/NSAP/2019/88214",
                },
                "expected": {
                    "v1_root": "CLOSED_MAPPED_ACCOUNT",
                    "v1_secondary": "NAME_MISMATCH",
                    "v2_root": "DORMANT_MAPPED_ACCOUNT",
                    "v2_secondary": "NAME_MISMATCH",
                },
            },
            "documents": [
                {
                    "kind": "AADHAAR", "filename": "aadhaar_shantabai.jpg",
                    "text_content": _aadhaar_text(
                        "SHANTA BAI DAGDU PAWAR", "12/07/1958", "4321 6543 2109",
                        "Gat No. 112, Sinnar, Nashik, Maharashtra - 422103"),
                },
                {
                    "kind": "PASSBOOK", "filename": "passbook_page1.jpg",
                    "text_content": (
                        "BANK OF MAHARASHTRA — SINNAR BRANCH\n"
                        "A/c Name: SHANTABAI D. PAWAR\n"
                        "A/c No: 6031224521\n"
                        "IFSC: MAHB0001234\n"
                        "Savings Account — Passbook statement extract (page 1)\n"
                        "01/11/2024  DBT-CREDIT  NSAP PENSION       +1,200.00   Bal 8,420.00\n"
                        "28/11/2024  APBS-RETURN PENSION RETURNED   -1,200.00   Bal 8,420.00\n"
                        "12/11/2024  REMARK: ACCOUNT FLAGGED INACTIVE BY BANK\n"
                        "Last customer-initiated transaction on this page: 01/08/2024\n"),
                },
                {
                    "kind": "SMS", "filename": "sms_failure.png",
                    "text_content": (
                        "[SMS 05-03-2026 18:22] MAHDBT-NSAP: "
                        "Your pension instalments for Dec-2025, Jan-2026, Feb-2026 could not be credited. "
                        "APBS return code 25. URN: 20260305123456789. "
                        "Please contact your bank branch. Total amount: Rs. 3,600\n"),
                },
                {
                    "kind": "SCHEME_LETTER", "filename": "gram_panchayat_letter.jpg",
                    "text_content": (
                        "GRAM PANCHAYAT, SINNAR — SOCIAL WELFARE SECTION\n"
                        "Scheme: Sanjay Gandhi Niradhar Anudan Yojana (Old Age Pension) — NSAP-IGNOAPS\n"
                        "Beneficiary ID: MH/NSAP/2019/88214\n"
                        "Name: SHANTA BAI DAGDU PAWAR\n"
                        "Payment status: 3 instalments returned by bank (Dec 2025 – Feb 2026)\n"
                        "Reason as per treasury: account validation / credit returned\n"),
                },
            ],
            "portal_profile": {
                "scheme_portal": {
                    "check": "beneficiary payment status",
                    "status": "OK", "code": "PAYMENT_RELEASED",
                    "message": "3 instalments (Dec-2025, Jan-2026, Feb-2026) of Rs. 1,200 each released on 05-03-2026 via DBT.",
                    "detail": "Sanjay Gandhi Niradhar Anudan Yojana · Beneficiary MH/NSAP/2019/88214",
                    "urn": "20260305123456789",
                    "raw": {"instalments": ["2025-12", "2026-01", "2026-02"], "amount_each": 1200, "released_on": "2026-03-05"},
                },
                "pfms": {
                    "check": "payment batch processing",
                    "status": "OK", "code": "PAYMENT_PROCESSED",
                    "message": "PFMS processed the payment file on 06-03-2026 and forwarded to APBS.",
                    "detail": "Payment reference ID: PFMS/NSAP/2026/778219",
                    "raw": {"pfms_ref": "PFMS/NSAP/2026/778219"},
                },
                "apbs": {
                    "check": "APBS credit routing",
                    "status": "FAIL", "code": "PAYMENT_RETURNED_APBS",
                    "message": "APBS returned all 3 credits on 07-03-2026. Return code 25 — beneficiary account invalid/inactive.",
                    "detail": "Funds returned to the state treasury (sponsor).",
                    "urn": "20260305123456789",
                    "raw": {"return_code": 25, "returned_on": "2026-03-07"},
                },
                "npci_mapper": {
                    "check": "Aadhaar-bank mapping (BASE)",
                    "status": "FAIL", "code": "MAPPER_INACTIVE",
                    "message": "Aadhaar 4321xxxx2109 is mapped to Bank of Maharashtra, Sinnar — a/c ••••4521 — STATUS: INACTIVE.",
                    "detail": "No other active DBT mapping found. Last seeding: 2019.",
                    "raw": {"mapped_account": "••••4521", "mapped_bank": "Bank of Maharashtra", "mapper_status": "INACTIVE"},
                },
                "bank": {
                    "check": "account credit status (CBS)",
                    "status": "FAIL", "code": "ACCOUNT_CLOSED",
                    "message": "As per bank CBS records, a/c ••••4521 shows CLOSED (closed 12-11-2024). Credit attempts returned to sponsor.",
                    "detail": "Branch remarks: account closed on customer request.",
                    "raw": {"account_status": "CLOSED", "closed_on": "2024-11-12"},
                },
                "replan_updates": {
                    "bank": {
                        "check": "account credit status (CBS) — re-check after new evidence",
                        "status": "FAIL", "code": "ACCOUNT_DORMANT",
                        "message": "Re-check: a/c ••••4521 is NOT closed. Status: DORMANT/INOPERATIVE (no customer-initiated transaction for 18 months as of 01-2026).",
                        "detail": "Dormant accounts reject DBT credits but CAN be reactivated with one customer transaction + KYC.",
                        "raw": {"account_status": "DORMANT", "reactivable": True},
                    },
                    "npci_mapper": {
                        "check": "Aadhaar-bank mapping (BASE) — re-check",
                        "status": "FAIL", "code": "MAPPER_INACTIVE",
                        "message": "Aadhaar 4321xxxx2109 still mapped to a/c ••••4521 (Bank of Maharashtra) — STATUS: INACTIVE (dormant account).",
                        "detail": "Mapper re-points only after a fresh seeding request on the reactivated account.",
                        "raw": {"mapped_account": "••••4521", "mapper_status": "INACTIVE"},
                    },
                },
            },
            "replan_documents": [
                {
                    "kind": "PASSBOOK", "filename": "passbook_page2_new.jpg",
                    "text_content": (
                        "BANK OF MAHARASHTRA — SINNAR BRANCH\n"
                        "A/c Name: SHANTABAI D. PAWAR\n"
                        "A/c No: 6031224521\n"
                        "Savings Account — Passbook statement extract (page 2)\n"
                        "22/05/2026  CASH WDL    SELF                 -500.00    Bal 1,120.00\n"
                        "16/06/2026  DEP CASH    SELF                 +200.00    Bal 1,320.00\n"
                        "Customer-initiated transactions visible after 2025.\n"),
                }
            ],
        }

    if seed_id == "scholarship":
        return {
            "case_partial": {
                "seed_id": "scholarship",
                "language": "en-hi",
                "beneficiary": {
                    "name": "PRIYA RAMESH WAGH",
                    "aadhaar": "2233 4455 6677",
                    "dob": "04/09/2007",
                    "state": "Maharashtra", "district": "Kolhapur",
                    "scheme": "Post-Matric Scholarship (NSP / PFMS)",
                    "scheme_key": "NSP_POSTMATRIC",
                    "is_pension": False,
                    "language": "en",
                    "bank": "Central Bank of India, Kolhapur Main Branch",
                    "account_number": "3012345678",
                    "ifsc": "CBIN0281234",
                    "beneficiary_id": "MH2025260099123",
                },
                "expected": {"v1_root": "NAME_MISMATCH", "v1_secondary": "ACCOUNT_VALIDATION_FAILED"},
            },
            "documents": [
                {
                    "kind": "AADHAAR", "filename": "aadhaar_priya.jpg",
                    "text_content": _aadhaar_text(
                        "PRIYA RAMESH WAGH", "04/09/2007", "2233 4455 6677",
                        "Plot 7, Shahupuri, Kolhapur, Maharashtra - 416001"),
                },
                {
                    "kind": "PASSBOOK", "filename": "passbook_priya.jpg",
                    "text_content": (
                        "CENTRAL BANK OF INDIA — KOLHAPUR MAIN BRANCH\n"
                        "A/c Name: PRIYA R. WAGH\n"
                        "A/c No: 3012345678\n"
                        "IFSC: CBIN0281234\n"
                        "Savings Account — Student account\n"
                        "05/01/2026  DBT-CREDIT  SCHOLARSHIP FY24-25  +8,000.00  Bal 9,240.00\n"
                        "12/01/2026  APBS-RETURN SCHOLARSHIP RETURN -8,000.00  Bal 9,240.00\n"),
                },
                {
                    "kind": "SMS", "filename": "sms_nsp.png",
                    "text_content": (
                        "[SMS 12-01-2026] NSP: Post-Matric Scholarship FY 2025-26 instalment of Rs. 12,000 "
                        "could not be credited. PFMS status: ACCOUNT VALIDATION FAILED. "
                        "URN: 20260112998877665. Contact your institute nodal officer.\n"),
                },
                {
                    "kind": "SCHEME_LETTER", "filename": "nsp_status.jpg",
                    "text_content": (
                        "NATIONAL SCHOLARSHIP PORTAL — Application Status\n"
                        "Application ID: MH2025260099123\n"
                        "Name: PRIYA RAMESH WAGH\n"
                        "Scheme: Post-Matric Scholarship (SC Category)\n"
                        "Sanction amount: Rs. 12,000\n"
                        "Payment status: Sent to PFMS — rejected at bank validation\n"),
                },
            ],
            "portal_profile": {
                "scheme_portal": {
                    "check": "application + payment status",
                    "status": "OK", "code": "PAYMENT_RELEASED",
                    "message": "Scholarship sanctioned and sent to PFMS on 10-01-2026.",
                    "detail": "Application MH2025260099123 · Rs. 12,000",
                    "raw": {"application_id": "MH2025260099123"},
                },
                "pfms": {
                    "check": "account validation",
                    "status": "FAIL", "code": "ACCOUNT_VALIDATION_FAILED",
                    "message": "Account validation failed. Name in application (PRIYA RAMESH WAGH) does not match bank record (PRIYA R. WAGH). IFSC CBIN0281234 flagged as pre-merger code.",
                    "detail": "PFMS cannot route the payment until bank details validate.",
                    "raw": {"failure": ["NAME_MISMATCH", "IFSC_UNMAPPED"]},
                },
                "apbs": {
                    "check": "APBS credit routing",
                    "status": "WARN", "code": "NOT_ATTEMPTED",
                    "message": "Payment blocked at PFMS validation — APBS stage not reached.",
                    "detail": "", "raw": {},
                },
                "npci_mapper": {
                    "check": "Aadhaar-bank mapping (BASE)",
                    "status": "OK", "code": "ENABLED_FOR_DBT",
                    "message": "Aadhaar 2233xxxx6677 mapped to Central Bank of India a/c ••••5678 — Enabled for DBT.",
                    "detail": "Mapper is healthy — the failure is upstream at PFMS validation.",
                    "raw": {"mapper_status": "ENABLED"},
                },
                "bank": {
                    "check": "account status (CBS)",
                    "status": "WARN", "code": "NO_CREDIT_ACCOUNT_ACTIVE",
                    "message": "Account active. No DBT credit received in the window. Bank record name: PRIYA R. WAGH.",
                    "detail": "Branch: Kolhapur Main. Name correction possible with Aadhaar proof.",
                    "raw": {"account_status": "ACTIVE"},
                },
            },
            "replan_documents": [],
        }

    if seed_id == "pmkisan":
        return {
            "case_partial": {
                "seed_id": "pmkisan",
                "language": "hi-en",
                "beneficiary": {
                    "name": "RAMESH DEVIDAS YADAV",
                    "aadhaar": "7788 9900 1122",
                    "dob": "11/07/1968",
                    "state": "Maharashtra", "district": "Latur",
                    "scheme": "PM-KISAN Samman Nidhi",
                    "scheme_key": "PMKISAN",
                    "is_pension": False,
                    "language": "hi",
                    "bank": "Bank of India, Latur APMC Branch",
                    "account_number": "4567890123",
                    "ifsc": "BKID0004567",
                    "beneficiary_id": "MH-2019-8899221",
                },
                "expected": {"v1_root": "AADHAAR_NOT_SEEDED", "v1_secondary": "EKYC_PENDING"},
            },
            "documents": [
                {
                    "kind": "AADHAAR", "filename": "aadhaar_ramesh.jpg",
                    "text_content": _aadhaar_text(
                        "RAMESH DEVIDAS YADAV", "11/07/1968", "7788 9900 1122",
                        "At Post Ausa, Tal. Ausa, Latur, Maharashtra - 413520"),
                },
                {
                    "kind": "PASSBOOK", "filename": "passbook_ramesh.jpg",
                    "text_content": (
                        "BANK OF INDIA — LATUR APMC BRANCH\n"
                        "A/c Name: RAMESH D. YADAV\n"
                        "A/c No: 4567890123\n"
                        "IFSC: BKID0004567\n"
                        "Savings Account — Kisan account\n"
                        "02/08/2025  DBT-CREDIT  PMKISAN 15TH       +2,000.00   Bal 6,310.00\n"
                        "02/12/2025  APBS-RETURN PMKISAN 16TH       -2,000.00   Bal 6,310.00\n"),
                },
                {
                    "kind": "SMS", "filename": "sms_pmkisan.png",
                    "text_content": (
                        "[SMS 04-04-2026] PMKISAN: Your 17th instalment of Rs. 2,000 is on hold. "
                        "Aadhaar not seeded for DBT (UID never enabled). Complete eKYC and seeding at bank. "
                        "Ref: PMK/2026/8899221. URN: 20260404556677889\n"),
                },
                {
                    "kind": "SCHEME_LETTER", "filename": "pmkisan_status.jpg",
                    "text_content": (
                        "PM-KISAN SAMMAN NIDHI — Beneficiary Status\n"
                        "Beneficiary ID: MH-2019-8899221\n"
                        "Name: RAMESH DEVIDAS YADAV\n"
                        "eKYC Status: Pending\n"
                        "17th Instalment: Payment Failure — Aadhaar not seeded\n"),
                },
            ],
            "portal_profile": {
                "scheme_portal": {
                    "check": "beneficiary status",
                    "status": "WARN", "code": "EKYC_PENDING",
                    "message": "eKYC pending for beneficiary MH-2019-8899221. 17th instalment on hold.",
                    "detail": "OTP/face eKYC required at pmkisan.gov.in or CSC.",
                    "raw": {"ekyc": "PENDING"},
                },
                "pfms": {
                    "check": "beneficiary bank validation",
                    "status": "FAIL", "code": "AADHAAR_NOT_SEEDED",
                    "message": "Beneficiary bank account not validated — Aadhaar not seeded (UID never enabled for DBT).",
                    "detail": "", "raw": {},
                },
                "apbs": {
                    "check": "APBS credit routing",
                    "status": "FAIL", "code": "PAYMENT_RETURNED_APBS",
                    "message": "Credit attempt returned — no Aadhaar mapper entry for DBT.",
                    "urn": "20260404556677889", "raw": {"return_code": 25},
                },
                "npci_mapper": {
                    "check": "Aadhaar-bank mapping (BASE)",
                    "status": "FAIL", "code": "MAPPER_NOT_SEEDED",
                    "message": "UID never enabled for DBT — no active Aadhaar-bank mapping in the NPCI mapper.",
                    "detail": "Seeding request (Annexure I) required at the preferred bank branch.",
                    "raw": {"mapper_status": "NOT_SEEDED"},
                },
                "bank": {
                    "check": "Aadhaar seeding status (CBS)",
                    "status": "WARN", "code": "AADHAAR_KYC_ONLY",
                    "message": "Aadhaar is linked for KYC only — NOT seeded to the NPCI mapper for DBT.",
                    "detail": "Customer must submit the Aadhaar seeding request (Annexure I) at the branch.",
                    "raw": {"aadhaar_kyc": True, "npci_seeding": False},
                },
            },
            "replan_documents": [],
        }

    raise KeyError(f"unknown seed {seed_id}")


def derive_profile_from_case(case: dict) -> dict:
    """Generic realistic profile for user-created (non-seed) cases: derived from
    what the documents actually show — not hardcoded."""
    ex = case.get("extraction") or {}
    flags = set(case.get("evidence_flags") or [])
    mismatches = (ex.get("identity_graph") or {}).get("mismatches") or []
    pf = {
        "scheme_portal": {
            "check": "beneficiary payment status",
            "status": "WARN", "code": "SCHEME_NOT_RELEASED",
            "message": "Scheme portal shows recent instalment as pending/not released for this beneficiary.",
            "detail": "Demo adapter — simulated response derived from uploaded documents.",
            "raw": {},
        },
        "pfms": {"check": "payment batch processing", "status": "WARN", "code": "PAYMENT_PROCESSED",
                 "message": "PFMS has no processed payment in the stated window.", "raw": {}},
        "apbs": {"check": "APBS credit routing", "status": "FAIL", "code": "PAYMENT_RETURNED_APBS",
                 "message": "APBS returned the credit. Return code 25 — beneficiary account invalid/inactive.",
                 "raw": {"return_code": 25}},
        "npci_mapper": {"check": "Aadhaar-bank mapping (BASE)", "status": "FAIL", "code": "MAPPER_INACTIVE",
                        "message": "Mapper status not 'Enabled for DBT' for the uploaded documents.", "raw": {}},
        "bank": {"check": "account credit status (CBS)", "status": "FAIL", "code": "ACCOUNT_DORMANT",
                 "message": "Bank reports the mapped account as inactive/dormant — DBT credits rejected.",
                 "raw": {"account_status": "DORMANT"}},
    }
    if mismatches:
        pf["pfms"].update({
            "status": "FAIL", "code": "ACCOUNT_VALIDATION_FAILED",
            "message": "Account validation failed — beneficiary name differs between documents (B06 risk).",
        })
    if "ACCOUNT_RECENT_ACTIVITY" in flags:
        pf["bank"].update({
            "code": "ACCOUNT_DORMANT",
            "message": "Re-check after passbook evidence: account shows recent activity — status is DORMANT, not closed.",
        })
    for d in case.get("documents") or []:
        f = d.get("fields") or {}
        if f.get("urn"):
            pf["apbs"]["urn"] = f["urn"]
            break
    return pf
