"""KARM document factory — fixed templates with populated slots.
The LLM may never freely invent official forms: these templates are the only
source of document text. Fields come from confirmed case data only."""
from __future__ import annotations
from datetime import datetime

STYLE = """<style>
  body{font-family:'Segoe UI',Arial,sans-serif;background:#eef1f5;color:#1a2332;margin:0;padding:24px;}
  .sheet{background:#fff;max-width:760px;margin:0 auto 22px auto;padding:34px 40px;border-radius:10px;
         box-shadow:0 3px 14px rgba(10,25,50,.12);position:relative;}
  .brand{display:flex;justify-content:space-between;align-items:center;border-bottom:3px solid #0b3d91;padding-bottom:12px;margin-bottom:6px;}
  .brand .logo{font-size:19px;font-weight:800;color:#0b3d91;letter-spacing:.4px;}
  .brand .logo span{color:#e8850c;}
  .brand .tag{font-size:11px;color:#5a6b84;text-align:right;line-height:1.5;}
  .doctype{text-align:center;margin:18px 0 6px 0;}
  .doctype h1{font-size:17px;letter-spacing:.6px;margin:0;text-transform:uppercase;color:#12274d;}
  .doctype .sub{font-size:12px;color:#5a6b84;margin-top:4px;}
  .meta{display:flex;flex-wrap:wrap;gap:8px 26px;font-size:11.5px;color:#45566f;background:#f4f7fb;
        border:1px solid #dfe7f1;border-radius:6px;padding:9px 14px;margin:12px 0 18px 0;}
  .to{font-size:13.5px;margin:6px 0;}
  .to b{color:#12274d;}
  .body{font-size:13.5px;line-height:1.75;}
  .body p{margin:10px 0;}
  table.fields{width:100%;border-collapse:collapse;margin:14px 0;font-size:12.5px;}
  table.fields th,table.fields td{border:1px solid #d5deea;padding:7px 11px;text-align:left;}
  table.fields th{background:#eef3fa;color:#12274d;width:38%;}
  .quote{background:#fff8ec;border-left:4px solid #e8850c;padding:10px 14px;margin:12px 0;font-size:12.5px;}
  .sign{margin-top:34px;display:flex;justify-content:space-between;}
  .sign div{font-size:12.5px;}
  .sigline{border-top:1px solid #7c8aa0;width:190px;margin-top:42px;padding-top:6px;text-align:center;}
  .footer{max-width:760px;margin:0 auto 26px auto;font-size:10.5px;color:#7a889c;line-height:1.6;padding:0 8px;}
  .hi{font-family:'Noto Sans Devanagari','Segoe UI',Arial,sans-serif;}
  .scriptbox{background:#0e2038;color:#e7eefb;border-radius:8px;padding:16px 20px;font-size:13px;line-height:1.9;}
  .scriptbox .t{color:#8fc7ff;font-weight:700;letter-spacing:.6px;font-size:11px;}
  .ok{color:#127a3e;font-weight:700;}
  ul.tight{margin:8px 0 8px 18px;padding:0;}
  ul.tight li{margin:4px 0;}
</style>"""


def _fmt_date(dt: datetime | None = None) -> str:
    return (dt or datetime.now()).strftime("%d-%m-%Y")


def _mask_aadhaar(a: str) -> str:
    digits = re_sub = "".join(ch for ch in (a or "") if ch.isdigit())
    if len(digits) >= 12:
        return "XXXX XXXX " + digits[-4:]
    return "XXXX XXXX XXXX"


import re as _re

