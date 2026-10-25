// Montagem determinística de posts por templates, sem IA e sem rede.
// O texto usa somente o que a pessoa digitou; as frases fixas não afirmam fatos sobre ela.

export type Tom = "natural" | "profissional" | "inspirador";

export type DadosPost = {
  nome: string;
  profissao: string;
  experiencia: string;
  aprendizado: string;
  tom: Tom;
  exemplos: string; // apenas referência para a pessoa; não entra no texto
};

export const DADOS_VAZIOS: DadosPost = {
  nome: "",
  profissao: "",
  experiencia: "",
  aprendizado: "",
  tom: "natural",
  exemplos: "",
};

export const LIMITE_CARACTERES_LINKEDIN = 3000;

export const CAMPOS_OBRIGATORIOS: { campo: keyof DadosPost; rotulo: string }[] = [
  { campo: "nome", rotulo: "Nome" },
  { campo: "profissao", rotulo: "Profissão ou área de atuação" },
  { campo: "experiencia", rotulo: "Experiência, projeto ou acontecimento" },
];

export const TEMPLATES: Record<Tom, { abertura: string; rotuloAprendizado: string; fechamento: string }> = {
  natural: {
    abertura: "Quero compartilhar uma experiência por aqui.",
    rotuloAprendizado: "O que levo disso:",
    fechamento: "E você, já passou por algo parecido?",
  },
  profissional: {
    abertura: "Compartilho uma experiência da minha trajetória.",
    rotuloAprendizado: "Principal aprendizado:",
    fechamento: "Fico à disposição para trocar ideias sobre o tema.",
  },
  inspirador: {
    abertura: "Cada passo da trajetória conta, e este é um deles.",
    rotuloAprendizado: "O que quero levar adiante:",
    fechamento: "Que venham os próximos passos.",
  },
};

export function camposFaltando(dados: DadosPost): string[] {
  return CAMPOS_OBRIGATORIOS.filter(({ campo }) => !dados[campo].trim()).map(({ rotulo }) => rotulo);
}

/** Ajusta só a forma: espaços, inicial maiúscula e pontuação final. O conteúdo não muda. */
export function comoFrase(texto: string): string {
  const limpo = texto.trim().replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n");
  if (!limpo) return "";
  const comInicial = limpo.charAt(0).toUpperCase() + limpo.slice(1);
  return /[.!?…]$/.test(comInicial) ? comInicial : `${comInicial}.`;
}

export type ResultadoGeracao = { ok: true; texto: string } | { ok: false; faltando: string[] };

export function gerarPost(dados: DadosPost): ResultadoGeracao {
  const faltando = camposFaltando(dados);
  if (faltando.length) return { ok: false, faltando };

  const modelo = TEMPLATES[dados.tom];
  const partes = [modelo.abertura, comoFrase(dados.experiencia)];
  if (dados.aprendizado.trim()) {
    partes.push(`${modelo.rotuloAprendizado}\n${comoFrase(dados.aprendizado)}`);
  }
  partes.push(modelo.fechamento);
  return { ok: true, texto: partes.join("\n\n") };
}
