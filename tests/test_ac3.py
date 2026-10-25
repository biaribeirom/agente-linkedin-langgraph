"""Testes reproduzíveis da AC3 com LLM SIMULADO.

Executar a partir da raiz do projeto:
    C:\\venvs\\agente-linkedin\\Scripts\\python.exe tests\\test_ac3.py

O LLM é substituído por um modelo simulado que devolve respostas PREDEFINIDAS,
em ordem. Grafo, ferramenta, JSON, SQLite e main.py são executados de verdade.
Os testes não fazem chamadas à OpenAI: a rede fica bloqueada.

Cada cenário grava um log legível em evidencias/.
"""

import json
import os
import platform
import re
import socket
import subprocess
import sys
import unittest
import uuid
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any, NotRequired, TypedDict

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))


def _rede_bloqueada(*args, **kwargs):
    raise RuntimeError("Rede bloqueada nos testes: nenhuma chamada externa é permitida.")


socket.socket.connect = _rede_bloqueada
socket.create_connection = _rede_bloqueada

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

import main
import src.tools as tools
from src import prompts
from src.graph import construir_grafo

EVIDENCIAS = RAIZ / "evidencias"
# Banco separado do banco de uso normal (checkpoints.sqlite), na mesma pasta fora do repositório.
BANCO_TESTES = Path.home() / ".agente-linkedin" / "checkpoints_testes.sqlite"
NOME_PROMPT = {getattr(prompts, nome): nome for nome in dir(prompts) if nome.startswith("PROMPT_")}

# ---------------------------------------------------------------------------
# LLM simulado e respostas predefinidas
# ---------------------------------------------------------------------------

REGISTRO: list[dict[str, Any]] = []  # o que cada chamada ao LLM simulado recebeu


def _dados_da_mensagem(mensagem) -> dict[str, Any] | None:
    texto = mensagem.content if isinstance(mensagem.content, str) else ""
    if texto.startswith("<dados>\n") and texto.endswith("\n</dados>"):
        return json.loads(texto[len("<dados>\n"):-len("\n</dados>")])
    return None


class LLMSimulado(GenericFakeChatModel):
    """Devolve respostas PREDEFINIDAS, em ordem. Não gera nem verifica nada por conta própria."""

    def bind_tools(self, tools, **kwargs):
        return self.bind(ferramentas=[t.name for t in tools])

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        dados = _dados_da_mensagem(messages[-1])
        REGISTRO.append({
            "prompt": NOME_PROMPT.get(messages[0].content, "?"),
            "ferramentas": kwargs.get("ferramentas"),
            "mensagens": [type(m).__name__ for m in messages],
            "esclarecimento_no_historico": [
                m.content for m in messages
                if isinstance(m, HumanMessage) and str(m.content).startswith("Esclarecimento do usuário")
            ],
            "dados": dados,
        })
        return super()._generate(messages, stop, run_manager, **kwargs)


def _json(**campos) -> AIMessage:
    return AIMessage(json.dumps(campos, ensure_ascii=False))


SOLICITACAO = "Quero um post sobre a apresentação do meu projeto no workshop de IA aplicada."
RESPOSTA_HUMANA = "O projeto analisou dados fictícios de evasão escolar."
PERGUNTA = "Qual foi o tema do projeto de análise de dados que você apresentou?"