def field_bag(case: dict, step: dict | None, plan_version: int | None) -> dict:
    b = case.get("beneficiary") or {}
    ex_fields = (case.get("extraction") or {}).get("fields") or {}
    def fv(key, default=""):
        f = ex_fields.get(key) or {}
        return f.get("value") or b.get(key) or default
    urn = fv("urn") or (case.get("evidence") or [{}])[-1].get("urn", "")
    for e in case.get("evidence") or []:
        if e.get("urn"):
            urn = e["urn"]
            break
    return {
        "name": fv("name", b.get("name", "[NAME]")),
        "aadhaar_masked": _mask_aadhaar(fv("aadhaar", b.get("aadhaar", ""))),
        "account_number": fv("account_number", b.get("account_number", "[ACCOUNT]")),
        "ifsc": fv("ifsc", b.get("ifsc", "[IFSC]")),
        "bank": b.get("bank", "[BANK]"),
        "scheme": b.get("scheme", "[SCHEME]"),
        "beneficiary_id": fv("beneficiary_id", b.get("beneficiary_id", "[BENEFICIARY ID]")),
        "urn": urn or "[URN]",
        "state": b.get("state", "[STATE]"),
        "district": b.get("district", "[DISTRICT]"),
        "dob": fv("dob", b.get("dob", "[DOB]")),
        "case_id": case.get("id", "HAQ-XXX"),
        "today": _fmt_date(),
        "plan_version": plan_version or 1,
        "step_action": (step or {}).get("action", ""),
        "step_notes": (step or {}).get("notes", ""),
    }


def _wrap(body: str) -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'>{STYLE}</head><body>{body}</body></html>"


def _sheet_header(f: dict, title: str, sub: str) -> str:
    return f"""
    <div class='sheet'>
      <div class='brand'>
        <div class='logo'>HAQ <span>हक़</span> · DBT PAYMENT RECOVERY</div>
        <div class='tag'>Prepared by HAQ agent KARM · demo mode<br/>Synthetic beneficiary data · verify before submission</div>
      </div>
      <div class='doctype'><h1>{title}</h1><div class='sub'>{sub}</div></div>
      <div class='meta'>
        <div>CASE: <b>{f['case_id']}</b></div>
        <div>DATE: <b>{f['today']}</b></div>
        <div>PLAN: <b>v{f['plan_version']}</b></div>
        <div>SCHEME: <b>{f['scheme']}</b></div>
        <div>URN: <b>{f['urn']}</b></div>
      </div>"""


def _sign_block(f: dict) -> str:
    return f"""
      <div class='sign'>
        <div>Date: {f['today']}<br/>Place: {f['district']}, {f['state']}</div>
        <div><div class='sigline'>{f['name']}<br/>(Beneficiary / authorised family member)</div></div>
      </div>
    </div>
    <div class='footer'>This document was generated by the HAQ agent workflow (KARM) from the verified case file.
    Fields marked in the case file as confirmed were used as-is. Demo mode uses synthetic personal data — no real
    Aadhaar or financial information is present. Always attach self-attested copies of Aadhaar and passbook.</div>"""


def doc_aadhaar_seeding(f: dict, case: dict, step: dict) -> str:
    return _wrap(_sheet_header(f, "Application for Aadhaar Seeding / DBT Linkage (Annexure I)", "Request to seed Aadhaar in the NPCI mapper for Direct Benefit Transfer") + f"""
      <div class='to'>To,<br/><b>The Branch Manager</b><br/>{f['bank']}</div>
      <div class='body'>
        <p>Respected Sir/Madam,</p>
        <p>I, <b>{f['name']}</b>, holder of the savings account detailed below, request you to seed my Aadhaar number
        with this account in the <b>NPCI Aadhaar Mapper</b> as the primary account for receiving
        <b>Direct Benefit Transfer (DBT)</b> payments under the scheme <b>{f['scheme']}</b>.</p>
        <table class='fields'>
          <tr><th>Beneficiary name (as per Aadhaar)</th><td>{f['name']}</td></tr>
          <tr><th>Aadhaar number (masked)</th><td>{f['aadhaar_masked']}</td></tr>
          <tr><th>Bank account number</th><td>{f['account_number']}</td></tr>
          <tr><th>IFSC</th><td>{f['ifsc']}</td></tr>
          <tr><th>Bank &amp; branch</th><td>{f['bank']}</td></tr>
          <tr><th>Scheme / benefit</th><td>{f['scheme']}</td></tr>
          <tr><th>Scheme beneficiary ID</th><td>{f['beneficiary_id']}</td></tr>
        </table>
        <p>I understand that the mapper reflects the updated seeding within 24–48 hours after NPCI validates the
        request with UIDAI. I request an <b>acknowledgement receipt with the seeding request number</b> for my records.</p>
        <p>Also kindly ensure the name in my bank records matches my Aadhaar exactly before submitting the seeding
        request, so that it is not rejected (B06 name mismatch).</p>
      </div>""" + _sign_block(f))


