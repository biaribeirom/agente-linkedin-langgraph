"""Grafo do Agente LinkedIn."""

import json
import os
import re
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from src.prompts import (
    PROMPT_GERACAO,
    PROMPT_REVISAO,
    PROMPT_SISTEMA,
    PROMPT_VALIDACAO,
    PROMPT_VERIFICACAO,
)
from src.state import AgentState, Verificacao
from src.tools import consultar_perfil

MAX_REVISOES = 1


class ErroAgente(RuntimeError):
    """Falha técnica na execução (não é pedido de revisão humana)."""

    def __init__(self, tipo: str, mensagem: str) -> None:
        super().__init__(f"[{tipo}] {mensagem}")
        self.tipo = tipo
        self.mensagem = mensagem


class ErroConfiguracao(ErroAgente):
    """Variáveis de ambiente necessárias ausentes."""


class ErroDecisaoLLM(ErroAgente):
    """O LLM não produziu a chamada de ferramenta esperada."""


class ErroConsultaPerfil(ErroAgente):
    """A ferramenta consultar_perfil retornou erro."""


class ErroValidacao(ErroAgente):
    """O validador de suficiência devolveu uma saída fora do formato esperado."""


class ErroGeracao(ErroAgente):
    """O LLM não devolveu um rascunho textual utilizável."""


class ErroVerificacao(ErroAgente):
    """O verificador devolveu uma saída fora da estrutura Verificacao."""


class ErroRevisao(ErroAgente):
    """A revisão automática falhou ou excederia o limite permitido."""


def criar_llm() -> ChatOpenAI:
    """Cria o ChatOpenAI a partir de OPENAI_API_KEY e OPENAI_MODEL, sem valores padrão."""
    ausentes = [nome for nome in ("OPENAI_API_KEY", "OPENAI_MODEL") if not os.getenv(nome)]
    if ausentes:
        raise ErroConfiguracao("configuracao_ausente", f"Variáveis não definidas: {', '.join(ausentes)}")
    return ChatOpenAI(model=os.environ["OPENAI_MODEL"], api_key=os.environ["OPENAI_API_KEY"])


def _validar_chamada(resposta: AIMessage) -> None:
    """Aceita apenas uma chamada a consultar_perfil, sem argumentos."""
    chamadas = resposta.tool_calls
    if not chamadas:
        raise ErroDecisaoLLM("sem_chamada_ferramenta", "O modelo não solicitou a consulta ao perfil.")
    if len(chamadas) > 1:
        raise ErroDecisaoLLM("multiplas_chamadas", f"O modelo solicitou {len(chamadas)} chamadas; apenas uma é permitida.")
    chamada = chamadas[0]
    if chamada["name"] != consultar_perfil.name:
        raise ErroDecisaoLLM("ferramenta_nao_autorizada", f"Ferramenta não autorizada: {chamada['name']}")
    if chamada["args"]:
        raise ErroDecisaoLLM("argumentos_inesperados", f"Argumentos não aceitos: {sorted(chamada['args'])}")


def _mensagem_json(dados: dict[str, Any]) -> HumanMessage:
    return HumanMessage(f"<dados>\n{json.dumps(dados, ensure_ascii=False, indent=2)}\n</dados>")


def _mensagem_dados(state: AgentState, **extras: Any) -> HumanMessage:
    """Empacota solicitação, esclarecimentos, contexto e extras como dados, separados das instruções."""
    contexto = state["contexto"]
    return _mensagem_json({
        "solicitacao": state["solicitacao"],
        "esclarecimentos_usuario": state.get("esclarecimentos", []),
        "fatos_autorizados": contexto["fatos_autorizados"],
        "preferencias_estilo": contexto["preferencias_estilo"],
        "exemplos_posts_somente_estilo": contexto["exemplos_posts"],
        **extras,
    })


def _validar_suficiencia(texto: str) -> tuple[bool, str | None]:
    """Converte a resposta do validador em (suficiente, pergunta), rejeitando qualquer desvio."""
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip())
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ErroValidacao("saida_invalida", f"A resposta do validador não é JSON: {exc}") from exc

    if not isinstance(dados, dict) or set(dados) != {"suficiente", "pergunta"}:
        raise ErroValidacao("saida_invalida", "A resposta deve conter exatamente as chaves ['pergunta', 'suficiente'].")
    suficiente, pergunta = dados["suficiente"], dados["pergunta"]
    if not isinstance(suficiente, bool):
        raise ErroValidacao("saida_invalida", "'suficiente' deve ser booleano.")
    if suficiente and pergunta is not None:
        raise ErroValidacao("saida_inconsistente", "Com 'suficiente' true, 'pergunta' deve ser null.")
    if not suficiente and not (isinstance(pergunta, str) and pergunta.strip()):
        raise ErroValidacao("saida_inconsistente", "Com 'suficiente' false, 'pergunta' deve ser um texto não vazio.")
    return suficiente, pergunta.strip() if pergunta else None


