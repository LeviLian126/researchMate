document.documentElement.classList.add('js');

const languageStyle = document.createElement('style');
languageStyle.textContent = `
  .mast-tools { display: flex; align-items: center; justify-content: flex-end; gap: 10px; flex-wrap: wrap; }
  .language-switch { display: inline-flex; align-items: center; min-height: 34px; border: 1px solid var(--g300); border-radius: 999px; background: var(--paper); padding: 7px 12px; color: var(--g700); font: 700 11px/1 var(--sans); text-decoration: none; white-space: nowrap; }
  .language-switch:hover, .language-switch:focus-visible { border-color: var(--clay); color: var(--clay-dark); }
  @media (max-width: 640px) {
    .mast-row { align-items: center; }
    .mast-tools { gap: 7px; }
    .stamp { text-align: right; }
  }
`;
document.head.appendChild(languageStyle);

function docsLanguageTarget() {
  const pathname = document.location.pathname.replace(/\\/g, '/');
  const isChinese = document.documentElement.lang.toLowerCase().startsWith('zh');
  if (isChinese) {
    const englishPath = pathname.replace('/docs/zh/', '/docs/').replace('/zh/', '/');
    return englishPath.endsWith('/') ? `${englishPath}index.html` : englishPath;
  }

  const marker = '/docs/';
  const markerIndex = pathname.indexOf(marker);
  if (markerIndex >= 0) {
    const prefix = pathname.slice(0, markerIndex + marker.length);
    const relative = pathname.slice(markerIndex + marker.length) || 'index.html';
    return `${prefix}zh/${relative}`;
  }

  const parts = pathname.split('/').filter(Boolean);
  const filename = parts.at(-1)?.includes('.') ? parts.pop() : 'index.html';
  const depth = Math.max(0, parts.length - 1);
  return `${'../'.repeat(depth)}zh/${[...parts.slice(1), filename].join('/')}`;
}

const mastRow = document.querySelector('.mast-row');
if (mastRow) {
  const stamp = mastRow.querySelector('.stamp');
  const tools = document.createElement('div');
  tools.className = 'mast-tools';
  if (stamp) tools.appendChild(stamp);

  const isChinese = document.documentElement.lang.toLowerCase().startsWith('zh');
  const switcher = document.createElement('a');
  switcher.className = 'language-switch';
  switcher.href = docsLanguageTarget();
  switcher.textContent = isChinese ? 'English' : '中文';
  switcher.setAttribute('aria-label', isChinese ? 'Switch to English documentation' : '切换到中文文档');
  tools.appendChild(switcher);
  mastRow.appendChild(tools);
}

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
  if (status) status.textContent = `${count} of ${apiItems.length} operations shown`;
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