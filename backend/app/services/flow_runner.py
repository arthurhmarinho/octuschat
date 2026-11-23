"""Execução do grafo da automação: máquina de passos PURA (sem I/O).

O grafo é a fonte única do conteúdo (ver schemas/automation.py). Tipos de nó:

- ``message``   → envia o texto (com botões de link OU respostas rápidas).
                  Sem respostas rápidas, segue pela saída padrão. Com elas,
                  ESPERA: o toque segue ``qr:<id>``, texto livre segue
                  ``other`` e o prazo vencido segue ``timeout``.
- ``question``  → envia o texto e ESPERA a resposta; guarda o texto em
                  ``context.vars[save_as]`` e segue ``answered`` (ou ``timeout``).
- ``condition`` → ``yes`` / ``no`` (texto contém, contato novo, variável…).
- ``image``     → envia a imagem e segue.
- ``delay``     → ESPERA `hours` e segue.

`advance(graph, node_id, context, event)` anda pelo grafo até encontrar um nó
que espera (ou o fim) e devolve o que enviar (`actions`) e o próximo estado.
O envio e a persistência do estado ficam no automation_engine.

`plan_steps` é o atalho síncrono: anda até a primeira espera.
"""

import copy
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("inboxpilot.flow")

# Trava de segurança contra ciclos/flows muito longos (por chamada).
MAX_STEPS = 50
# Prazo padrão de espera por resposta (a janela de 24h da Meta fecha em 24).
DEFAULT_WAIT_HOURS = 23.0

# Limites da Meta em bytes UTF-8 (iguais aos de schemas/automation.py).
MAX_TEXT_BYTES = 1000
MAX_TEXT_BYTES_WITH_BUTTONS = 640

_VAR_RE = re.compile(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}")


# ── Utilidades ──────────────────────────────────────────────


def normalize_graph(graph) -> dict:
    """Garante as chaves do grafo (tolerante a dados incompletos)."""
    graph = graph if isinstance(graph, dict) else {}
    nodes = [n for n in (graph.get("nodes") or []) if isinstance(n, dict)]
    edges = [e for e in (graph.get("edges") or []) if isinstance(e, dict)]
    start = graph.get("start") or (nodes[0].get("id") if nodes else None)
    return {"nodes": nodes, "edges": edges, "start": start}


def render_text(text: str, context: dict) -> str:
    """Troca ``{{username}}`` e ``{{variavel}}``. Variável inexistente vira vazio."""
    vars_ = context.get("vars") or {}

    def sub(match: re.Match) -> str:
        name = match.group(1)
        if name == "username":
            return str(context.get("username") or "")
        return str(vars_.get(name, ""))

    return _VAR_RE.sub(sub, text or "")


def _clip_bytes(text: str, limit: int) -> str:
    """Corta no limite de bytes UTF-8 sem partir um caractere ao meio."""
    raw = text.encode("utf-8")
    if len(raw) <= limit:
        return text
    return raw[:limit].decode("utf-8", errors="ignore")


def evaluate_condition(node: dict, context: dict) -> bool:
    """Avalia um nó de condição contra o contexto.

    Contexto: ``{"text", "is_new_contact", "username", "vars"}``. ``text`` é o
    texto que disparou o flow, ou a última resposta do contato.
    """
    mode = node.get("mode") or "text_contains"
    vars_ = context.get("vars") or {}
    if mode == "text_contains":
        value = (node.get("value") or "").strip().lower()
        if not value:
            return False
        return value in (context.get("text") or "").lower()
    if mode == "is_new_contact":
        return bool(context.get("is_new_contact"))
    if mode == "var_contains":
        value = (node.get("value") or "").strip().lower()
        if not value:
            return False
        return value in str(vars_.get(node.get("var") or "", "")).lower()
    if mode == "var_exists":
        return bool(str(vars_.get(node.get("var") or "", "")).strip())
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


def quick_reply_payload(node_id: str, reply_id: str) -> str:
    """Payload da resposta rápida: não depende da execução, só do nó e da opção."""
    return f"qr:{node_id}:{reply_id}"


# ── Resultado ───────────────────────────────────────────────


@dataclass
class Outcome:
    """O que `advance` decidiu.

    ``actions``: envios, em ordem, já com as variáveis aplicadas.
      - ``{"type": "send_text", "node_id", "text", "buttons"}``
      - ``{"type": "send_image", "node_id", "url"}``
      - ``{"type": "send_quick_replies", "node_id", "text", "replies": [{"id", "title", "payload"}]}``
    ``next_state``:
      - ``{"status": "completed"}``
      - ``{"status": "waiting", "waiting_for": "reply", "node_id": <nó que espera>,
           "resume_in_hours": h}``
      - ``{"status": "waiting", "waiting_for": "timer", "node_id": <PRÓXIMO nó>,
           "resume_in_hours": h}``
    ``context``: cópia atualizada (variáveis salvas, último texto).
    """

    actions: list[dict] = field(default_factory=list)
    next_state: dict = field(default_factory=lambda: {"status": "completed"})
    context: dict = field(default_factory=dict)


def _waiting_reply(node_id: str, hours) -> dict:
    return {
        "status": "waiting",
        "waiting_for": "reply",
        "node_id": node_id,
        "resume_in_hours": float(hours) if hours else DEFAULT_WAIT_HOURS,
    }


# ── Máquina de passos ───────────────────────────────────────


