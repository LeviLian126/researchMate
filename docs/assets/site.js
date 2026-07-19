document.documentElement.classList.add('js');

const languageStyle = document.createElement('style');
languageStyle.textContent = `
  .mast-tools { display: flex; align-items: center; justify-content: flex-end; gap: 10px; flex-wrap: wrap; }
  .language-switch { display: inline-flex; align-items: center; min-height: 34px; border: 1px solid var(--g300); border-radius: 999px; background: var(--paper); padding: 7