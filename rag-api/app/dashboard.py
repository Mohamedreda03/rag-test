"""Self-contained HTML dashboard for inspecting pipeline traces step by step.

Served at GET /dashboard. The page text is in Egyptian Arabic because it is
user-facing; all code stays in English.
"""

DASHBOARD_HTML = """<!doctype html>
<html lang='ar' dir='rtl'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>RAG Pipeline Dashboard</title>
<style>
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;margin:0;display:flex;height:100vh;background:#0f172a;color:#e2e8f0}
#sidebar{width:340px;border-left:1px solid #334155;overflow-y:auto;padding:14px;flex-shrink:0}
#main{flex:1;overflow-y:auto;padding:22px}
h1{font-size:17px;margin:0 0 10px}
.trace-item{padding:10px;border:1px solid #334155;border-radius:8px;margin-top:8px;cursor:pointer}
.trace-item:hover,.trace-item.active{background:#1e293b}
.muted{color:#94a3b8;font-size:12px}
.step{border:1px solid #334155;border-radius:10px;margin-bottom:14px;background:#1e293b;overflow:hidden}
.step header{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-bottom:1px solid #334155}
.step pre{margin:0;padding:12px 14px;white-space:pre-wrap;word-break:break-word;font-size:13px;direction:ltr;text-align:left;max-height:340px;overflow-y:auto}
.answer{border-color:#166534}
.answer header{background:#14532d}
button{background:#3b82f6;color:#fff;border:none;border-radius:6px;padding:6px 12px;cursor:pointer;font-size:13px}
button:hover{background:#2563eb}
.toolbar{display:flex;gap:8px;margin:12px 0 18px;flex-wrap:wrap}
</style>
</head>
<body>
<div id='sidebar'>
  <h1>\u0627\u0644\u0623\u0633\u0626\u0644\u0629 \u0627\u0644\u0623\u062e\u064a\u0631\u0629</h1>
  <button onclick='loadTraces()'>\u062a\u062d\u062f\u064a\u062b \u0627\u0644\u0642\u0627\u064a\u0645\u0629</button>
  <div id='traces'></div>
</div>
<div id='main'>
  <p class='muted'>\u0627\u062e\u062a\u0627\u0631 \u0633\u0624\u0627\u0644 \u0645\u0646 \u0627\u0644\u0642\u0627\u064a\u0645\u0629 \u0639\u0634\u0627\u0646 \u062a\u0634\u0648\u0641 \u0643\u0644 \u062e\u0637\u0648\u0627\u062a \u0627\u0644\u0640 pipeline \u0648\u0646\u062a\u064a\u062c\u0629 \u0643\u0644 \u062e\u0637\u0648\u0629\u060c \u0648\u062a\u0642\u062f\u0631 \u062a\u0646\u0633\u062e \u0623\u064a \u062e\u0637\u0648\u0629 \u0623\u0648 \u0627\u0644\u0640 pipeline \u0643\u0644\u0647.</p>
</div>
<script>
let traceData = null;
let currentId = null;

function esc(value) {
  const div = document.createElement('div');
  div.textContent = value == null ? '' : String(value);
  return div.innerHTML;
}

function copyText(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    const old = btn.textContent;
    btn.textContent = '\u0627\u062a\u0646\u0633\u062e \u2713';
    setTimeout(() => { btn.textContent = old; }, 1200);
  });
}

function copyAll(btn) { copyText(JSON.stringify(traceData, null, 2), btn); }
function copyStep(i, btn) { copyText(JSON.stringify(traceData.steps[i], null, 2), btn); }
function copyAnswer(btn) { copyText(traceData.answer || '', btn); }

async function loadTraces() {
  const res = await fetch('/traces');
  const list = await res.json();
  const el = document.getElementById('traces');
  el.innerHTML = '';
  list.forEach(t => {
    const item = document.createElement('div');
    item.className = 'trace-item' + (t.id === currentId ? ' active' : '');
    item.innerHTML = '<div>' + esc(t.question) + '</div>' +
      '<div class=\"muted\">' + esc(t.created_at) + ' \u00b7 ' + (t.duration_ms ?? '-') + ' ms \u00b7 ' + t.step_count + ' \u062e\u0637\u0648\u0627\u062a</div>';
    item.onclick = () => loadTrace(t.id);
    el.appendChild(item);
  });
}

async function loadTrace(id) {
  const res = await fetch('/traces/' + id);
  if (!res.ok) return;
  traceData = await res.json();
  currentId = id;
  const main = document.getElementById('main');
  let html = '<h1>' + esc(traceData.question) + '</h1>' +
    '<div class=\"muted\">trace: ' + traceData.id + ' \u00b7 ' + (traceData.duration_ms ?? '-') + ' ms \u00b7 verified: ' + traceData.verified + '</div>' +
    '<div class=\"toolbar\"><button onclick=\"copyAll(this)\">\u0646\u0633\u062e \u0627\u0644\u0640 pipeline \u0643\u0644\u0647</button></div>';
  traceData.steps.forEach((s, i) => {
    html += '<div class=\"step\"><header><div><b>' + (i + 1) + '. ' + esc(s.name) + '</b> ' +
      '<span class=\"muted\">' + (s.duration_ms ?? '-') + ' ms</span></div>' +
      '<button onclick=\"copyStep(' + i + ', this)\">\u0646\u0633\u062e \u0627\u0644\u062e\u0637\u0648\u0629</button></header>' +
      '<pre>' + esc(JSON.stringify(s.output, null, 2)) + '</pre></div>';
  });
  if (traceData.answer) {
    html += '<div class=\"step answer\"><header><b>\u0627\u0644\u0625\u062c\u0627\u0628\u0629 \u0627\u0644\u0646\u0647\u0627\u0626\u064a\u0629</b>' +
      '<button onclick=\"copyAnswer(this)\">\u0646\u0633\u062e \u0627\u0644\u0625\u062c\u0627\u0628\u0629</button></header>' +
      '<pre style=\"direction:rtl;text-align:right\">' + esc(traceData.answer) + '</pre></div>';
  }
  main.innerHTML = html;
  loadTraces();
}

loadTraces();
setInterval(loadTraces, 10000);
</script>
</body>
</html>
"""
