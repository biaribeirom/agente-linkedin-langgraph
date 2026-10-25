// Dados da demonstração: os mesmos cenários e textos predefinidos dos testes da AC3
// (tests/test_ac3.py). Nada aqui é gerado por um modelo de IA.
//
// Uma futura integração com o agente Python poderia substituir estes dados pelo
// resultado real do grafo, mantendo os mesmos tipos.

export type Fato = { id: string; descricao: string };

export const PERFIL = {
  nome: "Marina Alves",
  profissao: "Estudante de Ciência de Dados",
  area: "Dados e Inteligência Artificial",
  fatos: [
    { id: "F01", descricao: "Cursa graduação em Ciência de Dados." },
    { id: "F02", descricao: "Participou de um workshop universitário sobre IA aplicada." },
    { id: "F03", descricao: "Apresentou um projeto de análise de dados durante esse workshop." },
  ] satisfies Fato[],
};

export type TipoEtapa = "ok" | "alerta" | "erro";

export type Etapa = {
  no: string; // nó correspondente no grafo LangGraph
  titulo: string;
  detalhe: string;
  tipo: TipoEtapa;
  rascunho?: string;
  problemas?: { factuais: string[]; estilo: string[] };
  pergunta?: string;
};

export type IdCenario = "suficiente" | "esclarecimento" | "inventado";

export type Cenario = {
  id: IdCenario;
  nome: string;
  descricao: string;
  solicitacao: string;
  etapas: Etapa[];
  rascunhoFinal: string;
  revisoes: number;
  aviso?: string;
};

const SOLICITACAO = "Quero um post sobre a apresentação do meu projeto no workshop de IA aplicada.";

const RASCUNHO_FIEL =
  "Apresentei um projeto de análise de dados no workshop de IA aplicada da universidade. " +
  "Explicar o raciocínio por trás da análise foi um ótimo aprendizado. 💡";

export const RESPOSTA_EXEMPLO = "O projeto analisou dados fictícios de evasão escolar.";

const ETAPAS_CONSULTA: Etapa[] = [
  {
    no: "decidir_acao",
    titulo: "Decisão do agente",
    detalhe: "O agente solicita a ferramenta consultar_perfil.",
    tipo: "ok",
  },
  {
    no: "executar_ferramenta",
    titulo: "Consulta ao perfil",
    detalhe: "3 fatos autorizados e 2 exemplos de escrita recuperados.",
    tipo: "ok",
  },
];

export const CENARIOS: Cenario[] = [
  {
    id: "suficiente",
    nome: "Informações suficientes",
    descricao: "Os fatos do perfil bastam para escrever o post.",
    solicitacao: SOLICITACAO,
    etapas: [
      ...ETAPAS_CONSULTA,
      { no: "validar_informacoes", titulo: "Validação", detalhe: "Informações suficientes.", tipo: "ok" },
      { no: "gerar_rascunho", titulo: "Geração do rascunho", detalhe: "Rascunho baseado em F02 e F03.", tipo: "ok" },
      { no: "verificar_rascunho", titulo: "Verificação factual e de estilo", detalhe: "Aprovado, sem problemas.", tipo: "ok" },
    ],
    rascunhoFinal: RASCUNHO_FIEL,
    revisoes: 0,
  },
  {
    id: "esclarecimento",
    nome: "Preciso de um esclarecimento",
    descricao: "Falta uma informação essencial e o agente pergunta antes de escrever.",
    solicitacao: SOLICITACAO,
    etapas: [
      ...ETAPAS_CONSULTA,
      {
        no: "validar_informacoes",
        titulo: "Validação",
        detalhe: "Falta uma informação essencial.",
        tipo: "alerta",
      },
      {
        no: "solicitar_esclarecimento",
        titulo: "Pedido de esclarecimento",
        detalhe: "A execução fica pausada até a resposta.",
        tipo: "alerta",
        pergunta: "Qual foi o tema do projeto de análise de dados que você apresentou?",
      },
      { no: "validar_informacoes", titulo: "Nova validação", detalhe: "Informações suficientes.", tipo: "ok" },
      {
        no: "gerar_rascunho",
        titulo: "Geração do rascunho",
        detalhe: "Rascunho baseado em F02, F03 e no esclarecimento.",
        tipo: "ok",
      },
      { no: "verificar_rascunho", titulo: "Verificação factual e de estilo", detalhe: "Aprovado, sem problemas.", tipo: "ok" },
    ],
    rascunhoFinal:
      "No workshop de IA aplicada, apresentei meu projeto de análise de dados sobre evasão escolar. " +
      "Foi muito bom compartilhar o raciocínio por trás da análise. 💡",
    revisoes: 0,
    aviso:
      `Na demonstração, sua resposta não é interpretada: o rascunho é fixo e usa a resposta de exemplo ` +
      `dos testes (“${RESPOSTA_EXEMPLO}”).`,
  },
  {
    id: "inventado",
    nome: "Verificação de informações inventadas",
    descricao: "O primeiro rascunho traz fatos não autorizados e passa por uma revisão.",
    solicitacao: SOLICITACAO,
    etapas: [
      ...ETAPAS_CONSULTA,
      { no: "validar_informacoes", titulo: "Validação", detalhe: "Informações suficientes.", tipo: "ok" },
      {
        no: "gerar_rascunho",
        titulo: "Geração do rascunho",
        detalhe: "Exemplo predefinido de rascunho com informações inventadas.",
        tipo: "alerta",
        rascunho:
          "Como Cientista de Dados Sênior na DataX, venci o workshop de IA aplicada com um modelo " +
          "de 98% de acurácia! 🚀🔥 Inovação disruptiva sempre!",
      },
      {
        no: "verificar_rascunho",
        titulo: "Verificação factual e de estilo",
        detalhe: "Reprovado.",
        tipo: "erro",
        problemas: {
          factuais: [
            "“Cientista de Dados Sênior na DataX”: cargo e empresa sem suporte; F01 indica apenas que Marina cursa graduação.",
            "“venci o workshop”: conquista sem suporte; F02 e F03 indicam apenas participação e apresentação.",
            "“98% de acurácia”: número sem suporte nos fatos autorizados.",
          ],
          estilo: ["Dois emojis; o limite é um.", "“Inovação disruptiva sempre!”: frase genérica e exagerada."],
        },
      },
      {
        no: "revisar_rascunho",
        titulo: "Revisão automática (1 de 1)",
        detalhe: "Afirmações sem suporte removidas e estilo ajustado.",
        tipo: "ok",
      },
      { no: "verificar_rascunho", titulo: "Nova verificação", detalhe: "Aprovado, sem problemas.", tipo: "ok" },
    ],
    rascunhoFinal: RASCUNHO_FIEL,
    revisoes: 1,
  },
];
