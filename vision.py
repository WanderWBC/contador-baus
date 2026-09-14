import os
import base64
import json
import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODEL = "claude-sonnet-4-6"

EXTRACTION_PROMPT = """Você está vendo um print da tela "Baús de presente" do jogo Total Battle.
Cada card na lista tem: um nome de baú, uma linha "De: <jogador>" e uma linha "Fonte: <fonte>".

Extraia TODOS os cards visíveis na imagem e devolva SOMENTE um JSON válido (sem markdown, sem texto
antes ou depois), no formato:

{
  "eventos": [
    {"bau": "<nome do baú>", "jogador": "<nome depois de 'De:'>", "fonte": "<texto depois de 'Fonte:'>"}
  ]
}

Se não conseguir ler algum campo com confiança, não inclua esse card no resultado.
Não invente jogadores ou fontes que não estejam escritos na imagem.
"""


def _media_type_for(path):
    ext = path.lower().rsplit(".", 1)[-1]
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "image/jpeg")


def extract_chest_events(image_path):
    """Envia uma imagem para a API da Anthropic e devolve uma lista de eventos
    [{"bau":..., "jogador":..., "fonte":...}, ...].

    Requer a variável de ambiente ANTHROPIC_API_KEY configurada (veja MANUAL.md).
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY não configurada. Defina essa variável de ambiente "
            "com sua chave da API da Anthropic (veja MANUAL.md, seção 'Configuração')."
        )

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "model": MODEL,
        "max_tokens": 2000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": _media_type_for(image_path),
                            "data": img_b64,
                        },
                    },
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }
        ],
    }
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    resp = requests.post(ANTHROPIC_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    text = "".join(
        block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
    )
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    parsed = json.loads(text)
    return parsed.get("eventos", [])
