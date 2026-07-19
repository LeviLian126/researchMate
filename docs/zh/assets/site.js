document.documentElement.classList.add('js');
document.documentElement.lang = 'zh-CN';

const languageStyle = document.createElement('style');
languageStyle.textContent = `
  .mast-tools { display: flex; align-items: center; justify-content: flex-end; gap: 10px; flex-wrap: wrap; }
  .language-switch { display: inline-flex; align-items: center; min-height: 34px; border: 1px solid var(--g300); border-radius: 999px; background: var(--paper); padding: 7px 12px; color: var(--g700); font: 700 11px/1 var(--sans); text-decoration: none; white-space: nowrap; }
  .language-switch:hover, .language-switch:focus-visible { border-color: var(--clay); color: var(--clay-dark); }
  .translation-state { position: fixed; right: 18px; bottom: 18px; z-index: 1000; max-width: min(360px, calc(100vw - 36px)); border: 1px solid var(--g300); border-radius: 10px; background: var(--paper); box-shadow: 0 8px 30px rgba(0,0,0,.09); padding: 10px 13px; color: var(--g700); font: 12px/1.45 var(--sans); }
  .translation-state[hidden] { display: none; }
  @media (max-width: 640px) { .mast-row { align-items: center; } .mast-tools { gap: 7px; } .stamp { text-align: right; } }
`;
document.head.appendChild(languageStyle);

function englishTarget() {
  const pathname = document.location.pathname.replace(/\\/g, '/');
  const target = pathname.replace('/docs/zh/', '/docs/').replace('/zh/', '/');
  return target.endsWith('/') ? `${target}index.html` : target;
}

const mastRow = document.querySelector('.mast-row');
if (mastRow) {
  const stamp = mastRow.querySelector('.stamp');
  const tools = document.createElement('div');
  tools.className = 'mast-tools';
  if (stamp) tools.appendChild(stamp);
  const switcher = document.createElement('a');
  switcher.className = 'language-switch';
  switcher.href = englishTarget();
  switcher.textContent = 'English';
  switcher.setAttribute('aria-label', '切换到英文文档');
  tools.appendChild(switcher);
  mastRow.appendChild(tools);
}

const state = document.createElement('div');
state.className = 'translation-state';
state.textContent = '正在载入完整中文文档…';
document.body.appendChild(state);

const apiSearch = document.querySelector('[data-endpoint-search]');
const apiButtons = [...document.querySelectorAll('[data-api-filter], [data-method-filter], [data-access-filter]')];
const apiItems = [...document.querySelectorAll('[data-api-card]')];

function applyApiFilter() {
  if (!apiItems.length) return;
  const group = document.querySelector('[data-api-filter][aria-pressed="true"]')?.dataset.apiFilter || 'all';
  const method = document.querySelector('[data-method-filter][aria-pressed="true"]')?.dataset.methodFilter || 'all';
  const access = document.querySelector('[data-access-filter][aria-pressed="true"]')?.dataset.accessFilter || 'all';
  const query = (apiSearch?.value || '').trim().toLowerCase();
  apiItems.forEach((item) => {
    const matchesGroup = group === 'all' || item.dataset.api === group;
    const matchesMethod = method === 'all' || item.dataset.method === method;
    const matchesAccess = access === 'all' || item.dataset.access === access;
    const matchesQuery = !query || item.textContent.toLowerCase().includes(query);
    item.hidden = !(matchesGroup && matchesMethod && matchesAccess && matchesQuery);
  });
  const count = apiItems.filter((item) => !item.hidden).length;
  const status = document.querySelector('[data-filter-status]');
  if (status) status.textContent = `显示 ${count} / ${apiItems.length} 个操作`;
}

apiButtons.forEach((button) => button.addEventListener('click', () => {
  const family = button.hasAttribute('data-api-filter') ? 'data-api-filter' : button.hasAttribute('data-method-filter') ? 'data-method-filter' : 'data-access-filter';
  apiButtons.filter((candidate) => candidate.hasAttribute(family)).forEach((candidate) => candidate.setAttribute('aria-pressed', String(candidate === button)));
  applyApiFilter();
}));
apiSearch?.addEventListener('input', applyApiFilter);
applyApiFilter();

const dbButtons = [...document.querySelectorAll('[data-db-filter]')];
const dbItems = [...document.querySelectorAll('[data-db]')];
dbButtons.forEach((button) => button.addEventListener('click', () => {
  dbButtons.forEach((candidate) => candidate.setAttribute('aria-pressed', String(candidate === button)));
  const group = button.dataset.dbFilter;
  dbItems.forEach((item) => { item.hidden = group !== 'all' && item.dataset.db !== group; });
}));

const archButtons = [...document.querySelectorAll('[data-arch-node]')];
const archTitle = document.querySelector('[data-arch-title]');
const archBody = document.querySelector('[data-arch-body]');
archButtons.forEach((button) => button.addEventListener('click', () => {
  archButtons.forEach((candidate) => candidate.setAttribute('aria-pressed', String(candidate === button)));
  if (archTitle) archTitle.textContent = button.dataset.title || button.textContent.trim();
  if (archBody) archBody.textContent = button.dataset.detail || '';
}));

