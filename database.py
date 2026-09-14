import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "clan.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS name_aliases (
            raw_name TEXT PRIMARY KEY,
            player_id INTEGER NOT NULL,
            FOREIGN KEY (player_id) REFERENCES players(id)
        );

        CREATE TABLE IF NOT EXISTS chest_points (
            source TEXT PRIMARY KEY,
            points INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS chest_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            chest_name TEXT,
            source TEXT NOT NULL,
            batch_id TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (player_id) REFERENCES players(id)
        );
        """
    )
    conn.commit()
    conn.close()


def upsert_player(name):
    """Retorna o id do jogador, criando se não existir."""
    conn = get_db()
    row = conn.execute("SELECT id FROM players WHERE name = ?", (name,)).fetchone()
    if row:
        conn.close()
        return row["id"]
    cur = conn.execute(
        "INSERT INTO players (name, active, created_at) VALUES (?, 1, ?)",
        (name, datetime.utcnow().isoformat()),
    )
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid


def list_players(active_only=True):
    conn = get_db()
    q = "SELECT * FROM players"
    if active_only:
        q += " WHERE active = 1"
    q += " ORDER BY name COLLATE NOCASE"
    rows = conn.execute(q).fetchall()
    conn.close()
    return rows


def set_player_active(player_id, active):
    conn = get_db()
    conn.execute("UPDATE players SET active = ? WHERE id = ?", (1 if active else 0, player_id))
    conn.commit()
    conn.close()


def delete_player(player_id):
    conn = get_db()
    conn.execute("DELETE FROM players WHERE id = ?", (player_id,))
    conn.commit()
    conn.close()


def add_chest_event(player_name, chest_name, source, batch_id=None):
    player_id = upsert_player(player_name)
    conn = get_db()
    conn.execute(
        "INSERT INTO chest_events (player_id, chest_name, source, batch_id, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (player_id, chest_name, source, batch_id, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_chest_points():
    conn = get_db()
    rows = conn.execute("SELECT * FROM chest_points ORDER BY source").fetchall()
    conn.close()
    return rows


def set_chest_points(source, points):
    conn = get_db()
    conn.execute(
        "INSERT INTO chest_points (source, points) VALUES (?, ?) "
        "ON CONFLICT(source) DO UPDATE SET points = excluded.points",
        (source, points),
    )
    conn.commit()
    conn.close()


def get_ranking():
    """Soma pontos por jogador: contagem de baus por fonte * pontos da fonte."""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT p.id, p.name,
               COUNT(ce.id) AS total_baus,
               COALESCE(SUM(cp.points), 0) AS total_pontos
        FROM players p
        LEFT JOIN chest_events ce ON ce.player_id = p.id
        LEFT JOIN chest_points cp ON cp.source = ce.source
        WHERE p.active = 1
        GROUP BY p.id
        ORDER BY total_pontos DESC, total_baus DESC
        """
    ).fetchall()
    conn.close()
    return rows


def get_player_breakdown(player_id):
    conn = get_db()
    rows = conn.execute(
        """
        SELECT ce.source, COUNT(*) AS qtd, COALESCE(cp.points, 0) AS pontos_unit
        FROM chest_events ce
        LEFT JOIN chest_points cp ON cp.source = ce.source
        WHERE ce.player_id = ?
        GROUP BY ce.source
        ORDER BY qtd DESC
        """,
        (player_id,),
    ).fetchall()
    conn.close()
    return rows