CHAMADA_FERRAMENTA = AIMessage(
    content="", tool_calls=[{"name": "consultar_perfil", "args": {}, "id": "call_1", "type": "tool_call"}]
)
SUFICIENTE = _json(suficiente=True, pergunta=None)
INSUFICIENTE = _json(suficiente=False, pergunta=PERGUNTA)
RASCUNHO_FIEL = (
    "[MOCK] Apresentei um projeto de análise de dados no workshop de IA aplicada da universidade. "
    "Explicar o raciocínio por trás da análise foi um ótimo aprendizado. 💡"
)
RASCUNHO_COM_TEMA = (
    "[MOCK] No workshop de IA aplicada, apresentei meu projeto de análise de dados sobre evasão escolar. "
    "Foi muito bom compartilhar o raciocínio por trás da análise. 💡"
)
RASCUNHO_NAO_AUTORIZADO = (
    "[MOCK] Como Cientista de Dados Sênior na DataX, venci o workshop de IA aplicada com um modelo "
    "de 98% de acurácia! 🚀🔥 Inovação disruptiva sempre!"
)
VERIFICACAO_APROVADA = _json(aprovado=True, problemas_factuais=[], problemas_estilo=[])
VERIFICACAO_REPROVADA = _json(
    aprovado=False,
    problemas_factuais=[
        "'Cientista de Dados Sênior na DataX': cargo e empresa sem suporte; F01 indica apenas que Marina cursa graduação.",
        "'venci o workshop': conquista sem suporte; F02 e F03 indicam apenas participação e apresentação.",
        "'98% de acurácia': número sem suporte nos fatos autorizados.",
    ],
    problemas_estilo=["Dois emojis; o limite é um.", "'Inovação disruptiva sempre!': frase genérica e exagerada."],
)

CENARIOS_PROCESSO = {
    "iniciar_incompleto": [CHAMADA_FERRAMENTA, INSUFICIENTE],
    "retomar_ok": [SUFICIENTE, AIMessage(RASCUNHO_COM_TEMA), VERIFICACAO_APROVADA],
}

# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------


def _anonimizar(texto: str) -> str:
    return texto.replace(str(Path.home()), "~")


def _descrever_mock(resposta: AIMessage) -> str:
    if resposta.tool_calls:
        chamada = resposta.tool_calls[0]
        return f"tool_call {chamada['name']}(args={chamada['args']})"
    return resposta.text


def _sequencia_nos(grafo, config) -> list[str]:
    """Reconstrói a ordem dos nós executados a partir do histórico de checkpoints do SQLite."""
    historico = reversed(list(grafo.get_state_history(config)))
    return [h.next[0] for h in historico if h.next and not h.next[0].startswith("__")]


def _contar_tool_messages(estado: dict[str, Any]) -> int:
    return sum(isinstance(m, ToolMessage) for m in estado.get("mensagens", []))


