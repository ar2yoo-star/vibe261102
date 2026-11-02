import * as store from './store.js';
import { todayKey } from './date.js';
import { render } from './render.js';
import { MAX_LEN, newId, pendingFromPast } from './todo.js';

const $ = (selector) => document.querySelector(selector);

const els = {
  todayLabel: $('#today-label'),
  themeToggle: $('#theme-toggle'),
  storageBanner: $('#storage-banner'),
  carryBanner: $('#carry-banner'),
  carryText: $('#carry-text'),
  carryAccept: $('#carry-accept'),
  carryDismiss: $('#carry-dismiss'),
  form: $('#add-form'),
  input: $('#new-todo'),
  counter: $('#counter'),
  hint: $('#input-hint'),
  progressText: $('#progress-text'),
  progressPct: $('#progress-pct'),
  progressBar: $('#progress-bar'),
  progressFill: $('#progress-fill'),
  filterLinks: document.querySelectorAll('.filters a'),
  list: $('#todo-list'),
  empty: $('#empty'),
  clearDone: $('#clear-done'),
  toast: $('#toast'),
  toastMsg: $('#toast-msg'),
  toastAction: $('#toast-action'),
};

const FILTER_BY_HASH = { '': 'all', '#/': 'all', '#/active': 'active', '#/done': 'done' };
const filterFromHash = () => FILTER_BY_HASH[location.hash] ?? 'all';

// 저장하지 않는 화면 상태
const ui = {
  today: todayKey(),
  filter: filterFromHash(),
  editingId: null,
  newId: null,  // 추가 애니메이션을 줄 항목
  focus: null,  // 렌더 후 포커스를 돌려줄 위치 { id, selector, select }
};

const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
const darkQuery = matchMedia('(prefers-color-scheme: dark)');
const CONTROLS = ['.handle', '.toggle', '.star', '.edit-btn', '.delete'];

function renderAll() {
  render(store.getState(), ui, els);
  els.storageBanner.hidden = store.isPersistent();
  ui.newId = null;

  if (ui.focus) {
    const { id, selector, select } = ui.focus;
    ui.focus = null;
    const item = id && els.list.querySelector(`.item[data-id="${CSS.escape(id)}"]`);
    const target = (item && item.querySelector(selector)) || (selector === 'input' ? els.input : null);
    if (target) {
      target.focus();
      if (select) target.select();
    }
  }
}

/* ---------- 테마 ---------- */

const effectiveTheme = (theme) => (theme === 'system' ? (darkQuery.matches ? 'dark' : 'light') : theme);

function applyTheme() {
  const { theme } = store.getState().settings;
  const root = document.documentElement;
  if (theme === 'system') delete root.dataset.theme;
  else root.dataset.theme = theme;
  const mode = effectiveTheme(theme);
  els.themeToggle.dataset.mode = mode;
  els.themeToggle.setAttribute('aria-label', mode === 'dark' ? '라이트 모드로 전환' : '다크 모드로 전환');
}

els.themeToggle.addEventListener('click', () => {
  const next = effectiveTheme(store.getState().settings.theme) === 'dark' ? 'light' : 'dark';
  // 시스템 설정과 같아지면 다시 시스템을 따르게 한다
  store.dispatch({ type: 'SET_THEME', theme: next === effectiveTheme('system') ? 'system' : next });
});
darkQuery.addEventListener('change', applyTheme);

/* ---------- 토스트 ---------- */

let toastTimer;

function hideToast() {
  clearTimeout(toastTimer);
  els.toast.hidden = true;
}

function showToast(message, action) {
  clearTimeout(toastTimer);
  els.toastMsg.textContent = message;
  els.toastAction.hidden = !action;
  if (action) {
    els.toastAction.textContent = action.label;
    els.toastAction.onclick = () => {
      hideToast();
      action.onAction();
    };
  }
  els.toast.hidden = false;
  toastTimer = setTimeout(hideToast, 5000);
}

/* ---------- 입력 ---------- */

function updateCounter() {
  const len = els.input.value.length;
  els.counter.textContent = `${len}/${MAX_LEN}`;
  els.counter.classList.toggle('near', len >= MAX_LEN - 10);
}

function flashInvalid(message) {
  els.input.classList.remove('shake');
  void els.input.offsetWidth; // 애니메이션 재시작
  els.input.classList.add('shake');
  els.input.setAttribute('aria-invalid', 'true');
  els.hint.textContent = message;
  els.input.focus();
}

