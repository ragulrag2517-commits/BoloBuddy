from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def initialize_database(db_path: str | Path, data_path: str | Path) -> None:
    data = json.loads(Path(data_path).read_text(encoding="utf-8"))
    with _connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS vocabulary (
                id TEXT PRIMARY KEY,
                english TEXT NOT NULL,
                category TEXT NOT NULL,
                emoji TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS translations (
                vocabulary_id TEXT NOT NULL REFERENCES vocabulary(id) ON DELETE CASCADE,
                language_code TEXT NOT NULL,
                translation TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected')),
                contributor TEXT NOT NULL DEFAULT '',
                reviewer TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (vocabulary_id, language_code)
            );
            CREATE TABLE IF NOT EXISTS contributions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vocabulary_id TEXT NOT NULL REFERENCES vocabulary(id) ON DELETE CASCADE,
                language_code TEXT NOT NULL,
                translation TEXT NOT NULL,
                contributor TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'approved', 'rejected')),
                reviewer TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_type TEXT NOT NULL,
                score INTEGER NOT NULL DEFAULT 0,
                stars INTEGER NOT NULL DEFAULT 0,
                details TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS offline_items (
                item_key TEXT PRIMARY KEY,
                item_type TEXT NOT NULL,
                content_json TEXT NOT NULL,
                saved_at TEXT NOT NULL
            );
            """
        )
        for word in data["words"]:
            connection.execute(
                "INSERT OR IGNORE INTO vocabulary(id, english, category, emoji) VALUES (?, ?, ?, ?)",
                (word["id"], word["en"], word["category"], word["emoji"]),
            )
            for language_code, translation in word["translations"].items():
                if translation and translation.get("status") == "approved":
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO translations
                            (vocabulary_id, language_code, translation, status, contributor, reviewer, source, notes, updated_at)
                        VALUES (?, ?, ?, 'approved', ?, ?, ?, ?, ?)
                        """,
                        (
                            word["id"],
                            language_code,
                            translation["text"],
                            translation.get("contributor", "BoloBuddy starter vocabulary"),
                            translation.get("reviewed_by", ""),
                            translation.get("source", ""),
                            translation.get("notes", ""),
                            _now(),
                        ),
                    )


def get_vocabulary(db_path: str | Path, language_code: str) -> list[dict[str, Any]]:
    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT v.id, v.english AS en, v.category, v.emoji, t.translation,
                   ht.translation AS hindi,
                   t.status, t.source, t.reviewer
            FROM vocabulary v
            JOIN translations t ON t.vocabulary_id = v.id
            LEFT JOIN translations ht ON ht.vocabulary_id = v.id
                AND ht.language_code = 'hi' AND ht.status = 'approved'
            WHERE t.language_code = ? AND t.status = 'approved'
            ORDER BY v.category, v.english COLLATE NOCASE
            """,
            (language_code,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_translations(db_path: str | Path, vocabulary_id: str) -> list[dict[str, Any]]:
    with _connect(db_path) as connection:
        rows = connection.execute(
            "SELECT language_code, translation, status, reviewer, source FROM translations WHERE vocabulary_id = ?",
            (vocabulary_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_vocabulary(
    db_path: str | Path,
    english: str,
    hindi: str,
    category: str,
    emoji: str,
    data_path: str | Path,
) -> str:
    english = english.strip()
    hindi = hindi.strip()
    category = category.strip()
    if not english or not category:
        raise ValueError("An English word and category are required.")
    word_id = re.sub(r"[^a-z0-9]+", "-", english.casefold()).strip("-")
    if not word_id:
        raise ValueError("The English word must include at least one letter or number.")
    with _connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO vocabulary(id, english, category, emoji) VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET english = excluded.english, category = excluded.category, emoji = excluded.emoji
            """,
            (word_id, english, category, emoji.strip() or "🌱"),
        )
        if hindi:
            connection.execute(
                """
                INSERT INTO translations
                    (vocabulary_id, language_code, translation, status, contributor, source, updated_at)
                VALUES (?, 'hi', ?, 'approved', 'Teacher', 'Teacher-added Hindi vocabulary', ?)
                ON CONFLICT(vocabulary_id, language_code) DO UPDATE SET
                    translation = excluded.translation, status = 'approved', updated_at = excluded.updated_at
                """,
                (word_id, hindi, _now()),
            )
    _write_language_json(db_path, data_path)
    return word_id


