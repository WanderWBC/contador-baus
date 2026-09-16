import os
import io
import csv
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, jsonify,
    Response
)
from werkzeug.utils import secure_filename

import database as db
from vision import extract_chest_events, extract_player_names
from notify import notificar_telegram, montar_mensagem_destaques

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
CLAN_NAME = os.environ.get("CLAN_NAME", "Meu Clã")


@app.context_processor
def inject_clan_name():
    return {"clan_name": CLAN_NAME}

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

db.init_db()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Faça login como admin para acessar essa página.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def ranking():
    db.maybe_archive_previous_cycle()
    rows = db.get_ranking()
    cycle_start = db.current_cycle_start()
    return render_template(
        "ranking.html", ranking=rows, is_admin=session.get("is_admin", False),
        cycle_start=cycle_start,
    )


@app.route("/jogador/<int:player_id>")
def player_detail(player_id):
    conn = db.get_db()
    cur = db._cursor(conn)
    cur.execute("SELECT name FROM players WHERE id = %s", (player_id,))
    player_row = cur.fetchone()
    cur.close()
    conn.close()

    rows = db.get_player_breakdown(player_id)
    historico = db.get_player_history(player_row["name"]) if player_row else []
    return render_template(
        "player_detail.html", breakdown=rows, player_id=player_id,
        player_name=player_row["name"] if player_row else "",
        historico=historico,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            flash("Login feito com sucesso.")
            return redirect(url_for("admin_upload"))
        flash("Senha incorreta.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("is_admin", None)
    return redirect(url_for("ranking"))


@app.route("/admin/upload", methods=["GET", "POST"])
@admin_required
def admin_upload():
    resultado = None
    erros = None
    if request.method == "POST":
        files = request.files.getlist("print_baus")
        files = [f for f in files if f and f.filename]
        if not files:
            flash("Selecione ao menos um arquivo de imagem.")
            return redirect(url_for("admin_upload"))

        resultado = []
        erros = []
        for file in files:
            filename = secure_filename(file.filename)
            path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{filename}")
            file.save(path)

            try:
                eventos = extract_chest_events(path)
            except Exception as e:
                erros.append(f"{filename}: {e}")
                continue

            batch_id = uuid.uuid4().hex[:10]
            tuplas = [
                (ev.get("jogador", "").strip(), ev.get("bau", "").strip(), ev.get("fonte", "").strip())
                for ev in eventos
            ]
            db.add_chest_events_batch(tuplas, batch_id=batch_id)
            resultado.extend(eventos)

            msg = montar_mensagem_destaques(eventos)
            if msg:
                notificar_telegram(msg)

        if erros:
            flash("Alguns arquivos deram erro: " + " | ".join(erros))

    return render_template("admin_upload.html", resultado=resultado)


@app.route("/admin/upload_jogadores", methods=["GET", "POST"])
@admin_required
def admin_upload_players():
    resultado = None
    erros = None
    if request.method == "POST":
        files = request.files.getlist("print_membros")
        files = [f for f in files if f and f.filename]
        if not files:
            flash("Selecione ao menos um arquivo de imagem.")
            return redirect(url_for("admin_upload_players"))

        resultado = []
        erros = []
        for file in files:
            filename = secure_filename(file.filename)
            path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{filename}")
            file.save(path)

            try:
                nomes = extract_player_names(path)
            except Exception as e:
                erros.append(f"{filename}: {e}")
                continue

            nomes_limpos = [n.strip() for n in nomes if n.strip()]
            db.upsert_players_batch(nomes_limpos)
            resultado.extend(nomes_limpos)

        if erros:
            flash("Alguns arquivos deram erro: " + " | ".join(erros))

    return render_template("admin_upload_players.html", resultado=resultado)


@app.route("/admin/jogadores", methods=["GET", "POST"])
@admin_required
def admin_players():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            name = request.form.get("name", "").strip()
            level = request.form.get("level", "").strip()
            if name:
                pid = db.upsert_player(name)
                if level:
                    db.set_player_level(pid, level)
                flash(f"Jogador '{name}' cadastrado.")
        elif action == "remove":
            player_id = request.form.get("player_id")
            db.set_player_active(int(player_id), False)
            flash("Jogador removido do clã (desativado).")
        elif action == "set_level":
            player_id = int(request.form.get("player_id"))
            level = request.form.get("level", "").strip()
            db.set_player_level(player_id, level)
            flash("Nível atualizado.")
        return redirect(url_for("admin_players"))

    players = db.list_players(active_only=False)
    return render_template("admin_players.html", players=players, levels=db.VALID_LEVELS)


@app.route("/admin/metas", methods=["GET", "POST"])
@admin_required
def admin_level_goals():
    if request.method == "POST":
        level = request.form.get("level", "").strip()
        goal = request.form.get("goal_points", "0").strip()
        if level:
            db.set_level_goal(level, int(goal or 0))
            flash(f"Meta do nível {level} atualizada para {goal} pontos.")
        return redirect(url_for("admin_level_goals"))

    goals = db.get_level_goals()
    return render_template("admin_level_goals.html", levels=db.VALID_LEVELS, goals=goals)


@app.route("/admin/pontuacao", methods=["GET", "POST"])
@admin_required
def admin_points():
    if request.method == "POST":
        source = request.form.get("source", "").strip()
        points = request.form.get("points", "0").strip()
        if source:
            db.set_chest_points(source, int(points or 0))
            flash(f"Pontuação de '{source}' atualizada para {points}.")
        return redirect(url_for("admin_points"))

    rows = db.get_chest_points()
    return render_template("admin_points.html", points=rows)


@app.route("/export/ranking.csv")
def export_ranking_csv():
    rows = db.get_ranking()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Jogador", "Baús", "Pontos"])
    for r in rows:
        writer.writerow([r["name"], r["total_baus"], r["total_pontos"]])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=ranking.csv"},
    )


@app.route("/semanas")
def admin_week():
    weeks = db.list_week_labels()
    cycle_start = db.current_cycle_start()
    return render_template("admin_week.html", weeks=weeks, cycle_start=cycle_start)


@app.route("/semanas/<label>")
def week_detail(label):
    rows = db.get_week_ranking(label)
    return render_template("week_detail.html", rows=rows, label=label)


@app.route("/admin/semana/<label>.csv")
@admin_required
def export_week_csv(label):
    rows = db.get_week_archive(label)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Jogador", "Baús", "Pontos"])
    for r in rows:
        writer.writerow([r["player_name"], r["total_baus"], r["total_pontos"]])
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=semana_{label}.csv"},
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