class Evidencia:
    """Acumula o log de um cenário e as verificações realizadas."""

    def __init__(self, arquivo: str, titulo: str) -> None:
        self.arquivo = EVIDENCIAS / f"{arquivo}.log"
        self.verificacoes: list[tuple[str, bool]] = []
        self.linhas = [
            "=" * 78,
            titulo,
            "=" * 78,
            f"Executado em: {datetime.now().isoformat(timespec='seconds')}",
            f"Python {platform.python_version()} | langgraph {version('langgraph')} | "
            f"langgraph-checkpoint-sqlite {version('langgraph-checkpoint-sqlite')} | "
            f"langchain-core {version('langchain-core')}",
            "LLM: SIMULADO (GenericFakeChatModel com respostas predefinidas). Rede bloqueada.",
            "Nenhuma chamada à OpenAI. Grafo, ferramenta, JSON, SQLite e main.py executados de verdade.",
            f"Banco de testes: {_anonimizar(str(BANCO_TESTES))}",
        ]

    def secao(self, titulo: str) -> None:
        self.linhas += ["", f"--- {titulo} ---"]

    def linha(self, texto: Any = "") -> None:
        self.linhas += _anonimizar(str(texto)).splitlines() or [""]

    def mock(self, respostas: list[AIMessage], titulo: str = "Respostas PREDEFINIDAS do LLM simulado") -> None:
        self.secao(f"{titulo} (não foram geradas por um LLM)")
        for i, resposta in enumerate(respostas, 1):
            self.linha(f"  {i}. {_descrever_mock(resposta)}")

    def chamadas_llm(self, registro: list[dict[str, Any]]) -> None:
        self.linha(f"Chamadas ao LLM simulado: {len(registro)}")
        for i, chamada in enumerate(registro, 1):
            self.linha(f"  {i}. {chamada['prompt']} | ferramentas vinculadas={chamada['ferramentas']} | "
                       f"mensagens={chamada['mensagens']}")
            if chamada["esclarecimento_no_historico"]:
                self.linha(f"     esclarecimento no histórico: {chamada['esclarecimento_no_historico']}")
            if chamada["dados"] and chamada["dados"].get("esclarecimentos_usuario"):
                self.linha(f"     esclarecimentos_usuario nos dados: {chamada['dados']['esclarecimentos_usuario']}")

    def estado(self, estado: dict[str, Any]) -> None:
        verificacao = estado.get("verificacao")
        self.linha(f"status: {estado.get('status')}")
        self.linha(f"tentativas_revisao (revisões automáticas): {estado.get('tentativas_revisao')}")
        self.linha(f"esclarecimentos: {estado.get('esclarecimentos')}")
        self.linha(f"pergunta_pendente: {estado.get('pergunta_pendente')!r}")
        self.linha(f"rascunho: {estado.get('rascunho')!r}")
        if verificacao:
            self.linha(f"verificacao.aprovado: {verificacao['aprovado']}")
            self.linha(f"verificacao.problemas_factuais: {verificacao['problemas_factuais']}")
            self.linha(f"verificacao.problemas_estilo: {verificacao['problemas_estilo']}")
        self.linha(f"mensagens: {[type(m).__name__ for m in estado.get('mensagens', [])]}")

    def verificar(self, descricao: str, condicao: bool) -> None:
        self.verificacoes.append((descricao, bool(condicao)))

    def salvar(self) -> list[tuple[str, bool]]:
        self.secao("Verificações automáticas")
        for descricao, ok in self.verificacoes:
            self.linha(f"  [{'OK' if ok else 'FALHOU'}] {descricao}")
        aprovadas = sum(ok for _, ok in self.verificacoes)
        self.linha(f"Resultado: {aprovadas}/{len(self.verificacoes)} verificações atendidas.")
        self.arquivo.write_text("\n".join(self.linhas) + "\n", encoding="utf-8")
        return self.verificacoes


def _executar_main_em_processo(acao: str, cenario: str, entrada: str, thread_id: str | None = None):
    """Roda o main.py real num processo Python novo, com o LLM simulado."""
    comando = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", acao, cenario]
    if thread_id:
        comando.append(thread_id)
    resultado = subprocess.run(
        comando, input=entrada + "\n", capture_output=True, text=True, encoding="utf-8",
        cwd=RAIZ, env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=120,
    )
    saida, registro, pid = [], [], None
    for linha in resultado.stdout.splitlines():
        if linha.startswith("REGISTRO_LLM="):
            registro = json.loads(linha[len("REGISTRO_LLM="):])
        elif linha.startswith("PID="):
            pid = int(linha[len("PID="):])
        else:
            saida.append(linha)
    return resultado.returncode, "\n".join(saida).strip(), resultado.stderr.strip(), registro, pid


def _worker(acao: str, cenario: str, thread_id: str | None = None) -> int:
    """Executado no processo filho: main.py real, com LLM simulado e banco de testes."""
    main.criar_llm = lambda: LLMSimulado(messages=iter(CENARIOS_PROCESSO[cenario]))
    main.caminho_banco = lambda: BANCO_TESTES
    if acao == "retomar":
        # Se a retomada consultasse o perfil de novo, a ferramenta falharia com este caminho.
        tools.CAMINHO_PERFIL = RAIZ / "data" / "inexistente_prova_de_nao_reconsulta.json"
    codigo = main.main([] if acao == "iniciar" else ["--resume", thread_id])
    sys.stdout.flush()
    # Quebra de linha: o prompt "Resposta: " do main.py não termina a linha.
    print(f"\nPID={os.getpid()}")
    print("REGISTRO_LLM=" + json.dumps(
        [{**r, "dados": None} | {"esclarecimentos_nos_dados": (r["dados"] or {}).get("esclarecimentos_usuario")}
         for r in REGISTRO], ensure_ascii=False))
    return codigo


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def setUpModule():
    BANCO_TESTES.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCIAS.mkdir(exist_ok=True)