def submit_translation(
    db_path: str | Path,
    vocabulary_id: str,
    language_code: str,
    translation: str,
    contributor: str,
    notes: str = "",
) -> int:
    vocabulary_id = (vocabulary_id or "").strip()
    translation, contributor = translation.strip(), contributor.strip()
    if language_code not in {"sat", "hoc", "unr"}:
        raise ValueError("Community contributions must target Santhali, Ho, or Mundari.")
    if not vocabulary_id:
        raise ValueError("A vocabulary word is required.")
    if not translation or not contributor:
        raise ValueError("A translation and contributor name are required.")
    with _connect(db_path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM vocabulary WHERE id = ?",
            (vocabulary_id,),
        ).fetchone()
        if exists is None:
            raise ValueError("This vocabulary word does not exist.")
        cursor = connection.execute(
            """
            INSERT INTO contributions(vocabulary_id, language_code, translation, contributor, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (vocabulary_id, language_code, translation, contributor, notes.strip(), _now()),
        )
    return int(cursor.lastrowid)


def get_contributions(db_path: str | Path, status: str | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT c.id, c.vocabulary_id, c.language_code, c.translation, c.contributor,
               c.notes, c.status, c.reviewer, c.created_at, v.english
        FROM contributions c JOIN vocabulary v ON v.id = c.vocabulary_id
    """
    parameters: tuple[Any, ...] = ()
    if status:
        query += " WHERE c.status = ?"
        parameters = (status,)
    query += " ORDER BY c.created_at DESC, c.id DESC"
    with _connect(db_path) as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [dict(row) for row in rows]


def approve_translation(
    db_path: str | Path,
    contribution_id: int,
    reviewer: str,
    source: str,
    native_speaker_reviewed: bool,
    data_path: str | Path,
) -> None:
    reviewer, source = reviewer.strip(), source.strip()
    if not reviewer or not source or not native_speaker_reviewed:
        raise ValueError("Approval requires a reviewer, a source reference, and native-speaker review confirmation.")
    with _connect(db_path) as connection:
        contribution = connection.execute(
            "SELECT * FROM contributions WHERE id = ? AND status = 'pending'",
            (contribution_id,),
        ).fetchone()
        if contribution is None:
            raise ValueError("This translation is no longer waiting for review.")
        connection.execute(
            """
            INSERT INTO translations
                (vocabulary_id, language_code, translation, status, contributor, reviewer, source, notes, updated_at)
            VALUES (?, ?, ?, 'approved', ?, ?, ?, ?, ?)
            ON CONFLICT(vocabulary_id, language_code) DO UPDATE SET
                translation = excluded.translation, status = 'approved', contributor = excluded.contributor,
                reviewer = excluded.reviewer, source = excluded.source, notes = excluded.notes, updated_at = excluded.updated_at
            """,
            (
                contribution["vocabulary_id"],
                contribution["language_code"],
                contribution["translation"],
                contribution["contributor"],
                reviewer,
                source,
                contribution["notes"],
                _now(),
            ),
        )
        connection.execute(
            "UPDATE contributions SET status = 'approved', reviewer = ? WHERE id = ?",
            (reviewer, contribution_id),
        )
    _write_language_json(db_path, data_path)


def reject_translation(db_path: str | Path, contribution_id: int, reviewer: str) -> None:
    with _connect(db_path) as connection:
        cursor = connection.execute(
            "UPDATE contributions SET status = 'rejected', reviewer = ? WHERE id = ? AND status = 'pending'",
            (reviewer.strip(), contribution_id),
        )
        if cursor.rowcount == 0:
            raise ValueError("This translation is no longer waiting for review.")


def _write_language_json(db_path: str | Path, data_path: str | Path) -> None:
    data_file = Path(data_path)
    data = json.loads(data_file.read_text(encoding="utf-8"))
    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT v.id, t.language_code, t.translation, t.status, t.contributor, t.reviewer, t.source, t.notes
            FROM vocabulary v LEFT JOIN translations t ON t.vocabulary_id = v.id
            ORDER BY v.id
            """
        ).fetchall()
        vocabulary = connection.execute(
            "SELECT id, english, category, emoji FROM vocabulary ORDER BY id"
        ).fetchall()
    translations_by_id: dict[str, dict[str, dict[str, str]]] = {}
    for row in rows:
        if row["language_code"]:
            translations_by_id.setdefault(row["id"], {})[row["language_code"]] = {
                "text": row["translation"],
                "status": row["status"],
                "contributor": row["contributor"],
                "reviewed_by": row["reviewer"],
                "source": row["source"],
                "notes": row["notes"],
            }
    data["words"] = [
        {
            "id": row["id"],
            "en": row["english"],
            "category": row["category"],
            "emoji": row["emoji"],
            "translations": translations_by_id.get(row["id"], {}),
        }
        for row in vocabulary
    ]
    data_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record_activity(
    db_path: str | Path,
    activity_type: str,
    score: int,
    stars: int,
    details: str = "",
) -> None:
    with _connect(db_path) as connection:
        connection.execute(
            "INSERT INTO activities(activity_type, score, stars, details, created_at) VALUES (?, ?, ?, ?, ?)",
            (activity_type, max(0, score), max(0, stars), details, _now()),
        )


def get_activity_summary(db_path: str | Path) -> dict[str, int]:
    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS activities, COALESCE(SUM(score), 0) AS correct, COALESCE(SUM(stars), 0) AS stars FROM activities"
        ).fetchone()
    return dict(row)


def get_activity_history(db_path: str | Path) -> list[dict[str, Any]]:
    with _connect(db_path) as connection:
        rows = connection.execute(
            "SELECT activity_type, score, stars, details, created_at FROM activities ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def save_offline_item(
    db_path: str | Path,
    item_key: str,
    item_type: str,
    content: dict[str, Any],
) -> None:
    with _connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO offline_items(item_key, item_type, content_json, saved_at) VALUES (?, ?, ?, ?)
            ON CONFLICT(item_key) DO UPDATE SET
                item_type = excluded.item_type, content_json = excluded.content_json, saved_at = excluded.saved_at
            """,
            (item_key, item_type, json.dumps(content, ensure_ascii=False), _now()),
        )


def get_offline_items(db_path: str | Path) -> list[dict[str, Any]]:
    with _connect(db_path) as connection:
        rows = connection.execute(
            "SELECT item_key, item_type, content_json, saved_at FROM offline_items ORDER BY saved_at DESC"
        ).fetchall()
    return [
        {
            "key": row["item_key"],
            "type": row["item_type"],
            "content": json.loads(row["content_json"]),
            "saved_at": row["saved_at"],
        }
        for row in rows
    ]


def remove_offline_item(db_path: str | Path, item_key: str) -> None:
    with _connect(db_path) as connection:
        connection.execute("DELETE FROM offline_items WHERE item_key = ?", (item_key,))
