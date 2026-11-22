import { STR } from '/static/i18n.js';
const $ = s => document.querySelector(s);
const MAX_BYTES = 5 * 1024 * 1024, TYPES = ['image/png', 'image/jpeg', 'image/webp'];
let templates = {}, viewer = null, busy = false, visionOn = false, provider = null;
let lang = 'en';
lang = localStorage.getItem('lang') || ((navigator.language || '').toLowerCase().startsWith('ar') ? 'ar' : 'en');
let mode = 'sketch', file = null, sketchUrl = null, proposal = null, lastStatus = ['stReady', false], lastAi = null;
const t = (key, vars = {}) => (STR[lang][key] ?? STR.en[key] ?? key).replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '');
const half = (text, i) => { const p = String(text).split(' / '); return p[i] ?? p[0]; };
const pick = text => half(text, lang === 'ar' ? 1 : 0);

function status(key, error = false, vars = {}) {
  lastStatus = [key, error, vars]; $('#status').textContent = key.startsWith('raw:') ? key.slice(4) : t(key, vars);
  $('#status').classList.toggle('error', error);
}
function applyLang() {
  document.documentElement.lang = lang; document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
  for (const el of document.querySelectorAll('[data-i18n]')) el.textContent = t(el.dataset.i18n);
  for (const b of document.querySelectorAll('[data-lang]')) b.setAttribute('aria-pressed', String(b.dataset.lang === lang));
  const key = lastStatus[0]; if (key) status(key, lastStatus[1], lastStatus[2] || {});
  renderPartOptions(); renderFields(currentValues()); renderBanner(); renderAiStatus(); updateButtons();
}
function setLang(next) { lang = next; localStorage.setItem('lang', next); applyLang(); }

function renderPartOptions() {
  const sel = $('#part-type'), current = sel.value; sel.replaceChildren();
  for (const [key, item] of Object.entries(templates)) {
    const o = document.createElement('option'); o.value = key; o.textContent = pick(item.label); sel.append(o);
  }
  if (current && templates[current]) sel.value = current;
}
function currentValues() {
  const out = {}; for (const el of $('#fields').querySelectorAll('input')) out[el.name] = el.value; return out;
}
function renderFields(values = null) {
  const target = $('#fields'); target.replaceChildren();
  const type = $('#part-type').value; if (!templates[type]) return;
  const missing = proposal && proposal.part_type === type ? proposal.missing : [];
  for (const [name, spec] of Object.entries(templates[type].fields)) {
    const group = document.createElement('div');
    const label = document.createElement('label'); label.htmlFor = `dim-${name}`; label.textContent = pick(spec.label);
    const wrap = document.createElement('div'); wrap.className = 'input-wrap';
    const input = document.createElement('input'); input.type = 'number'; input.id = `dim-${name}`;
    input.name = name; input.min = spec.min; input.max = spec.max; input.step = 'any'; input.required = true;
    input.value = values?.[name] ?? spec.default;
    if (missing.includes(name)) input.classList.add('flag');
    input.addEventListener('input', () => { input.classList.remove('flag'); hint.textContent = ''; invalidate(); status('stDims'); });
    const unit = document.createElement('span'); unit.textContent = 'mm'; unit.className = 'unit';
    const hint = document.createElement('div'); hint.className = 'hint';
    if (missing.includes(name)) hint.textContent = t('flagged');
    wrap.append(input, unit); group.append(label, wrap, hint); target.append(group);
  }
}
function renderBanner() {
  const b = $('#banner');
  if (!proposal) { b.hidden = true; return; }
  b.hidden = false;
  const part = pick(templates[proposal.part_type]?.label ?? proposal.part_type);
  const conf = proposal.confidence ? ' ' + t('confidence', { c: t('conf_' + proposal.confidence) }) : '';
  $('#banner-text').textContent = t('reviewIntro', { part }) + conf;
  const names = (proposal.missing || []).map(n => pick(templates[proposal.part_type].fields[n].label));
  // Model notes are untrusted text: shown only via textContent, and only in the original language.
  const notes = [names.length ? t('missing', { list: names.join(', ') }) : '', proposal.notes || ''].filter(Boolean).join(' ');
  $('#banner-notes').textContent = notes;
}
function renderAiStatus() {
  let key = '';
  if (lastAi === 'error') key = '';
  $('#ai-status').textContent = visionOn ? (provider ? t('aiOnProvider', { p: provider }) : t('aiOn')) : t('aiOff');
}
function updateButtons() {
  const sketchMode = mode === 'sketch';
  $('#tab-sketch').setAttribute('aria-selected', String(sketchMode)); $('#tab-manual').setAttribute('aria-selected', String(!sketchMode));
  $('#sketch-box').hidden = !sketchMode;
  $('#review').hidden = sketchMode && !proposal;
  $('#confirm-row').hidden = !(sketchMode && proposal);
  const needConfirm = sketchMode && proposal && !$('#confirm-check').checked;
  const ready = Object.keys(templates).length > 0;
  for (const el of document.querySelectorAll('#fields input, #part-type, #sketch-clear, #confirm-check')) el.disabled = busy || !ready;
  $('#analyze').disabled = busy || !file || !visionOn;
  $('#generate').disabled = busy || !ready || !!needConfirm;
  $('#generate-text').textContent = busy ? t('working') : (sketchMode && proposal ? t('confirmGenerate') : t('generate'));
  $('#sketch-chosen').hidden = !file;
  $('#compare').classList.toggle('has-sketch', !!sketchUrl && sketchMode);
  $('#sketch-card').hidden = !(sketchUrl && sketchMode);
}
function setBusy(value) { busy = value; updateButtons(); }
function invalidate() { $('#result').hidden = true; viewer?.clear(); }
function setMode(next) {
  mode = next; invalidate();
  if (next === 'manual') { renderFields(currentValues()); status('stReady'); }
  updateButtons();
}
function setFile(f) {
  if (sketchUrl) URL.revokeObjectURL(sketchUrl);
  sketchUrl = null; file = null; proposal = null; $('#confirm-check').checked = false; invalidate();
  if (f) {
    if (f.size > MAX_BYTES) { status('stTooBig', true); }
    else if (!TYPES.includes(f.type)) { status('stBadType', true); }
    else {
      file = f; sketchUrl = URL.createObjectURL(f);
      $('#sketch-thumb').src = sketchUrl; $('#sketch-big').src = sketchUrl; $('#sketch-name').textContent = f.name;
      status('stReady');
    }
  }
  $('#sketch').value = '';
  renderBanner(); renderFields(currentValues()); updateButtons();
}
async function jsonResponse(response) {
  let data = null;
  try { data = await response.json(); } catch { /* non-JSON error page */ }
  if (!response.ok) {
    const err = new Error(typeof data?.detail === 'string' ? data.detail : 'HTTP ' + response.status);
    err.status = response.status; throw err;
  }
  return data;
}
function apiError(error) {
  const s = error.status;
  if ([503, 413, 415, 429, 502].includes(s)) return t('e' + s);
  if (s === 422) return t('e422') + error.message;
  if (!s) return t('eNet');
  return error.message;
}

