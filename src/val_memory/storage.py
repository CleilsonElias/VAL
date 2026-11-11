"""Versioned SQLite JSON snapshots; no pickle or executable deserialization."""

from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path
import sqlite3

from .core import VALMemory
from .maths import positive_int


class RevisionConflict(RuntimeError):
    pass


class SQLiteStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> tuple[VALMemory, int]:
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
            row = connection.execute("SELECT revision, payload FROM val_state WHERE id=1").fetchone()
        if row is None:
            raise ValueError("state has not been initialized")
        return VALMemory.restore(json.loads(row[1])), row[0]

    def save(self, engine: VALMemory, *, expected_revision: int) -> int:
        positive_int(expected_revision, "expected_revision", allow_zero=True)
        payload = json.dumps(engine.snapshot(), ensure_ascii=False, allow_nan=False)
        with closing(sqlite3.connect(self.path, timeout=15)) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("CREATE TABLE IF NOT EXISTS val_state "
                                   "(id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, payload TEXT NOT NULL)")
                row = connection.execute("SELECT revision FROM val_state WHERE id=1").fetchone()
                current = row[0] if row else 0
                if current != expected_revision:
                    raise RevisionConflict(f"expected revision {expected_revision}, found {current}")
                revision = current + 1
                connection.execute("INSERT INTO val_state VALUES(1,?,?) ON CONFLICT(id) DO UPDATE "
                                   "SET revision=excluded.revision, payload=excluded.payload", (revision, payload))
        return revision

