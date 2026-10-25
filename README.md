# agente-linkedin-langgraph
Agente de IA para geração personalizada e validação de posts no LinkedIn, desenvolvido com Python, LangGraph e ReAct.

Protótipo mínimo da AC3 (IA e Agentes Computacionais em Sistemas Complexos — IBMEC). O agente gera **rascunhos**; não publica nada no LinkedIn.

## Fluxo do agente

```
START → decidir_acao → executar_ferramenta → observar_resultado → validar_informacoes
validar_informacoes → gerar_rascunho                      (informações suficientes)
validar_informacoes → solicitar_esclarecimento (interrupt) → validar_informacoes   (no máximo uma vez)
validar_informacoes → END                                 (ainda insuficiente: informacoes_insuficientes)
gerar_rascunho → verificar_rascunho → END                 (aprovado: aguardando_aprovacao)
verificar_rascunho → revisar_rascunho → verificar_rascunho (no máximo uma revisão automática)
verificar_rascunho → END                                  (reprovado após a revisão: revisao_humana_necessaria)
```

- Fonte única de dados profissionais: `data/perfil_exemplo.json` (perfil **fictício**).
- Ferramenta única: `consultar_perfil` (`src/tools.py`), chamada pelo LLM via tool calling.
- Estado persistido com SQLite Checkpointer em `~/.agente-linkedin/checkpoints.sqlite`, fora do repositório.

## Ambiente

- Python 3.11 com as dependências de `requirements.txt`.
- Ambiente virtual usado no desenvolvimento: `C:\venvs\agente-linkedin` (fora do OneDrive).

```powershell
py -3.11 -m venv C:\venvs\agente-linkedin
C:\venvs\agente-linkedin\Scripts\python.exe -m pip install -r requirements.txt
```

## Configuração da API (somente para uso com LLM real)

Crie um arquivo `.env` na raiz do projeto, a partir de `.env.example`, com `OPENAI_API_KEY` e `OPENAI_MODEL`. O `.env` é ignorado pelo Git. Nunca versione a chave.

## Execução pelo terminal

```powershell
C:\venvs\agente-linkedin\Scripts\python.exe main.py                     # nova execução
C:\venvs\agente-linkedin\Scripts\python.exe main.py --resume THREAD_ID  # responde a um esclarecimento
```

Cada execução recebe um `thread_id`. Se o agente precisar de um esclarecimento, o terminal mostra a pergunta e o comando de retomada.

## Testes da AC3

Os testes usam **exclusivamente um LLM simulado**, com rede bloqueada. Nenhuma chamada é feita à OpenAI, e não é preciso `.env`.

```powershell
C:\venvs\agente-linkedin\Scripts\python.exe tests\test_ac3.py
```

| Teste | Cenário |
|---|---|
| A | Informações suficientes: consulta ao perfil, geração e verificação |
| B | Informação essencial ausente: `interrupt()`, SQLite e retomada com `Command(resume=...)` em outro processo Python (via `main.py`) |
| B2 | Complementar: resposta vazia na retomada (problema e ajuste) |
| C | Rascunho com fatos não autorizados: reprovação, uma revisão e nova verificação |

Cada teste grava um log em `evidencias/`, com a entrada, as respostas predefinidas do mock, o resultado esperado, o resultado obtido e as verificações automáticas. A saída do `unittest` fica em `evidencias/execucao_unittest.log`. Os testes usam um banco separado, `~/.agente-linkedin/checkpoints_testes.sqlite`.

## Problema encontrado e ajuste

Durante o desenvolvimento do esclarecimento, um teste exploratório num grafo mínimo mostrou que, se o nó lança uma exceção ao receber uma resposta vazia via `Command(resume=...)`, essa resposta fica registrada no checkpoint e é reaproveitada nas retomadas seguintes. Assim, até uma resposta válida falha, e o thread fica sem saída.

Ajuste aplicado antes da integração: `solicitar_esclarecimento` repete o `interrupt()` com um aviso quando a resposta é vazia, e o `main.py` recusa respostas vazias antes de retomar. O teste B2 reproduz o mecanismo no grafo mínimo e confirma o comportamento atual do agente.

## Limitações

- **Os testes com mock validam o fluxo, não a qualidade do modelo.** Rascunhos, vereditos de suficiência e verificações são respostas predefinidas. Os testes não demonstram que um LLM real detecta lacunas, evita inventar fatos ou verifica corretamente.
- O agente ainda não foi executado com um modelo real da OpenAI.
- O código não confere sozinho as regras de estilo (por exemplo, o limite de emojis): essa conferência depende do LLM verificador.
- Erros da API (chave inválida, modelo inexistente, limite de uso) aparecem como traceback do Python, sem mensagem tratada.
- Com a entrada enviada por pipe, a saída aparece na mesma linha do prompt (`Solicitação: …`). Isso não acontece quando se digita no terminal.
- Sem aprovação humana final nem publicação: o fluxo termina em `aguardando_aprovacao`.