def doc_kyc_name_correction(f: dict, case: dict, step: dict) -> str:
    ex = (case.get("extraction") or {})
    ig = ex.get("identity_graph") or {}
    rows = ""
    for nv in ig.get("name_values") or []:
        rows += f"<tr><th>{nv.get('kind')} ({nv.get('doc')})</th><td>{nv.get('value')}</td></tr>"
    return _wrap(_sheet_header(f, "Request for KYC Name Correction in Bank Records", "Mandatory before Aadhaar re-seeding — B06 rule") + f"""
      <div class='to'>To,<br/><b>The Branch Manager</b><br/>{f['bank']}</div>
      <div class='body'>
        <p>Respected Sir/Madam,</p>
        <p>My name as per Aadhaar is <b>{f['name']}</b>, but the name in my bank records does not match it
        character-by-character. Because of this, my DBT payments are being rejected (NPCI/PFMS name mismatch — B06).</p>
        <table class='fields'>
          <tr><th>Correct name (as per Aadhaar)</th><td><b>{f['name']}</b></td></tr>
          {rows}
          <tr><th>Aadhaar number (masked)</th><td>{f['aadhaar_masked']}</td></tr>
          <tr><th>Account number</th><td>{f['account_number']}</td></tr>
        </table>
        <p>I request you to update my KYC/name in the CBS exactly as per my Aadhaar and confirm when done.
        The name must match exactly — including spacing and full middle name — otherwise the Aadhaar seeding
        request will be rejected again.</p>
        <p>Documents attached: self-attested Aadhaar copy, passbook first page.</p>
      </div>""" + _sign_block(f))


def doc_non_payment_certificate(f: dict, case: dict, step: dict) -> str:
    return _wrap(_sheet_header(f, "Request for Non-Payment Certificate", "Required by Tahsildar / District Social Welfare Officer for pension arrears") + f"""
      <div class='to'>To,<br/><b>The Branch Manager</b><br/>{f['bank']}</div>
      <div class='body'>
        <p>Respected Sir/Madam,</p>
        <p>I request a written <b>Non-Payment Certificate</b> stating that DBT pension instalments under
        <b>{f['scheme']}</b> (Beneficiary ID: {f['beneficiary_id']}; URN: {f['urn']}) were <b>not credited</b>
        to my account <b>{f['account_number']}</b> during the failed payment period.</p>
        <p>This certificate is mandatory for claiming pension arrears from the District Social Welfare Office /
        Tahsildar. Kindly issue it on the bank letterhead with the stamp and authorised signature.</p>
      </div>""" + _sign_block(f))


