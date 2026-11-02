import * as T from './todo.js';

const KEY = 'todolist:v1';
const BACKUP_KEY = 'todolist:v1:backup';

const initialState = () => ({
  version: 1,
  todos: [],
  settings: {
    theme: 'system',        // 'system' | 'light' | 'dark'
    carryDismissedOn: null, // 이월 배너에서 '무시'를 누른 날짜
  },
});

let state = initialState();
let persistent = true;
const listeners = new Set();

const isValidTodo = (t) =>
  t && typeof t.id === 'string' && typeof t.text === 'string' && typeof t.date === 'string';

function normalize(data) {
  if (!data || data.version !== 1 || !Array.isArray(data.todos)) throw new Error('invalid state');
  const base = initialState();
  return {
    ...base,
    todos: data.todos.filter(isValidTodo).map((t, i) => ({
      done: false, important: false, order: i, createdAt: 0, completedAt: null, ...t,
    })),
    settings: { ...base.settings, ...data.settings },
  };
}

// 저장된 상태를 읽는다. 문제가 있으면 경고 코드 목록을 돌려준다.
export function init() {
  let raw;
  try {
    localStorage.setItem(`${KEY}:probe`, '1');
    localStorage.removeItem(`${KEY}:probe`);
    raw = localStorage.getItem(KEY);
  } catch {
    persistent = false;
    return ['unavailable'];
  }
  if (raw === null) return [];
  try {
    state = normalize(JSON.parse(raw));
    return [];
  } catch {
    try {
      localStorage.setItem(BACKUP_KEY, raw);
      localStorage.removeItem(KEY);
    } catch {}
    return ['corrupt'];
  }
}

function save() {
  if (!persistent) return;
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    persistent = false;
  }
}

const withTodos = (s, todos) => (todos === s.todos ? s : { ...s, todos });
const withSettings = (s, patch) => ({ ...s, settings: { ...s.settings, ...patch } });

function reduce(s, a) {
  switch (a.type) {
    case 'ADD': return withTodos(s, T.addTodo(s.todos, a));
    case 'TOGGLE': return withTodos(s, T.toggleTodo(s.todos, a.id));
    case 'EDIT': return withTodos(s, T.editTodo(s.todos, a.id, a.text));
    case 'DELETE': return withTodos(s, T.deleteTodo(s.todos, a.id));
    case 'RESTORE': return withTodos(s, T.restoreTodos(s.todos, a.todos));
    case 'CLEAR_DONE': return withTodos(s, T.clearDone(s.todos, a.date));
    case 'TOGGLE_IMPORTANT': return withTodos(s, T.toggleImportant(s.todos, a.id));
    case 'REORDER': return withTodos(s, T.reorder(s.todos, a.ids));
    case 'CARRY_OVER': return withTodos(s, T.carryOver(s.todos, a.today));
    case 'DISMISS_CARRY':
      return s.settings.carryDismissedOn === a.today ? s : withSettings(s, { carryDismissedOn: a.today });
    case 'SET_THEME':
      return s.settings.theme === a.theme ? s : withSettings(s, { theme: a.theme });
    default: return s;
  }
}

export const getState = () => state;
export const isPersistent = () => persistent;

// 상태가 바뀌었으면 저장하고 구독자에게 알린 뒤 true를 돌려준다
export function dispatch(action) {
  const next = reduce(state, action);
  if (next === state) return false;
  state = next;
  save();
  listeners.forEach((fn) => fn(state));
  return true;
}

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
