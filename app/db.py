import sqlite3
import json
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
import os

DB_PATH = os.getenv("DB_PATH", "data/traces.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    input TEXT NOT NULL,
    output TEXT NOT NULL,
    tool_calls TEXT,
    latency_ms INTEGER,
    cost_usd REAL,
    git_sha TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    expected TEXT,
    added_at TEXT NOT NULL,
    FOREIGN KEY (trace_id) REFERENCES traces(id)
);
CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    commit_sha TEXT,
    score REAL,
    reason TEXT,
    regression INTEGER,
    graded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_traces_agent ON traces(agent_id);
CREATE INDEX IF NOT EXISTS idx_grades_agent ON grades(agent_id);
"""

def _ensure_dir():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

@contextmanager
def get_db():
    _ensure_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
