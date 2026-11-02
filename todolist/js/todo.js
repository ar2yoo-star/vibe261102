// 할일 목록을 다루는 순수 함수 모음.
// 변경이 없으면 입력 배열을 그대로 돌려줘서 store가 불필요한 저장·렌더를 건너뛸 수 있게 한다.

export const MAX_LEN = 100;

export function newId() {
  if (globalThis.crypto && crypto.randomUUID) return crypto.randomUUID();
  return Date.now().toString(36) + Math.random().toString(36).slice(2);
}

export function normalizeText(text) {
  return String(text ?? '').trim().slice(0, MAX_LEN);
}

const nextOrder = (todos, date) =>
  todos.reduce((max, t) => (t.date === date && t.order > max ? t.order : max), -1) + 1;

function update(todos, id, fn) {
  let changed = false;
  const next = todos.map((t) => {
    if (t.id !== id) return t;
    const updated = fn(t);
    if (updated !== t) changed = true;
    return updated;
  });
  return changed ? next : todos;
}

function without(todos, predicate) {
  const next = todos.filter((t) => !predicate(t));
  return next.length === todos.length ? todos : next;
}

export function addTodo(todos, { id = newId(), text, date, now = Date.now() }) {
  const clean = normalizeText(text);
  if (!clean) return todos;
  return [...todos, {
    id,
    text: clean,
    done: false,
    important: false,
    date,
    order: nextOrder(todos, date),
    createdAt: now,
    completedAt: null,
  }];
}

export const toggleTodo = (todos, id, now = Date.now()) =>
  update(todos, id, (t) => ({ ...t, done: !t.done, completedAt: t.done ? null : now }));

export function editTodo(todos, id, text) {
  const clean = normalizeText(text);
  return update(todos, id, (t) => (!clean || clean === t.text ? t : { ...t, text: clean }));
}

export const toggleImportant = (todos, id) =>
  update(todos, id, (t) => ({ ...t, important: !t.important }));

export const deleteTodo = (todos, id) => without(todos, (t) => t.id === id);

export const clearDone = (todos, date) => without(todos, (t) => t.date === date && t.done);

export function restoreTodos(todos, removed) {
  const existing = new Set(todos.map((t) => t.id));
  const back = removed.filter((t) => !existing.has(t.id));
  return back.length ? [...todos, ...back] : todos;
}

// ids 순서대로 정렬되도록, 해당 항목들이 원래 갖고 있던 order 값을 다시 나눠 준다.
// 필터로 일부만 보이는 상태에서 옮겨도 숨은 항목의 위치는 바뀌지 않는다.
export function reorder(todos, ids) {
  const targets = new Set(ids);
  const pool = todos.filter((t) => targets.has(t.id)).map((t) => t.order).sort((a, b) => a - b);
  if (pool.length !== ids.length) return todos;
  const orderOf = new Map(ids.map((id, i) => [id, pool[i]]));
  let changed = false;
  const next = todos.map((t) => {
    const order = orderOf.get(t.id);
    if (order === undefined || order === t.order) return t;
    changed = true;
    return { ...t, order };
  });
  return changed ? next : todos;
}

const byDateThenOrder = (a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : a.order - b.order);

export const pendingFromPast = (todos, today) =>
  todos.filter((t) => !t.done && t.date < today).sort(byDateThenOrder);

// 지난 날짜의 미완료 항목을 오늘로 옮긴다 (오늘 목록의 맨 뒤에 붙음)
export function carryOver(todos, today) {
  const pending = pendingFromPast(todos, today);
  if (!pending.length) return todos;
  const start = nextOrder(todos, today);
  const orderOf = new Map(pending.map((t, i) => [t.id, start + i]));
  return todos.map((t) => (orderOf.has(t.id) ? { ...t, date: today, order: orderOf.get(t.id) } : t));
}

const FILTERS = {
  all: () => true,
  active: (t) => !t.done,
  done: (t) => t.done,
};

// 해당 날짜의 할일을 필터링하고, 중요 항목을 위로 올려 정렬한다
export function selectDay(todos, date, filter = 'all') {
  const match = FILTERS[filter] ?? FILTERS.all;
  return todos
    .filter((t) => t.date === date && match(t))
    .sort((a, b) => (b.important - a.important) || (a.order - b.order));
}