def _validar_verificacao(texto: str, ids_fatos: set[str]) -> Verificacao:
    """Converte a resposta do verificador em Verificacao, rejeitando qualquer desvio."""
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip())
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ErroVerificacao("saida_invalida", f"A resposta do verificador não é JSON: {exc}") from exc

    chaves = {"aprovado", "problemas_factuais", "problemas_estilo"}
    if not isinstance(dados, dict) or set(dados) != chaves:
        raise ErroVerificacao("saida_invalida", f"A resposta deve conter exatamente as chaves {sorted(chaves)}.")
    if not isinstance(dados["aprovado"], bool):
        raise ErroVerificacao("saida_invalida", "'aprovado' deve ser booleano.")
    for campo in ("problemas_factuais", "problemas_estilo"):
        lista = dados[campo]
        if not isinstance(lista, list) or not all(isinstance(p, str) and p.strip() for p in lista):
            raise ErroVerificacao("saida_invalida", f"'{campo}' deve ser uma lista de textos não vazios.")

    tem_problemas = bool(dados["problemas_factuais"] or dados["problemas_estilo"])
    if dados["aprovado"] == tem_problemas:
        raise ErroVerificacao("saida_inconsistente", "'aprovado' deve ser true se, e somente se, não houver problemas.")

    citados = set(re.findall(r"\bF\d+\b", " ".join(dados["problemas_factuais"])))
    if citados - ids_fatos:
        raise ErroVerificacao("referencia_inexistente", f"Fatos citados que não existem: {sorted(citados - ids_fatos)}")
    return dados


def _status_apos_verificacao(aprovado: bool, tentativas: int) -> str:
    if aprovado:
        return "aguardando_aprovacao"
    return "em_revisao" if tentativas < MAX_REVISOES else "revisao_humana_necessaria"


