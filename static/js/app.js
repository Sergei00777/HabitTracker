// ---- Тема: светлая / тёмная / как в системе ----
(function () {
  const root = document.documentElement;
  const btn = document.getElementById('theme-toggle');
  const label = document.getElementById('theme-label');
  const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

  function effective() {
    const t = root.getAttribute('data-theme');
    if (t) return t;
    return media && media.matches ? 'dark' : 'light';
  }
  function updateLabel() {
    if (label) label.textContent = effective() === 'dark' ? 'Светлая тема' : 'Тёмная тема';
  }
  updateLabel();
  if (media && media.addEventListener) media.addEventListener('change', updateLabel);

  if (btn) {
    btn.addEventListener('click', () => {
      const next = effective() === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('habit-tracker-theme', next); } catch (e) {}
      updateLabel();
    });
  }
})();

// ---- Хелперы для CSS-донатов и CSS-баров (без внешних библиотек) ----
function setDonut(el, pct) {
  if (!el) return;
  el.style.setProperty('--pct', Math.max(0, Math.min(100, pct)));
}

function renderBars(container, values, labels, opts) {
  if (!container) return;
  opts = opts || {};
  container.innerHTML = '';
  values.forEach((v, i) => {
    const day = labels ? labels[i] : i + 1;
    const col = document.createElement('div');
    col.className = 'bar-col' + (opts.today && day === opts.today ? ' is-today' : '');
    const bar = document.createElement('div');
    bar.className = 'bar' + (v >= 70 ? ' bar-good' : v > 0 ? ' bar-mid' : '');
    bar.style.height = Math.max(2, v) + '%';
    bar.title = day + ': ' + Math.round(v) + '%';
    col.appendChild(bar);
    if (labels && (opts.allLabels || i === 0 || (i + 1) % 5 === 0 || day === opts.today)) {
      const lb = document.createElement('div');
      lb.className = 'bar-day-label';
      lb.textContent = day;
      col.appendChild(lb);
    }
    container.appendChild(col);
  });
}

// ---- Удаление в два нажатия вместо всплывающего окна ----
function confirmDelete(form, e) {
  const btn = form.querySelector('button');
  if (form.dataset.armed) return true;
  e.preventDefault();
  form.dataset.armed = '1';
  const old = btn.textContent;
  btn.textContent = 'Удалить?';
  btn.classList.add('is-armed');
  setTimeout(() => {
    delete form.dataset.armed;
    btn.textContent = old;
    btn.classList.remove('is-armed');
  }, 3000);
  return false;
}

// ---- Короткое уведомление внизу экрана ----
function toast(text) {
  let el = document.getElementById('toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'toast';
    el.className = 'toast';
    el.setAttribute('role', 'status');
    document.body.appendChild(el);
  }
  el.textContent = text;
  el.classList.add('show');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), 3500);
}