def doc_reprocessing(f: dict, case: dict, step: dict) -> str:
    return _wrap(_sheet_header(f, "Request for Re-Processing of Returned DBT Instalments", "To the scheme nodal officer — quote URN references") + f"""
      <div class='to'>To,<br/><b>The Nodal Officer / District Social Welfare Officer</b><br/>
      Scheme: {f['scheme']}<br/>{f['district']}, {f['state']}</div>
      <div class='body'>
        <p>Respected Sir/Madam,</p>
        <p>I am the beneficiary <b>{f['name']}</b> (Beneficiary ID: <b>{f['beneficiary_id']}</b>) under
        <b>{f['scheme']}</b>. My instalments were released by the department but were <b>returned by the bank/payment
        rail</b> and have not reached me. The underlying bank/mapper issue has now been corrected.</p>
        <table class='fields'>
          <tr><th>Beneficiary</th><td>{f['name']} · {f['aadhaar_masked']}</td></tr>
          <tr><th>APBS URN (quote in all correspondence)</th><td><b>{f['urn']}</b></td></tr>
          <tr><th>Account receiving DBT</th><td>{f['account_number']} · IFSC {f['ifsc']}</td></tr>
          <tr><th>Bank</th><td>{f['bank']}</td></tr>
        </table>
        <div class='quote'>Returned funds are lying with the government/treasury. They must be
        <b>re-processed / re-released</b> to my corrected account. Kindly treat this as urgent — my family
        depends on this money for daily needs.</div>
        <p>Attachments: bank acknowledgement of the fix, Aadhaar copy, passbook, payment failure SMS/URN proof.</p>
      </div>""" + _sign_block(f))


def doc_cpgrams(f: dict, case: dict, step: dict) -> str:
    return _wrap(_sheet_header(f, "CPGRAMS Grievance Draft (pgportal.gov.in)", "Escalation level 4 — prepared for filing if unresolved by T+15") + f"""
      <div class='body'>
        <table class='fields'>
          <tr><th>Grievance category</th><td>Pension / DBT benefit not received — payment returned</td></tr>
          <tr><th>Complainant</th><td>{f['name']} · {f['district']}, {f['state']}</td></tr>
          <tr><th>Beneficiary ID</th><td>{f['beneficiary_id']}</td></tr>
          <tr><th>Scheme</th><td>{f['scheme']}</td></tr>
          <tr><th>Department</th><td>Social Welfare / Rural Development (scheme department)</td></tr>
        </table>
        <p><b>Grievance description (copy-paste ready):</b></p>
        <div class='quote'>I am a beneficiary under {f['scheme']} (Beneficiary ID {f['beneficiary_id']}).
        My instalments (APBS URN {f['urn']}) were released by the department but returned by the payment rail
        and have not been credited to my account {f['account_number']} at {f['bank']}. The bank/mapper defect has
        been corrected (documents attached). Despite following up, the returned instalments have not been
        re-processed. I request: (1) immediate re-processing of all returned instalments to my corrected account;
        (2) written intimation of the credit date; (3) action against the delay as per rules.</div>
        <p><b>Relief sought:</b> Re-process returned instalments + compensation for delay as admissible.</p>
        <p class='ok'>HAQ note: this draft is auto-filed by the watchdog if the case is unresolved at T+15.</p>
      </div>""" + _sign_block(f))


def doc_rti(f: dict, case: dict, step: dict) -> str:
    return _wrap(_sheet_header(f, "RTI Application Draft (Under the RTI Act, 2005)", "Escalation level 5 — to the Public Information Officer of the scheme department") + f"""
      <div class='to'>To,<br/><b>The Public Information Officer</b><br/>
      {f['scheme']} Department<br/>{f['district']}, {f['state']}</div>
      <div class='body'>
        <p>Subject: Information regarding DBT payment made to beneficiary {f['beneficiary_id']} under {f['scheme']}.</p>
        <p>Respected Sir/Madam,</p>
        <p>Under Section 6(1) of the RTI Act, 2005, kindly provide the following information:</p>
        <ul class='tight'>
          <li>The account number and bank branch to which the instalment(s) associated with APBS URN
              <b>{f['urn']}</b> were actually credited, with the date of credit.</li>
          <li>The current Aadhaar seeding status recorded for Aadhaar ending {f['aadhaar_masked']} in the DBT pipeline.</li>
          <li>The exact reason / return code for the failure/return of each instalment, and the officer responsible
              for re-processing returned instalments.</li>
          <li>The file notings and timeline of action taken on my representation regarding non-receipt of these instalments.</li>
          <li>Rules under which returned instalments are re-processed, and the maximum time limit prescribed.</li>
        </ul>
        <p>Application fee of ₹10 is enclosed (IPO / court fee stamp). If this query pertains to another public
        authority, kindly transfer u/s 6(3) and inform me.</p>
      </div>""" + _sign_block(f))