class TestesAC3(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        REGISTRO.clear()
        self.perfil_original = json.loads(tools.CAMINHO_PERFIL.read_text(encoding="utf-8"))

    def _concluir(self, evidencia: Evidencia) -> None:
        falhas = [descricao for descricao, ok in evidencia.salvar() if not ok]
        self.assertEqual(falhas, [], f"Verificações não atendidas (ver {evidencia.arquivo.name})")

    def test_A_informacoes_suficientes(self):
        ev = Evidencia("teste_A_informacoes_suficientes", "Teste A — Solicitação com informações suficientes")
        respostas = [CHAMADA_FERRAMENTA, SUFICIENTE, AIMessage(RASCUNHO_FIEL), VERIFICACAO_APROVADA]
        ev.secao("Entrada")
        ev.linha(f"Solicitação: {SOLICITACAO!r}")
        ev.linha("Perfil: data/perfil_exemplo.json (Marina Alves, fatos F01–F03)")
        ev.mock(respostas)
        ev.secao("Resultado esperado")
        ev.linha("consultar_perfil executada uma vez; nenhum interrupt; geração e verificação;")
        ev.linha("status aguardando_aprovacao; 0 revisões; 4 chamadas ao LLM.")

        config = {"configurable": {"thread_id": f"ac3-A-{uuid.uuid4()}"}}
        with SqliteSaver.from_conn_string(str(BANCO_TESTES)) as checkpointer:
            grafo = construir_grafo(LLMSimulado(messages=iter(respostas)), checkpointer)
            grafo.invoke({"solicitacao": SOLICITACAO}, config)
            snapshot = grafo.get_state(config)
            sequencia = _sequencia_nos(grafo, config)
        estado = snapshot.values

        ev.secao("Resultado obtido")
        ev.linha(f"thread_id: {config['configurable']['thread_id']}")
        ev.linha(f"Sequência de nós (histórico do SQLite): {' → '.join(sequencia)}")
        ev.chamadas_llm(REGISTRO)
        ev.linha(f"interrupts pendentes: {list(snapshot.interrupts)} | próximo nó: {snapshot.next}")
        ev.estado(estado)

        ev.verificar("Sequência sem solicitar_esclarecimento e sem revisar_rascunho", sequencia == [
            "decidir_acao", "executar_ferramenta", "observar_resultado",
            "validar_informacoes", "gerar_rascunho", "verificar_rascunho"])
        ev.verificar("Nenhum interrupt pendente e execução encerrada", not snapshot.interrupts and snapshot.next == ())
        ev.verificar("4 chamadas ao LLM (decisão, validação, geração, verificação)",
                     [r["prompt"] for r in REGISTRO] == ["PROMPT_SISTEMA", "PROMPT_VALIDACAO", "PROMPT_GERACAO", "PROMPT_VERIFICACAO"])
        ev.verificar("Ferramenta vinculada somente na decisão inicial",
                     [r["ferramentas"] for r in REGISTRO] == [["consultar_perfil"], None, None, None])
        ev.verificar("consultar_perfil executada uma única vez (1 ToolMessage)", _contar_tool_messages(estado) == 1)
        ev.verificar("Geração recebeu o resultado da ferramenta (ToolMessage no histórico)",
                     "ToolMessage" in REGISTRO[2]["mensagens"])
        ev.verificar("contexto igual ao JSON de origem", estado["contexto"] == self.perfil_original)
        ev.verificar("Solicitação original preservada", estado["solicitacao"] == SOLICITACAO)
        ev.verificar("Status aguardando_aprovacao", estado["status"] == "aguardando_aprovacao")
        ev.verificar("0 revisões automáticas", estado["tentativas_revisao"] == 0)
        self._concluir(ev)

    def test_B_esclarecimento_entre_processos(self):
        ev = Evidencia("teste_B_esclarecimento_retomada",
                       "Teste B — Informação essencial ausente: interrupt, SQLite e retomada em outro processo")
        ev.secao("Entrada")
        ev.linha(f"Solicitação (processo 1): {SOLICITACAO!r}")
        ev.linha(f"Resposta humana fictícia (processo 2): {RESPOSTA_HUMANA!r}")
        ev.mock(CENARIOS_PROCESSO["iniciar_incompleto"], "Processo 1 — respostas PREDEFINIDAS do LLM simulado")
        ev.mock(CENARIOS_PROCESSO["retomar_ok"], "Processo 2 — respostas PREDEFINIDAS do LLM simulado")
        ev.linha("Observação: a avaliação de que falta o tema do projeto é predefinida no mock.")
        ev.secao("Resultado esperado")
        ev.linha("Processo 1: interrupt com a pergunta e o thread_id; estado salvo sem rascunho.")
        ev.linha("Processo 2: Command(resume) no mesmo thread_id; sem nova consulta ao perfil;")
        ev.linha("esclarecimento chega à geração e à verificação; status aguardando_aprovacao.")

        codigo1, saida1, erro1, registro1, pid1 = _executar_main_em_processo("iniciar", "iniciar_incompleto", SOLICITACAO)
        encontrado = re.search(r"thread_id da execução: ([0-9a-f-]{36})", saida1)
        thread_id = encontrado.group(1) if encontrado else ""
        config = {"configurable": {"thread_id": thread_id}}

        ev.secao(f"Processo 1 (PID {pid1}) — python main.py — saída real do terminal")
        ev.linha(saida1)
        if erro1:
            ev.linha(f"[stderr] {erro1}")
        ev.linha(f"Código de saída: {codigo1}")
        ev.chamadas_llm(registro1)

        with SqliteSaver.from_conn_string(str(BANCO_TESTES)) as checkpointer:
            pausado = construir_grafo(LLMSimulado(messages=iter([])), checkpointer).get_state(config)
        ev.secao(f"Inspeção do SQLite após o fim do processo 1 (processo de teste, PID {os.getpid()})")
        ev.linha(f"próximo nó: {pausado.next}")
        ev.linha(f"interrupts pendentes: {[i.value for i in pausado.interrupts]}")
        ev.estado(pausado.values)

        codigo2, saida2, erro2, registro2, pid2 = _executar_main_em_processo("retomar", "retomar_ok", RESPOSTA_HUMANA, thread_id)
        ev.secao(f"Processo 2 (PID {pid2}) — python main.py --resume {thread_id} — saída real do terminal")
        ev.linha(saida2)
        if erro2:
            ev.linha(f"[stderr] {erro2}")
        ev.linha(f"Código de saída: {codigo2}")
        ev.chamadas_llm([{**r, "dados": {"esclarecimentos_usuario": r["esclarecimentos_nos_dados"]}} for r in registro2])

        with SqliteSaver.from_conn_string(str(BANCO_TESTES)) as checkpointer:
            grafo = construir_grafo(LLMSimulado(messages=iter([])), checkpointer)
            final = grafo.get_state(config)
            sequencia = _sequencia_nos(grafo, config)
        estado = final.values
        ev.secao("Estado final recuperado do SQLite")
        ev.linha(f"Sequência de nós (histórico do SQLite): {' → '.join(sequencia)}")
        ev.linha(f"próximo nó: {final.next} | interrupts pendentes: {list(final.interrupts)}")
        ev.estado(estado)

        prompts2 = [r["prompt"] for r in registro2]
        ev.verificar("Processo 1 terminou normalmente (código 0)", codigo1 == 0)
        ev.verificar("Terminal mostrou a pergunta, o thread_id e o comando de retomada",
                     PERGUNTA in saida1 and thread_id and f"--resume {thread_id}" in saida1)
        ev.verificar("Execução suspensa em solicitar_esclarecimento com interrupt do tipo esclarecimento",
                     pausado.next == ("solicitar_esclarecimento",)
                     and [i.value for i in pausado.interrupts] == [{"tipo": "esclarecimento", "pergunta": PERGUNTA}])
        ev.verificar("Estado pausado sem rascunho e sem verificação",
                     "rascunho" not in pausado.values and "verificacao" not in pausado.values)
        ev.verificar("Processos 1 e 2 distintos (PIDs diferentes)", pid1 is not None and pid2 is not None and pid1 != pid2)
        ev.verificar("Processo 2 terminou normalmente (código 0)", codigo2 == 0)
        ev.verificar("Processo 2 não repetiu a decisão nem a consulta ao perfil",
                     "PROMPT_SISTEMA" not in prompts2 and _contar_tool_messages(estado) == 1)
        ev.verificar("Processo 2 fez validação, geração e verificação",
                     prompts2 == ["PROMPT_VALIDACAO", "PROMPT_GERACAO", "PROMPT_VERIFICACAO"])
        ev.verificar("Esclarecimento chegou ao histórico enviado à geração",
                     any(RESPOSTA_HUMANA in m for m in registro2[1]["esclarecimento_no_historico"]))
        ev.verificar("Esclarecimento chegou aos dados da verificação",
                     registro2[2]["esclarecimentos_nos_dados"] == [RESPOSTA_HUMANA])
        ev.verificar("Esclarecimento armazenado no estado e pergunta pendente limpa",
                     estado.get("esclarecimentos") == [RESPOSTA_HUMANA] and estado.get("pergunta_pendente") is None)
        ev.verificar("Solicitação original preservada", estado.get("solicitacao") == SOLICITACAO)
        ev.verificar("Status aguardando_aprovacao e 0 revisões",
                     estado.get("status") == "aguardando_aprovacao" and estado.get("tentativas_revisao") == 0)
        self._concluir(ev)

    def test_B2_resposta_vazia_na_retomada(self):
        ev = Evidencia("teste_B2_resposta_vazia",
                       "Teste B (complementar) — Problema da resposta vazia na retomada e ajuste aplicado")

        ev.secao("Parte 1 — Mecanismo do problema, reproduzido num grafo MÍNIMO (não é o código do agente)")
        ev.linha("Um nó que lança exceção ao receber resposta vazia após interrupt().")

        class Estado(TypedDict):
            resposta: NotRequired[str]

        def no_que_lanca_erro(state):
            valor = interrupt({"tipo": "esclarecimento", "pergunta": "?"})
            if not isinstance(valor, str) or not valor.strip():
                raise ValueError("resposta vazia")
            return {"resposta": valor}

        construtor = StateGraph(Estado)
        construtor.add_node("perguntar", no_que_lanca_erro)
        construtor.add_edge(START, "perguntar")
        construtor.add_edge("perguntar", END)
        minimo = construtor.compile(checkpointer=InMemorySaver())
        cfg_minimo = {"configurable": {"thread_id": "grafo-minimo"}}
        minimo.invoke({}, cfg_minimo)
        resultados_minimo = []
        for tentativa in ("   ", "resposta válida"):
            try:
                retorno = minimo.invoke(Command(resume=tentativa), cfg_minimo)
                resultados_minimo.append(f"Command(resume={tentativa!r}) -> concluiu: {retorno}")
            except ValueError as exc:
                resultados_minimo.append(f"Command(resume={tentativa!r}) -> ValueError: {exc}")
        for linha in resultados_minimo:
            ev.linha(f"  {linha}")
        ev.linha("Conclusão: a resposta vazia fica registrada no checkpoint e é reaproveitada;")
        ev.linha("até a resposta válida falha, e o thread não pode mais ser retomado.")

        ev.secao("Parte 2 — Agente atual (solicitar_esclarecimento repete o interrupt)")
        respostas = [CHAMADA_FERRAMENTA, INSUFICIENTE, SUFICIENTE, AIMessage(RASCUNHO_COM_TEMA), VERIFICACAO_APROVADA]
        ev.mock(respostas)
        config = {"configurable": {"thread_id": f"ac3-B2-{uuid.uuid4()}"}}
        with SqliteSaver.from_conn_string(str(BANCO_TESTES)) as checkpointer:
            grafo = construir_grafo(LLMSimulado(messages=iter(respostas)), checkpointer)
            grafo.invoke({"solicitacao": SOLICITACAO}, config)
            grafo.invoke(Command(resume="   "), config)
            apos_vazia = grafo.get_state(config)
            grafo.invoke(Command(resume=RESPOSTA_HUMANA), config)
            apos_valida = grafo.get_state(config)
        ev.linha("Após Command(resume='   '):")
        ev.linha(f"  próximo nó: {apos_vazia.next}")
        ev.linha(f"  interrupts pendentes: {[i.value for i in apos_vazia.interrupts]}")
        ev.linha(f"  esclarecimentos: {apos_vazia.values.get('esclarecimentos')}")
        ev.linha(f"Após Command(resume={RESPOSTA_HUMANA!r}):")
        ev.estado(apos_valida.values)

        ev.secao("Parte 3 — main.py --resume com resposta vazia (processo separado)")
        with SqliteSaver.from_conn_string(str(BANCO_TESTES)) as checkpointer:
            g = construir_grafo(LLMSimulado(messages=iter([CHAMADA_FERRAMENTA, INSUFICIENTE])), checkpointer)
            cfg3 = {"configurable": {"thread_id": f"ac3-B2-main-{uuid.uuid4()}"}}
            g.invoke({"solicitacao": SOLICITACAO}, cfg3)
        codigo, saida, erro, registro, _ = _executar_main_em_processo(
            "retomar", "retomar_ok", "", cfg3["configurable"]["thread_id"])
        ev.linha(saida)
        ev.linha(f"[stderr] {erro}")
        ev.linha(f"Código de saída: {codigo} | chamadas ao LLM: {len(registro)}")
        with SqliteSaver.from_conn_string(str(BANCO_TESTES)) as checkpointer:
            ainda_pausado = construir_grafo(LLMSimulado(messages=iter([])), checkpointer).get_state(cfg3)
        ev.linha(f"Depois: próximo nó = {ainda_pausado.next} (o thread continua aguardando)")

        ev.verificar("Grafo mínimo: resposta válida também falha depois da vazia (problema reproduzido)",
                     all("ValueError" in r for r in resultados_minimo))
        ev.verificar("Agente: resposta vazia gera novo interrupt com aviso, sem registrar esclarecimento",
                     apos_vazia.next == ("solicitar_esclarecimento",)
                     and apos_vazia.interrupts and apos_vazia.interrupts[0].value.get("aviso")
                     and not apos_vazia.values.get("esclarecimentos"))
        ev.verificar("Agente: resposta válida depois da vazia é aceita e o fluxo conclui",
                     apos_valida.values.get("esclarecimentos") == [RESPOSTA_HUMANA]
                     and apos_valida.values.get("status") == "aguardando_aprovacao")
        ev.verificar("main.py: resposta vazia recusada antes de chamar o grafo (código 1, 0 chamadas ao LLM)",
                     codigo == 1 and "não pode ser vazia" in erro and registro == [])
        ev.verificar("main.py: thread continua aguardando esclarecimento",
                     ainda_pausado.next == ("solicitar_esclarecimento",))
        self._concluir(ev)

    def test_C_fato_nao_autorizado(self):
        ev = Evidencia("teste_C_fato_nao_autorizado",
                       "Teste C — Rascunho com fatos não autorizados: reprovação, uma revisão e nova verificação")
        respostas = [CHAMADA_FERRAMENTA, SUFICIENTE, AIMessage(RASCUNHO_NAO_AUTORIZADO), VERIFICACAO_REPROVADA,
                     AIMessage(RASCUNHO_FIEL), VERIFICACAO_APROVADA]
        ev.secao("Entrada")
        ev.linha(f"Solicitação: {SOLICITACAO!r}")
        ev.mock(respostas)
        ev.linha("Observação: o rascunho com fatos inventados, a reprovação, o texto revisado e a")
        ev.linha("aprovação final são todos predefinidos. O teste demonstra o controle do fluxo,")
        ev.linha("não a capacidade de detectar ou corrigir fatos.")
        ev.secao("Resultado esperado")
        ev.linha("Primeira verificação reprova com problemas factuais e de estilo separados;")
        ev.linha("uma revisão recebe os problemas; segunda verificação aprova;")
        ev.linha("status aguardando_aprovacao; 1 revisão; 6 chamadas ao LLM.")

        config = {"configurable": {"thread_id": f"ac3-C-{uuid.uuid4()}"}}
        with SqliteSaver.from_conn_string(str(BANCO_TESTES)) as checkpointer:
            grafo = construir_grafo(LLMSimulado(messages=iter(respostas)), checkpointer)
            grafo.invoke({"solicitacao": SOLICITACAO}, config)
            snapshot = grafo.get_state(config)
            sequencia = _sequencia_nos(grafo, config)
            primeira = next(h.values for h in reversed(list(grafo.get_state_history(config)))
                            if h.values.get("verificacao"))
        estado = snapshot.values
        revisao = next(r for r in REGISTRO if r["prompt"] == "PROMPT_REVISAO")

        ev.secao("Resultado obtido")
        ev.linha(f"thread_id: {config['configurable']['thread_id']}")
        ev.linha(f"Sequência de nós (histórico do SQLite): {' → '.join(sequencia)}")
        ev.chamadas_llm(REGISTRO)
        ev.linha("Primeira verificação (recuperada do histórico do SQLite):")
        ev.linha(f"  status: {primeira['status']}")
        ev.linha(f"  rascunho avaliado: {primeira['rascunho']!r}")
        ev.linha(f"  problemas_factuais: {primeira['verificacao']['problemas_factuais']}")
        ev.linha(f"  problemas_estilo: {primeira['verificacao']['problemas_estilo']}")
        ev.linha("Dados recebidos pela revisão:")
        ev.linha(f"  rascunho_anterior: {revisao['dados']['rascunho_anterior']!r}")
        ev.linha(f"  problemas_factuais: {len(revisao['dados']['problemas_factuais'])} | "
                 f"problemas_estilo: {len(revisao['dados']['problemas_estilo'])}")
        ev.secao("Estado final")
        ev.estado(estado)

        ev.verificar("Sequência com exatamente uma revisão e duas verificações", sequencia == [
            "decidir_acao", "executar_ferramenta", "observar_resultado", "validar_informacoes",
            "gerar_rascunho", "verificar_rascunho", "revisar_rascunho", "verificar_rascunho"])
        ev.verificar("6 chamadas ao LLM na ordem esperada", [r["prompt"] for r in REGISTRO] == [
            "PROMPT_SISTEMA", "PROMPT_VALIDACAO", "PROMPT_GERACAO", "PROMPT_VERIFICACAO",
            "PROMPT_REVISAO", "PROMPT_VERIFICACAO"])
        ev.verificar("Primeira verificação reprovou com status em_revisao",
                     primeira["verificacao"]["aprovado"] is False and primeira["status"] == "em_revisao")
        ev.verificar("Problemas factuais e de estilo registrados separadamente",
                     len(primeira["verificacao"]["problemas_factuais"]) == 3
                     and len(primeira["verificacao"]["problemas_estilo"]) == 2)
        ev.verificar("Revisão recebeu o rascunho anterior e os problemas apontados",
                     revisao["dados"]["rascunho_anterior"] == RASCUNHO_NAO_AUTORIZADO
                     and len(revisao["dados"]["problemas_factuais"]) == 3)
        ev.verificar("Revisão sem ferramentas vinculadas", revisao["ferramentas"] is None)
        ev.verificar("Rascunho final é o texto revisado", estado["rascunho"] == RASCUNHO_FIEL)
        ev.verificar("Verificação final aprovada", estado["verificacao"]["aprovado"] is True)
        ev.verificar("1 revisão automática", estado["tentativas_revisao"] == 1)
        ev.verificar("Status aguardando_aprovacao", estado["status"] == "aguardando_aprovacao")
        ev.verificar("consultar_perfil executada uma única vez", _contar_tool_messages(estado) == 1)
        ev.verificar("Solicitação original preservada", estado["solicitacao"] == SOLICITACAO)
        self._concluir(ev)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        sys.exit(_worker(*sys.argv[2:]))
    unittest.main(verbosity=2)
