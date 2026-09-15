import os
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

DESTAQUE_PALAVRAS = ["epic", "épic", "rare", "raro", "heroic", "heroico", "lendár", "legend"]


def is_destaque(source):
    s = (source or "").lower()
    return any(palavra in s for palavra in DESTAQUE_PALAVRAS)


def notificar_telegram(texto):
    """Envia uma mensagem para o Telegram, se TELEGRAM_BOT_TOKEN/CHAT_ID estiverem
    configurados. Se não estiverem, não faz nada (silenciosamente)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": texto}, timeout=10)
        return True
    except Exception:
        return False


def montar_mensagem_destaques(eventos):
    """Recebe a lista de eventos extraídos do print e devolve o texto de notificação,
    ou None se nenhum evento for de destaque (raro/épico/heroico)."""
    destaques = [ev for ev in eventos if is_destaque(ev.get("fonte", ""))]
    if not destaques:
        return None
    linhas = ["🏆 Baú especial coletado!"]
    for ev in destaques:
        linhas.append(f"- {ev.get('jogador')}: {ev.get('bau')} ({ev.get('fonte')})")
    return "\n".join(linhas)
