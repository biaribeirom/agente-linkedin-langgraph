// Lógica da demonstração, sem dependência de React, para poder ser testada isoladamente.

import { CENARIOS, type Cenario, type IdCenario } from "./cenarios";

export type EstadoDemo = {
  cenario: IdCenario | null;
  executando: boolean;
  visiveis: number; // quantidade de etapas já exibidas
  resposta: string;
  respostaEnviada: string | null;
  erroResposta: string | null;
};

export type Acao =
  | { tipo: "selecionar"; cenario: IdCenario }
  | { tipo: "executar" }
  | { tipo: "avancar" }
  | { tipo: "digitar"; texto: string }
  | { tipo: "continuar" }
  | { tipo: "reiniciar" };

export const ESTADO_INICIAL: EstadoDemo = {
  cenario: null,
  executando: false,
  visiveis: 0,
  resposta: "",
  respostaEnviada: null,
  erroResposta: null,
};

export function cenarioAtual(estado: EstadoDemo): Cenario | null {
  return CENARIOS.find((c) => c.id === estado.cenario) ?? null;
}

export function aguardandoResposta(estado: EstadoDemo): boolean {
  const ultima = cenarioAtual(estado)?.etapas[estado.visiveis - 1];
  return Boolean(ultima?.pergunta) && estado.respostaEnviada === null;
}

export function concluido(estado: EstadoDemo): boolean {
  const cenario = cenarioAtual(estado);
  return cenario !== null && estado.visiveis === cenario.etapas.length;
}

export function podeAvancar(estado: EstadoDemo): boolean {
  return estado.executando && !concluido(estado) && !aguardandoResposta(estado);
}

export function reducer(estado: EstadoDemo, acao: Acao): EstadoDemo {
  switch (acao.tipo) {
    case "selecionar":
      return { ...ESTADO_INICIAL, cenario: acao.cenario };
    case "executar":
      if (!estado.cenario || estado.executando) return estado;
      return { ...estado, executando: true, visiveis: 1 };
    case "avancar":
      return podeAvancar(estado) ? { ...estado, visiveis: estado.visiveis + 1 } : estado;
    case "digitar":
      return { ...estado, resposta: acao.texto, erroResposta: null };
    case "continuar":
      if (!aguardandoResposta(estado)) return estado;
      if (!estado.resposta.trim()) {
        // Mesmo comportamento do main.py: resposta vazia não retoma a execução.
        return { ...estado, erroResposta: "Digite uma resposta para continuar." };
      }
      return { ...estado, respostaEnviada: estado.resposta.trim(), erroResposta: null };
    case "reiniciar":
      return ESTADO_INICIAL;
  }
}
