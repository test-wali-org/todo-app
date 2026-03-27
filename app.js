const STORAGE_KEY = "vanilla_todos_v1";

const todoForm = document.querySelector("#todo-form");
const todoInput = document.querySelector("#todo-input");
const todoList = document.querySelector("#todo-list");
const emptyState = document.querySelector("#empty-state");

let todos = loadTodos();

renderTodos();

todoForm.addEventListener("submit", (event) => {
  event.preventDefault();

  const text = todoInput.value.trim();
  if (!text) return;

  const todo = {
    id: crypto.randomUUID(),
    text,
    completed: false,
  };

  todos.unshift(todo);
  persistTodos();
  renderTodos();
  todoInput.value = "";
  todoInput.focus();
});

todoList.addEventListener("click", (event) => {
  const deleteButton = event.target.closest(".delete-btn");
  if (!deleteButton) return;

  const { id } = deleteButton.dataset;
  todos = todos.filter((todo) => todo.id !== id);
  persistTodos();
  renderTodos();
});

todoList.addEventListener("change", (event) => {
  const checkbox = event.target.closest('input[type="checkbox"]');
  if (!checkbox) return;

  const { id } = checkbox.dataset;
  todos = todos.map((todo) =>
    todo.id === id ? { ...todo, completed: checkbox.checked } : todo
  );
  persistTodos();
  renderTodos();
});

function loadTodos() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    console.error("Failed to load todos from storage", error);
    return [];
  }
}

function persistTodos() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(todos));
}

function renderTodos() {
  todoList.innerHTML = "";

  for (const todo of todos) {
    const item = document.createElement("li");
    item.className = `todo-item${todo.completed ? " completed" : ""}`;

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = todo.completed;
    checkbox.dataset.id = todo.id;
    checkbox.setAttribute("aria-label", `Mark "${todo.text}" complete`);

    const label = document.createElement("label");
    label.textContent = todo.text;

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "delete-btn";
    deleteButton.dataset.id = todo.id;
    deleteButton.textContent = "Delete";

    item.append(checkbox, label, deleteButton);
    todoList.append(item);
  }

  emptyState.classList.toggle("hidden", todos.length > 0);
}
