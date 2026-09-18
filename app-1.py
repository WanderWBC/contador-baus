import os
import uuid
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, jsonify
)
from werkzeug.utils import secure_filename

import database as db
from vision import extract_chest_events

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

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
    rows = db.get_ranking()
    return render_template("ranking.html", ranking=rows, is_admin=session.get("is_admin", False))


@app.route("/jogador/<int:player_id>")
def player_detail(player_id):
    rows = db.get_player_breakdown(player_id)
    return render_template("player_detail.html", breakdown=rows, player_id=player_id)


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
    if request.method == "POST":
        file = request.files.get("print_baus")
        if not file or file.filename == "":
            flash("Selecione um arquivo de imagem.")
            return redirect(url_for("admin_upload"))

        filename = secure_filename(file.filename)
        path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{filename}")
        file.save(path)

        try:
            eventos = extract_chest_events(path)
        except Exception as e:
            flash(f"Erro ao processar a imagem: {e}")
            return redirect(url_for("admin_upload"))

        batch_id = uuid.uuid4().hex[:10]
        for ev in eventos:
            db.add_chest_event(
                player_name=ev.get("jogador", "").strip(),
                chest_name=ev.get("bau", "").strip(),
                source=ev.get("fonte", "").strip(),
                batch_id=batch_id,
            )
        resultado = eventos

    return render_template("admin_upload.html", resultado=resultado)


@app.route("/admin/jogadores", methods=["GET", "POST"])
@admin_required
def admin_players():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            name = request.form.get("name", "").strip()
            if name:
                db.upsert_player(name)
                flash(f"Jogador '{name}' cadastrado.")
        elif action == "remove":
            player_id = request.form.get("player_id")
            db.set_player_active(int(player_id), False)
            flash("Jogador removido do clã (desativado).")
        return redirect(url_for("admin_players"))

    players = db.list_players(active_only=False)
    return render_template("admin_players.html", players=players)


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


@app.route("/admin/semanas")
@admin_required
def admin_week():
    flash("Relatório de semanas/ciclos ainda em construção.")
    return redirect(url_for("ranking"))


@app.route("/api/upload-print", methods=["POST"])
def api_upload_print():
    """Endpoint usado pelo robô de coleta automática (coletor_baus.py).
    Protegido por uma chave própria (AUTOMATION_API_KEY), separada da senha de admin."""
    api_key = request.headers.get("X-API-Key", "")
    expected = os.environ.get("AUTOMATION_API_KEY", "")
    if not expected or api_key != expected:
        return jsonify({"erro": "não autorizado"}), 401

    file = request.files.get("print_baus")
    if not file or file.filename == "":
        return jsonify({"erro": "nenhum arquivo enviado"}), 400

    filename = secure_filename(file.filename)
    path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{filename}")
    file.save(path)

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

    return jsonify({"eventos_processados": len(eventos), "eventos": eventos})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
