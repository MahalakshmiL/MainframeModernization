"""
chatbot.py - A standalone full-page chat assistant for the repo, with
no dashboard around it. Shares its grounding (architecture summary +
the real pipeline output) with dashboard.py's floating widget via
genie.py and dashboard.py's build_data_bundle, so the two never answer
from different data.
"""

import json
from pathlib import Path

from pipeline.dashboard import build_data_bundle
from pipeline.parser import PROJECT_ROOT

OUTPUT_DIR = PROJECT_ROOT / "output"


_HTML_TEMPLATE = r'''<title>Repo Genie</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap">
<style>
  :root{
    --bg:#F5F6F3; --panel:#FFFFFF; --panel-2:#EDEFEA;
    --ink:#1B2430; --ink-soft:#5B6472; --border:rgba(27,36,48,0.12);
    --accent:#0F8F8A; --accent-deep:#0A6B67; --accent-soft:rgba(15,143,138,0.10);
    --good:#1F8A5F; --good-soft:rgba(31,138,95,0.12);
    --warn:#9A6B12; --warn-soft:rgba(183,121,31,0.14);
    --bad:#B23B3B; --bad-soft:rgba(178,59,59,0.10);
    color-scheme: light;
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]){
      --bg:#14171A; --panel:#1C2024; --panel-2:#22262B;
      --ink:#E8EAED; --ink-soft:#9AA3AD; --border:rgba(232,234,237,0.14);
      --accent:#3DDAC3; --accent-deep:#179384; --accent-soft:rgba(61,218,195,0.14);
      --good:#34C185; --good-soft:rgba(52,193,133,0.14);
      --warn:#E0A93E; --warn-soft:rgba(224,169,62,0.16);
      --bad:#E2685F; --bad-soft:rgba(226,104,95,0.14);
      color-scheme: dark;
    }
  }
  :root[data-theme="dark"]{
    --bg:#14171A; --panel:#1C2024; --panel-2:#22262B;
    --ink:#E8EAED; --ink-soft:#9AA3AD; --border:rgba(232,234,237,0.14);
    --accent:#3DDAC3; --accent-deep:#179384; --accent-soft:rgba(61,218,195,0.14);
    --good:#34C185; --good-soft:rgba(52,193,133,0.14);
    --warn:#E0A93E; --warn-soft:rgba(224,169,62,0.16);
    --bad:#E2685F; --bad-soft:rgba(226,104,95,0.14);
    color-scheme: dark;
  }
  *{box-sizing:border-box;}
  html,body{height:100%;}
  body{
    background:var(--bg);color:var(--ink);
    font-family:"Inter",system-ui,-apple-system,sans-serif;
    margin:0;display:flex;flex-direction:column;
  }
  code,.mono{font-family:"JetBrains Mono",ui-monospace,monospace;}

  header{
    display:flex;align-items:center;gap:12px;
    padding:14px 20px;padding-top:calc(14px + env(safe-area-inset-top, 0px));
    border-bottom:1px solid var(--border);background:var(--panel);flex-shrink:0;
  }
  .lamp-badge{
    width:38px;height:38px;border-radius:11px;
    background:linear-gradient(135deg, var(--accent), var(--accent-deep));color:var(--bg);
    display:flex;align-items:center;justify-content:center;flex-shrink:0;
  }
  header .titles{flex:1;min-width:0;}
  header .t1{font-family:"Fraunces",Georgia,serif;font-size:17px;font-weight:600;line-height:1.2;}
  header .t2{font-size:11.5px;color:var(--ink-soft);display:flex;align-items:center;gap:6px;flex-wrap:wrap;}
  .official-badge{
    font-size:9px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
    background:var(--accent-soft);color:var(--accent);border-radius:4px;padding:1.5px 6px;
  }

  main{flex:1;overflow:hidden;display:flex;flex-direction:column;max-width:760px;margin:0 auto;width:100%;}

  #messages{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:12px;}
  .row{display:flex;gap:9px;max-width:88%;}
  .row.user{align-self:flex-end;flex-direction:row-reverse;}
  .row.assistant{align-self:flex-start;}
  .avatar{
    width:26px;height:26px;border-radius:8px;flex-shrink:0;margin-top:2px;
    display:flex;align-items:center;justify-content:center;background:var(--ink);color:var(--bg);
  }
  .row.user .avatar{background:var(--accent-soft);color:var(--accent);}
  .bubble{
    font-size:14px;line-height:1.55;padding:11px 14px;border-radius:14px;
    white-space:pre-wrap;word-break:break-word;
  }
  .row.assistant .bubble{background:var(--panel);border:1px solid var(--border);color:var(--ink);border-bottom-left-radius:4px;}
  .row.user .bubble{background:var(--ink);color:var(--bg);border-bottom-right-radius:4px;}

  #empty{margin:auto;text-align:center;color:var(--ink-soft);font-size:14px;padding:0 24px;max-width:460px;line-height:1.6;}
  #empty .lamp-badge{
    width:60px;height:60px;border-radius:18px;margin:0 auto 16px;
    background:linear-gradient(135deg, var(--accent), var(--accent-deep));color:var(--bg);
  }
  #empty h1{font-family:"Fraunces",Georgia,serif;font-size:21px;font-weight:600;color:var(--ink);margin:0 0 8px;letter-spacing:-.01em;}
  .suggest{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:18px;}
  .chip{
    font-family:inherit;font-size:12.5px;padding:7px 13px;border-radius:99px;
    border:1px solid var(--border);background:var(--panel);color:var(--ink-soft);cursor:pointer;
  }
  .chip:hover{border-color:var(--accent);color:var(--accent);}

  #status{font-size:12px;color:var(--ink-soft);padding:0 20px 8px;display:none;align-items:center;gap:7px;max-width:760px;margin:0 auto;width:100%;}
  #status.show{display:flex;}
  .dots span{display:inline-block;width:4px;height:4px;border-radius:50%;background:var(--ink-soft);margin-right:2px;animation:blink 1.2s infinite;}
  .dots span:nth-child(2){animation-delay:.2s;}
  .dots span:nth-child(3){animation-delay:.4s;}
  @keyframes blink{0%,80%,100%{opacity:.25;}40%{opacity:1;}}

  #notice{
    max-width:760px;margin:0 auto;width:100%;padding:0 20px 10px;font-size:12.5px;color:var(--bad);display:none;
  }
  #notice.show{display:block;}

  footer{
    border-top:1px solid var(--border);background:var(--panel);flex-shrink:0;
    padding:12px 20px;padding-bottom:calc(12px + env(safe-area-inset-bottom, 0px));
  }
  .input-row{display:flex;gap:9px;max-width:760px;margin:0 auto;}
  #input{
    flex:1;font-family:inherit;font-size:14px;padding:11px 14px;border-radius:12px;
    border:1px solid var(--border);background:var(--panel-2);color:var(--ink);resize:none;
    max-height:120px;line-height:1.4;
  }
  #input:focus{outline:none;border-color:var(--accent);}
  #input:disabled{opacity:.5;}
  #send{
    width:42px;height:42px;border-radius:12px;border:none;background:var(--ink);color:var(--bg);
    display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0;
  }
  #send:disabled{opacity:.4;cursor:default;}
  .foot-note{font-size:10.5px;color:var(--ink-soft);text-align:center;margin-top:8px;}
</style>

<header>
  <div class="lamp-badge">
    <svg viewBox="0 0 31 22" width="22" height="22" fill="none" aria-hidden="true">
      <path d="M5,19 C5,12 8,9 14,9 C19,9 21,12 21,16 C21,19 18,20 13,20 C8,20 5,20 5,19 Z" fill="currentColor"/>
      <path d="M9,9 C9,7 10.5,6 12.5,6 C14.5,6 16,7 16,9 Z" fill="currentColor"/>
      <circle cx="12.5" cy="5" r="1" fill="currentColor"/>
      <path d="M19,13 C22,11 24,8 25,5 L23,4.3 C22,7 20,10 17,12 Z" fill="currentColor"/>
      <path d="M26,1 L27.1,3.5 L29.6,4.6 L27.1,5.7 L26,8.2 L24.9,5.7 L22.4,4.6 L24.9,3.5 Z" fill="currentColor"/>
    </svg>
  </div>
  <div class="titles">
    <div class="t1">Repo Genie</div>
    <div class="t2">CP-04 Mainframe Knowledge Recovery <span class="official-badge">Claude</span></div>
  </div>
</header>

<main>
  <div id="messages">
    <div id="empty">
      <div class="lamp-badge" style="display:flex;align-items:center;justify-content:center;">
        <svg viewBox="0 0 31 22" width="32" height="32" fill="none" aria-hidden="true">
          <path d="M5,19 C5,12 8,9 14,9 C19,9 21,12 21,16 C21,19 18,20 13,20 C8,20 5,20 5,19 Z" fill="currentColor"/>
          <path d="M9,9 C9,7 10.5,6 12.5,6 C14.5,6 16,7 16,9 Z" fill="currentColor"/>
          <circle cx="12.5" cy="5" r="1" fill="currentColor"/>
          <path d="M19,13 C22,11 24,8 25,5 L23,4.3 C22,7 20,10 17,12 Z" fill="currentColor"/>
          <path d="M26,1 L27.1,3.5 L29.6,4.6 L27.1,5.7 L26,8.2 L24.9,5.7 L22.4,4.6 L24.9,3.5 Z" fill="currentColor"/>
        </svg>
      </div>
      <h1>Ask me anything</h1>
      <p>General questions, or anything about this repo &mdash; the COBOL programs, extracted rules, field lineage, contradictions, or how the pipeline itself works, grounded in the actual <code>output/*.json</code> from the last run.</p>
      <div class="suggest">
        <button class="chip" type="button" data-q="What does this pipeline actually do, end to end?">What does this pipeline do?</button>
        <button class="chip" type="button" data-q="What does the REDEFINES issue mean for ACCT-INT-RATE?">REDEFINES issue?</button>
        <button class="chip" type="button" data-q="Why was the fee-waiver threshold flagged as drift?">Fee-waiver drift?</button>
        <button class="chip" type="button" data-q="Explain REDEFINES in COBOL like I'm new to the language.">Explain REDEFINES</button>
      </div>
    </div>
  </div>
</main>

<div id="status">
  <span class="dots"><span></span><span></span><span></span></span>
  <span id="status-text">Thinking&hellip;</span>
</div>
<div id="notice"></div>

<footer>
  <div class="input-row">
    <textarea id="input" rows="1" placeholder="Ask a question&hellip;"></textarea>
    <button id="send" type="button" aria-label="Send">
      <svg viewBox="0 0 20 20" width="17" height="17" fill="none"><path d="M3 10h13M10 4l6 6-6 6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </button>
  </div>
  <div class="foot-note">Answers are generated by Claude from this repo's real pipeline output &mdash; verify anything important.</div>
</footer>

<script id="pipeline-data" type="application/json">__DATA_JSON__</script>
<script>
(function(){
  var data;
  try {
    data = JSON.parse(document.getElementById('pipeline-data').textContent);
  } catch(e) {
    document.getElementById('empty').textContent = 'Could not load repo data.';
    return;
  }

  var messagesEl = document.getElementById('messages');
  var emptyEl = document.getElementById('empty');
  var statusEl = document.getElementById('status');
  var noticeEl = document.getElementById('notice');
  var inputEl = document.getElementById('input');
  var sendBtn = document.getElementById('send');

  var sample = null;
  var history = [];
  var busy = false;
  var disabledPermanently = false;
  var INSTRUCTIONS = data.genie_instructions;

  function scrollDown(){ messagesEl.scrollTop = messagesEl.scrollHeight; }

  function addBubble(role, text){
    if (emptyEl) emptyEl.hidden = true;
    var row = document.createElement('div');
    row.className = 'row ' + role;
    var avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.innerHTML = role === 'user'
      ? '<svg viewBox="0 0 20 20" width="13" height="13" fill="none"><circle cx="10" cy="7" r="3.2" fill="currentColor"/><path d="M3 17c1.5-4 4.5-6 7-6s5.5 2 7 6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>'
      : '<svg viewBox="0 0 28 28" width="14" height="14" fill="none"><path d="M6 17c0-4 2.5-7 8-7s8 3 8 7-3 5-8 5-8-1-8-5z" fill="currentColor"/></svg>';
    var bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = text;
    row.appendChild(avatar);
    row.appendChild(bubble);
    messagesEl.appendChild(row);
    scrollDown();
    return bubble;
  }

  function setBusy(v){
    busy = v;
    sendBtn.disabled = v || disabledPermanently;
    inputEl.disabled = disabledPermanently;
  }

  function errorMessage(code){
    switch(code){
      case 'not_granted': return "This assistant isn't enabled for your account.";
      case 'sampling_disabled': return "Claude isn't available for this account right now.";
      case 'rate_limited': return "Too many requests right now — try again in a moment.";
      case 'session_expired': return "Your session expired — reopen this page and sign in again.";
      case 'refused': return "That request couldn't be answered — try rephrasing it.";
      case 'empty_completion': return "No answer came back — try asking a more specific question.";
      case 'upstream_error': return "Something went wrong on our end — try again.";
      default: return "Something went wrong — try again.";
    }
  }

  var PERMANENT_HIDE_CODES = {not_granted:1, sampling_disabled:1, not_declared:1, capability_disabled:1, capability_removed:1};

  async function send(text){
    text = (text || '').trim();
    if (!text || busy || disabledPermanently || !sample) return;
    addBubble('user', text);
    history.push({role:'user', content:text});
    if (history.length > 12) history.splice(0, history.length - 12);
    inputEl.value = '';
    inputEl.style.height = 'auto';
    setBusy(true);
    statusEl.classList.add('show');

    var bubble = null;
    try {
      var result = await sample([{role:'user', content: INSTRUCTIONS}].concat(history), {
        cache: false,
        onText: function(update){
          statusEl.classList.remove('show');
          if (!bubble) bubble = addBubble('assistant', '');
          bubble.textContent = update.text;
          scrollDown();
        }
      });
      history.push({role:'assistant', content: result.text});
      if (result.truncated && bubble) bubble.textContent += '\n\n[answer cut short]';
    } catch (e) {
      statusEl.classList.remove('show');
      var code = e && e.code;
      if (PERMANENT_HIDE_CODES[code]) {
        disabledPermanently = true;
        noticeEl.textContent = errorMessage(code);
        noticeEl.classList.add('show');
        setBusy(true);
      } else if (code === 'cancelled') {
        // no-op
      } else {
        if (bubble && e.text) { bubble.textContent = e.text; }
        addBubble('assistant', errorMessage(code));
      }
    } finally {
      if (!disabledPermanently) setBusy(false);
    }
  }

  sendBtn.addEventListener('click', function(){ send(inputEl.value); });
  inputEl.addEventListener('keydown', function(ev){
    if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); send(inputEl.value); }
  });
  inputEl.addEventListener('input', function(){
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
  });
  document.querySelectorAll('.chip').forEach(function(chip){
    chip.addEventListener('click', function(){ send(chip.getAttribute('data-q')); });
  });

  (async function init(){
    setBusy(true);
    try {
      sample = (window.claude && typeof window.claude.use === 'function') ? await window.claude.use('sample') : null;
    } catch(e) { sample = null; }
    if (sample) {
      setBusy(false);
      inputEl.focus();
    } else {
      noticeEl.textContent = "This assistant isn't available in this context — open this page in Claude to use it.";
      noticeEl.classList.add('show');
    }
  })();
})();
</script>
'''


def build_chatbot_html(bundle):
    data_json = json.dumps(bundle).replace("</", "<\\/")
    return _HTML_TEMPLATE.replace("__DATA_JSON__", data_json)


def write_chatbot(path=None, lineage_field="ACCT-INT-RATE"):
    path = Path(path) if path else OUTPUT_DIR / "chatbot.html"
    bundle = build_data_bundle(lineage_field)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_chatbot_html(bundle))
    return path


if __name__ == "__main__":
    out = write_chatbot()
    print(f"wrote {out}")
