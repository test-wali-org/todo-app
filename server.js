const express = require("express");
const path = require("path");
const crypto = require("crypto");

const app = express();
const PORT = process.env.PORT || 3000;

let todos = [];

app.use(express.json());
app.use(express.static(path.join(__dirname)));

app.get("/api/todos", (_req, res) => {
  res.json(todos);
});

app.post("/api/todos", (req, res) => {
  const text = req.body?.text?.trim();
  if (!text) {
    return res.status(400).json({ error: "Todo text is required." });
  }

  const todo = {
    id: crypto.randomUUID(),
    text,
    completed: false,
  };

  todos.unshift(todo);
  return res.status(201).json(todo);
});

app.patch("/api/todos/:id", (req, res) => {
  const { id } = req.params;
  const index = todos.findIndex((todo) => todo.id === id);
  if (index === -1) {
    return res.status(404).json({ error: "Todo not found." });
  }

  const updated = {
    ...todos[index],
    ...(typeof req.body?.text === "string" ? { text: req.body.text.trim() } : {}),
    ...(typeof req.body?.completed === "boolean"
      ? { completed: req.body.completed }
      : {}),
  };

  if (!updated.text) {
    return res.status(400).json({ error: "Todo text cannot be empty." });
  }

  todos[index] = updated;
  return res.json(updated);
});

app.delete("/api/todos/:id", (req, res) => {
  const { id } = req.params;
  const existingLength = todos.length;
  todos = todos.filter((todo) => todo.id !== id);

  if (todos.length === existingLength) {
    return res.status(404).json({ error: "Todo not found." });
  }

  return res.status(204).send();
});

app.listen(PORT, () => {
  console.log(`Todo server running at http://localhost:${PORT}`);
});
