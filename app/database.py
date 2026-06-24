import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "personal_context.sqlite3"


def database_path() -> Path:
    return Path(os.environ.get("PCA_DB_PATH", DEFAULT_DB_PATH)).resolve()


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT '',
                preferences TEXT NOT NULL DEFAULT '',
                communication_style TEXT NOT NULL DEFAULT '',
                long_term_context TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS project_profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                goal TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT '',
                stack TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS issue_progress (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                title TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'active',
                priority TEXT NOT NULL DEFAULT 'medium',
                current_step TEXT NOT NULL DEFAULT '',
                next_action TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES project_profiles(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS error_records (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                title TEXT NOT NULL,
                environment TEXT NOT NULL DEFAULT '',
                symptom TEXT NOT NULL DEFAULT '',
                root_cause TEXT NOT NULL DEFAULT '',
                fix TEXT NOT NULL DEFAULT '',
                prevention TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES project_profiles(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS prompt_templates (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]

