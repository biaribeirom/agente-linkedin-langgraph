"""Estado compartilhado entre os nós do grafo do Agente LinkedIn."""

from typing import Annotated, Any, Literal, NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


Status = Literal[
    "iniciado",
    "aguardando_esclarecimento",
    "rascunho_gerado",
    "em_revisao",
    "aguardando_aprovacao",
    "revisao_humana_necessaria",
    "concluido",
    "informacoes_insuficientes",
]


class Verificacao(TypedDict):
    """Resultado da verificação factual e de estilo de um rascunho."""

    aprovado: bool
    problemas_factuais: list[str]
    problemas_estilo: list[str]


class AgentState(TypedDict):
    """Estado do agente. Apenas `solicitacao` é exigido na entrada inicial."""

    solicitacao: str
    contexto: NotRequired[dict[str, Any]]
    esclarecimentos: NotRequired[list[str]]
    pergunta_pendente: NotRequired[str | None]
    rascunho: NotRequired[str | None]
    verificacao: NotRequired[Verificacao | None]
    tentativas_revisao: NotRequired[int]
    status: NotRequired[Status]
    # Mensagens do ciclo de tool calling; add_messages acumula em vez de sobrescrever.
    mensagens: NotRequired[Annotated[list[AnyMessage], add_messages]]
