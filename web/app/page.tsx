"use client";

import { useState } from "react";

import DemonstracaoAC3 from "./componentes/DemonstracaoAC3";
import TesteLivre from "./componentes/TesteLivre";

type Aba = "demo" | "livre";

const ABAS: { id: Aba; rotulo: string }[] = [
  { id: "demo", rotulo: "Demonstração AC3" },
  { id: "livre", rotulo: "Teste livre" },
];

export default function Pagina() {
  const [aba, setAba] = useState<Aba>("demo");

  return (
    <main className="pagina">
      <header className="cabecalho">
        <h1>LinkedIn Agent</h1>
        <p className="subtitulo">Transforme suas experiências profissionais em posts com a sua identidade.</p>
        <div className="abas" role="tablist" aria-label="Seções">
          {ABAS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              id={`aba-${item.id}`}
              aria-selected={aba === item.id}
              aria-controls={`painel-${item.id}`}
              className={`aba ${aba === item.id ? "ativa" : ""}`}
              onClick={() => setAba(item.id)}
            >
              {item.rotulo}
            </button>
          ))}
        </div>
      </header>

      {/* As duas abas ficam montadas para preservar o estado de cada uma ao alternar. */}
      <div role="tabpanel" id="painel-demo" aria-labelledby="aba-demo" hidden={aba !== "demo"}>
        <DemonstracaoAC3 />
      </div>
      <div role="tabpanel" id="painel-livre" aria-labelledby="aba-livre" hidden={aba !== "livre"}>
        <TesteLivre />
      </div>
    </main>
  );
}
