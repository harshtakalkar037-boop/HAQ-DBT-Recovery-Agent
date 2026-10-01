/* ============ HAQ command center v2 — agentic case-resolution frontend ============ */
const App = (() => {
  const state = {
    view: 'landing', caseId: null, case: null, events: [], lastSeq: 0,
    agents: {}, meta: null, catalog: [], tab: 'overview', planView: null,
    intakeDocs: [], poll: null, pollFast: true, currentDoc: null,
    lang: 'en', zoom: 0, pendingSeed: null, recognition: null,
  };

  const AGENT_ORDER = ['SAMVAAD', 'KHOJ', 'NIDAAN', 'YOJNA', 'KARM', 'NYAYA', 'SATYAPAN', 'ANUSARAN'];
  const PIPE_KEYS = ['SCHEME_STATUS', 'PFMS_STATUS', 'APBS_STATUS', 'NPCI_MAPPER', 'BANK_CBS'];
  const PIPE_NAMES = { SCHEME_STATUS: 'SCHEME', PFMS_STATUS: 'PFMS / TREASURY', APBS_STATUS: 'APBS', NPCI_MAPPER: 'NPCI MAPPER', BANK_CBS: 'BANK' };

  // ---------------------------------------------------------------- i18n
  const T = {
    en: {
      privacy: 'Privacy', sources: 'Sources', home: 'Home',
      hero_sub: 'Find out why your government payment is stuck — and let HAQ work out what to do next.',
      start_case: 'Start My Case →', how_it_works: 'See How HAQ Works',
      not_chatbot: 'HAQ is not a chatbot. It is an AI case-resolution agent that does the work.',
      demo_cases: 'Demo cases', demo_cases_sub: 'synthetic beneficiaries · realistic failure chains · runs the full agent workflow',
      how_title: 'How HAQ works', start_case_title: 'Start your case',
      start_case_sub: 'Tell us what happened — Hindi, English or Hinglish. Add whatever documents you have.',
      speak: 'Speak instead', describe: 'Describe the problem', beneficiary_name: 'Beneficiary name',
      scheme: 'Scheme', account: 'Account number', ifsc: 'IFSC', add_docs: 'Add documents',
      upload: 'Upload file', paste_doc: 'Paste document text',
      consent_title: 'Your documents contain sensitive information.',
      consent_body: 'HAQ will use them only to analyze this case and prepare the requested actions.',
      consent_check: 'I have read the privacy notice and consent to processing for this case.',
      agree_continue: '✓ I Agree & Continue', read_privacy: 'Read Privacy Policy',
      new_evidence: 'Deliver new evidence', upload_evidence: 'Upload new evidence', delete_case: 'Delete My Case',
    },
    hi: {
      privacy: 'गोपनीयता', sources: 'स्रोत', home: 'होम',
      hero_sub: 'जानिए आपका सरकारी भुगतान क्यों अटका है — और HAQ को आगे क्या करना है, यह तय करने दीजिए।',
      start_case: 'मेरा केस शुरू करें →', how_it_works: 'देखें HAQ कैसे काम करता है',
      not_chatbot: 'HAQ चैटबॉट नहीं है। यह एक AI केस-समाधान एजेंट है जो वास्तव में काम करता है।',
      demo_cases: 'डेमो केस', demo_cases_sub: 'काल्पनिक लाभार्थी · वास्तविक जैसी विफलताएँ · पूरा एजेंट वर्कफ़्लो',
      how_title: 'HAQ कैसे काम करता है', start_case_title: 'अपना केस शुरू करें',
      start_case_sub: 'बताइए क्या हुआ — हिंदी, अंग्रेज़ी या हिंग्लिश में। जो दस्तावेज़ हैं जोड़िए।',
      speak: 'बोलकर बताएँ', describe: 'समस्या बताइए', beneficiary_name: 'लाभार्थी का नाम',
      scheme: 'योजना', account: 'खाता संख्या', ifsc: 'IFSC', add_docs: 'दस्तावेज़ जोड़ें',
      upload: 'फ़ाइल अपलोड करें', paste_doc: 'दस्तावेज़ का टेक्स्ट जोड़ें',
      consent_title: 'आपके दस्तावेज़ों में संवेदनशील जानकारी है।',
      consent_body: 'HAQ इनका उपयोग केवल इस केस का विश्लेषण और कार्रवाई तैयार करने के लिए करेगा।',
      consent_check: 'मैंने गोपनीयता सूचना पढ़ी है और सहमत हूँ।',
      agree_continue: '✓ मैं सहमत हूँ और आगे बढ़ें', read_privacy: 'गोपनीयता नीति पढ़ें',
      new_evidence: 'नया प्रमाण जोड़ें', upload_evidence: 'नया प्रमाण अपलोड करें', delete_case: 'मेरा केस हटाएँ',
    },
  };
  const t = (k) => (T[state.lang] && T[state.lang][k]) || T.en[k] || k;

  function applyLang() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      el.textContent = t(el.getAttribute('data-i18n'));
    });
    const lb = document.getElementById('lang-btn');
    if (lb) lb.textContent = state.lang === 'en' ? 'EN / हिं' : 'हिं / EN';
  }
  function toggleLang() { state.lang = state.lang === 'en' ? 'hi' : 'en'; applyLang(); renderTab(); }

  function zoomText(d) {
    state.zoom = Math.max(-1, Math.min(2, state.zoom + d));
    document.documentElement.classList.remove('text-lg', 'text-xl');
    if (state.zoom === 1) document.documentElement.classList.add('text-lg');
    if (state.zoom >= 2) document.documentElement.classList.add('text-xl');
  }
  function toggleContrast() { document.body.classList.toggle('contrast'); }

  // ---------------------------------------------------------------- api
  async function api(path, opts) {
    const r = await fetch(path, opts);
    if (!r.ok) {
      let msg = r.statusText;
      try { msg = (await r.json()).detail || msg; } catch (e) {}
      throw new Error(msg);
    }
    return r.json();
  }
  const post = (path, body) => api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });

  // ---------------------------------------------------------------- boot
  async function init() {
    try {
      state.meta = await api('/api/meta');
      state.catalog = state.meta.catalog;
    } catch (e) { state.meta = { agents: [], catalog: [], disclaimer: '' }; }
    renderCatalog();
    renderAgentCards();
    animateTerminal();
    animateChain();
    applyLang();
    document.getElementById('in-file').addEventListener('change', onIntakeFile);
    document.getElementById('ev-file').addEventListener('change', onEvidenceFile);
    document.querySelectorAll('.tab').forEach(tEl => tEl.addEventListener('click', () => {
      state.tab = tEl.dataset.tab;
      document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === tEl));
      renderTab();
    }));
  }

  function animateTerminal() {
    const el = document.getElementById('hero-terminal');
    if (!el) return;
    const lines = [...el.children];
    lines.forEach(l => l.style.opacity = 0);
    let i = 0;
    const tmr = setInterval(() => {
      if (i >= lines.length) { clearInterval(tmr); return; }
      lines[i].style.transition = 'opacity .4s'; lines[i].style.opacity = 1; i++;
    }, 420);
  }

  function animateChain() {
    const nodes = document.querySelectorAll('.chain-node');
    const where = document.getElementById('chain-where');
    let i = 0;
    setInterval(() => {
      nodes.forEach((n, idx) => {
        n.classList.remove('lit');
        if (idx < i) n.classList.add('okn');
        if (idx === i) n.classList.add('lit');
      });
      if (i === 4 && where) where.textContent = '✕ THIS is where it breaks — HAQ finds out why';
      i = (i + 1) % (nodes.length + 2);
      if (i === 0) { nodes.forEach(n => n.classList.remove('okn')); if (where) where.textContent = 'watch where it breaks'; }
    }, 900);
  }

  // ---------------------------------------------------------------- landing
  function renderCatalog() {
    const el = document.getElementById('catalog-cards');
    if (!el) return;
    el.innerHTML = state.catalog.map((c, i) => `
      <div class="card ${i === 0 ? 'golden' : ''}">
        <div class="k">${i === 0 ? '★ GOLDEN DEMO' : 'DEMO CASE ' + (i + 1)}</div>
        <h3>${c.title}</h3>
        <p>${c.blurb}</p>
        <ul><li><b>${c.person}</b></li><li>${c.scheme}</li><li class="muted">“${c.narrative.slice(0, 80)}…”</li></ul>
        <div class="card-cta">
          <button class="btn ${i === 0 ? 'btn-primary' : 'btn-outline'}" onclick="App.selectSeed('${c.id}')">▶ Run this case</button>
        </div>
      </div>`).join('');
  }

  function renderAgentCards() {
    const el = document.getElementById('agent-cards');
    if (!el) return;
    el.innerHTML = ((state.meta && state.meta.agents) || []).map(a => `
      <div class="card"><div class="k">${a.key}</div><h3>${a.role}</h3><p>${a.desc}</p></div>`).join('');
  }

  // ---------------------------------------------------------------- navigation
  function show(view) {
    state.view = view;
    for (const v of ['landing', 'intake', 'case'])
      document.getElementById('view-' + v).classList.toggle('hidden', v !== view);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  function goHome() { stopPolling(); clearBanner(); show('landing'); }

  function startMyCase() { newCustomCase(); }
  function howItWorks() {
    if (state.view !== 'landing') { show('landing'); }
    setTimeout(() => document.getElementById('how-it-works').scrollIntoView({ behavior: 'smooth' }), 120);
  }

  function selectSeed(id) {
    const c = state.catalog.find(x => x.id === id);
    state.intakeDocs = []; state.pendingSeed = id;
    show('intake');
    document.getElementById('in-narrative').value = c ? c.narrative : '';
    document.getElementById('in-name').value = c ? c.person.split(',')[0] : '';
    renderIntakeDocs();
    clearBanner();
  }

  function newCustomCase() {
    state.pendingSeed = null; state.intakeDocs = [];
    show('intake');
    ['in-narrative', 'in-name', 'in-acct', 'in-ifsc', 'in-pin'].forEach(id => {
      const el = document.getElementById(id); if (el) el.value = '';
    });
    const cb = document.getElementById('in-consent'); if (cb) cb.checked = false;
    renderIntakeDocs(); clearBanner();
  }

  // ---------------------------------------------------------------- intake
  function renderIntakeDocs() {
    const el = document.getElementById('doc-list');
    if (!el) return;
    el.innerHTML = state.intakeDocs.map((d, i) => `
      <div class="doc-item">
        <span class="kind">${d.kind}</span><span>${d.filename}</span>
        <span class="muted small">${(d.text_content || '').length ? d.text_content.length + ' chars ready for extraction' : 'image — fields to be confirmed'}</span>
        <span class="spacer"></span>
        <button class="btn btn-ghost" onclick="App.removeIntakeDoc(${i})" aria-label="Remove">✕</button>
      </div>`).join('');
  }
  function removeIntakeDoc(i) { state.intakeDocs.splice(i, 1); renderIntakeDocs(); }

  function addTextDoc() {
    const text = prompt('Paste the document text (passbook page, SMS, scheme letter):');
    if (!text) return;
    const kind = /sms/i.test(text.slice(0, 20)) ? 'SMS' : /passbook|a\/c|ifsc/i.test(text) ? 'PASSBOOK'
      : /aadhaar|uidai/i.test(text) ? 'AADHAAR' : 'SCHEME_LETTER';
    state.intakeDocs.push({ kind, filename: `pasted_${state.intakeDocs.length + 1}.txt`, text_content: text });
    renderIntakeDocs();
  }

  function onIntakeFile(e) {
    const f = e.target.files[0]; if (!f) return;
    if (/\.(txt|csv|log)$/i.test(f.name)) {
      const r = new FileReader();
      r.onload = () => { state.intakeDocs.push({ kind: guessKind(f.name, r.result), filename: f.name, text_content: r.result }); renderIntakeDocs(); };
      r.readAsText(f);
    } else {
      state.intakeDocs.push({ kind: guessKind(f.name, ''), filename: f.name, text_content: '' });
      renderIntakeDocs();
      banner('info', 'Image stored. We\'ll extract what we can — and ask you to confirm anything we can\'t read confidently.');
    }
    e.target.value = '';
  }
  function guessKind(name, text) {
    const s = (name + ' ' + (text || '').slice(0, 200)).toLowerCase();
    if (/sms/.test(s)) return 'SMS';
    if (/passbook|statement/.test(s)) return 'PASSBOOK';
    if (/aadhaar|aadhar|uidai/.test(s)) return 'AADHAAR';
    return 'SCHEME_LETTER';
  }

  // ---------------------------------------------------------------- voice
  function toggleMic() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const status = document.getElementById('mic-status');
    if (!SR) { if (status) status.textContent = 'Voice input is not supported in this browser — please type instead.'; return; }
    if (state.recognition) { state.recognition.stop(); state.recognition = null; if (status) status.textContent = ''; return; }
    const rec = new SR();
    rec.lang = state.lang === 'hi' ? 'hi-IN' : 'en-IN';
    rec.interimResults = true;
    rec.onresult = (ev) => {
      const txt = [...ev.results].map(r => r[0].transcript).join('');
      document.getElementById('in-narrative').value = txt;
    };
    rec.onerror = () => { if (status) status.textContent = 'Mic error — please type instead.'; };
    rec.onend = () => { state.recognition = null; if (status) status.textContent = 'Voice captured ✓'; };
    rec.start();
    state.recognition = rec;
    if (status) status.textContent = 'Listening… speak now (Hindi/English)';
  }

  function speak(text) {
    if (!window.speechSynthesis) return;
    const u = new SpeechSynthesisUtterance(text.replace(/[#*→✓✕●🔧🧠📋⏰]/g, ''));
    u.lang = state.lang === 'hi' ? 'hi-IN' : 'en-IN';
    window.speechSynthesis.speak(u);
  }

  // ---------------------------------------------------------------- consent + submit
  async function submitCase() {
    const consent = document.getElementById('in-consent').checked;
    if (!consent) {
      banner('replan', 'Please accept the privacy notice before HAQ can process your documents.');
      document.getElementById('consent-box').scrollIntoView({ behavior: 'smooth' });
      return;
    }
    const narrative = document.getElementById('in-narrative').value.trim() || 'Mera sarkari paisa nahi aaya.';
    const docs = state.intakeDocs.map(d => ({ kind: d.kind, filename: d.filename, text_content: d.text_content }));
    try {
      const res = await post('/api/cases', { seed_id: state.pendingSeed, narrative, documents: docs, consent: true });
      clearBanner();
      openCase(res.id);
      banner('info', 'Case created. HAQ is starting the agent workflow…');
      await post('/api/cases/' + res.id + '/run', {});
    } catch (err) { banner('replan', 'Could not start the case: ' + err.message); }
  }

  // ---------------------------------------------------------------- polling
  function openCase(id) {
    state.caseId = id; state.lastSeq = 0; state.events = []; state.agents = {};
    AGENT_ORDER.forEach(a => state.agents[a] = { status: 'waiting', detail: 'Waiting…' });
    state.agents.NYAYA.detail = 'Policy engine — ordering, deadlines, guardrails';
    state.planView = null; state.tab = 'overview';
    document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x.dataset.tab === 'overview'));
    show('case');
    renderCaseShell();
    startPolling();
  }
  function startPolling() {
    stopPolling(); state.pollFast = true;
    state.poll = setInterval(pollOnce, 650); pollOnce();
  }
  function stopPolling() { if (state.poll) clearInterval(state.poll); state.poll = null; }

  async function pollOnce() {
    if (!state.caseId) return;
    try {
      const [c, ev] = await Promise.all([
        api('/api/cases/' + state.caseId),
        api(`/api/cases/${state.caseId}/events?after=${state.lastSeq}`),
      ]);
      state.case = c;
      if (ev.events.length) {
        ev.events.forEach(e => { state.events.push(e); state.lastSeq = e.seq; applyEvent(e); });
      } else if (['WATCHDOG', 'CLOSED'].includes(c.status) && state.pollFast) {
        state.pollFast = false; stopPolling();
        state.poll = setInterval(pollOnce, 6000);
      }
      renderCase();
    } catch (e) { /* transient */ }
  }

  function applyEvent(e) {
    const a = state.agents[e.agent];
    if (a) {
      a.status = { START: 'start', WORK: 'working', TOOL_CALL: 'working', TOOL_RESULT: 'working',
                   DONE: 'done', ALERT: 'alert' }[e.status] || 'working';
      a.detail = e.detail;
    }
    if (e.agent === 'YOJNA' && e.status === 'DONE')
      state.agents.NYAYA = { status: 'done', detail: 'Ordering, blocking & deadlines validated against policy rules' };
    if (e.extra && e.extra.banner) banner(e.status === 'ALERT' ? 'replan' : 'info', e.extra.banner);
  }

  // ---------------------------------------------------------------- banners
  function banner(kind, text) {
    const el = document.getElementById('banner-area');
    el.innerHTML = `<div class="banner ${kind}">${kind === 'replan' ? '⟳' : kind === 'ok' ? '✓' : 'ℹ'} ${text}</div>`;
  }
  function clearBanner() { document.getElementById('banner-area').innerHTML = ''; }

  // ---------------------------------------------------------------- case render
  function renderCaseShell() {
    document.getElementById('agent-board').innerHTML = AGENT_ORDER.map(a => `
      <div class="agent-cell" id="ag-${a}" role="status" aria-label="${a} agent status">
        <div class="st"></div><div class="nm">${a}</div>
        <div class="rl">${agentRole(a)}</div><div class="dt" id="agd-${a}">Waiting…</div>
      </div>`).join('');
  }
  function agentRole(k) { return ((state.meta.agents || []).find(a => a.key === k) || {}).role || ''; }

  function renderCase() {
    const c = state.case; if (!c) return;
    document.getElementById('ch-id').textContent = 'CASE ' + c.id;
    const b = c.beneficiary || {};
    document.getElementById('ch-person').innerHTML =
      `<b>${esc(b.name || '—')}</b> · ${esc(b.scheme || '')} · ${esc(b.district || '')}, ${esc(b.state || '')}`;
    const d = c.diagnosis;
    document.getElementById('ch-causes').innerHTML = d ? `
      <div class="cause-chip root"><div class="lbl">PRIMARY CAUSE</div><div class="val">${d.root_cause_code}</div></div>
      <div class="cause-chip sec"><div class="lbl">SECONDARY</div><div class="val">${d.secondary_cause_code || '—'}</div></div>
      <div class="cause-chip"><div class="lbl">CONFIDENCE</div><div class="val">${Math.round(d.confidence * 100)}%</div></div>
      <div class="cause-chip"><div class="lbl">PLAN</div><div class="val">v${(c.plans || []).length} · ${(c.plans || []).slice(-1)[0] ? c.plans.slice(-1)[0].trigger : '—'}</div></div>`
      : `<div class="cause-chip"><div class="lbl">STATUS</div><div class="val">Investigation in progress…</div></div>`;

    const sp = document.getElementById('ch-status');
    sp.textContent = c.status === 'WATCHDOG' ? '🔴 PAYMENT BLOCKED · WATCHDOG ACTIVE' : c.status;
    sp.className = 'status-pill ' + (c.status === 'WATCHDOG' ? 'watch' : c.status === 'CLOSED' ? 'closed'
      : c.status === 'REPLANNING' ? 'replan' : 'working');
    const w = document.getElementById('ch-watch');
    if (c.watchdog && c.watchdog.active) {
      w.textContent = '🛡 HAQ WATCHDOG ACTIVE · NEXT: ' + (c.watchdog.next_action || '').slice(0, 55);
      w.className = 'watch-pill';
    } else if (c.status === 'CLOSED') {
      w.textContent = '✓ CLOSED — PAYMENT VERIFIED'; w.className = 'watch-pill';
    } else { w.textContent = 'WATCHDOG — arming…'; w.className = 'watch-pill off'; }

    AGENT_ORDER.forEach(a => {
      const cell = document.getElementById('ag-' + a); const st = state.agents[a] || {};
      cell.className = 'agent-cell ' + (st.status === 'waiting' ? '' : st.status);
      document.getElementById('agd-' + a).textContent = st.detail || 'Waiting…';
    });
    document.getElementById('board-progress').textContent =
      `${AGENT_ORDER.filter(a => state.agents[a].status === 'done').length}/8 agents completed`;

    const pipe = document.getElementById('pipeline');
    const evs = (c.evidence || []).filter(e => PIPE_KEYS.includes(e.tool));
    pipe.innerHTML = evs.length ? evs.map((e, i) => `
      ${i ? '<div class="pipe-arrow">→</div>' : ''}
      <div class="pipe-node ${e.status === 'OK' ? 'ok' : e.status === 'FAIL' ? 'fail' : 'warn'}">
        <div class="pn-head"><div class="pn-name">${PIPE_NAMES[e.tool] || e.tool}</div>
          <div class="pipe-mark">${e.status === 'OK' ? '✓' : e.status === 'FAIL' ? '✕' : '●'}</div></div>
        <div class="pn-code">${e.code}</div>
        <div class="pn-msg">${esc(e.message.slice(0, 105))}</div>
        <div style="margin-top:8px">${modeChip(e.mode)}</div>
      </div>`).join('') : '<div class="muted small">KHOJ has not reported yet…</div>';

    const be = document.getElementById('btn-new-evidence');
    if ((c.replan_documents || []).length === 0) {
      be.disabled = true;
      be.textContent = c.seed_id === 'pension' ? '📥 New evidence already delivered' : '📥 No queued demo evidence';
    }
    renderTab();
  }

  // ---------------------------------------------------------------- tabs
  function renderTab() {
    const c = state.case; if (!c) return;
    const el = document.getElementById('tab-body');
    const map = {
      overview: tabOverview, evidence: tabEvidence, activity: tabActivity, diagnosis: tabDiagnosis,
      plan: tabPlan, docs: tabDocs, verify: tabVerify, timeline: tabTimeline,
    };
    el.innerHTML = (map[state.tab] || tabOverview)(c);
    if (state.tab === 'docs') { /* inline onclick handlers used */ }
  }

  function modeChip(mode) {
    if (mode === 'LIVE' || mode === 'PUBLIC')
      return `<span class="mode-chip live">${mode === 'LIVE' ? '🟢 LIVE SOURCE' : '🟢 PUBLIC SOURCE'}</span>`;
    if (mode === 'UNAVAILABLE') return '<span class="mode-chip unav">🟠 SOURCE UNAVAILABLE</span>';
    return '<span class="mode-chip demo">🟡 DEMO / SIMULATED</span>';
  }

  function tabOverview(c) {
    const b = c.beneficiary || {};
    const n = c.narrative_analysis || {};
    return `
      ${c.needs_input ? `<div class="needs-input"><b>⚠ ${esc(c.needs_input.message)}</b>
        <div class="muted small" style="margin-top:6px">${(c.needs_input.conflicts || c.needs_input.docs || []).map(esc).join(' · ')}</div></div>` : ''}
      <div class="grid-2">
        <div>
          <div class="block-title">WHAT HAPPENED</div>
          <div class="ev-item"><div class="ev-msg" style="color:var(--ink);font-size:14px">“${esc(c.narrative)}”</div>
            <div style="margin-top:9px">
              <span class="pill blue">lang: ${n.language_detected || '—'}</span>
              <span class="pill blue">intent: ${n.intent || '—'}</span>
              ${n.duration_months ? `<span class="pill warn">stuck ~${n.duration_months} months</span>` : ''}
              <span class="pill gray">affected: ${n.affected_person || 'self'}</span>
              <button class="btn btn-ghost tts-btn" onclick="App.speakCase()">🔊 Read aloud</button>
            </div>
          </div>
          <div class="block-title">CASE FILE (sensitive fields masked)</div>
          ${Object.entries(b).filter(([k]) => !['is_pension', 'language', 'scheme_key'].includes(k))
            .map(([k, v]) => `<div class="kv"><span class="k">${k.replace(/_/g, ' ')}</span><span class="v">${esc(String(v))}</span></div>`).join('')}
        </div>
        <div>
          <div class="block-title">WHAT HAQ THINKS</div>
          ${c.diagnosis ? `
            <div class="ev-item">
              <div class="ev-top"><div class="ev-src">${c.diagnosis.root_cause_label}</div>
                <span class="pill warn">${Math.round(c.diagnosis.confidence * 100)}% confidence</span></div>
              <div class="ev-msg">Secondary: ${c.diagnosis.secondary_cause_label || '—'}</div>
              <button class="btn btn-ghost tts-btn" onclick="App.speakCase()">🔊 Read aloud</button>
            </div>
            <div class="block-title">WHY? — EVIDENCE</div>
            ${(c.diagnosis.evidence || []).slice(0, 3).map(e => `
              <div class="ev-item"><div class="ev-top"><div class="ev-src">${esc(e.source)}</div>
                <span class="pill ${e.status === 'OK' ? 'ok' : e.status === 'FAIL' ? 'fail' : 'warn'}">${e.code}</span></div>
                <div class="ev-msg">${esc(e.message)}</div></div>`).join('')}
            <div class="block-title">RULE USED</div>
            ${(c.diagnosis.rules_applied || []).map(r => `<div class="rule-chip">${esc(r)}</div>`).join('')}
          ` : '<div class="muted">Diagnosis in progress…</div>'}
          <div class="block-title">EXTRACTED FIELDS — CONFIRMED BEFORE USE</div>
          ${Object.entries((c.extraction && c.extraction.fields) || {}).map(([k, v]) => `
            <div class="kv"><span class="k">${k.replace(/_/g, ' ')}</span>
            <span class="v">${esc(String(v.value))} <span class="pill ${v.confirmed ? 'ok' : 'warn'}">${v.confirmed ? '✓' : 'confirm?'}</span></span></div>`).join('')}
          <div class="block-title">IDENTITY GRAPH</div>
          ${(((c.extraction || {}).identity_graph || {}).mismatches || []).length
            ? ((c.extraction || {}).identity_graph.mismatches).map(m => `
            <div class="mis-card"><b>${m.field.toUpperCase()} MISMATCH DETECTED</b> <span class="pill fail">${m.type}</span>
              <div class="vs"><div class="side">${esc(m.left.value)}</div><div>≠</div><div class="side">${esc(m.right.value)}</div></div>
              <div class="rule">${esc(m.rule)}<br/>${esc(m.detail)}</div></div>`).join('')
            : '<div class="muted small">No inconsistencies detected.</div>'}
        </div>
      </div>`;
  }

  function tabEvidence(c) {
    if (!c.evidence || !c.evidence.length) return '<div class="muted">KHOJ is still investigating…</div>';
    return `
      <div class="block-title">EVIDENCE CHAIN — SOURCE · DATA · TIMESTAMP · CONFIDENCE</div>
      ${c.evidence.map(e => `
        <div class="ev-item">
          <div class="ev-top">
            <div class="ev-src">${esc(e.source_label)}</div>
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
              ${modeChip(e.mode)}
              <span class="pill ${e.status === 'OK' ? 'ok' : e.status === 'FAIL' ? 'fail' : 'warn'}">${e.status}</span>
              <span class="ev-when">Checked: ${e.retrieved_at || '—'}</span>
            </div>
          </div>
          <div class="ev-msg"><b>${e.code}</b> — ${esc(e.message)}</div>
          ${e.detail ? `<div class="ev-detail">${esc(e.detail)}</div>` : ''}
          <div class="ev-detail">confidence: ${Math.round((e.confidence || 0.7) * 100)}%
            ${e.source_url ? ` · <a href="${e.source_url}" target="_blank" rel="noopener" style="color:#8fc2ff">${esc(e.source_url.slice(0, 60))}…</a>` : ''}
            ${e.urn ? ` · URN: <b>${e.urn}</b> <span class="rule-chip">RULE-QUOTE-URN</span>` : ''}</div>
        </div>`).join('')}
      ${(c.evidence_flags || []).length ? `
        <div class="block-title">FLAGS FROM YOUR DOCUMENTS</div>
        ${(c.evidence_flag_details || []).map(f => `<div class="override-note">⚑ ${esc(f)}</div>`).join('')}` : ''}`;
  }

  function tabActivity(c) {
    return `
      <div class="block-title">AGENT ACTIVITY / TOOL TRACE — ${state.events.length} EVENTS (real backend events)</div>
      <div class="feed" id="feed-box" role="log" aria-live="polite">
        ${state.events.map(e => `
          <div class="feed-row ${e.status === 'ALERT' ? 'alert' : e.status.toLowerCase()}">
            <span class="t">${new Date(e.ts).toLocaleTimeString('en-IN', { hour12: false })}</span>
            <span class="a">${e.agent}</span>
            <span>${e.action === 'TOOL_CALL' ? '🔧' : e.action === 'TOOL_RESULT' ? '✓' : e.action === 'ALERT' ? '⚠' : ''} ${esc(e.detail)}</span>
          </div>`).join('')}
      </div>`;
  }

  function tabDiagnosis(c) {
    const d = c.diagnosis;
    if (!d) return '<div class="muted">NIDAAN has not concluded yet…</div>';
    return `
      <div class="diag-hero">
        <div class="conf-ring" style="--pct:${Math.round(d.confidence * 100)}">
          <div class="inner"><div class="pct">${Math.round(d.confidence * 100)}%</div><div class="lb">CONFIDENCE</div></div>
        </div>
        <div>
          <div class="block-title" style="margin-top:0">WHAT HAQ THINKS</div>
          <h2 style="font-size:20px">${esc(d.root_cause_label)}</h2>
          <div class="muted small" style="margin-top:6px">Taxonomy ref: ${d.root_cause_ref} · <span class="hi">${esc(d.root_cause_label_hi || '')}</span></div>
          ${d.secondary_cause_code ? `<div style="margin-top:10px"><span class="pill warn">SECONDARY: ${d.secondary_cause_code} — ${esc(d.secondary_cause_label || '')}</span></div>` : ''}
          ${(d.additional_causes || []).map(a => `<span class="pill gray" style="margin:6px 4px 0 0">also observed: ${a}</span>`).join('')}
          ${(d.watch_items || []).map(w => `<div class="override-note">⏱ WATCH — <b>${esc(w.label)}</b><br/>${esc(w.reason)}</div>`).join('')}
          <div style="margin-top:12px">${esc(d.explanation)}</div>
          <button class="btn btn-ghost tts-btn" onclick="App.speakCase()">🔊 Read this aloud</button>
        </div>
      </div>
      ${d.override_note ? `<div class="override-note"><b>⟳ RE-PLANNING TRIGGER — OVERRIDE RULE R-DORMANT-01</b><br/>${esc(d.override_note)}</div>` : ''}
      <div class="block-title">WHY? — EVIDENCE</div>
      ${(d.evidence || []).map(e => `
        <div class="ev-item">
          <div class="ev-top"><div class="ev-src">${esc(e.source)}</div>
            <span class="pill ${e.status === 'OK' ? 'ok' : e.status === 'FAIL' ? 'fail' : 'warn'}">${e.code}</span></div>
          <div class="ev-msg">${esc(e.message)}</div>
        </div>`).join('')}
      <div class="block-title">MATCHED TAXONOMY SIGNALS</div>
      ${(d.matched_signals || []).map(s => `<div class="rule-chip">[${s.weight}] ${s.id} — ${esc(s.text)}</div>`).join('')}
      <div class="block-title">RULES / REASONING USED</div>
      ${(d.rules_applied || []).map(r => `<div class="rule-chip">${esc(r)}</div>`).join('')}
      <div class="rule-chip">confidence basis: ${esc(d.confidence_basis)}</div>`;
  }

  function tabPlan(c) {
    const plans = c.plans || [];
    if (!plans.length) return '<div class="muted">YOJNA is building the plan…</div>';
    const cur = plans.find(p => p.version === state.planView) || plans[plans.length - 1];
    state.planView = cur.version;
    const diff = cur.rationale.changed_steps || {};
    return `
      <div class="plan-ver">
        ${plans.map(p => `
          <button class="pv-btn ${p.version === cur.version ? 'active' : ''} ${p.superseded ? 'superseded' : ''}"
            onclick="App.setPlanView(${p.version})">
            PLAN v${p.version} · ${p.trigger} ${p.superseded ? '— SUPERSEDED / ❌ Invalidated' : p.version === cur.version ? '✓ Current' : ''}
          </button>`).join('')}
      </div>
      ${cur.trigger === 'NEW_EVIDENCE' ? `
        <div class="override-note"><b>⟳ NEW EVIDENCE CHANGED THE PLAN</b><br/>
          ${esc(cur.rationale.note || '')}
          ${diff.removed && diff.removed.length ? `<br/>❌ Invalidated actions → ${diff.removed.join(', ')}` : ''}
          ${diff.added && diff.added.length ? `<br/>✓ New actions → ${diff.added.join(', ')}` : ''}
        </div>` : ''}
      <div class="block-title">DEPENDENCY-ORDERED ACTIONS</div>
      ${cur.steps.map((s, i) => `
        <div class="step ${s.status.toLowerCase()}">
          <div class="idx">${i + 1}</div>
          <div class="body">
            <div class="act">${esc(s.action)}</div>
            <div class="meta">
              <span class="pill blue">owner: ${s.owner.replace(/_/g, ' ')}</span>
              <span class="pill gray">deadline: T+${s.deadline_days}d</span>
              <span class="pill ${s.status === 'DONE' ? 'ok' : s.status === 'BLOCKED' ? 'warn' : s.status === 'READY' ? 'ok' : 'gray'}">${s.status}</span>
              ${s.depends_on.length ? `<span class="pill gray">after → ${s.depends_on.join(', ')}</span>` : ''}
              ${(s.required_docs || []).length ? `<span class="pill gray">docs: ${s.required_docs.join(' · ')}</span>` : ''}
            </div>
            <div class="notes"><span class="hi">${esc(s.action_hi || '')}</span> — ${esc(s.notes)}</div>
            <div class="notes"><b>✓ Completion condition:</b> ${esc(s.completion_condition || '—')}</div>
            ${s.blocked_reason ? `<div class="block-reason"><b>NYAYA BLOCK:</b> ${esc(s.blocked_reason)}</div>` : ''}
          </div>
        </div>`).join('')}
      <div class="block-title">WHY THIS ORDER (YOJNA + NYAYA)</div>
      <div class="rule-chip">${esc(cur.rationale.ordering)}</div>
      ${(cur.rationale.policy_rules_fired || []).map(r => `<div class="rule-chip">FIRING: ${r.id} — ${esc(r.label)}</div>`).join('')}
      ${(cur.rationale.guardrails || []).map(g => `<div class="ev-item"><div class="ev-msg">🛡 GUARDRAIL — ${esc(g)}</div></div>`).join('')}
      <div class="block-title">ESCALATION LADDER</div>
      ${(cur.escalation_ladder || []).map(l => `<div class="kv"><span class="k">L${l.level} · ${l.t}</span><span class="v">${esc(l.step)}</span></div>`).join('')}`;
  }

  function tabDocs(c) {
    const docs = c.documents_generated || [];
    if (!docs.length) return '<div class="muted">KARM is drafting the action pack…</div>';
    return `
      <div class="block-title">ACTION PACK — PREVIEW → VERIFIED → DOWNLOAD</div>
      <div class="doc-grid">
        ${docs.map(d => `
          <div class="doc-card ${d.status === 'VERIFIED' ? 'verified' : d.status === 'INVALIDATED' ? 'invalid' : ''}"
            onclick="App.openDoc('${d.id}')" tabindex="0" onkeydown="if(event.key==='Enter')App.openDoc('${d.id}')">
            <span class="pill ${d.status === 'VERIFIED' ? 'ok' : d.status === 'INVALIDATED' ? 'fail' : 'warn'}">${d.status}</span>
            <span class="pill gray">plan v${d.plan_version}</span>
            <div class="dt">${esc(d.title)}</div>
            <div class="da">→ ${esc(d.authority)}</div>
            ${d.invalidated_reason ? `<div class="inv-reason">✕ ${esc(d.invalidated_reason)}</div>` : ''}
          </div>`).join('')}
      </div>`;
  }

  function tabVerify(c) {
    const v = c.verification;
    if (!v) return '<div class="muted">SATYAPAN is verifying…</div>';
    return `
      <div class="block-title">VERIFICATION SUMMARY</div>
      <div style="margin-bottom:14px">
        <span class="pill ok">${v.verified} VERIFIED</span>
        <span class="pill warn">${v.draft} DRAFT</span>
        <span class="pill fail">${v.invalidated} INVALIDATED</span>
        <span class="pill ${v.fields_confirmed ? 'ok' : 'warn'}">identity fields ${v.fields_confirmed ? 'confirmed' : 'need confirmation'}</span>
      </div>
      ${v.results.map(r => `
        <div class="ev-item">
          <div class="ev-top"><div class="ev-src">${r.doc} · ${esc(r.title)}</div>
            <span class="pill ${r.status === 'VERIFIED' ? 'ok' : r.status === 'INVALIDATED' ? 'fail' : 'warn'}">${r.status}</span></div>
          ${r.checks.map(ch => `
            <div class="check-row"><span class="${ch.pass ? 'ok' : 'no'}">${ch.pass ? '✓' : '✕'}</span>
              <b style="min-width:250px">${esc(ch.name)}</b><span class="muted small">${esc(ch.detail)}</span></div>`).join('')}
        </div>`).join('')}`;
  }

  function tabTimeline(c) {
    const f = c.followup; const w = c.watchdog || {};
    return `
      <div class="watchdog-card">
        <div class="big">${c.status === 'CLOSED' ? '✓ CASE CLOSED — PAYMENT VERIFIED' : '🛡 HAQ WATCHDOG ACTIVE'}</div>
        <div class="muted" style="margin-top:6px">The case remains open until the payment is verified — nothing is closed on promises.
        Next action: <b>${esc(w.next_action || '—')}</b></div>
      </div>
      ${f ? `<div class="block-title">CASE TIMELINE — REAL DEADLINES STORED ON THIS CASE</div>
      <div class="tl">
        ${f.timeline.map(tl => `
          <div class="tl-item ${tl.status === 'DONE' ? 'done' : ''} ${tl.kind === 'ESCALATION' ? 'esc' : ''}">
            <div class="dot"></div>
            <div class="when">${tl.when} · ${tl.kind}</div>
            <div class="tt">${esc(tl.title)}</div>
            <div class="dd">${esc(tl.detail)}</div>
          </div>`).join('')}
      </div>` : '<div class="muted">ANUSARAN is building the timeline…</div>'}
      <div class="block-title">SIMULATED WHATSAPP UPDATE (Hindi) — notifications simulated in demo mode</div>
      <div class="ev-item hi"><div class="ev-msg" style="color:var(--ink)">
        नमस्ते! HAQ अपडेट — ${esc((c.beneficiary.name || '').split(' ')[0])} जी का मामला चालू है।
        अगला कदम: ${esc(w.next_action || '—')}। पैसा आने तक HAQ WATCHDOG चालू रहेगा।</div></div>`;
  }

  // ---------------------------------------------------------------- actions
  async function deliverSeedEvidence() {
    try {
      const r = await post(`/api/cases/${state.caseId}/evidence/seed-replan`);
      banner('replan', '📥 NEW EVIDENCE DELIVERED — ' + r.doc + '. Watch SATYAPAN detect the change and YOJNA re-plan.');
      state.pollFast = true; startPolling();
    } catch (e) { banner('info', e.message); }
  }

  async function onEvidenceFile(e) {
    const f = e.target.files[0]; if (!f) return;
    const fd = new FormData();
    fd.append('file', f); fd.append('filename', f.name); fd.append('kind', guessKind(f.name, ''));
    try {
      const r = await api(`/api/cases/${state.caseId}/evidence`, { method: 'POST', body: fd });
      banner('replan', '📥 NEW EVIDENCE UPLOADED — ' + r.doc + '. Re-planning loop started.');
      state.pollFast = true; startPolling();
    } catch (err) { banner('info', err.message); }
    e.target.value = '';
  }

  async function simulate(action) {
    try {
      await post(`/api/cases/${state.caseId}/simulate`, { action });
      if (action === 'payment_received') banner('ok', 'PAYMENT VERIFIED — case closed. HAQ closes cases only on verified credits.');
      pollOnce();
    } catch (e) { banner('info', e.message); }
  }

  async function deleteCase() {
    if (!state.caseId) return;
    if (!confirm('Delete this case permanently? All documents, evidence and plans will be removed. This cannot be undone.')) return;
    try {
      await api('/api/cases/' + state.caseId, { method: 'DELETE' });
      banner('ok', 'Case and all associated data permanently deleted.');
      goHome();
    } catch (e) { banner('info', e.message); }
  }

  function setPlanView(v) { state.planView = v; renderTab(); }

  // ---------------------------------------------------------------- docs
  function openDoc(id) {
    const d = (state.case.documents_generated || []).find(x => x.id === id);
    if (!d) return;
    state.currentDoc = d;
    document.getElementById('modal-title').textContent = d.title + ' — ' + d.status;
    document.getElementById('doc-frame').srcdoc = d.html;
    document.getElementById('doc-modal').classList.remove('hidden');
  }
  function closeDoc() {
    document.getElementById('doc-modal').classList.add('hidden');
    document.getElementById('doc-frame').srcdoc = '';
  }
  function printDoc() {
    if (!state.currentDoc) return;
    const w = window.open('', '_blank');
    w.document.write(state.currentDoc.html); w.document.close();
    setTimeout(() => w.print(), 350);
  }
  function downloadDoc() {
    if (!state.currentDoc) return;
    const blob = new Blob([state.currentDoc.html], { type: 'text/html' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = state.currentDoc.title.replace(/[^a-z0-9]+/gi, '_') + '.html';
    a.click();
  }

  // ---------------------------------------------------------------- info modals
  function openInfo(title, html) {
    document.getElementById('info-title').textContent = title;
    document.getElementById('info-body').innerHTML = html;
    document.getElementById('info-modal').classList.remove('hidden');
  }
  function closeInfo() { document.getElementById('info-modal').classList.add('hidden'); }

  function openPrivacy() {
    openInfo('Privacy & Security', `
      <h3>What data is collected</h3>
      <p>Only what your case needs: your description, the documents you choose to upload (Aadhaar, passbook, SMS, scheme letter), and contact-free case metadata. No cookies for advertising. No data sold.</p>
      <h3>Why it is collected</h3>
      <p>To extract case facts, build the identity graph, diagnose the payment failure, and prepare the resolution documents you asked for.</p>
      <h3>How sensitive data is protected</h3>
      <ul>
        <li><b>Data minimisation:</b> we collect only what the case requires.</li>
        <li><b>Masking:</b> Aadhaar shows as XXXX XXXX 1234 and accounts as XXXX4521 in the interface.</li>
        <li><b>No secrets in logs:</b> no OTPs, passwords or API keys are ever stored in the frontend or logs. Server keys use environment variables.</li>
      </ul>
      <h3>Consent</h3>
      <p>Before document processing: “Your documents contain sensitive information. HAQ will use them only to analyze this case and prepare the requested actions.” You must actively agree.</p>
      <h3>Third-party AI processing disclosure</h3>
      <p>When a live language model key is configured (Groq/Gemini), narrative text and document text may be sent to that provider for summarisation. In demo mode the deterministic language layer is used and <b>no external AI call is made</b>.</p>
      <h3>API / source disclosure</h3>
      <p>See the <a href="#" onclick="App.openSources();return false">Sources</a> page: every tool is labelled LIVE, PUBLIC, DEMO or UNAVAILABLE.</p>
      <h3>Retention & deletion</h3>
      <p>Cases persist until you delete them. <b>Delete My Case</b> permanently removes the case and its events. In production, cases auto-expire after resolution + 90 days.</p>
      <h3>Contact</h3>
      <p>privacy@haq.example · responses within 7 working days.</p>
    `);
  }

  function openSources() {
    api('/api/sources').then(s => {
      openInfo('Sources & Data Transparency', `
        <p>${esc(s.statement)}</p>
        <h3>Tools used by KHOJ</h3>
        ${s.tools.map(tl => `
          <div class="src-item">
            <b>${esc(tl.title)}</b> ${tl.mode === 'LIVE' || tl.mode === 'PUBLIC'
              ? '<span class="mode-chip live">' + tl.mode_label + '</span>'
              : tl.mode === 'UNAVAILABLE' ? '<span class="mode-chip unav">' + tl.mode_label + '</span>'
              : '<span class="mode-chip demo">' + tl.mode_label + '</span>'}
            <div class="muted small" style="margin-top:5px">${esc(tl.description)}</div>
            ${tl.source_url ? `<div class="small" style="margin-top:4px"><a href="${tl.source_url}" target="_blank" rel="noopener">${esc(tl.source_url)}</a></div>` : ''}
          </div>`).join('')}
        <h3>Public guidance corpus (with real links)</h3>
        ${s.public_sources.map(k => `
          <div class="src-item"><b>${esc(k.title)}</b>
            <div class="muted small">${esc(k.source)}</div>
            <div class="small"><a href="${k.url}" target="_blank" rel="noopener">${esc(k.url)}</a></div></div>`).join('')}
      `);
    }).catch(e => openInfo('Sources', '<p>Source registry unavailable: ' + esc(e.message) + '</p>'));
  }

  function openAbout() {
    openInfo('About HAQ', `
      <p><b>HAQ (हक़)</b> — <span class="hi">हक़ आपका है. पैसा भी आपका है.</span></p>
      <p>HAQ is an AI <b>case-resolution agent</b> for India's Direct Benefit Transfer (DBT) payments. When a pension, scholarship, PM-KISAN instalment or wage payment doesn't arrive, HAQ investigates the Scheme → PFMS/Treasury → APBS → NPCI Mapper → Bank chain, diagnoses the failure, builds a dependency-ordered resolution plan, generates office-ready documents, verifies its own work, re-plans when new evidence arrives, and follows up until the payment is verified.</p>
      <p>It is <b>not</b> a chatbot: every case has state, tools, documents, deadlines and verification — the same work that currently takes families weeks of office rounds.</p>
      <p class="muted">Built for BHARAT AGENTIC 2026 · demo mode uses synthetic beneficiary data.</p>
    `);
  }

  function openTerms() {
    openInfo('Terms of Use', `
      <p>HAQ provides information, evidence analysis and assistance in preparing resolution actions. It does <b>not</b> guarantee government payment, bank approval, benefit eligibility or grievance resolution.</p>
      <p>Users should verify important actions with the relevant government department, bank or qualified professional before submission.</p>
      <p>Documents generated are drafts prepared from templates and the case information provided by the user. The user is responsible for their accuracy and submission.</p>
      <p>Demo mode may use synthetic beneficiary data and simulated institutional responses. Live sources are explicitly labelled.</p>
    `);
  }

  function openContact() {
    openInfo('Contact', `
      <p>Questions, accessibility requests or grievances about this product:</p>
      <ul>
        <li>Email: <b>help@haq.example</b></li>
        <li>Accessibility: <b>access@haq.example</b></li>
        <li>Privacy: <b>privacy@haq.example</b></li>
      </ul>
      <p class="muted">This is a hackathon demonstration product; contacts are placeholders.</p>
    `);
  }

  function openAccessibility() {
    openInfo('Accessibility', `
      <p>HAQ is designed for citizens with varying digital literacy:</p>
      <ul>
        <li>Large touch targets and readable typography; <b>A+ / A−</b> text scaling and <b>high-contrast mode</b> in the top bar.</li>
        <li>Hindi / English interface toggle (EN / हिं).</li>
        <li>Voice input (where the browser supports it) and text-to-speech for key explanations.</li>
        <li>Keyboard navigable controls and screen-reader-friendly structure (landmarks, live regions, ARIA labels).</li>
        <li>Simple language: every screen answers <i>what happened · why · what to do · what HAQ is doing · what happens next</i>.</li>
      </ul>
    `);
  }

  // ---------------------------------------------------------------- helpers
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

  function speakCase() {
    const c = state.case; if (!c) return;
    const d = c.diagnosis;
    const parts = [`Case ${c.id}.`, `Status: ${c.status}.`];
    if (d) {
      parts.push(`Primary cause: ${d.root_cause_label}.`);
      if (d.secondary_cause_label) parts.push(`Secondary: ${d.secondary_cause_label}.`);
      parts.push(d.explanation || '');
    }
    if (c.watchdog && c.watchdog.next_action) parts.push('Next action: ' + c.watchdog.next_action);
    speak(parts.join(' '));
  }

  return {
    init, goHome, startMyCase, howItWorks, selectSeed, newCustomCase, addTextDoc, removeIntakeDoc,
    submitCase, deliverSeedEvidence, onEvidenceFile: null, simulate, setPlanView,
    openDoc, closeDoc, printDoc, downloadDoc, deleteCase, toggleMic, speakCase,
    openPrivacy, openSources, openAbout, openTerms, openContact, openAccessibility, closeInfo,
    toggleLang, zoomText, toggleContrast,
  };
})();

document.addEventListener('DOMContentLoaded', App.init);
