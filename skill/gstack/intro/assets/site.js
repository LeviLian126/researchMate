const savedMode = localStorage.getItem('intro-color-mode');
const initialMode = savedMode || 'light';
document.documentElement.dataset.mode = initialMode;

const header = document.querySelector('.site-header');
if (header) {
  window.addEventListener('scroll', () => {
    header.classList.toggle('is-scrolled', window.scrollY > 18);
  });
}

const themeToggle = document.querySelector('.theme-toggle');
const syncThemeToggle = () => {
  if (!themeToggle) return;
  const isDark = document.documentElement.dataset.mode === 'dark';
  themeToggle.setAttribute('aria-pressed', String(isDark));
  const label = isDark ? '亮色' : '暗色';
  themeToggle.setAttribute('aria-label', `切换到${label}主题`);
  const text = themeToggle.querySelector('.theme-toggle-text');
  if (text) text.textContent = label;
};

syncThemeToggle();
if (themeToggle) {
  themeToggle.addEventListener('click', () => {
    const nextMode = document.documentElement.dataset.mode === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.mode = nextMode;
    localStorage.setItem('intro-color-mode', nextMode);
    syncThemeToggle();
  });
}

const observer = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (entry.isIntersecting) entry.target.classList.add('in-view');
  });
}, { threshold: 0.12 });

document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
