"""Ferramenta de consulta ao perfil profissional do usuário."""

import json
from pathlib import Path
from typing import Any

from langchain_core.tools import tool


# Caminho fixo, relativo a este módulo: o LLM não escolhe arquivos.
CAMINHO_PERFIL = Path(__file__).resolve().parent.parent / "data" / "perfil_exemplo.json"

SECOES_OBRIGATORIAS = (
    "perfil",
    "fatos_autorizados",
    "preferencias_estilo",
    "exemplos_posts",
)


def _erro(tipo: str, mensagem: str) -> dict[str, Any]:
    return {"ok": False, "erro": {"tipo": tipo, "mensagem": mensagem}}


@tool
def consultar_perfil() -> dict[str, Any]:
    """Consulta as informações profissionais autorizadas do usuário.

    Retorna o perfil, os fatos autorizados (cada um com seu identificador),
    as preferências de estilo de escrita e os exemplos de posts com as
    referências aos fatos que utilizam. Somente os fatos autorizados podem
    ser afirmados em um post; os exemplos servem apenas como referência de
    estilo. Não recebe argumentos.
    """
    try:
        conteudo = CAMINHO_PERFIL.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _erro("arquivo_nao_encontrado", f"Arquivo não encontrado: {CAMINHO_PERFIL.name}")
    except (OSError, UnicodeDecodeError) as exc:
        return _erro("erro_leitura", f"Não foi possível ler {CAMINHO_PERFIL.name}: {exc}")

    try:
        dados = json.loads(conteudo)
    except json.JSONDecodeError as exc:
        return _erro("json_invalido", f"JSON inválido em {CAMINHO_PERFIL.name}: {exc}")

    if not isinstance(dados, dict):
        return _erro("estrutura_invalida", "O conteúdo do JSON deve ser um objeto.")

    ausentes = [secao for secao in SECOES_OBRIGATORIAS if secao not in dados]
    if ausentes:
        return _erro("estrutura_invalida", f"Seções obrigatórias ausentes: {', '.join(ausentes)}")

    return {"ok": True, "dados": {secao: dados[secao] for secao in SECOES_OBRIGATORIAS}}
