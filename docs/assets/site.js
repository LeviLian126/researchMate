document.documentElement.classList.add('js');

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
