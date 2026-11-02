import { formatKey, addDays } from './date.js';
import { selectDay, pendingFromPast, MAX_LEN } from './todo.js';

const EMPTY_TEXT = {
  all: '오늘 할 일을 추가해 보세요',
  active: '남은 일이 없어요. 수고했어요!',
  done: '아직 완료한 일이 없어요',
};

function el(tag, className, props = {}) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  return Object.assign(node, props);
}

function ctrl(className, label, symbol) {
  const button = el('button', `ctrl ${className}`, { type: 'button', textContent: symbol });
  button.setAttribute('aria-label', label);
  button.title = label.split(':')[0];
  return button;
}

function renderItem(todo, ui) {
  const li = el('li', 'item');
  li.dataset.id = todo.id;
  li.classList.toggle('done', todo.done);
  li.classList.toggle('important', todo.important);
  li.classList.toggle('is-new', todo.id === ui.newId);

  const handle = ctrl('handle', `순서 이동: ${todo.text}`, '⠿');
  handle.title = '드래그해서 순서 변경 (Alt+↑↓)';

  const check = el('label', 'check');
  const box = el('input', 'toggle', { type: 'checkbox', checked: todo.done });
  box.setAttribute('aria-label', `완료: ${todo.text}`);
  check.append(box);

  const star = ctrl('star', `중요 표시: ${todo.text}`, todo.important ? '★' : '☆');
  star.setAttribute('aria-pressed', String(todo.important));

  let body;
  if (todo.id === ui.editingId) {
    body = el('input', 'edit', { type: 'text', value: todo.text, maxLength: MAX_LEN });
    body.setAttribute('aria-label', '할일 수정 (Enter 저장, Esc 취소)');
  } else {
    // 사용자 입력은 textContent로만 넣는다 (XSS 방지)
    body = el('span', 'text', { textContent: todo.text });
  }

  const actions = el('div', 'actions');
  actions.append(
    ctrl('edit-btn', `수정: ${todo.text}`, '✎'),
    ctrl('delete', `삭제: ${todo.text}`, '✕'),
  );

  li.append(handle, check, star, body, actions);
  return li;
}

export function render(state, ui, els) {
  const day = state.todos.filter((t) => t.date === ui.today);
  const total = day.length;
  const doneCount = day.filter((t) => t.done).length;
  const pct = total ? Math.round((doneCount / total) * 100) : 0;

  els.todayLabel.textContent = formatKey(ui.today);
  document.title = `오늘의 할일 (${doneCount}/${total})`;

  els.progressText.textContent = `완료 ${doneCount} / 전체 ${total}`;
  els.progressPct.textContent = `${pct}%`;
  els.progressFill.style.width = `${pct}%`;
  els.progressBar.setAttribute('aria-valuenow', String(pct));

  for (const link of els.filterLinks) {
    const active = link.dataset.filter === ui.filter;
    link.classList.toggle('active', active);
    if (active) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }

  const visible = selectDay(state.todos, ui.today, ui.filter);
  els.list.replaceChildren(...visible.map((t) => renderItem(t, ui)));
  els.empty.hidden = visible.length > 0;
  els.empty.textContent = total === 0 ? EMPTY_TEXT.all : EMPTY_TEXT[ui.filter];

  els.clearDone.disabled = doneCount === 0;

  const pending = pendingFromPast(state.todos, ui.today);
  const showCarry = pending.length > 0 && state.settings.carryDismissedOn !== ui.today;
  els.carryBanner.hidden = !showCarry;
  if (showCarry) {
    const yesterday = addDays(ui.today, -1);
    const when = pending.every((t) => t.date === yesterday) ? '어제' : '지난날';
    els.carryText.textContent = `${when} 끝내지 못한 일 ${pending.length}개가 있어요`;
  }
}
