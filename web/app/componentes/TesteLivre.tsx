"use client";

import { useState, type ReactNode } from "react";

import {
  DADOS_VAZIOS,
  LIMITE_CARACTERES_LINKEDIN,
  gerarPost,
  type DadosPost,
  type Tom,
} from "../gerador";
import { rotuloCopia, useCopiar } from "../useCopiar";

const TONS: { valor: Tom; rotulo: string }[] = [
  { valor: "natural", rotulo: "Natural" },
  { valor: "profissional", rotulo: "Profissional" },
  { valor: "inspirador", rotulo: "Inspirador" },
];

// Os dados ficam apenas no estado da página: nada é enviado, gravado ou armazenado no navegador.
export default function TesteLivre() {
  const [dados, setDados] = useState<DadosPost>(DADOS_VAZIOS);
  const [faltando, setFaltando] = useState<string[]>([]);
  const [texto, setTexto] = useState<string | null>(null);
  const copia = useCopiar();

  function alterar<K extends keyof DadosPost>(campo: K, valor: DadosPost[K]) {
    setDados((atual) => ({ ...atual, [campo]: valor }));
  }

  function gerar() {
    const resultado = gerarPost(dados);
    if (resultado.ok) {
      setFaltando([]);
      setTexto(resultado.texto);
    } else {
      setFaltando(resultado.faltando);
      setTexto(null);
    }
    copia.limpar();
  }

  function limpar() {
    setDados(DADOS_VAZIOS);
    setFaltando([]);
    setTexto(null);
    copia.limpar();
  }

  const caracteres = texto?.length ?? 0;

  return (
    <>
      <p className="aviso" role="note">
        Modo experimental: o texto é montado com templates, sem modelo de IA conectado. Revise as informações
        antes de publicar.
      </p>

      <div className="grade livre">
        <section className="card" aria-labelledby="titulo-formulario">
          <h2 id="titulo-formulario">Suas informações</h2>
          <form
            className="formulario"
            onSubmit={(e) => {
              e.preventDefault();
              gerar();
            }}
          >
            <Campo id="livre-nome" rotulo="Nome" obrigatorio>
              <input
                id="livre-nome"
                className="campo"
                value={dados.nome}
                maxLength={80}
                autoComplete="off"
                onChange={(e) => alterar("nome", e.target.value)}
              />
            </Campo>
            <Campo id="livre-profissao" rotulo="Profissão ou área de atuação" obrigatorio>
              <input
                id="livre-profissao"
                className="campo"
                value={dados.profissao}
                maxLength={120}
                autoComplete="off"
                onChange={(e) => alterar("profissao", e.target.value)}
              />
            </Campo>
            <Campo id="livre-experiencia" rotulo="Experiência, projeto ou acontecimento que deseja compartilhar" obrigatorio>
              <textarea
                id="livre-experiencia"
                className="campo"
                rows={4}
                value={dados.experiencia}
                maxLength={1500}
                onChange={(e) => alterar("experiencia", e.target.value)}
              />
            </Campo>
            <Campo id="livre-aprendizado" rotulo="Aprendizado ou reflexão pessoal">
              <textarea
                id="livre-aprendizado"
                className="campo"
                rows={3}
                value={dados.aprendizado}
                maxLength={800}
                onChange={(e) => alterar("aprendizado", e.target.value)}
              />
            </Campo>

            <fieldset className="tons">
              <legend className="rotulo">Tom de escrita</legend>
              {TONS.map((tom) => (
                <label key={tom.valor} className={`tom ${dados.tom === tom.valor ? "selecionado" : ""}`}>
                  <input
                    type="radio"
                    name="tom"
                    value={tom.valor}
                    checked={dados.tom === tom.valor}
                    onChange={() => alterar("tom", tom.valor)}
                  />
                  {tom.rotulo}
                </label>
              ))}
            </fieldset>

            <Campo id="livre-exemplos" rotulo="Exemplos de posts anteriores">
              <textarea
                id="livre-exemplos"
                className="campo"
                rows={3}
                value={dados.exemplos}
                maxLength={3000}
                onChange={(e) => alterar("exemplos", e.target.value)}
              />
              <p className="nota">
                Apenas referência para você comparar com o resultado. Os exemplos não entram no texto e o estilo
                deles não é reproduzido.
              </p>
            </Campo>

            {faltando.length > 0 && (
              <div className="erro-caixa" role="alert">
                Preencha os campos obrigatórios:
                <ul>
                  {faltando.map((campo) => (
                    <li key={campo}>{campo}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="acoes">
              <button type="submit" className="botao">
                Gerar meu post
              </button>
              <button type="button" className="botao secundario" onClick={limpar}>
                Limpar formulário
              </button>
            </div>
          </form>
        </section>

        <section className="card" aria-labelledby="titulo-post">
          <h2 id="titulo-post">Seu post</h2>
          {texto === null ? (
            <p className="vazio">Preencha o formulário e clique em “Gerar meu post”.</p>
          ) : (
            <>
              <div className="autor">
                <strong>{dados.nome.trim()}</strong>
                <span>{dados.profissao.trim()}</span>
              </div>
              <label className="rotulo" htmlFor="livre-post">
                Texto (você pode editar antes de copiar)
              </label>
              <textarea
                id="livre-post"
                className="campo post"
                rows={12}
                value={texto}
                onChange={(e) => setTexto(e.target.value)}
              />
              <div className="acoes">
                <button type="button" className="botao" onClick={() => copia.copiar(texto)}>
                  {rotuloCopia(copia.estado, "Copiar post")}
                </button>
              </div>

              <div className="verificacoes-basicas">
                <p>Verificações básicas do formulário (não analisam o conteúdo do texto)</p>
                <ul>
                  <li>Campos obrigatórios preenchidos.</li>
                  <li className={caracteres > LIMITE_CARACTERES_LINKEDIN ? "excedido" : ""}>
                    Tamanho: {caracteres} de {LIMITE_CARACTERES_LINKEDIN} caracteres.
                  </li>
                </ul>
                <p className="nota">
                  O texto usa apenas o que você digitou, com frases de ligação fixas do template. Confira se tudo
                  está correto antes de publicar.
                </p>
              </div>
            </>
          )}
        </section>
      </div>
    </>
  );
}

function Campo(props: { id: string; rotulo: string; obrigatorio?: boolean; children: ReactNode }) {
  return (
    <div className="campo-grupo">
      <label className="rotulo" htmlFor={props.id}>
        {props.rotulo}
        {props.obrigatorio ? <span className="obrigatorio"> (obrigatório)</span> : <span> (opcional)</span>}
      </label>
      {props.children}
    </div>
  );
}
