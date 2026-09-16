import os
import time
from datetime import datetime

import psycopg2
import psycopg2.extras

from cycle import current_cycle_start, previous_cycle_bounds

DATABASE_URL = os.environ.get("DATABASE_URL", "")

VALID_LEVELS = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10"]


def get_db():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL não configurada. Defina essa variável de ambiente com a "
            "string de conexão do seu banco Postgres (veja MANUAL.md, seção 'Banco de dados')."
        )
    ultima_falha = None
    for tentativa in range(3):
        try:
            return psycopg2.connect(DATABASE_URL)
        except psycopg2.OperationalError as e:
            ultima_falha = e
            # o banco pode estar "acordando" de um período de inatividade -
            # espera um pouco e tenta de novo antes de desistir
            time.sleep(1.5 * (tentativa + 1))
    raise ultima_falha


def _cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


def init_db():
    conn = get_db()
    cur = _cursor(conn)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS players (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            level TEXT,
            created_at TEXT NOT NULL
        );

        ALTER TABLE players ADD COLUMN IF NOT EXISTS level TEXT;

        CREATE TABLE IF NOT EXISTS level_goals (
            level TEXT PRIMARY KEY,
            goal_points INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS name_aliases (
            raw_name TEXT PRIMARY KEY,
            player_id INTEGER NOT NULL REFERENCES players(id)
        );

        CREATE TABLE IF NOT EXISTS chest_points (
            source TEXT PRIMARY KEY,
            points INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS chest_events (
            id SERIAL PRIMARY KEY,
            player_id INTEGER NOT NULL REFERENCES players(id),
            chest_name TEXT,
            source TEXT NOT NULL,
            batch_id TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS weekly_archive (
            id SERIAL PRIMARY KEY,
            week_label TEXT NOT NULL,
            player_name TEXT NOT NULL,
            total_baus INTEGER NOT NULL,
            total_pontos INTEGER NOT NULL,
            closed_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    cur.close()
    conn.close()


def upsert_player(name, conn=None):
    """Retorna o id do jogador, criando se não existir.
    Se `conn` for passado, reaproveita a conexão em vez de abrir uma nova
    (usado pelos envios em lote, pra não abrir dezenas de conexões seguidas)."""
    own_conn = conn is None
    if own_conn:
        conn = get_db()
    cur = _cursor(conn)
    cur.execute("SELECT id FROM players WHERE name = %s", (name,))
    row = cur.fetchone()
    if row:
        pid = row["id"]
    else:
        cur.execute(
            "INSERT INTO players (name, active, created_at) VALUES (%s, 1, %s) RETURNING id",
            (name, datetime.utcnow().isoformat()),
        )
        pid = cur.fetchone()["id"]
        if own_conn:
            conn.commit()
    cur.close()
    if own_conn:
        conn.close()
    return pid


def add_chest_events_batch(player_names_chests, batch_id=None):
    """Lança vários eventos de baú de uma vez usando UMA única conexão,
    em vez de abrir/fechar conexão pra cada jogador/baú separadamente.

    player_names_chests: lista de tuplas (player_name, chest_name, source)."""
    if not player_names_chests:
        return
    conn = get_db()
    now = datetime.utcnow().isoformat()
    try:
        for player_name, chest_name, source in player_names_chests:
            pid = upsert_player(player_name, conn=conn)
            cur = _cursor(conn)
            cur.execute(
                "INSERT INTO chest_events (player_id, chest_name, source, batch_id, created_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                (pid, chest_name, source, batch_id, now),
            )
            cur.close()
        conn.commit()
    finally:
        conn.close()


def upsert_players_batch(names):
    """Cadastra vários jogadores de uma vez usando UMA única conexão."""
    if not names:
        return
    conn = get_db()
    try:
        for name in names:
            upsert_player(name, conn=conn)
        conn.commit()
    finally:
        conn.close()


def list_players(active_only=True):
    conn = get_db()
    cur = _cursor(conn)
    q = "SELECT * FROM players"
    if active_only:
        q += " WHERE active = 1"
    q += " ORDER BY LOWER(name)"
    cur.execute(q)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def set_player_active(player_id, active):
    conn = get_db()
    cur = _cursor(conn)
    cur.execute("UPDATE players SET active = %s WHERE id = %s", (1 if active else 0, player_id))
    conn.commit()
    cur.close()
    conn.close()


def set_player_level(player_id, level):
    if level not in VALID_LEVELS and level != "":
        raise ValueError(f"Nível inválido: {level}")
    conn = get_db()
    cur = _cursor(conn)
    cur.execute("UPDATE players SET level = %s WHERE id = %s", (level or None, player_id))
    conn.commit()
    cur.close()
    conn.close()


def get_level_goals():
    conn = get_db()
    cur = _cursor(conn)
    cur.execute("SELECT * FROM level_goals")
    rows = {r["level"]: r["goal_points"] for r in cur.fetchall()}
    cur.close()
    conn.close()
    return rows


def set_level_goal(level, goal_points):
    if level not in VALID_LEVELS:
        raise ValueError(f"Nível inválido: {level}")
    conn = get_db()
    cur = _cursor(conn)
    cur.execute(
        "INSERT INTO level_goals (level, goal_points) VALUES (%s, %s) "
        "ON CONFLICT (level) DO UPDATE SET goal_points = excluded.goal_points",
        (level, goal_points),
    )
    conn.commit()
    cur.close()
    conn.close()


def delete_player(player_id):
    conn = get_db()
    cur = _cursor(conn)
    cur.execute("DELETE FROM players WHERE id = %s", (player_id,))
    conn.commit()
    cur.close()
    conn.close()


def add_chest_event(player_name, chest_name, source, batch_id=None):
    player_id = upsert_player(player_name)
    conn = get_db()
    cur = _cursor(conn)
    cur.execute(
        "INSERT INTO chest_events (player_id, chest_name, source, batch_id, created_at) "
        "VALUES (%s, %s, %s, %s, %s)",
        (player_id, chest_name, source, batch_id, datetime.utcnow().isoformat()),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_chest_points():
    conn = get_db()
    cur = _cursor(conn)
    cur.execute("SELECT * FROM chest_points ORDER BY source")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def set_chest_points(source, points):
    conn = get_db()
    cur = _cursor(conn)
    cur.execute(
        "INSERT INTO chest_points (source, points) VALUES (%s, %s) "
        "ON CONFLICT (source) DO UPDATE SET points = excluded.points",
        (source, points),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_setting(key, default=None):
    conn = get_db()
    cur = _cursor(conn)
    cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_db()
    cur = _cursor(conn)
    cur.execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) "
        "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
    cur.close()
    conn.close()


def get_period_start():
    return get_setting("period_start")


def get_ranking(cycle_start=None):
    """Ranking do ciclo atual (ou do cycle_start informado), com nível, meta
    e quanto falta para bater a meta."""
    if cycle_start is None:
        cycle_start = current_cycle_start()
    conn = get_db()
    cur = _cursor(conn)
    cur.execute(
        """
        SELECT p.id, p.name, p.level,
               COUNT(ce.id) AS total_baus,
               COALESCE(SUM(cp.points), 0) AS total_pontos,
               lg.goal_points
        FROM players p
        LEFT JOIN chest_events ce ON ce.player_id = p.id AND ce.created_at >= %s
        LEFT JOIN chest_points cp ON cp.source = ce.source
        LEFT JOIN level_goals lg ON lg.level = p.level
        WHERE p.active = 1
        GROUP BY p.id, p.level, lg.goal_points
        ORDER BY total_pontos DESC, total_baus DESC
        """,
        (cycle_start,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    resultado = []
    for r in rows:
        row = dict(r)
        goal = row.get("goal_points")
        pontos = row["total_pontos"]
        if goal is None:
            row["status"] = None  # sem nível/meta definida
        elif pontos >= goal:
            row["status"] = "concluido"
        else:
            row["faltam"] = goal - pontos
            row["status"] = "faltando"
        resultado.append(row)
    return resultado


def maybe_archive_previous_cycle():
    """Se o ciclo anterior (domingo 14h -> domingo 14h) já terminou e ainda não
    foi arquivado, calcula o ranking final dele e salva em weekly_archive.
    Chamado de forma preguiçosa (a cada carregamento do ranking) — não depende
    de nenhum agendador rodando em segundo plano."""
    prev_start, prev_end = previous_cycle_bounds()
    last_archived = get_setting("last_archived_cycle_start")
    if last_archived == prev_start:
        return  # esse ciclo já foi arquivado

    rows = get_ranking(cycle_start=prev_start)
    # esse get_ranking usa "created_at >= cycle_start" sem limite superior;
    # para o ciclo já fechado, filtramos manualmente também o fim:
    conn = get_db()
    cur = _cursor(conn)
    cur.execute(
        """
        SELECT p.id, p.name,
               COUNT(ce.id) AS total_baus,
               COALESCE(SUM(cp.points), 0) AS total_pontos
        FROM players p
        LEFT JOIN chest_events ce ON ce.player_id = p.id
            AND ce.created_at >= %s AND ce.created_at < %s
        LEFT JOIN chest_points cp ON cp.source = ce.source
        WHERE p.active = 1
        GROUP BY p.id
        ORDER BY total_pontos DESC, total_baus DESC
        """,
        (prev_start, prev_end),
    )
    rows = cur.fetchall()

    week_label = prev_start[:10]  # AAAA-MM-DD do início do ciclo
    now = datetime.utcnow().isoformat()
    for r in rows:
        if r["total_baus"] == 0:
            continue
        cur.execute(
            "INSERT INTO weekly_archive (week_label, player_name, total_baus, total_pontos, closed_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (week_label, r["name"], r["total_baus"], r["total_pontos"], now),
        )
    conn.commit()
    cur.close()
    conn.close()
    set_setting("last_archived_cycle_start", prev_start)


def close_week(week_label):
    """Congela o ranking atual da semana em weekly_archive e abre um novo período."""
    rows = get_ranking()
    conn = get_db()
    cur = _cursor(conn)
    now = datetime.utcnow().isoformat()
    for r in rows:
        cur.execute(
            "INSERT INTO weekly_archive (week_label, player_name, total_baus, total_pontos, closed_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (week_label, r["name"], r["total_baus"], r["total_pontos"], now),
        )
    conn.commit()
    cur.close()
    conn.close()
    set_setting("period_start", now)


def get_player_history(player_name):
    """Histórico do jogador em ciclos já arquivados, do mais recente pro mais antigo."""
    conn = get_db()
    cur = _cursor(conn)
    cur.execute(
        "SELECT week_label, total_baus, total_pontos FROM weekly_archive "
        "WHERE player_name = %s ORDER BY week_label DESC",
        (player_name,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_week_ranking(week_label):
    """Ranking completo (todos os jogadores) de um ciclo já arquivado, ordenado por pontos."""
    conn = get_db()
    cur = _cursor(conn)
    cur.execute(
        "SELECT player_name, total_baus, total_pontos FROM weekly_archive "
        "WHERE week_label = %s ORDER BY total_pontos DESC, total_baus DESC",
        (week_label,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def list_week_labels():
    conn = get_db()
    cur = _cursor(conn)
    cur.execute(
        "SELECT DISTINCT week_label, closed_at FROM weekly_archive ORDER BY closed_at DESC"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_week_archive(week_label):
    conn = get_db()
    cur = _cursor(conn)
    cur.execute(
        "SELECT * FROM weekly_archive WHERE week_label = %s ORDER BY total_pontos DESC",
        (week_label,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_player_breakdown(player_id, cycle_start=None):
    if cycle_start is None:
        cycle_start = current_cycle_start()
    conn = get_db()
    cur = _cursor(conn)
    cur.execute(
        """
        SELECT ce.source, COUNT(*) AS qtd, COALESCE(cp.points, 0) AS pontos_unit
        FROM chest_events ce
        LEFT JOIN chest_points cp ON cp.source = ce.source
        WHERE ce.player_id = %s AND ce.created_at >= %s
        GROUP BY ce.source, cp.points
        ORDER BY qtd DESC
        """,
        (player_id, cycle_start),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
