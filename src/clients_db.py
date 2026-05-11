"""
Navigator client store — SQLite.

Demo-grade: caseworker_id is trusted from the client (localStorage UUID).
TODO: real caseworker auth (SSO / org-scoped identity). When that lands,
caseworker_id should be derived server-side from an authenticated session
and these functions should reject mismatched or absent identities.
"""

import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from typing import Optional

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'navigator.db'
)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id            TEXT PRIMARY KEY,
    caseworker_id TEXT NOT NULL,
    name          TEXT NOT NULL,
    state         TEXT,
    intake_json   TEXT,
    plan_json     TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    archived_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_clients_caseworker ON clients(caseworker_id);
CREATE INDEX IF NOT EXISTS idx_clients_active     ON clients(caseworker_id, archived_at);
"""


@contextmanager
def _conn(db_path):
    path = db_path or DEFAULT_DB_PATH
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db(db_path: Optional[str] = None) -> None:
    with _conn(db_path) as c:
        c.executescript(_SCHEMA)


def _gen_id() -> str:
    return 'CL-' + secrets.token_hex(3).upper()


def _dump_json(obj):
    if obj is None:
        return None
    return json.dumps(obj)


def _load_json(s):
    if s is None or s == '':
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return None


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        'id': row['id'],
        'caseworker_id': row['caseworker_id'],
        'name': row['name'],
        'state': row['state'],
        'intake': _load_json(row['intake_json']),
        'plan': _load_json(row['plan_json']),
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
        'archived_at': row['archived_at'],
    }


def create_client(caseworker_id: str, name: str, state: Optional[str] = None,
                  intake: Optional[dict] = None, plan: Optional[dict] = None,
                  db_path: Optional[str] = None) -> dict:
    init_db(db_path)
    new_id = _gen_id()
    with _conn(db_path) as c:
        # On the astronomically rare chance of collision, retry.
        for _ in range(5):
            try:
                c.execute(
                    "INSERT INTO clients (id, caseworker_id, name, state, intake_json, plan_json) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (new_id, caseworker_id, name, state, _dump_json(intake), _dump_json(plan)),
                )
                break
            except sqlite3.IntegrityError:
                new_id = _gen_id()
        row = c.execute("SELECT * FROM clients WHERE id = ?", (new_id,)).fetchone()
    return _row_to_dict(row)


def get_client(client_id: str, db_path: Optional[str] = None) -> Optional[dict]:
    init_db(db_path)
    with _conn(db_path) as c:
        row = c.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_clients(caseworker_id: str, include_archived: bool = False,
                 db_path: Optional[str] = None) -> list:
    init_db(db_path)
    with _conn(db_path) as c:
        if include_archived:
            rows = c.execute(
                "SELECT * FROM clients WHERE caseworker_id = ? ORDER BY updated_at DESC",
                (caseworker_id,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM clients WHERE caseworker_id = ? AND archived_at IS NULL "
                "ORDER BY updated_at DESC",
                (caseworker_id,),
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


_UNSET = object()


def update_client(client_id: str, *,
                  name=_UNSET, state=_UNSET, intake=_UNSET, plan=_UNSET,
                  db_path: Optional[str] = None) -> Optional[dict]:
    init_db(db_path)
    sets = []
    params = []
    if name is not _UNSET:
        sets.append("name = ?")
        params.append(name)
    if state is not _UNSET:
        sets.append("state = ?")
        params.append(state)
    if intake is not _UNSET:
        sets.append("intake_json = ?")
        params.append(_dump_json(intake))
    if plan is not _UNSET:
        sets.append("plan_json = ?")
        params.append(_dump_json(plan))
    if not sets:
        return get_client(client_id, db_path=db_path)
    sets.append("updated_at = datetime('now')")
    params.append(client_id)
    with _conn(db_path) as c:
        cur = c.execute(
            "UPDATE clients SET " + ", ".join(sets) + " WHERE id = ?",
            params,
        )
        if cur.rowcount == 0:
            return None
        row = c.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    return _row_to_dict(row) if row else None


def archive_client(client_id: str, db_path: Optional[str] = None) -> Optional[dict]:
    init_db(db_path)
    with _conn(db_path) as c:
        cur = c.execute(
            "UPDATE clients SET archived_at = datetime('now'), updated_at = datetime('now') "
            "WHERE id = ? AND archived_at IS NULL",
            (client_id,),
        )
        if cur.rowcount == 0:
            row = c.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
            return _row_to_dict(row) if row else None
        row = c.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    return _row_to_dict(row) if row else None


def unarchive_client(client_id: str, db_path: Optional[str] = None) -> Optional[dict]:
    init_db(db_path)
    with _conn(db_path) as c:
        cur = c.execute(
            "UPDATE clients SET archived_at = NULL, updated_at = datetime('now') "
            "WHERE id = ?",
            (client_id,),
        )
        if cur.rowcount == 0:
            return None
        row = c.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    return _row_to_dict(row) if row else None