els.input.addEventListener('input', () => {
  updateCounter();
  if (els.hint.textContent) {
    els.hint.textContent = '';
    els.input.removeAttribute('aria-invalid');
  }
});
els.input.addEventListener('animationend', () => els.input.classList.remove('shake'));

els.form.addEventListener('submit', (e) => {
  e.preventDefault();
  if (!els.input.value.trim()) {
    flashInvalid('할 일을 입력해 주세요');
    return;
  }
  const id = newId();
  ui.newId = id;
  store.dispatch({ type: 'ADD', id, text: els.input.value, date: ui.today });
  els.input.value = '';
  updateCounter();
  els.input.focus();
});

/* ---------- 삭제 (실행 취소 포함) ---------- */

// 항목을 흐리게 사라지게 한 뒤 콜백 실행
function fadeOut(items, then) {
  if (reduceMotion.matches || !items.length) return then();
  items.forEach((li) => li.classList.add('is-leaving'));
  setTimeout(then, 150);
}

function deleteItem(li) {
  if (li.classList.contains('is-leaving')) return;
  const { id } = li.dataset;
  const removed = store.getState().todos.filter((t) => t.id === id);
  const neighbor = li.nextElementSibling || li.previousElementSibling;
  const hadFocus = li.contains(document.activeElement);

  fadeOut([li], () => {
    if (hadFocus) ui.focus = neighbor ? { id: neighbor.dataset.id, selector: '.toggle' } : { selector: 'input' };
    store.dispatch({ type: 'DELETE', id });
    showToast('할일을 삭제했어요', {
      label: '실행 취소',
      onAction: () => store.dispatch({ type: 'RESTORE', todos: removed }),
    });
  });
}

els.clearDone.addEventListener('click', () => {
  const removed = store.getState().todos.filter((t) => t.date === ui.today && t.done);
  if (!removed.length) return;
  fadeOut([...els.list.querySelectorAll('.item.done')], () => {
    store.dispatch({ type: 'CLEAR_DONE', date: ui.today });
    showToast(`완료 항목 ${removed.length}개를 지웠어요`, {
      label: '실행 취소',
      onAction: () => store.dispatch({ type: 'RESTORE', todos: removed }),
    });
  });
});

/* ---------- 수정 ---------- */

function startEdit(id) {
  ui.editingId = id;
  ui.focus = { id, selector: '.edit', select: true };
  renderAll();
}

function finishEdit(id, text, { save, refocus }) {
  if (ui.editingId !== id) return; // 렌더로 입력창이 사라질 때 생기는 중복 호출 방지
  ui.editingId = null;
  if (refocus) ui.focus = { id, selector: '.edit-btn' };
  const changed = save && store.dispatch({ type: 'EDIT', id, text });
  if (!changed) renderAll();
}

/* ---------- 순서 변경 ---------- */

const visibleIds = () => [...els.list.querySelectorAll('.item')].map((li) => li.dataset.id);

function moveItem(li, direction, selector) {
  const items = [...els.list.querySelectorAll('.item')];
  const from = items.indexOf(li);
  const to = from + direction;
  if (to < 0 || to >= items.length) return;
  // 중요 항목은 항상 위에 정렬되므로 그룹을 넘나드는 이동은 막는다
  if (items[to].classList.contains('important') !== li.classList.contains('important')) return;
  const ids = visibleIds();
  [ids[from], ids[to]] = [ids[to], ids[from]];
  ui.focus = { id: li.dataset.id, selector };
  store.dispatch({ type: 'REORDER', ids });
}

