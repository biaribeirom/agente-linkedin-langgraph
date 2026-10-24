"""Ponto de entrada do Agente LinkedIn pelo terminal.

Execução nova:  python main.py
Retomada:       python main.py --resume THREAD_ID
"""

import argparse
import sys
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command, StateSnapshot

from src.graph import ErroAgente, ErroConfiguracao, construir_grafo, criar_llm


def caminho_banco() -> Path:
    """Banco de checkpoints na pasta do usuário, fora do OneDrive e do repositório.

    Evita AppData, que o Python da Microsoft Store redireciona para a pasta do pacote.
    """
    return Path.home() / ".agente-linkedin" / "checkpoints.sqlite"


def _pedido_esclarecimento(snapshot: StateSnapshot) -> dict[str, Any] | None:
    """Devolve o pedido de esclarecimento pendente no thread, se houver."""
    for pendente in snapshot.interrupts:
        if isinstance(pendente.value, dict) and pendente.value.get("tipo") == "esclarecimento":
            return pendente.value
    return None


def _exibir_resultado(snapshot: StateSnapshot, thread_id: str, banco: Path) -> None:
    pedido = _pedido_esclarecimento(snapshot)
    if pedido:
        print("\nO agente precisa de um esclarecimento antes de continuar.")
        if pedido.get("aviso"):
            print(pedido["aviso"])
        print(f"Pergunta: {pedido['pergunta']}")
        print(f"thread_id: {thread_id}")
        print(f"Para responder: python main.py --resume {thread_id}")
        return

    estado = snapshot.values
    if estado.get("status") == "informacoes_insuficientes":
        print("\nMesmo com o esclarecimento, ainda faltam informações essenciais. Nenhum post foi gerado.")
        print(f"Informação ainda ausente: {estado['pergunta_pendente']}")
        print(f"Status: {estado['status']}")
        return

    chamada = estado["mensagens"][1].tool_calls[0]
    contexto = estado["contexto"]
    print(f"O modelo solicitou a ferramenta: {chamada['name']}")
    print("Perfil consultado com sucesso.")
    print(f"Nome: {contexto['perfil']['nome']}")
    print(f"Fatos autorizados: {len(contexto['fatos_autorizados'])}")
    print(f"Exemplos de posts: {len(contexto['exemplos_posts'])}")
    print("\nRascunho final:\n")
    print(estado["rascunho"])

    verificacao = estado["verificacao"]
    print(f"\nVerificação: {'aprovado' if verificacao['aprovado'] else 'reprovado'}")
    for titulo, campo in (("Problemas factuais", "problemas_factuais"), ("Problemas de estilo", "problemas_estilo")):
        if verificacao[campo]:
            print(f"{titulo}:")
            for problema in verificacao[campo]:
                print(f"  - {problema}")
    print(f"Revisões automáticas: {estado['tentativas_revisao']}")
    print(f"Status: {estado['status']}")
    print(f"\nEstado salvo em {banco} (thread_id: {thread_id})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agente LinkedIn")
    parser.add_argument("--resume", metavar="THREAD_ID", help="retoma uma execução que aguarda esclarecimento")
    args = parser.parse_args(argv)

    load_dotenv()
    try:
        llm = criar_llm()
    except ErroConfiguracao as exc:
        print(f"Erro de configuração: {exc}", file=sys.stderr)
        return 1

    banco = caminho_banco()
    if args.resume:
        # Não abre o SQLite se ele não existe, para não criar um banco vazio numa retomada.
        if not banco.exists():
            print(f"Erro: thread_id não encontrado: {args.resume}", file=sys.stderr)
            return 1
    else:
        banco.parent.mkdir(parents=True, exist_ok=True)

    # A conexão fica aberta durante toda a execução do grafo e é fechada ao sair do bloco.
    with SqliteSaver.from_conn_string(str(banco)) as checkpointer:
        grafo = construir_grafo(llm, checkpointer)

        if args.resume:
            thread_id = args.resume
            config = {"configurable": {"thread_id": thread_id}}
            snapshot = grafo.get_state(config)
            if not snapshot.values:
                print(f"Erro: thread_id não encontrado: {thread_id}", file=sys.stderr)
                return 1
            pedido = _pedido_esclarecimento(snapshot)
            if pedido is None:
                print(f"Erro: a execução {thread_id} não está aguardando esclarecimento.", file=sys.stderr)
                return 1
            print(f"Pergunta: {pedido['pergunta']}")
            resposta = input("Resposta: ").strip()
            if not resposta:
                print("Erro: a resposta não pode ser vazia. A execução continua aguardando.", file=sys.stderr)
                return 1
            entrada = Command(resume=resposta)
        else:
            solicitacao = input("Solicitação: ")
            # Cada solicitação é uma execução independente, com seu próprio thread_id.
            thread_id = str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}
            entrada = {"solicitacao": solicitacao}

        print(f"thread_id da execução: {thread_id}")
        try:
            grafo.invoke(entrada, config)
        except ErroAgente as exc:
            print(f"Falha na execução: {exc}", file=sys.stderr)
            print(f"Estado parcial salvo no thread_id: {thread_id}", file=sys.stderr)
            return 1
        snapshot = grafo.get_state(config)

    _exibir_resultado(snapshot, thread_id, banco)
    return 0


if __name__ == "__main__":
    sys.exit(main())
