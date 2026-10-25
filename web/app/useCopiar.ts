"use client";

import { useEffect, useRef, useState } from "react";

export type EstadoCopia = "" | "copiado" | "falhou";

/** Copia texto para a área de transferência e mostra o resultado por 2 segundos. */
export function useCopiar() {
  const [estado, setEstado] = useState<EstadoCopia>("");
  const temporizador = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => () => clearTimeout(temporizador.current), []);

  async function copiar(texto: string) {
    try {
      await navigator.clipboard.writeText(texto);
      setEstado("copiado");
    } catch {
      setEstado("falhou");
    }
    clearTimeout(temporizador.current);
    temporizador.current = setTimeout(() => setEstado(""), 2000);
  }

  function limpar() {
    clearTimeout(temporizador.current);
    setEstado("");
  }

  return { estado, copiar, limpar };
}

export function rotuloCopia(estado: EstadoCopia, padrao: string): string {
  if (estado === "copiado") return "Copiado!";
  if (estado === "falhou") return "Não foi possível copiar";
  return padrao;
}
