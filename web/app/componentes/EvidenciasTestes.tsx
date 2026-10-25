import { ARQUIVO_UNITTEST, TESTES, TOTAL_VERIFICACOES } from "../evidencias";

export default function EvidenciasTestes() {
  return (
    <section className="card evidencias" aria-labelledby="titulo-evidencias">
      <div className="titulo-com-acao">
        <h2 id="titulo-evidencias">Evidências dos testes técnicos</h2>
        <span className="selo">Total: {TOTAL_VERIFICACOES} verificações atendidas</span>
      </div>
      <p className="nota destaque">
        Os testes executaram o LangGraph, a ferramenta de consulta e o SQLite reais, utilizando respostas
        predefinidas de um LLM simulado. Eles não comprovam a qualidade da geração ou da verificação por uma IA
        real.
      </p>
      <p className="nota">“Satisfatório” se refere ao comportamento técnico do fluxo demonstrado em cada teste.</p>

      <div className="lista-testes">
        {TESTES.map((teste) => (
          <article key={teste.id} className="teste">
            <div className="titulo-com-acao">
              <h3>
                Teste {teste.id} — {teste.nome}
              </h3>
              <span className="etiqueta">{teste.verificacoes} verificações</span>
            </div>
            <dl className="teste-detalhes">
              <dt>Objetivo</dt>
              <dd>{teste.objetivo}</dd>
              <dt>Resultado observado</dt>
              <dd>{teste.observado}</dd>
              <dt>Classificação</dt>
              <dd>{teste.classificacao}</dd>
            </dl>
            <a className="link" href={teste.arquivo} target="_blank" rel="noopener">
              Abrir log do teste {teste.id}
            </a>
          </article>
        ))}
      </div>

      <p className="nota">
        Saída completa da execução dos testes (unittest):{" "}
        <a className="link" href={ARQUIVO_UNITTEST} target="_blank" rel="noopener">
          abrir log
        </a>
        . Os arquivos são cópias idênticas dos logs da pasta evidencias/ do projeto.
      </p>
    </section>
  );
}