$('#part-type').addEventListener('change', () => { renderFields(); invalidate(); status('stTemplate'); });
$('#reset-view').addEventListener('click', () => viewer?.reset());
$('#tab-sketch').addEventListener('click', () => setMode('sketch'));
$('#tab-manual').addEventListener('click', () => setMode('manual'));
$('#lang-en').addEventListener('click', () => setLang('en'));
$('#lang-ar').addEventListener('click', () => setLang('ar'));
$('#sketch').addEventListener('change', e => setFile(e.target.files[0]));
$('#sketch-clear').addEventListener('click', () => setFile(null));
$('#confirm-check').addEventListener('change', updateButtons);
const drop = $('#drop');
for (const ev of ['dragenter', 'dragover']) drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); });
for (const ev of ['dragleave', 'drop']) drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); });
drop.addEventListener('drop', e => { if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]); });

$('#analyze').addEventListener('click', async () => {
  if (busy) return;
  if (!file) { status('stNeedFile', true); return; }
  setBusy(true); invalidate(); proposal = null; renderBanner(); status('stAnalyzing');
  try {
    const form = new FormData(); form.append('image', file);
    const data = await jsonResponse(await fetch('/api/interpret', { method: 'POST', body: form }));
    proposal = data; $('#confirm-check').checked = false;
    $('#part-type').value = data.part_type; renderFields(data.dimensions); renderBanner();
    status('stProposal');
  } catch (error) { status('raw:' + apiError(error), true); }
  finally { setBusy(false); }
});

$('#dimensions-form').addEventListener('submit', async event => {
  event.preventDefault(); if (busy) return;
  const dimensions = Object.fromEntries([...$('#fields').querySelectorAll('input')].map(el => [el.name, Number(el.value)]));
  invalidate(); setBusy(true); status('stBuilding');
  try {
    const data = await jsonResponse(await fetch('/api/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ part_type: $('#part-type').value, dimensions }) }));
    $('#step-link').href = data.step_url; $('#stl-link').href = data.stl_url;
    $('#step-link').download = 'part.step'; $('#stl-link').download = 'part.stl';
    $('#metrics').replaceChildren();
    for (const value of [t('valid'), `${t('volume')}: ${data.validation.volume_mm3.toLocaleString()} mm³`, `${t('bounds')}: ${data.validation.bbox_mm.join(' × ')} mm`]) {
      const span = document.createElement('span'); span.textContent = value; $('#metrics').append(span);
    }
    $('#result').hidden = false; status('stDone');
    if (viewer) {
      try { await viewer.load(data.stl_url); }
      catch { status('stPreviewFail', true); }
    } else status('stNoPreview');
  } catch (error) { status('raw:' + apiError(error), true); }
  finally { setBusy(false); }
});

async function init() {
  applyLang();
  try {
    templates = await jsonResponse(await fetch('/api/templates'));
    const health = await jsonResponse(await fetch('/api/health'));
    visionOn = !!health.vision_configured; provider = health.vision_provider || null;
    renderPartOptions(); renderFields();
    // Without AI, land on the manual tab so the app is immediately useful.
    mode = visionOn ? 'sketch' : 'manual';
    status('stReady'); applyLang();
  } catch (error) { status('raw:' + t('stLoadFail') + error.message, true); return; }
  try { const { createViewer } = await import('/static/viewer.js'); viewer = createViewer($('#viewer')); }
  catch { status('stNoPreview'); }
}
init();
