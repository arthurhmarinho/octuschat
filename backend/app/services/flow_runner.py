"""Execução do grafo da automação (Fase 3).

O grafo é a fonte única do conteúdo (ver schemas/automation.py):

    {"version": 2, "start": "m1",
     "nodes": [{"id","type","text","buttons","mode","value"}],
     "edges": [{"source","target","branch"}]}

`start` é a mensagem 1. Tipos de nó:
- ``message``   → envia uma mensagem; segue pela aresta sem `branch`.
- ``condition`` → avalia contra o contexto do gatilho e segue pela aresta
                  `branch: "yes"` ou `"no"`.

`plan_steps` é **puro** (sem I/O): recebe o grafo + contexto e devolve a
lista ordenada de mensagens a enviar — o envio fica no automation_engine.
"""

import logging

logger = logging.getLogger("inboxpilot.flow")

# Trava de segurança contra ciclos/flows muito longos.
MAX_STEPS = 20


def normalize_graph(graph) -> dict:
    """Garante as chaves do grafo (tolerante a dados incompletos)."""
    graph = graph if isinstance(graph, dict) else {}
    nodes = [n for n in (graph.get("nodes") or []) if isinstance(n, dict)]
    edges = [e for e in (graph.get("edges") or []) if isinstance(e, dict)]
    start = graph.get("start") or (nodes[0].get("id") if nodes else None)
    return {"nodes": nodes, "edges": edges, "start": start}


def evaluate_condition(node: dict, context: dict) -> bool:
    """Avalia um nó de condição contra o contexto do gatilho.

    Contexto: ``{"text": <texto que disparou>, "is_new_contact": bool}``.
    """
    mode = node.get("mode") or "text_contains"
    if mode == "text_contains":
        value = (node.get("value") or "").strip().lower()
        if not value:
            return False
        return value in (context.get("text") or "").lower()
    if mode == "is_new_contact":
        return bool(context.get("is_new_contact"))
    logger.warning("Condição com modo desconhecido: %s (tratando como falsa)", mode)
    return False


def _next_id(graph: dict, node_id: str, branch: str | None = None) -> str | None:
    """Id do próximo nó. Com `branch`, só considera arestas daquele ramo;
    sem `branch`, só as arestas sem ramo."""
    for edge in graph["edges"]:
        if edge.get("source") != node_id:
            continue
        if branch is None:
            if not edge.get("branch"):
                return edge.get("target")
        elif edge.get("branch") == branch:
            return edge.get("target")
    return None


def plan_steps(graph, context: dict | None = None) -> list[dict]:
    """Percorre o grafo e devolve as mensagens a enviar, em ordem.

    Função pura: não envia nada, só decide o que enviar.
    """
    context = context or {}
    graph = normalize_graph(graph)
    by_id = {n.get("id"): n for n in graph["nodes"] if n.get("id")}

    steps: list[dict] = []
    current = graph["start"]
    visited = 0
    while current and visited < MAX_STEPS:
        visited += 1
        node = by_id.get(current)
        if node is None:
            logger.warning("Flow aponta para nó inexistente: %s", current)
            break

        node_type = node.get("type") or "message"
        if node_type == "message":
            text = (node.get("text") or "").strip()
            buttons = node.get("buttons") or None
            if text or buttons:
                steps.append({"node_id": current, "text": text, "buttons": buttons})
            current = _next_id(graph, current)
        elif node_type == "condition":
            branch = "yes" if evaluate_condition(node, context) else "no"
            current = _next_id(graph, current, branch)
        else:
            logger.warning("Tipo de nó desconhecido: %s (pulando)", node_type)
            current = _next_id(graph, current)

    if visited >= MAX_STEPS:
        logger.warning("Flow atingiu o limite de %s passos (ciclo?).", MAX_STEPS)
    return steps