def doc_old_branch(f: dict, case: dict, step: dict) -> str:
    return _wrap(_sheet_header(f, "Letter to Old Mapped Branch — Status Confirmation & Return of Bounced Credits", "For the branch where the mapper points") + f"""
      <div class='to'>To,<br/><b>The Branch Manager</b><br/>{f['bank']}</div>
      <div class='body'>
        <p>Respected Sir/Madam,</p>
        <p>My Aadhaar is mapped in the NPCI mapper to account <b>{f['account_number']}</b> at this branch,
        and my DBT instalments (URN <b>{f['urn']}</b>) are being routed here and bounced/returned.</p>
        <p>Kindly: (1) issue a written confirmation of the exact status of this account (active / dormant / closed)
        with the date; (2) confirm whether any DBT credits were received and returned, with the return reference;
        (3) help re-route future credits by updating my Aadhaar seeding to my active account after due KYC.</p>
      </div>""" + _sign_block(f))


def doc_counter_script(f: dict, case: dict, step: dict) -> str:
    return _wrap(_sheet_header(f, "Bank Counter Script — क्या बोलें", "Carry this page with your documents") + f"""
      <div class='body'>
        <div class='scriptbox hi'>
          <div class='t'>हिंदी में — बैंक काउंटर पर बोलें</div>
          "नमस्ते। मेरा नाम <b>{f['name']}</b> है। मेरी डीबीटी ({f['scheme']}) की किस्त नहीं आ रही।
          कृपया ये तीन काम कर दीजिए: <b>(1)</b> मेरे खाते ({f['account_number']}) की स्थिति देखिए — यह डोरमेंट तो नहीं;
          अगर डोरमेंट है तो एक छोटी जमा/निकासी करके सक्रिय कर दीजिए। <b>(2)</b> मेरे बैंक रिकॉर्ड का नाम
          आधार के अनुसार ठीक कर दीजिए — {f['name']}। <b>(3)</b> फिर एनपीसीआई मैपर में आधार सीडिंग (अनुबंध-I)
          जमा कर दीजिए। कृपया सीडिंग रसीद/संदर्भ संख्या दे दीजिए। मेरा URN है: <b>{f['urn']}</b>।"
          <br/><br/>
          <div class='t'>IF THE OFFICER SAYS "HOGAYA / HO JAYEGA"</div>
          "कृपया लिखित एकनॉलेजमेंट दे दीजिए जिसमें सीडिंग रिक्वेस्ट नंबर और तारीख लिखी हो।
          मुझे 48 घंटे में मैपर स्टेटस देखना है।"
          <br/><br/>
          <div class='t'>DOCUMENTS TO CARRY</div>
          आधार की फोटोकॉपी (सेल्फ-अटेस्टेड) · पासबुक · यह पेज · सीडिंग फॉर्म · भुगतान विफलता का SMS/प्रिंट
        </div>
        <p><b>English summary for the officer:</b> Please (1) check/reactivate the dormant account status,
        (2) correct my KYC name to match Aadhaar exactly: <b>{f['name']}</b>, (3) submit the Aadhaar seeding
        (Annexure I) to the NPCI mapper for DBT, and (4) give me the seeding acknowledgement number.
        Scheme: {f['scheme']} · URN {f['urn']}.</p>
      </div>""" + _sign_block(f))