const SKIP = new Set(['CODE', 'PRE', 'SCRIPT', 'STYLE', 'KBD', 'SAMP', 'VAR', 'NOSCRIPT']);
const ATTRIBUTES = ['aria-label', 'title', 'placeholder', 'data-title', 'data-detail'];
const CACHE_KEY = 'researchmate-docs-zh-v2';
const SEPARATOR = '\n⟦RMSEP9A7F⟧\n';

function shouldTranslate(value) {
  const text = value.trim();
  if (!text || !/[A-Za-z]/.test(text)) return false;
  if (/^[A-Za-z0-9_./:@+\-#?=&%<>()[\]{}'"|* ]+$/.test(text)) {
    const words = text.split(/\s+/);
    if (words.length <= 2 && /[_./:@#?=&%<>{}\[\]()]/.test(text)) return false;
  }
  return true;
}

function loadCache() {
  try { return JSON.parse(localStorage.getItem(CACHE_KEY) || '{}'); }
  catch { return {}; }
}

function saveCache(cache) {
  try { localStorage.setItem(CACHE_KEY, JSON.stringify(cache)); }
  catch { /* Storage is optional; translation still works. */ }
}

function collectTargets() {
  const targets = [];
  const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const parent = node.parentElement;
    if (!parent || SKIP.has(parent.tagName) || parent.closest('.translation-state')) continue;
    if (shouldTranslate(node.nodeValue || '')) {
      targets.push({ type: 'text', node, value: node.nodeValue.trim(), original: node.nodeValue });
    }
  }
  document.querySelectorAll('*').forEach((element) => {
    if (SKIP.has(element.tagName)) return;
    ATTRIBUTES.forEach((name) => {
      const value = element.getAttribute(name);
      if (value && shouldTranslate(value)) targets.push({ type: 'attribute', node: element, name, value, original: value });
    });
  });
  const description = document.querySelector('meta[name="description"]');
  const content = description?.getAttribute('content');
  if (description && content && shouldTranslate(content)) {
    targets.push({ type: 'attribute', node: description, name: 'content', value: content, original: content });
  }
  return targets;
}

function applyTarget(target, translated) {
  if (target.type === 'text') {
    const leading = target.original.match(/^\s*/)?.[0] || '';
    const trailing = target.original.match(/\s*$/)?.[0] || '';
    target.node.nodeValue = `${leading}${translated.trim()}${trailing}`;
  } else {
    target.node.setAttribute(target.name, translated.trim());
  }
}

async function translateRequest(text) {
  const url = new URL('https://translate.googleapis.com/translate_a/single');
  url.searchParams.set('client', 'gtx');
  url.searchParams.set('sl', 'en');
  url.searchParams.set('tl', 'zh-CN');
  url.searchParams.set('dt', 't');
  url.searchParams.set('q', text);
  const response = await fetch(url.toString(), { mode: 'cors', credentials: 'omit' });
  if (!response.ok) throw new Error(`翻译服务返回 ${response.status}`);
  const data = await response.json();
  return (data[0] || []).map((part) => part[0] || '').join('');
}

async function translateValues(values) {
  const joined = values.join(SEPARATOR);
  const output = await translateRequest(joined);
  const pieces = output.split(SEPARATOR);
  if (pieces.length === values.length) return pieces;
  const translated = [];
  for (const value of values) translated.push(await translateRequest(value));
  return translated;
}

async function translatePage() {
  const cache = loadCache();
  const targets = collectTargets();
  const pending = [];
  targets.forEach((target) => {
    const cached = cache[target.value];
    if (cached) applyTarget(target, cached);
    else pending.push(target);
  });

  let cursor = 0;
  while (cursor < pending.length) {
    const batch = [];
    let chars = 0;
    while (cursor + batch.length < pending.length && batch.length < 14) {
      const candidate = pending[cursor + batch.length];
      if (batch.length && chars + candidate.value.length > 1800) break;
      batch.push(candidate);
      chars += candidate.value.length;
    }
    const translations = await translateValues(batch.map((target) => target.value));
    batch.forEach((target, index) => {
      const translated = translations[index];
      cache[target.value] = translated;
      applyTarget(target, translated);
    });
    cursor += batch.length;
    state.textContent = `正在载入完整中文文档… ${Math.min(cursor, pending.length)} / ${pending.length}`;
    if (cursor % 70 === 0 || cursor === pending.length) saveCache(cache);
  }

  saveCache(cache);
  state.textContent = '完整中文内容已载入；代码、字段名、端点和结构保持原样。';
  window.setTimeout(() => { state.hidden = true; }, 2600);
  applyApiFilter();
}

translatePage().catch((error) => {
  console.error('ResearchMate Chinese translation failed', error);
  state.textContent = `中文翻译载入失败：${error.message}。页面保留完整英文原文，请刷新后重试。`;
});