def _resolve_event(node: dict | None, event: dict, context: dict) -> str | None:
    """Saída (`branch`) que o evento escolhe no nó que esperava.

    Atualiza `context` (último texto; variável da Pergunta). Devolve None se o
    nó não é de espera (estado incoerente).
    """
    node_type = (node or {}).get("type") or "message"
    kind = event.get("type")

    if node_type == "question":
        if kind == "timeout":
            return "timeout"
        text = (event.get("text") or "").strip()
        context["text"] = text
        save_as = node.get("save_as") or ""
        if save_as:
            context.setdefault("vars", {})[save_as] = text
        return "answered"

    if node_type == "message" and node.get("quick_replies"):
        if kind == "timeout":
            return "timeout"
        context["text"] = event.get("text") or ""
        payload = event.get("quick_reply_payload") or ""
        parts = payload.split(":", 2)
        if len(parts) == 3 and parts[0] == "qr" and parts[1] == node.get("id"):
            if any(q.get("id") == parts[2] for q in node["quick_replies"]):
                return f"qr:{parts[2]}"
        return "other"  # texto livre, ou toque numa opção de outra mensagem

    return None


def advance(graph, node_id: str | None, context: dict | None, event: dict | None = None) -> Outcome:
    """Anda pelo grafo até uma espera ou o fim.

    - ``event=None``: PROCESSA ``node_id`` (emite as ações dele) e segue. É como
      se começa (``node_id`` = ``start``) e como se retoma depois de um atraso
      (``node_id`` = o nó seguinte, guardado no estado).
    - ``event={"type": "reply", "text", "quick_reply_payload"}`` ou
      ``{"type": "timeout"}``: ``node_id`` é o nó que esperava; o evento escolhe
      a saída e o fluxo segue a partir do destino dela.

    Função pura: não envia nada nem altera `graph` ou `context` de entrada.
    """
    ctx = copy.deepcopy(context) if context else {}
    ctx.setdefault("vars", {})
    graph = normalize_graph(graph)
    by_id = {n.get("id"): n for n in graph["nodes"] if n.get("id")}
    outcome = Outcome(context=ctx)

    if event is not None:
        branch = _resolve_event(by_id.get(node_id), event, ctx)
        if branch is None:
            logger.warning("Evento %s num nó que não espera (%s); encerrando.", event.get("type"), node_id)
            return outcome
        current = _next_id(graph, node_id, branch)
    else:
        current = node_id

    visited = 0
    while current and visited < MAX_STEPS:
        visited += 1
        node = by_id.get(current)
        if node is None:
            logger.warning("Flow aponta para nó inexistente: %s", current)
            break

        node_type = node.get("type") or "message"
        if node_type == "message":
            buttons = node.get("buttons") or None
            limit = MAX_TEXT_BYTES_WITH_BUTTONS if buttons else MAX_TEXT_BYTES
            text = _clip_bytes(render_text(node.get("text") or "", ctx).strip(), limit)
            replies = node.get("quick_replies") or None
            if replies:
                outcome.actions.append({
                    "type": "send_quick_replies",
                    "node_id": current,
                    "text": text,
                    "replies": [
                        {"id": q["id"], "title": q["title"],
                         "payload": quick_reply_payload(current, q["id"])}
                        for q in replies
                    ],
                })
                outcome.next_state = _waiting_reply(current, node.get("timeout_hours"))
                return outcome
            if text or buttons:
                outcome.actions.append(
                    {"type": "send_text", "node_id": current, "text": text, "buttons": buttons}
                )
            current = _next_id(graph, current)
        elif node_type == "question":
            outcome.actions.append({
                "type": "send_text",
                "node_id": current,
                "text": _clip_bytes(render_text(node.get("text") or "", ctx).strip(), MAX_TEXT_BYTES),
                "buttons": None,
            })
            outcome.next_state = _waiting_reply(current, node.get("timeout_hours"))
            return outcome
        elif node_type == "image":
            url = (node.get("url") or "").strip()
            if url:
                outcome.actions.append({"type": "send_image", "node_id": current, "url": url})
            current = _next_id(graph, current)
        elif node_type == "delay":
            after = _next_id(graph, current)
            if after is None:  # nada depois do atraso: esperar não serve a ninguém
                break
            outcome.next_state = {
                "status": "waiting",
                "waiting_for": "timer",
                "node_id": after,
                "resume_in_hours": float(node.get("hours") or 0),
            }
            return outcome
        elif node_type == "condition":
            branch = "yes" if evaluate_condition(node, ctx) else "no"
            current = _next_id(graph, current, branch)
        else:
            logger.warning("Tipo de nó desconhecido: %s (pulando)", node_type)
            current = _next_id(graph, current)

    if visited >= MAX_STEPS and current:
        logger.warning("Flow atingiu o limite de %s passos (ciclo?).", MAX_STEPS)
    return outcome


def plan_steps(graph, context: dict | None = None) -> list[dict]:
    """Atalho síncrono: o que enviar do início até a primeira espera.

    Cada passo: ``{"node_id", "text", "buttons"}``; respostas rápidas somam
    ``"quick_replies"`` e imagens ``"image_url"``. Função pura.
    """
    start = normalize_graph(graph)["start"]
    steps: list[dict] = []
    for action in advance(graph, start, context).actions:
        step = {
            "node_id": action["node_id"],
            "text": action.get("text", ""),
            "buttons": action.get("buttons"),
        }
        if action["type"] == "send_quick_replies":
            step["quick_replies"] = action["replies"]
        elif action["type"] == "send_image":
            step["image_url"] = action["url"]
        steps.append(step)
    return steps
