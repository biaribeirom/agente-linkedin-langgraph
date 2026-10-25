// Resumo dos testes técnicos da AC3, transcrito dos logs reais em evidencias/
// (cópias idênticas em public/evidencias/, com extensão .txt).

export type ResumoTeste = {
  id: string;
  nome: string;
  objetivo: string;
  observado: string;
  verificacoes: string;
  classificacao: string;
  arquivo: string;
};

export const TESTES: ResumoTeste[] = [
  {
    id: "A",
    nome: "Informações suficientes",
    objetivo: "Consultar o perfil, gerar e verificar o rascunho sem pedir esclarecimento.",
    observado:
      "Sequência decidir_acao → executar_ferramenta → observar_resultado → validar_informacoes → " +
      "gerar_rascunho → verificar_rascunho; 4 chamadas ao LLM simulado; consultar_perfil executada uma vez; " +
      "status aguardando_aprovacao; 0 revisões.",
    verificacoes: "10/10",
    classificacao: "Satisfatório",
    arquivo: "/evidencias/teste_A_informacoes_suficientes.txt",
  },
  {
    id: "B",
    nome: "Esclarecimento e retomada",
    objetivo: "Interromper por falta de informação essencial e retomar em outro processo Python.",
    observado:
      "Processo 1 pausou em solicitar_esclarecimento e mostrou a pergunta e o thread_id; o estado ficou no SQLite " +
      "sem rascunho. Processo 2, com outro PID, retomou com Command(resume) sem nova consulta ao perfil; o " +
      "esclarecimento chegou à geração e à verificação; status aguardando_aprovacao.",
    verificacoes: "13/13",
    classificacao: "Satisfatório",
    arquivo: "/evidencias/teste_B_esclarecimento_retomada.txt",
  },
  {
    id: "C",
    nome: "Fatos não autorizados",
    objetivo: "Reprovar um rascunho com fatos inventados, fazer uma revisão e verificar de novo.",
    observado:
      "Primeira verificação reprovou com 3 problemas factuais e 2 de estilo, registrados separadamente; uma revisão " +
      "recebeu o rascunho anterior e os problemas; a nova verificação aprovou; 6 chamadas ao LLM simulado; 1 revisão.",
    verificacoes: "12/12",
    classificacao: "Satisfatório quanto ao fluxo; a detecção dos fatos foi predefinida e não foi avaliada",
    arquivo: "/evidencias/teste_C_fato_nao_autorizado.txt",
  },
  {
    id: "B2",
    nome: "Resposta vazia",
    objetivo: "Documentar o problema da resposta vazia na retomada e o ajuste aplicado.",
    observado:
      "Num grafo mínimo, lançar erro deixou o thread travado até para uma resposta válida. No agente, a resposta " +
      "vazia gerou um novo interrupt com aviso e a resposta válida seguinte foi aceita; o main.py recusou a " +
      "resposta vazia sem chamar o LLM.",
    verificacoes: "5/5",
    classificacao: "Satisfatório",
    arquivo: "/evidencias/teste_B2_resposta_vazia.txt",
  },
];

export const TOTAL_VERIFICACOES = "40/40";
export const ARQUIVO_UNITTEST = "/evidencias/execucao_unittest.txt";