def construir_grafo(llm: BaseChatModel, checkpointer: BaseCheckpointSaver | None = None):
    """Monta e compila o grafo:
    START → decidir_acao → executar_ferramenta → observar_resultado
          → validar_informacoes ⇄ solicitar_esclarecimento (no máximo uma vez)
          → gerar_rascunho → verificar_rascunho ⇄ revisar_rascunho (no máximo uma vez) → END.

    Com `checkpointer`, o estado é salvo a cada passo, associado ao thread_id da execução.
    O esclarecimento exige checkpointer, pois interrompe a execução até a retomada.
    """
    llm_com_ferramenta = llm.bind_tools([consultar_perfil])

    def decidir_acao(state: AgentState) -> dict[str, Any]:
        """Reason: o LLM analisa a solicitação e decide chamar a ferramenta."""
        pedido = HumanMessage(state["solicitacao"])
        resposta = llm_com_ferramenta.invoke([SystemMessage(PROMPT_SISTEMA), pedido])
        _validar_chamada(resposta)
        return {"mensagens": [pedido, resposta]}

    def executar_ferramenta(state: AgentState) -> dict[str, Any]:
        """Act: executa a chamada estruturada registrada pelo LLM."""
        chamada = state["mensagens"][-1].tool_calls[0]
        resultado = consultar_perfil.invoke(chamada["args"])
        observacao = ToolMessage(
            content=json.dumps(resultado, ensure_ascii=False),
            tool_call_id=chamada["id"],
            name=chamada["name"],
            status="success" if resultado["ok"] else "error",
        )
        return {"mensagens": [observacao]}

    def observar_resultado(state: AgentState) -> dict[str, Any]:
        """Observe: interpreta a observação e armazena os dados em `contexto`."""
        resultado = json.loads(state["mensagens"][-1].content)
        if not resultado["ok"]:
            erro = resultado["erro"]
            raise ErroConsultaPerfil(erro["tipo"], erro["mensagem"])
        return {"contexto": resultado["dados"]}

    def validar_informacoes(state: AgentState) -> dict[str, Any]:
        """Avalia se solicitação, fatos e esclarecimentos bastam para escrever o post."""
        dados = _mensagem_json({
            "solicitacao": state["solicitacao"],
            "fatos_autorizados": state["contexto"]["fatos_autorizados"],
            "esclarecimentos_usuario": state.get("esclarecimentos", []),
        })
        resposta = llm.invoke([SystemMessage(PROMPT_VALIDACAO), dados])
        if resposta.tool_calls:
            raise ErroValidacao("saida_invalida", "O validador tentou chamar uma ferramenta.")
        suficiente, pergunta = _validar_suficiencia(resposta.text)
        if suficiente:
            return {"pergunta_pendente": None}
        # Depois de um esclarecimento, a pergunta fica registrada como a lacuna não resolvida.
        status = "informacoes_insuficientes" if state.get("esclarecimentos") else "aguardando_esclarecimento"
        return {"pergunta_pendente": pergunta, "status": status}

    def solicitar_esclarecimento(state: AgentState) -> dict[str, Any]:
        """Interrompe a execução até o usuário responder à pergunta pendente.

        Ao retomar, o LangGraph reexecuta este nó desde o início; por isso nada
        com efeito colateral pode vir antes de interrupt().
        """
        pergunta = state["pergunta_pendente"]
        pedido = {"tipo": "esclarecimento", "pergunta": pergunta}
        # Uma resposta vazia repete a mesma pergunta; lançar erro aqui deixaria
        # a resposta inválida gravada no checkpoint e impediria novas retomadas.
        while True:
            resposta = interrupt(pedido)
            if isinstance(resposta, str) and resposta.strip():
                break
            pedido = {**pedido, "aviso": "A resposta anterior estava vazia."}
        resposta = resposta.strip()
        return {
            "esclarecimentos": [*state.get("esclarecimentos", []), resposta],
            "pergunta_pendente": None,
            # Entra no histórico para que gerar_rascunho receba o esclarecimento.
            "mensagens": [HumanMessage(f'Esclarecimento do usuário à pergunta "{pergunta}": {resposta}')],
        }

    def rotear_apos_validacao(state: AgentState) -> str:
        if state.get("pergunta_pendente") is None:
            return "gerar_rascunho"
        if not state.get("esclarecimentos"):
            return "solicitar_esclarecimento"
        return END

    def gerar_rascunho(state: AgentState) -> dict[str, Any]:
        """Gera o rascunho a partir do histórico, que inclui a observação da ferramenta."""
        # Sem ferramentas vinculadas: o modelo só pode responder com texto.
        resposta = llm.invoke([SystemMessage(PROMPT_GERACAO), *state["mensagens"]])
        texto = resposta.text.strip()
        if resposta.tool_calls or not texto:
            raise ErroGeracao("rascunho_invalido", "O modelo não devolveu um rascunho textual.")
        return {"mensagens": [resposta], "rascunho": texto, "status": "rascunho_gerado"}

    def verificar_rascunho(state: AgentState) -> dict[str, Any]:
        """Avalia fatos e estilo do rascunho e devolve uma Verificacao validada."""
        dados = _mensagem_dados(state, rascunho=state["rascunho"])
        resposta = llm.invoke([SystemMessage(PROMPT_VERIFICACAO), dados])
        if resposta.tool_calls:
            raise ErroVerificacao("saida_invalida", "O verificador tentou chamar uma ferramenta.")
        ids_fatos = {fato["id"] for fato in state["contexto"]["fatos_autorizados"]}
        verificacao = _validar_verificacao(resposta.text, ids_fatos)
        tentativas = state.get("tentativas_revisao", 0)
        return {
            "verificacao": verificacao,
            "tentativas_revisao": tentativas,
            "status": _status_apos_verificacao(verificacao["aprovado"], tentativas),
        }

    def revisar_rascunho(state: AgentState) -> dict[str, Any]:
        """Corrige o rascunho reprovado, usando os problemas apontados."""
        tentativas = state.get("tentativas_revisao", 0)
        if tentativas >= MAX_REVISOES:
            raise ErroRevisao("limite_revisoes", f"Limite de {MAX_REVISOES} revisão automática atingido.")
        verificacao = state["verificacao"]
        dados = _mensagem_dados(
            state,
            rascunho_anterior=state["rascunho"],
            problemas_factuais=verificacao["problemas_factuais"],
            problemas_estilo=verificacao["problemas_estilo"],
        )
        resposta = llm.invoke([SystemMessage(PROMPT_REVISAO), dados])
        texto = resposta.text.strip()
        if resposta.tool_calls or not texto:
            raise ErroRevisao("revisao_invalida", "O modelo não devolveu um rascunho revisado.")
        return {"mensagens": [resposta], "rascunho": texto, "tentativas_revisao": tentativas + 1}

    def rotear_apos_verificacao(state: AgentState) -> str:
        if state["verificacao"]["aprovado"]:
            return END
        if state.get("tentativas_revisao", 0) < MAX_REVISOES:
            return "revisar_rascunho"
        return END

    builder = StateGraph(AgentState)
    builder.add_node("decidir_acao", decidir_acao)
    builder.add_node("executar_ferramenta", executar_ferramenta)
    builder.add_node("observar_resultado", observar_resultado)
    builder.add_node("validar_informacoes", validar_informacoes)
    builder.add_node("solicitar_esclarecimento", solicitar_esclarecimento)
    builder.add_node("gerar_rascunho", gerar_rascunho)
    builder.add_node("verificar_rascunho", verificar_rascunho)
    builder.add_node("revisar_rascunho", revisar_rascunho)
    builder.add_edge(START, "decidir_acao")
    builder.add_edge("decidir_acao", "executar_ferramenta")
    builder.add_edge("executar_ferramenta", "observar_resultado")
    builder.add_edge("observar_resultado", "validar_informacoes")
    builder.add_conditional_edges(
        "validar_informacoes", rotear_apos_validacao, ["gerar_rascunho", "solicitar_esclarecimento", END]
    )
    builder.add_edge("solicitar_esclarecimento", "validar_informacoes")
    builder.add_edge("gerar_rascunho", "verificar_rascunho")
    builder.add_conditional_edges(
        "verificar_rascunho", rotear_apos_verificacao, ["revisar_rascunho", END]
    )
    builder.add_edge("revisar_rascunho", "verificar_rascunho")
    return builder.compile(checkpointer=checkpointer)
