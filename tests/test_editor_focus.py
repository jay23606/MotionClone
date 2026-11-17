import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Minimal DOM stand-in: enough of document/element behaviour for web/editor.js to build its rows.
# Removing a focused element moves focus to <body>, as browsers do. Enter on a focused, enabled button clicks it.
HARNESS = r'''
const p = JSON.parse(process.argv[process.argv.length - 1]);
const fs = require('fs');
const camel = s => s.replace(/-(\w)/g, (_, c) => c.toUpperCase());
function contains(root, el) { for (let x = el; x; x = x.parent) if (x === root) return true; return false; }
function walk(n, f) { for (const c of n.children) { f(c); walk(c, f); } }
function attr(n, k) {
  if (k === 'disabled') return n.disabled ? 'true' : null;
  if (k.startsWith('data-')) return n.dataset[camel(k.slice(5))] ?? null;
  return n.getAttribute(k);
}
function matches(n, sel) {
  const tag = (sel.match(/^[a-zA-Z]+/) || [''])[0];
  if (tag && n.tagName !== tag.toUpperCase()) return false;
  for (const m of sel.matchAll(/\[([\w-]+)="([^"]*)"\]/g)) if (attr(n, m[1]) !== m[2]) return false;
  for (const m of sel.matchAll(/:not\(\[([\w-]+)\]\)/g)) if (attr(n, m[1]) !== null) return false;
  return true;
}
class El {
  constructor(tag, id = '') { this.tagName = tag.toUpperCase(); this.id = id; this.children = []; this.parent = null; this.attrs = {}; this.dataset = {}; this.disabled = false; this.hidden = false; this.value = ''; this.textContent = ''; this.className = ''; this.files = []; this.listeners = {}; this.onclick = null; this.classList = { add() {}, remove() {}, toggle() {} }; this.style = {}; }
  append(...ns) { for (const n of ns) if (typeof n === 'object') { n.parent = this; this.children.push(n); } }
  replaceChildren(...ns) { if (contains(this, document.activeElement)) document.activeElement = document.body; for (const c of this.children) c.parent = null; this.children = []; this.append(...ns); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  addEventListener(t, f) { (this.listeners[t] || (this.listeners[t] = [])).push(f); }
  focus() { if (!this.disabled) document.activeElement = this; }
  pause() {} play() { return Promise.resolve(); }
  querySelectorAll(sel) { const out = []; walk(this, n => { if (matches(n, sel)) out.push(n); }); return out; }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
}
const body = new El('body'); body.dataset.hosted = 'false';
const byId = {};
const document = {
  body, activeElement: body,
  getElementById(id) { if (!byId[id]) { byId[id] = new El('div', id); body.append(byId[id]); } return byId[id]; },
  createElement(tag) { return new El(tag); },
  addEventListener() {}
};
globalThis.document = document;
globalThis.window = { addEventListener() {} };
globalThis.FormData = class {};
const routes = { '/api/status': { token: 't', chatgpt: true, active: false }, '/api/library': [], '/api/editor/draft': p.draft };
globalThis.fetch = async path => { const data = routes[new URL(path, 'http://x').pathname]; return { ok: true, status: 200, json: async () => data }; };
const label = el => el.getAttribute('aria-label') || el.id || el.tagName;
const order = () => document.getElementById('segments').children.filter(li => li.className === 'segment').map(li => li.querySelectorAll('input')[0].value);
(async () => {
  new Function(fs.readFileSync(p.editor, 'utf8'))();
  await new Promise(r => setTimeout(r, 10));
  const trace = [{ step: 'load', order: order(), focus: label(document.activeElement) }];
  for (const step of p.steps) {
    if (step.startsWith('focus:')) {
      const el = body.querySelectorAll(`[aria-label="${step.slice(6)}"]`)[0];
      if (!el) { trace.push({ step, error: 'no element labelled ' + step.slice(6) }); break; }
      el.focus();
    } else {
      const el = document.activeElement;
      if (el.tagName === 'BUTTON' && !el.disabled && el.onclick) el.onclick();
    }
    await new Promise(r => setTimeout(r, 0));
    trace.push({ step, order: order(), focus: label(document.activeElement) });
  }
  console.log(JSON.stringify(trace));
})();
'''


def run(steps, *notes):
    draft = {'brand': '', 'instructions': '', 'format': '', 'keep_audio': False,
             'segments': [{'project': 'a'*12, 'start': 0, 'end': 1, 'notes': n} for n in notes]}
    payload = json.dumps({'editor': str(ROOT / 'web' / 'editor.js'), 'draft': draft, 'steps': steps})
    done = subprocess.run(['node', '-e', HARNESS, payload], capture_output=True, text=True, check=True, timeout=60)
    return json.loads(done.stdout)


def test_keyboard_move_later_twice_moves_same_segment_without_retabbing():
    trace = run(['focus:Move later segment 1', 'enter', 'enter'], 'A', 'B', 'C')
    assert trace[2]['focus'] == 'Move later segment 2', 'keyboard focus must stay on the moved segment after Move later'
    assert trace[3]['order'] == ['B', 'C', 'A'], 'second Enter must move the same segment again'
    assert trace[3]['focus'] == 'Move earlier segment 3', 'focus must fall back to the opposite arrow once Move later is disabled'


def test_remove_moves_focus_to_next_remove_button():
    trace = run(['focus:Remove segment 2', 'enter'], 'A', 'B', 'C')
    assert trace[2]['order'] == ['A', 'C']
    assert trace[2]['focus'] == 'Remove segment 2', 'focus must move to the Remove button of the next segment'


def test_remove_last_segment_moves_focus_to_add_segment():
    trace = run(['focus:Remove segment 1', 'enter'], 'A')
    assert trace[2]['order'] == []
    assert trace[2]['focus'] == 'add-segment', 'focus must move to #add-segment when the list is empty'
