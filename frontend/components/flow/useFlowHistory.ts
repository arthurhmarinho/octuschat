"use client";

import { useCallback, useRef, useState } from "react";
import { pruneEdges, type FlowGraph } from "@/lib/flowGraph";

const MAX_HISTORY = 50;
const COALESCE_MS = 800;

type State = { past: FlowGraph[]; present: FlowGraph; future: FlowGraph[] };

/**
 * Grafo com desfazer/refazer (snapshots, máximo 50).
 *
 * - `update(fn)`: uma edição = um passo. Com `key`, edições seguidas da mesma
 *   chave em menos de 0,8 s viram um passo só (digitar um texto não gera um
 *   passo por letra).
 * - `transient(fn)`: muda sem registrar (arrastar um nó enquanto se move).
 * - `beginGesture()` / `endGesture()`: registra UM passo para o gesto inteiro
 *   (arrastar = um passo só, no `onNodeDragStop`).
 */
export function useFlowHistory(initial: FlowGraph) {
  const [state, setState] = useState<State>({ past: [], present: initial, future: [] });
  const last = useRef<{ key: string; at: number } | null>(null);
  const gesture = useRef<FlowGraph | null>(null);

  const update = useCallback((fn: (g: FlowGraph) => FlowGraph, key?: string) => {
    setState((s) => {
      const next = pruneEdges(fn(s.present));
      if (next === s.present) return s;
      const now = Date.now();
      const coalesce = key && last.current?.key === key && now - last.current.at < COALESCE_MS;
      last.current = key ? { key, at: now } : null;
      if (coalesce) return { ...s, present: next, future: [] };
      return { past: [...s.past, s.present].slice(-MAX_HISTORY), present: next, future: [] };
    });
  }, []);

  const transient = useCallback((fn: (g: FlowGraph) => FlowGraph) => {
    setState((s) => {
      const next = fn(s.present);
      return next === s.present ? s : { ...s, present: next };
    });
  }, []);

  const beginGesture = useCallback(() => {
    setState((s) => {
      gesture.current = s.present;
      return s;
    });
  }, []);

  const endGesture = useCallback(() => {
    setState((s) => {
      const base = gesture.current;
      gesture.current = null;
      last.current = null;
      if (!base || base === s.present) return s;
      return { past: [...s.past, base].slice(-MAX_HISTORY), present: s.present, future: [] };
    });
  }, []);

  const undo = useCallback(() => {
    last.current = null;
    setState((s) => {
      if (!s.past.length) return s;
      const prev = s.past[s.past.length - 1];
      return { past: s.past.slice(0, -1), present: prev, future: [s.present, ...s.future] };
    });
  }, []);

  const redo = useCallback(() => {
    last.current = null;
    setState((s) => {
      if (!s.future.length) return s;
      const [next, ...rest] = s.future;
      return { past: [...s.past, s.present], present: next, future: rest };
    });
  }, []);

  return {
    graph: state.present,
    update,
    transient,
    beginGesture,
    endGesture,
    undo,
    redo,
    canUndo: state.past.length > 0,
    canRedo: state.future.length > 0,
  };
}