def doc_whatsapp(f: dict, case: dict, step: dict) -> str:
    name = f['name'].split()[0]
    return _wrap(_sheet_header(f, "WhatsApp / SMS Update (Hindi)", "Ready-to-send status message for the family") + f"""
      <div class='body'>
        <div class='scriptbox hi'>
          <div class='t'>संदेश</div>
          नमस्ते! HAQ अपडेट — <b>{name} जी</b> की {f['scheme']} की जांच पूरी हुई।<br/><br/>
          कारण मिला: बैंक खाता/नाम/आधार सीडिंग की समस्या (URN: {f['urn']})।<br/><br/>
          तैयार किए गए काम:<br/>
          1. बैंक नाम सुधार + खाता सक्रिय कराना<br/>
          2. आधार सीडिंग (अनुबंध-I) जमा करना<br/>
          3. मैपर जांच के बाद योजना विभाग से दोबारा भुगतान का अनुरोध<br/><br/>
          सारे फॉर्म/पत्र तैयार हैं। पैसा आने तक <b>HAQ WATCHDOG</b> चालू रहेगा।
        </div>
        <p class='ok'>Watchdog will send this update at each milestone and re-draft it on every status change.</p>
      </div>""" + _sign_block(f))


RENDERERS = {
    "AADHAAR_SEEDING_REQUEST": doc_aadhaar_seeding,
    "KYC_NAME_CORRECTION": doc_kyc_name_correction,
    "NON_PAYMENT_CERTIFICATE": doc_non_payment_certificate,
    "PAYMENT_REPROCESSING_REQUEST": doc_reprocessing,
    "CPGRAMS_GRIEVANCE": doc_cpgrams,
    "RTI_APPLICATION": doc_rti,
    "OLD_BRANCH_LETTER": doc_old_branch,
    "BANK_COUNTER_SCRIPT": doc_counter_script,
    "WHATSAPP_UPDATE": doc_whatsapp,
}

DOC_SPECS = {
    "AADHAAR_SEEDING_REQUEST": {"title": "Aadhaar Seeding Request (Annexure I)", "authority": "Branch Manager",
                                "required_fields": ["name", "aadhaar_masked", "account_number", "ifsc", "bank", "scheme"]},
    "KYC_NAME_CORRECTION": {"title": "KYC Name Correction Letter", "authority": "Branch Manager",
                            "required_fields": ["name", "account_number", "bank"]},
    "NON_PAYMENT_CERTIFICATE": {"title": "Non-Payment Certificate Request", "authority": "Branch Manager",
                               "required_fields": ["name", "account_number", "bank", "scheme"]},
    "PAYMENT_REPROCESSING_REQUEST": {"title": "Payment Re-Processing Request", "authority": "Nodal Officer",
                                     "required_fields": ["name", "beneficiary_id", "urn", "account_number", "scheme"]},
    "CPGRAMS_GRIEVANCE": {"title": "CPGRAMS Grievance Draft", "authority": "CPGRAMS",
                          "required_fields": ["name", "beneficiary_id", "urn", "scheme"]},
    "RTI_APPLICATION": {"title": "RTI Application Draft", "authority": "Public Information Officer",
                        "required_fields": ["name", "urn", "beneficiary_id", "scheme"]},
    "OLD_BRANCH_LETTER": {"title": "Old Branch Status / Refund Letter", "authority": "Branch Manager",
                          "required_fields": ["name", "account_number", "urn", "bank"]},
    "BANK_COUNTER_SCRIPT": {"title": "Bank Counter Script (Hindi)", "authority": "Beneficiary",
                            "required_fields": ["name", "account_number", "urn"]},
    "WHATSAPP_UPDATE": {"title": "WhatsApp Status Update (Hindi)", "authority": "Family",
                        "required_fields": ["name", "scheme"]},
}


def render_document(doc_type: str, case: dict, step: dict | None, plan_version: int) -> dict:
    f = field_bag(case, step, plan_version)
    spec = DOC_SPECS[doc_type]
    html = RENDERERS[doc_type](f, case, step)
    return {
        "type": doc_type,
        "title": spec["title"],
        "authority": spec["authority"],
        "required_fields": spec["required_fields"],
        "fields_used": {k: v for k, v in f.items() if k not in ("step_action", "step_notes")},
        "html": html,
        "plan_version": plan_version,
        "step_key": (step or {}).get("key"),
    }
