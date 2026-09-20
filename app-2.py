import csv
import io
import os
import uuid
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
)
from werkzeug.utils import secure_filename

import database as db
import notify
from cycle import current_cycle_start
from vision import extract_chest_events, extract_player_names

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

db.init_db()


@app.context_processor
def inject_globals():
    """Disponibiliza clan_name em todos os templates automaticamente."""
    return {"clan_name": os.environ.get("CLAN_NAME", "Meu Clã")}


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Faça login como admin para acessar essa página.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def _save_upload(file):
    filename = secure_filename(file.filename)
    path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{filename}")
    file.save(path)
    return path


# ---------------------------------------------------------------------------
# Páginas públicas
# ---------------------------------------------------------------------------

@app.route("/")
def ranking():
    db.maybe_archive_previous_cycle()
    rows = db.get_ranking()
    return render_template(
        "ranking.html",
        ranking=rows,
        cycle_start=current_cycle_start(),
        is_admin=session.get("is_admin", False),
    )


@app.route("/jogador/<int:player_id>")
def player_detail(player_id):
    player = db.get_player_by_id(player_id)
    if not player:
        flash("Jogador não encontrado.")
        return redirect(url_for("ranking"))
    breakdown = db.get_player_breakdown(player_id)
    historico = db.get_player_history(player["name"])
    return render_template(
        "player_detail.html",
        breakdown=breakdown,
        historico=historico,
        player_name=player["name"],
        player_id=player_id,
    )


@app.route("/admin/semanas")
def admin_week():
    db.maybe_archive_previous_cycle()
    weeks = db.list_week_labels()
    return render_template("admin_week.html", cycle_start=current_cycle_start(), weeks=weeks)


@app.route("/admin/semanas/<label>")
def week_detail(label):
    rows = db.get_week_archive(label)
    return render_template("week_detail.html", label=label, rows=rows)


@app.route("/export/ranking.csv")
def export_ranking_csv():
    rows = db.get_ranking()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Jogador", "Nível", "Baús", "Pontos", "Meta", "Status"])
    for r in rows:
        writer.writerow([
            r["name"],
            r.get("level") or "-",
            r["total_baus"],
            r["total_pontos"],
            r.get("goal_points") if r.get("goal_points") is not None else "-",
            r.get("status") or "-",
        ])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=ranking_atual.csv"},
    )


@app.route("/admin/semanas/<label>/csv")
def export_week_csv(label):
    rows = db.get_week_archive(label)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Jogador", "Baús", "Pontos"])
    for r in rows:
        writer.writerow([r["player_name"], r["total_baus"], r["total_pontos"]])
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=semana_{label}.csv"},
    )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Área administrativa
# ---------------------------------------------------------------------------

@app.route("/admin/upload", methods=["GET", "POST"])
@admin_required
def admin_upload():
    resultado = None
    if request.method == "POST":
        files = [f for f in request.files.getlist("print_baus") if f and f.filename]
        if not files:
            flash("Selecione ao menos um arquivo de imagem.")
            return redirect(url_for("admin_upload"))

        batch_id = uuid.uuid4().hex[:10]
        todos_eventos = []
        for file in files:
            path = _save_upload(file)
            try:
                eventos = extract_chest_events(path)
            except Exception as e:
                flash(f"Erro ao processar {file.filename}: {e}")
                continue
            for ev in eventos:
                db.add_chest_event(
                    player_name=ev.get("jogador", "").strip(),
                    chest_name=ev.get("bau", "").strip(),
                    source=ev.get("fonte", "").strip(),
                    batch_id=batch_id,
                )
            todos_eventos.extend(eventos)

        msg = notify.montar_mensagem_destaques(todos_eventos)
        if msg:
            notify.notificar_telegram(msg)

        resultado = todos_eventos

    return render_template("admin_upload.html", resultado=resultado)


@app.route("/admin/jogadores/print", methods=["GET", "POST"])
@admin_required
def admin_upload_players():
    resultado = None
    if request.method == "POST":
        files = [f for f in request.files.getlist("print_membros") if f and f.filename]
        if not files:
            flash("Selecione ao menos um arquivo de imagem.")
            return redirect(url_for("admin_upload_players"))

        todos_nomes = []
        for file in files:
            path = _save_upload(file)
            try:
                nomes = extract_player_names(path)
            except Exception as e:
                flash(f"Erro ao processar {file.filename}: {e}")
                continue
            todos_nomes.extend(nomes)

        nomes_limpos = [n.strip() for n in todos_nomes if n and n.strip()]
        db.upsert_players_batch(nomes_limpos)
        resultado = nomes_limpos

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
        elif action == "set_level":
            player_id = int(request.form.get("player_id"))
            level = request.form.get("level", "").strip()
            db.set_player_level(player_id, level)
            flash("Nível atualizado.")
        elif action == "remove":
            player_id = request.form.get("player_id")
            db.set_player_active(int(player_id), False)
            flash("Jogador removido do clã (desativado).")
        return redirect(url_for("admin_players"))

    players = db.list_players(active_only=False)
    return render_template("admin_players.html", players=players, levels=db.VALID_LEVELS)


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


@app.route("/admin/niveis", methods=["GET", "POST"])
@admin_required
def admin_level_goals():
    if request.method == "POST":
        level = request.form.get("level")
        goal_points = int(request.form.get("goal_points", "0") or 0)
        try:
            db.set_level_goal(level, goal_points)
            flash(f"Meta do nível {level} atualizada para {goal_points}.")
        except ValueError as e:
            flash(str(e))
        return redirect(url_for("admin_level_goals"))

    goals = db.get_level_goals()
    return render_template("admin_level_goals.html", levels=db.VALID_LEVELS, goals=goals)


# ---------------------------------------------------------------------------
# API para o robô de coleta automática (PC e celular)
# ---------------------------------------------------------------------------

@app.route("/api/upload-print", methods=["POST"])
def api_upload_print():
    """Endpoint usado pelo robô de coleta automática (coletor_baus.py no PC,
    ou o fluxo do Automate no celular). Protegido por uma chave própria
    (AUTOMATION_API_KEY), separada da senha de admin."""
    api_key = request.headers.get("X-API-Key", "")
    expected = os.environ.get("AUTOMATION_API_KEY", "")
    if not expected or api_key != expected:
        return jsonify({"erro": "não autorizado"}), 401

    file = request.files.get("print_baus")
    if not file or file.filename == "":
        return jsonify({"erro": "nenhum arquivo enviado"}), 400

    path = _save_upload(file)

    try:
        eventos = extract_chest_events(path)
    except Exception as e:
        return jsonify({"erro": f"falha ao processar imagem: {e}"}), 500

    batch_id = uuid.uuid4().hex[:10]
    for ev in eventos:
        db.add_chest_event(
            player_name=ev.get("jogador", "").strip(),
            chest_name=ev.get("bau", "").strip(),
            source=ev.get("fonte", "").strip(),
            batch_id=batch_id,
        )

    msg = notify.montar_mensagem_destaques(eventos)
    if msg:
        notify.notificar_telegram(msg)

    return jsonify({"eventos_processados": len(eventos), "eventos": eventos})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
