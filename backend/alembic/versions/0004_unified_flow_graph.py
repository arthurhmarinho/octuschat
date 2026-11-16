"""Grafo único da automação (automations.graph) + contacts.last_inbound_at.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-15

Antes: a mensagem 1 ficava em colunas soltas (reply_message, buttons,
link_url/link_label) e as mensagens 2..N na coluna `flow` (lista legada
[{text, buttons}] ou grafo {nodes, edges, start}). Agora tudo vira UM grafo
em `graph`, com a mensagem 1 como nó inicial.

- As colunas antigas ficam DEPRECADAS (não são mais lidas nem escritas);
  `reply_message` passa a aceitar NULL. Uma migração futura as remove.
- link_url/link_label sem botões: o link é embutido no texto do nó, igual ao
  que era enviado (compose_message).
- `downgrade` reconstrói reply_message/buttons a partir do nó inicial e
  `flow` a partir do resto do grafo (lista se for uma cadeia linear de
  mensagens, grafo caso contrário). O link embutido continua no texto.

`contacts.last_inbound_at`: última mensagem RECEBIDA do contato por DM
(base da janela de 24h). Não muda quando ele só comenta. Preenchido com a
última mensagem "in" já registrada.

As funções de conversão são puras e ficam aqui (congeladas com a migração);
os testes as importam deste arquivo.
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GRAPH_VERSION = 2


# ── Conversão pura ───────────────────────────────────────────────────────────

def _compose(text: str, link_url, link_label) -> str:
    """Igual a automation_engine.compose_message (Fase 0)."""
    if not link_url:
        return text
    if link_label:
        return f"{text}\n\n👉 {link_label}: {link_url}"
    return f"{text}\n\n{link_url}"


def _new_buttons(buttons) -> list | None:
    """[{label, url}] → [{id, type: web_url, label, url}]."""
    out = []
    for i, b in enumerate(buttons or []):
        if not isinstance(b, dict):
            continue
        out.append(
            {
                "id": b.get("id") or f"b{i + 1}",
                "type": b.get("type") or "web_url",
                "label": b.get("label") or "",
                "url": b.get("url") or "",
            }
        )
    return out or None


def _message(node_id: str, text: str, buttons) -> dict:
    node = {"id": node_id, "type": "message", "text": text or ""}
    nb = _new_buttons(buttons)
    if nb:
        node["buttons"] = nb
    return node


def legacy_to_graph(reply_message, buttons, link_url, link_label, flow) -> dict:
    """Colunas antigas → grafo único (versão 2)."""
    buttons = buttons or None
    text = reply_message or ""
    if not buttons:
        text = _compose(text, link_url, link_label)

    if isinstance(flow, dict):
        old_nodes = [n for n in (flow.get("nodes") or []) if isinstance(n, dict)]
        old_edges = [e for e in (flow.get("edges") or []) if isinstance(e, dict)]
        old_start = flow.get("start") or (old_nodes[0].get("id") if old_nodes else None)
    else:
        old_nodes, old_edges, old_start = [], [], None
        for i, step in enumerate(flow or []):
            step = step or {}
            old_nodes.append(
                {"id": f"s{i}", "type": "message",
                 "text": step.get("text") or "", "buttons": step.get("buttons")}
            )
            if i:
                old_edges.append({"source": f"s{i - 1}", "target": f"s{i}"})
        old_start = old_nodes[0]["id"] if old_nodes else None

    taken = {n.get("id") for n in old_nodes}
    first_id = "m1"
    while first_id in taken:
        first_id += "_"

    nodes = [_message(first_id, text, buttons)]
    for n in old_nodes:
        if (n.get("type") or "message") == "message":
            nodes.append(_message(n["id"], n.get("text") or "", n.get("buttons")))
        else:
            nodes.append({k: v for k, v in n.items() if v is not None})

    edges = []
    if old_start:
        edges.append({"source": first_id, "target": old_start})
    for e in old_edges:
        edge = {"source": e.get("source"), "target": e.get("target")}
        if e.get("branch"):
            edge["branch"] = e["branch"]
        edges.append(edge)

    return {"version": GRAPH_VERSION, "start": first_id, "nodes": nodes, "edges": edges}


def _old_buttons(buttons) -> list | None:
    """Botões do grafo → formato antigo (só web_url)."""
    out = [
        {"label": b.get("label") or "", "url": b.get("url") or ""}
        for b in (buttons or [])
        if (b.get("type") or "web_url") == "web_url"
    ]
    return out or None


def graph_to_legacy(graph: dict) -> dict:
    """Grafo único → {reply_message, buttons, flow} (para o downgrade)."""
    nodes = [n for n in (graph or {}).get("nodes") or [] if isinstance(n, dict)]
    edges = [e for e in (graph or {}).get("edges") or [] if isinstance(e, dict)]
    by_id = {n.get("id"): n for n in nodes}
    start = by_id.get((graph or {}).get("start"))
    if start is None:
        return {"reply_message": "", "buttons": None, "flow": None}

    sid = start["id"]
    reply = start.get("text") or ""
    buttons = _old_buttons(start.get("buttons"))
    rest_nodes = [n for n in nodes if n.get("id") != sid]
    rest_edges = [e for e in edges if e.get("source") != sid and e.get("target") != sid]
    nxt = next(
        (e.get("target") for e in edges if e.get("source") == sid and not e.get("branch")),
        None,
    )
    if not rest_nodes or nxt is None:
        return {"reply_message": reply, "buttons": buttons, "flow": None}

    # Cadeia linear só de mensagens, sem ramos → lista legada.
    chain, cur, seen = [], nxt, set()
    linear = True
    while cur and cur not in seen:
        seen.add(cur)
        node = by_id.get(cur)
        if node is None or (node.get("type") or "message") != "message":
            linear = False
            break
        chain.append(node)
        outs = [e for e in rest_edges if e.get("source") == cur]
        if len(outs) > 1 or any(e.get("branch") for e in outs):
            linear = False
            break
        cur = outs[0].get("target") if outs else None
    if linear and len(chain) == len(rest_nodes):
        flow = []
        for n in chain:
            step = {"text": n.get("text") or ""}
            ob = _old_buttons(n.get("buttons"))
            if ob:
                step["buttons"] = ob
            flow.append(step)
        return {"reply_message": reply, "buttons": buttons, "flow": flow}

    old_nodes = []
    for n in rest_nodes:
        node = {k: v for k, v in n.items() if k != "position"}
        if (node.get("type") or "message") == "message":
            node["buttons"] = _old_buttons(node.get("buttons"))
            node.pop("quick_replies", None)
        old_nodes.append(node)
    return {
        "reply_message": reply,
        "buttons": buttons,
        "flow": {"nodes": old_nodes, "edges": rest_edges, "start": nxt},
    }


# ── Migração ─────────────────────────────────────────────────────────────────

def _load(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def upgrade() -> None:
    op.add_column(
        'automations',
        sa.Column('graph', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, reply_message, buttons, link_url, link_label, flow FROM automations"
        )
    ).mappings().all()
    update = sa.text("UPDATE automations SET graph = :graph WHERE id = :id").bindparams(
        sa.bindparam("graph", type_=postgresql.JSONB)
    )
    for r in rows:
        graph = legacy_to_graph(
            r["reply_message"], _load(r["buttons"]), r["link_url"], r["link_label"],
            _load(r["flow"]),
        )
        bind.execute(update, {"id": r["id"], "graph": graph})
    op.alter_column('automations', 'graph', nullable=False)
    op.alter_column('automations', 'reply_message', existing_type=sa.Text(), nullable=True)

    op.add_column(
        'contacts',
        sa.Column('last_inbound_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE contacts c SET last_inbound_at = m.last_in "
        "FROM (SELECT contact_id, max(created_at) AS last_in FROM messages "
        "      WHERE direction = 'in' GROUP BY contact_id) m "
        "WHERE m.contact_id = c.id"
    )


def downgrade() -> None:
    op.drop_column('contacts', 'last_inbound_at')

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, graph FROM automations")).mappings().all()
    # Sem botões, o link já está embutido no texto: zera link_url/label para o
    # engine antigo não embutir de novo. Com botões, o link era ignorado no
    # envio e fica como estava.
    update = sa.text(
        "UPDATE automations SET reply_message = :reply_message, buttons = :buttons, "
        "flow = :flow, "
        "link_url = CASE WHEN :has_buttons THEN link_url END, "
        "link_label = CASE WHEN :has_buttons THEN link_label END "
        "WHERE id = :id"
    ).bindparams(
        sa.bindparam("buttons", type_=postgresql.JSONB(none_as_null=True)),
        sa.bindparam("flow", type_=sa.JSON(none_as_null=True)),
        sa.bindparam("has_buttons", type_=sa.Boolean),
    )
    for r in rows:
        legacy = graph_to_legacy(_load(r["graph"]))
        bind.execute(
            update, {"id": r["id"], "has_buttons": bool(legacy["buttons"]), **legacy}
        )
    op.alter_column('automations', 'reply_message', existing_type=sa.Text(), nullable=False)
    op.drop_column('automations', 'graph')
