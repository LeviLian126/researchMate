document.documentElement.classList.add('js');

const languageStyle = document.createElement('style');
languageStyle.textContent = `
  .mast-tools { display: flex; align-items: center; justify-content: flex-end; gap: 10px; flex-wrap: wrap; }
  .language-switch { display: inline-flex; align-items: center; min-height: 34px; border: 1px solid var(--g300); border-radius: 999px; background: var(--paper); padding: 7px 12px; color: var(--g700); font: 700 11px/1 var(--sans); text-decoration: none; white-space: nowrap; }
  .language-switch:hover, .language-switch:focus-visible { border-color: var(--clay); color: var(--clay-dark); }
  @media (max-width: 640px) {
    .mast-row { align-items: center; }
    .