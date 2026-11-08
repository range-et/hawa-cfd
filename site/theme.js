(() => {
  const key = 'hawa-strata';
  const root = document.documentElement;
  const button = document.getElementById('theme-toggle');
  function apply(theme) {
    root.dataset.strata = theme;
    button.setAttribute('aria-pressed', String(theme === 'light'));
    button.setAttribute('aria-label', theme === 'light' ? 'Toggle dark theme' : 'Toggle light theme');
  }
  let theme = 'dark';
  try { const saved = localStorage.getItem(key); if (saved === 'light' || saved === 'dark') theme = saved; } catch (_) {}
  apply(theme);
  button.addEventListener('click', () => {
    const next = root.dataset.strata === 'dark' ? 'light' : 'dark';
    apply(next);
    try { localStorage.setItem(key, next); } catch (_) {}
  });
})();
