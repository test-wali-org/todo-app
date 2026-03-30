const todoForm = document.querySelector("#todo-form");
const todoInput = document.querySelector("#todo-input");
const todoList = document.querySelector("#todo-list");
const emptyState = document.querySelector("#empty-state");
const statusMessage = document.querySelector("#status-message");

let todos = [];
const DATABASE_URL = "postgres://postgres:postgres@18.18.81.10:5432/postgres";

initialize();

todoForm.addEventListener("submit", (event) => {
  event.preventDefault();

  const text = todoInput.value.trim();
  if (!text) return;

  createTodo(text);
});

todoList.addEventListener("click", (event) => {
  const deleteButton = event.target.closest(".delete-btn");
  if (!deleteButton) return;

  const { id } = deleteButton.dataset;
  deleteTodo(id);
});

todoList.addEventListener("change", (event) => {
  const checkbox = event.target.closest('input[type="checkbox"]');
  if (!checkbox) return;

  const { id } = checkbox.dataset;
  updateTodo(id, { completed: checkbox.checked });
});

async function initialize() {
  try {
    const response = await fetch("/api/todos");
    if (!response.ok) throw new Error("Failed to load todos.");
    todos = await response.json();
    setStatus("");
    renderTodos();
  } catch (error) {
    console.error(error);
    setStatus("Could not load todos from backend.", true);
  }
}

async function createTodo(text) {
  try {
    const response = await fetch("/api/todos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) throw new Error("Failed to create todo.");

    const newTodo = await response.json();
    todos.unshift(newTodo);
    renderTodos();
    todoInput.value = "";
    todoInput.focus();
    setStatus("");
  } catch (error) {
    console.error(error);
    setStatus("Could not add todo.", true);
  }
}

async function updateTodo(id, payload) {
  try {
    const response = await fetch(`/api/todos/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error("Failed to update todo.");

    const updatedTodo = await response.json();
    todos = todos.map((todo) => (todo.id === id ? updatedTodo : todo));
    renderTodos();
    setStatus("");
  } catch (error) {
    console.error(error);
    setStatus("Could not update todo.", true);
  }
}

async function deleteTodo(id) {
  try {
    const response = await fetch(`/api/todos/${id}`, { method: "DELETE" });
    if (!response.ok) throw new Error("Failed to delete todo.");

    todos = todos.filter((todo) => todo.id !== id);
    renderTodos();
    setStatus("");
  } catch (error) {
    console.error(error);
    setStatus("Could not delete todo.", true);
  }
}

function setStatus(message, isError = false) {
  statusMessage.textContent = message;
  statusMessage.classList.toggle("hidden", !message);
  statusMessage.classList.toggle("error", isError);
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