// 포인터(마우스·터치) 드래그
els.list.addEventListener('pointerdown', (e) => {
  const handle = e.target.closest('.handle');
  if (!handle || e.button !== 0) return;
  e.preventDefault();
  const li = handle.closest('.item');
  const before = visibleIds().join();
  handle.setPointerCapture(e.pointerId);
  li.classList.add('dragging');

  const onMove = (ev) => {
    const others = [...els.list.querySelectorAll('.item:not(.dragging)')];
    const next = others.find((other) => {
      const rect = other.getBoundingClientRect();
      return ev.clientY < rect.top + rect.height / 2;
    });
    if (next) {
      if (next !== li.nextElementSibling) els.list.insertBefore(li, next);
    } else if (li !== els.list.lastElementChild) {
      els.list.append(li);
    }
  };
  const onEnd = () => {
    handle.removeEventListener('pointermove', onMove);
    handle.removeEventListener('pointerup', onEnd);
    handle.removeEventListener('pointercancel', onEnd);
    li.classList.remove('dragging');
    const ids = visibleIds();
    // 중요 항목 그룹을 넘었으면 정렬 규칙에 따라 제자리로 돌아간다
    if (ids.join() === before || !store.dispatch({ type: 'REORDER', ids })) renderAll();
  };
  handle.addEventListener('pointermove', onMove);
  handle.addEventListener('pointerup', onEnd);
  handle.addEventListener('pointercancel', onEnd);
});

/* ---------- 목록 이벤트 (위임) ---------- */

els.list.addEventListener('change', (e) => {
  if (!e.target.matches('.toggle')) return;
  const { id } = e.target.closest('.item').dataset;
  ui.focus = { id, selector: '.toggle' };
  store.dispatch({ type: 'TOGGLE', id });
});

els.list.addEventListener('click', (e) => {
  const button = e.target.closest('button');
  if (!button) return;
  const li = button.closest('.item');
  const { id } = li.dataset;
  if (button.matches('.star')) {
    ui.focus = { id, selector: '.star' };
    store.dispatch({ type: 'TOGGLE_IMPORTANT', id });
  } else if (button.matches('.edit-btn')) {
    startEdit(id);
  } else if (button.matches('.delete')) {
    deleteItem(li);
  }
});

els.list.addEventListener('dblclick', (e) => {
  const text = e.target.closest('.text');
  if (text) startEdit(text.closest('.item').dataset.id);
});

els.list.addEventListener('focusout', (e) => {
  if (e.target.matches('.edit')) {
    finishEdit(e.target.closest('.item').dataset.id, e.target.value, { save: true });
  }
});

els.list.addEventListener('keydown', (e) => {
  const li = e.target.closest('.item');
  if (!li) return;

  if (e.target.matches('.edit')) {
    if (e.key === 'Enter' && !e.isComposing) {
      e.preventDefault();
      finishEdit(li.dataset.id, e.target.value, { save: true, refocus: true });
    } else if (e.key === 'Escape') {
      e.preventDefault();
      finishEdit(li.dataset.id, '', { save: false, refocus: true });
    }
    return;
  }

  if (e.key === 'Delete') {
    e.preventDefault();
    deleteItem(li);
  } else if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
    e.preventDefault();
    const selector = CONTROLS.find((sel) => e.target.matches(sel)) ?? '.toggle';
    moveItem(li, e.key === 'ArrowUp' ? -1 : 1, selector);
  }
});

/* ---------- 이월 배너 ---------- */

els.carryAccept.addEventListener('click', () => {
  const count = pendingFromPast(store.getState().todos, ui.today).length;
  store.dispatch({ type: 'CARRY_OVER', today: ui.today });
  showToast(`${count}개를 오늘로 가져왔어요`);
});

els.carryDismiss.addEventListener('click', () => {
  store.dispatch({ type: 'DISMISS_CARRY', today: ui.today });
});

/* ---------- 전역 ---------- */

document.addEventListener('keydown', (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey || e.isComposing) return;
  const typing = e.target.closest('input, textarea, [contenteditable="true"]');
  if (!typing && (e.key === '/' || e.key === 'n')) {
    e.preventDefault();
    els.input.focus();
  }
});

window.addEventListener('hashchange', () => {
  ui.filter = filterFromHash();
  ui.editingId = null;
  renderAll();
});

// 자정이 지나면 '오늘'을 다시 계산한다
function checkDate() {
  const today = todayKey();
  if (today === ui.today) return;
  ui.today = today;
  ui.editingId = null;
  renderAll();
}
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) checkDate();
});
setInterval(checkDate, 60_000);

/* ---------- 시작 ---------- */

const warnings = store.init();
store.subscribe(() => {
  applyTheme();
  renderAll();
});
applyTheme();
updateCounter();
renderAll();

if (warnings.includes('corrupt')) {
  showToast('저장된 데이터를 읽을 수 없어 새로 시작해요 (기존 데이터는 백업해 두었어요)');
}
