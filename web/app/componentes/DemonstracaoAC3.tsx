"use client";

import { useEffect, useReducer } from "react";

import { CENARIOS, PERFIL, RESPOSTA_EXEMPLO, type Etapa } from "../cenarios";
import {
  ESTADO_INICIAL,
  aguardandoResposta,
  cenarioAtual,
  concluido,
  podeAvancar,
  reducer,
} from "../demo";
import { rotuloCopia, useCopiar } from "../useCopiar";
import EvidenciasTestes from "./EvidenciasTestes";

const INTERVALO_ETAPAS_MS = 650;
const ICONE = { ok: "✓", alerta: "!", erro: "✕" } as const;

export default function DemonstracaoAC3() {
  const [estado, despachar] = useReducer(reducer, ESTADO_INICIAL);
  const copia = useCopiar();
  const cenario = cenarioAtual(estado);
  const finalizado = concluido(estado);

  // Exibe as etapas uma a uma, para mostrar a sequência do fluxo.
  useEffect(() => {
    if (!podeAvancar(estado)) return;
    const temporizador = setTimeout(() => despachar({ tipo: "avancar" }), INTERVALO_ETAPAS_MS);
    return () => clearTimeout(temporizador);
  }, [estado]);

  function reiniciar() {
    despachar({ tipo: "reiniciar" });
    copia.limpar();
  }

  return (
    <>
      <p className="aviso" role="note">
        Modo demonstração — respostas simuladas, sem conexão com um modelo de IA.
        <span> Esta aba reproduz os cenários testados na AC3 e não executa o agente LangGraph.</span>
      </p>

      <div className="grade">
        <section className="card" aria-labelledby="titulo-perfil">
          <h2 id="titulo-perfil">Perfil profissional</h2>
          <dl className="perfil">
            <dt>Nome</dt>
            <dd>{PERFIL.nome}</dd>
            <dt>Profissão</dt>
            <dd>{PERFIL.profissao}</dd>
            <dt>Área</dt>
            <dd>{PERFIL.area}</dd>
          </dl>
          <h3>Fatos autorizados</h3>
          <ul className="fatos">
            {PERFIL.fatos.map((fato) => (
              <li key={fato.id}>
                <span className="etiqueta">{fato.id}</span>
                {fato.descricao}
              </li>
            ))}
          </ul>
          <p className="nota">
            O agente usa somente estes fatos e exemplos de escrita do perfil como referência. Perfil fictício.
          </p>
        </section>

        <div className="coluna">
          <section className="card" aria-labelledby="titulo-cenarios">
            <h2 id="titulo-cenarios">Escolha um cenário</h2>
            <div className="cenarios" role="radiogroup" aria-label="Cenários de demonstração">
              {CENARIOS.map((opcao, i) => (
                <button
                  key={opcao.id}
                  type="button"
                  role="radio"
                  aria-checked={estado.cenario === opcao.id}
                  className={`cenario ${estado.cenario === opcao.id ? "selecionado" : ""}`}
                  onClick={() => despachar({ tipo: "selecionar", cenario: opcao.id })}
                >
                  <strong>
                    {i + 1}. {opcao.nome}
                  </strong>
                  <span>{opcao.descricao}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="card" aria-labelledby="titulo-demo">
            <div className="titulo-com-acao">
              <h2 id="titulo-demo">Demonstração do agente</h2>
              <button type="button" className="botao secundario" onClick={reiniciar} disabled={!estado.cenario}>
                Reiniciar
              </button>
            </div>

            {!cenario ? (
              <p className="vazio">Selecione um cenário para começar.</p>
            ) : (
              <>
                <label className="rotulo" htmlFor="solicitacao">
                  Solicitação
                </label>
                <textarea id="solicitacao" className="campo" value={cenario.solicitacao} readOnly rows={2} />
                {!estado.executando && (
                  <button type="button" className="botao" onClick={() => despachar({ tipo: "executar" })}>
                    Executar demonstração
                  </button>
                )}

                <ol className="etapas" aria-live="polite">
                  {cenario.etapas.slice(0, estado.visiveis).map((etapa, i) => (
                    <li key={i} className={`etapa ${etapa.tipo}`}>
                      <span className="icone" aria-hidden>
                        {ICONE[etapa.tipo]}
                      </span>
                      <div>
                        <p className="etapa-titulo">
                          {etapa.titulo} <code>{etapa.no}</code>
                        </p>
                        <p className="etapa-detalhe">{etapa.detalhe}</p>
                        <DetalhesEtapa etapa={etapa} />
                        {etapa.pergunta && (
                          <Esclarecimento
                            pergunta={etapa.pergunta}
                            aguardando={aguardandoResposta(estado)}
                            resposta={estado.resposta}
                            respostaEnviada={estado.respostaEnviada}
                            erro={estado.erroResposta}
                            aviso={cenario.aviso}
                            onDigitar={(texto) => despachar({ tipo: "digitar", texto })}
                            onContinuar={() => despachar({ tipo: "continuar" })}
                          />
                        )}
                      </div>
                    </li>
                  ))}
                </ol>

                {finalizado && (
                  <div className="resultado">
                    <div className="titulo-com-acao">
                      <h3>Rascunho final</h3>
                      <button type="button" className="botao" onClick={() => copia.copiar(cenario.rascunhoFinal)}>
                        {rotuloCopia(copia.estado, "Copiar rascunho")}
                      </button>
                    </div>
                    <p className="rascunho">{cenario.rascunhoFinal}</p>
                    <p className="rotulo-mock">Texto de demonstração predefinido.</p>
                    <div className="status">
                      <span className="selo">Aguardando aprovação</span>
                      <span>Verificação: aprovado</span>
                      <span>Revisões automáticas: {cenario.revisoes}</span>
                    </div>
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      </div>

      <EvidenciasTestes />
    </>
  );
}

function DetalhesEtapa({ etapa }: { etapa: Etapa }) {
  return (
    <>
      {etapa.rascunho && (
        <blockquote className="rascunho reprovado">
          {etapa.rascunho}
          <span className="rotulo-mock">Texto de demonstração predefinido.</span>
        </blockquote>
      )}
      {etapa.problemas && (
        <div className="problemas">
          <p>Problemas factuais</p>
          <ul>
            {etapa.problemas.factuais.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
          <p>Problemas de estilo</p>
          <ul>
            {etapa.problemas.estilo.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

type PropsEsclarecimento = {
  pergunta: string;
  aguardando: boolean;
  resposta: string;
  respostaEnviada: string | null;
  erro: string | null;
  aviso?: string;
  onDigitar: (texto: string) => void;
  onContinuar: () => void;
};

function Esclarecimento(props: PropsEsclarecimento) {
  return (
    <div className="esclarecimento">
      <p className="pergunta">{props.pergunta}</p>
      {props.aguardando ? (
        <>
          <label className="rotulo" htmlFor="resposta">
            Sua resposta
          </label>
          <textarea
            id="resposta"
            className="campo"
            rows={2}
            value={props.resposta}
            placeholder={`Ex.: ${RESPOSTA_EXEMPLO}`}
            onChange={(e) => props.onDigitar(e.target.value)}
          />
          {props.erro && (
            <p className="erro" role="alert">
              {props.erro}
            </p>
          )}
          <button type="button" className="botao" onClick={props.onContinuar}>
            Continuar
          </button>
        </>
      ) : (
        <>
          <p className="recebida">
            Resposta recebida: <q>{props.respostaEnviada}</q>
          </p>
          {props.aviso && <p className="nota">{props.aviso}</p>}
        </>
      )}
    </div>
  );
}
