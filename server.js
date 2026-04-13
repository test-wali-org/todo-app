const express = require("express");
const path = require("path");
const crypto = require("crypto");
const TodoStore = require("./todoStore");

const app = express();
const PORT = process.env.PORT || 3000;

const todoStore = new TodoStore(path.join(__dirname, "todos.json"));

app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

app.get("/api/todos", (_req, res) => {
  res.json(todoStore.getAll());
});

app.post("/api/todos", (req, res) => {
  let text = req.body?.text;
  if (typeof text !== "string") {
    return res.status(400).json({ error: "Todo text is required." });
  }

  text = text.trim();
  if (!text) {
    return res.status(400).json({ error: "Todo text is required." });
  }

  const todo = {
    id: crypto.randomUUID(),
    text,
    completed: false,
  };

  todoStore.create(todo);
  return res.status(201).json(todo);
});

app.patch("/api/todos/:id", (req, res) => {
  const { id } = req.params;
  const existingTodo = todoStore.getById(id);
  if (!existingTodo) {
    return res.status(404).json({ error: "Todo not found." });
  }

  const updated = {
    ...existingTodo,
    ...(typeof req.body?.text === "string" ? { text: req.body.text.trim() } : {}),
    ...(typeof req.body?.completed === "boolean"
      ? { completed: req.body.completed }
      : {}),
  };

  if (!updated.text) {
    return res.status(400).json({ error: "Todo text cannot be empty." });
  }

  todoStore.update(id, updated);
  return res.json(updated);
});

app.delete("/api/todos/:id", (req, res) => {
  const { id } = req.params;
  const deleted = todoStore.delete(id);

  if (!deleted) {
    return res.status(404).json({ error: "Todo not found." });
  }

  return res.status(204).send();
});

app.listen(PORT, () => {
  console.log(`Todo server running at http://localhost:${PORT}`);
});