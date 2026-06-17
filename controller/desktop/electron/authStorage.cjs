const fs = require("node:fs");
const path = require("node:path");
const { app } = require("electron");

/** @type {Record<string, string> | null} */
let cache = null;

function storagePath() {
  return path.join(app.getPath("userData"), "supabase-auth-storage.json");
}

function loadStore() {
  if (cache) {
    return cache;
  }
  try {
    const raw = fs.readFileSync(storagePath(), "utf8");
    cache = JSON.parse(raw);
    if (!cache || typeof cache !== "object") {
      cache = {};
    }
  } catch {
    cache = {};
  }
  return cache;
}

function persistStore() {
  const file = storagePath();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(cache ?? {}, null, 0), "utf8");
}

function getItem(key) {
  const store = loadStore();
  return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null;
}

function setItem(key, value) {
  const store = loadStore();
  store[key] = value;
  persistStore();
}

function removeItem(key) {
  const store = loadStore();
  delete store[key];
  persistStore();
}

module.exports = { getItem, setItem, removeItem, storagePath };
