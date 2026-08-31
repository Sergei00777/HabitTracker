(function () {
  const root = document.documentElement;
  const btn = document.getElementById('theme-toggle');
  const icon = document.getElementById('theme-icon');
  const label = document.getElementById('theme-label');

  function applyTheme(theme) {
    root.setAttribute('data-theme', theme);
    if (icon && label) {
      if (theme === 'dark') {
        icon.textContent = '☀️';
        label.textContent = 'Светлая тема';
      } else {
        icon.textContent = '🌙';
        label.textContent = 'Тёмная тема';
      }
    }
    // перерисовать графики Chart.js под новую тему (сетка/сепараторы читаются из CSS-переменных при следующей отрисовке)
  }

  const saved = localStorage.getItem('habit-tracker-theme') || 'light';
  applyTheme(saved);

  if (btn) {
    btn.addEventListener('click', () => {
      const current = root.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      localStorage.setItem('habit-tracker-theme', next);
      applyTheme(next);
    });
  }
})();

// ---- Хелперы для CSS-донатов и CSS-баров (без внешних библиотек) ----
function setDonut(el, pct) {
  if (!el) return;
  el.style.setProperty('--pct', Math.max(0, Math.min(100, pct)));
}

function renderBars(container, values, labels) {
  container.innerHTML = '';
  values.forEach((v, i) => {
    const col = document.createElement('div');
    col.className = 'bar-col';
    const bar = document.createElement('div');
    bar.className = 'bar' + (v >= 70 ? ' bar-good' : '');
    bar.style.height = Math.max(2, v) + '%';
    bar.title = (labels ? labels[i] : i + 1) + ': ' + v + '%';
    col.appendChild(bar);
    container.appendChild(col);
  });
}
