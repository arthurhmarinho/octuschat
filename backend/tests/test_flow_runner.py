"""Testes do flow_runner.plan_steps (função pura: grafo + contexto → mensagens)."""

import logging

import pytest

from app.services import flow_runner
from app.services.flow_runner import MAX_STEPS, normalize_graph, plan_steps

BTN = [{"label": "Abrir", "url": "https://exemplo.com"}]


def texts(steps: list[dict]) -> list[str]:
    return [s["text"] for s in steps]


def msg(node_id: str, text: str, buttons=None) -> dict:
    return {"id": node_id, "type": "message", "text": text, "buttons": buttons}


def cond(node_id: str, mode: str = "text_contains", value: str | None = None) -> dict:
    return {"id": node_id, "type": "condition", "mode": mode, "value": value}


def edge(source: str, target: str, branch: str | None = None) -> dict:
    e = {"source": source, "target": target}
    if branch:
        e["branch"] = branch
    return e


def chain(*steps) -> dict:
    """Grafo linear: cada item é um texto ou um nó de mensagem pronto."""
    nodes = [
        s if isinstance(s, dict) else msg(f"s{i}", s) for i, s in enumerate(steps)
    ]
    edges = [edge(nodes[i - 1]["id"], nodes[i]["id"]) for i in range(1, len(nodes))]
    return {"version": 2, "start": nodes[0]["id"] if nodes else None,
            "nodes": nodes, "edges": edges}


# ── Grafo vazio / incompleto ────────────────────────────────


@pytest.mark.parametrize("graph", [None, [], {}, {"nodes": [], "edges": []}])
def test_grafo_vazio_nao_envia_nada(graph):
    assert plan_steps(graph) == []


def test_normalize_graph_tolera_lixo():
    g = normalize_graph({"nodes": [None, msg("a", "x"), "lixo"], "edges": [1, edge("a", "b")]})
    assert g == {"nodes": [msg("a", "x")], "edges": [edge("a", "b")], "start": "a"}


# ── Cadeia linear ───────────────────────────────────────────


def test_cadeia_em_ordem_com_botoes_e_node_id():
    graph = chain("um", msg("d", "dois", BTN), "três")
    steps = plan_steps(graph)
    assert texts(steps) == ["um", "dois", "três"]
    assert [s["node_id"] for s in steps] == ["s0", "d", "s2"]
    assert steps[0]["buttons"] is None
    assert steps[1]["buttons"] == BTN


def test_cadeia_pula_mensagens_vazias_mas_segue():
    graph = chain("um", "   ", msg("b", "", BTN), "fim")
    steps = plan_steps(graph)
    # vazio é pulado; só-botões é enviado (texto vazio + botões)
    assert texts(steps) == ["um", "", "fim"]
    assert steps[1]["buttons"] == BTN


def test_texto_e_aparado():
    assert texts(plan_steps(chain("  oi  "))) == ["oi"]


# ── Grafo ───────────────────────────────────────────────────


def test_grafo_segue_arestas_e_nao_a_ordem_dos_nos():
    flow = {
        "nodes": [msg("c", "terceiro"), msg("a", "primeiro"), msg("b", "segundo")],
        "edges": [edge("a", "b"), edge("b", "c")],
        "start": "a",
    }
    assert texts(plan_steps(flow)) == ["primeiro", "segundo", "terceiro"]


def test_grafo_sem_start_comeca_no_primeiro_no():
    flow = {"nodes": [msg("x", "um"), msg("y", "dois")], "edges": [edge("x", "y")]}
    assert texts(plan_steps(flow)) == ["um", "dois"]


def test_grafo_para_quando_nao_ha_proxima_aresta():
    flow = {"nodes": [msg("a", "um"), msg("b", "solto")], "edges": [], "start": "a"}
    assert texts(plan_steps(flow)) == ["um"]


def test_no_de_mensagem_ignora_arestas_com_branch():
    # De um nó de mensagem só se segue por aresta SEM branch.
    flow = {
        "nodes": [msg("a", "um"), msg("b", "errado"), msg("c", "certo")],
        "edges": [edge("a", "b", "yes"), edge("a", "c")],
        "start": "a",
    }
    assert texts(plan_steps(flow)) == ["um", "certo"]


def test_tipo_desconhecido_e_pulado_e_segue_a_cadeia(caplog):
    # (`delay` virou tipo de verdade na v3; aqui vai um tipo que não existe.)
    flow = {
        "nodes": [msg("a", "um"), {"id": "x", "type": "carrossel"}, msg("b", "dois")],
        "edges": [edge("a", "x"), edge("x", "b")],
        "start": "a",
    }
    with caplog.at_level(logging.WARNING, logger="inboxpilot.flow"):
        assert texts(plan_steps(flow)) == ["um", "dois"]
    assert "desconhecido" in caplog.text


def test_no_sem_type_e_tratado_como_mensagem():
    flow = {"nodes": [{"id": "a", "text": "oi"}], "edges": [], "start": "a"}
    assert texts(plan_steps(flow)) == ["oi"]


# ── Condição sim/não ────────────────────────────────────────


def _flow_condicao(node: dict) -> dict:
    return {
        "nodes": [msg("m0", "antes"), node, msg("sim", "SIM"), msg("nao", "NÃO")],
        "edges": [edge("m0", "c"), edge("c", "sim", "yes"), edge("c", "nao", "no")],
        "start": "m0",
    }


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Quero o PREÇO, por favor", "SIM"),  # case-insensitive
        ("me manda o link", "NÃO"),
        ("", "NÃO"),
    ],
)
def test_condicao_text_contains(texto, esperado):
    flow = _flow_condicao(cond("c", "text_contains", " Preço "))
    assert texts(plan_steps(flow, {"text": texto})) == ["antes", esperado]


def test_condicao_text_contains_com_valor_vazio_e_falsa():
    flow = _flow_condicao(cond("c", "text_contains", "  "))
    assert texts(plan_steps(flow, {"text": "qualquer coisa"})) == ["antes", "NÃO"]


def test_condicao_sem_mode_usa_text_contains():
    node = {"id": "c", "type": "condition", "value": "oi"}
    assert texts(plan_steps(_flow_condicao(node), {"text": "oi!"})) == ["antes", "SIM"]


@pytest.mark.parametrize(("novo", "esperado"), [(True, "SIM"), (False, "NÃO")])
def test_condicao_is_new_contact(novo, esperado):
    flow = _flow_condicao(cond("c", "is_new_contact"))
    assert texts(plan_steps(flow, {"is_new_contact": novo})) == ["antes", esperado]


def test_condicao_sem_contexto_cai_no_nao():
    flow = _flow_condicao(cond("c", "is_new_contact"))
    assert texts(plan_steps(flow)) == ["antes", "NÃO"]


def test_condicao_modo_desconhecido_cai_no_nao():
    flow = _flow_condicao(cond("c", "tem_tag", "vip"))
    assert texts(plan_steps(flow, {"text": "vip"})) == ["antes", "NÃO"]


def test_condicao_sem_aresta_do_ramo_encerra_o_flow():
    flow = {
        "nodes": [cond("c", "is_new_contact"), msg("sim", "SIM")],
        "edges": [edge("c", "sim", "yes")],  # não há ramo "no"
        "start": "c",
    }
    assert plan_steps(flow, {"is_new_contact": False}) == []
    assert texts(plan_steps(flow, {"is_new_contact": True})) == ["SIM"]


def test_condicao_ignora_aresta_sem_branch():
    flow = {
        "nodes": [cond("c", "is_new_contact"), msg("x", "sem ramo")],
        "edges": [edge("c", "x")],
        "start": "c",
    }
    assert plan_steps(flow, {"is_new_contact": True}) == []


def test_condicoes_encadeadas():
    flow = {
        "nodes": [
            cond("c1", "is_new_contact"),
            cond("c2", "text_contains", "preço"),
            msg("a", "novo+preço"),
            msg("b", "novo sem preço"),
            msg("c", "antigo"),
        ],
        "edges": [
            edge("c1", "c2", "yes"),
            edge("c1", "c", "no"),
            edge("c2", "a", "yes"),
            edge("c2", "b", "no"),
        ],
        "start": "c1",
    }
    assert texts(plan_steps(flow, {"is_new_contact": True, "text": "preço?"})) == ["novo+preço"]
    assert texts(plan_steps(flow, {"is_new_contact": True, "text": "oi"})) == ["novo sem preço"]
    assert texts(plan_steps(flow, {"is_new_contact": False, "text": "preço"})) == ["antigo"]


# ── Nó inexistente ──────────────────────────────────────────


def test_aresta_para_no_inexistente_para_com_o_que_ja_planejou(caplog):
    flow = {"nodes": [msg("a", "um")], "edges": [edge("a", "fantasma")], "start": "a"}
    with caplog.at_level(logging.WARNING, logger="inboxpilot.flow"):
        assert texts(plan_steps(flow)) == ["um"]
    assert "inexistente" in caplog.text


def test_start_inexistente_nao_envia_nada():
    flow = {"nodes": [msg("a", "um")], "edges": [], "start": "nao-existe"}
    assert plan_steps(flow) == []


def test_ramo_de_condicao_para_no_inexistente():
    flow = {
        "nodes": [cond("c", "is_new_contact")],
        "edges": [edge("c", "fantasma", "yes")],
        "start": "c",
    }
    assert plan_steps(flow, {"is_new_contact": True}) == []


# ── Ciclos / MAX_STEPS ──────────────────────────────────────


def test_ciclo_e_cortado_em_max_steps(caplog):
    flow = {
        "nodes": [msg("a", "A"), msg("b", "B")],
        "edges": [edge("a", "b"), edge("b", "a")],
        "start": "a",
    }
    with caplog.at_level(logging.WARNING, logger="inboxpilot.flow"):
        steps = plan_steps(flow)
    assert len(steps) == MAX_STEPS
    assert texts(steps)[:4] == ["A", "B", "A", "B"]
    assert "limite" in caplog.text


def test_auto_loop_em_condicao_termina_sem_enviar():
    flow = {"nodes": [cond("c", "is_new_contact")], "edges": [edge("c", "c", "no")], "start": "c"}
    assert plan_steps(flow, {"is_new_contact": False}) == []


def test_cadeia_maior_que_max_steps_e_truncada():
    flow = chain(*[f"m{i}" for i in range(MAX_STEPS + 5)])
    assert texts(plan_steps(flow)) == [f"m{i}" for i in range(MAX_STEPS)]


def test_respeita_max_steps_alterado(monkeypatch):
    monkeypatch.setattr(flow_runner, "MAX_STEPS", 3)
    assert len(plan_steps(chain(*[str(i) for i in range(10)]))) == 3


# ── Pureza ──────────────────────────────────────────────────


def test_nao_modifica_o_flow_de_entrada():
    import copy

    flow = _flow_condicao(cond("c", "text_contains", "x"))
    original = copy.deepcopy(flow)
    plan_steps(flow, {"text": "x"})
    assert flow == original


# ═══════════════════════════ v3: advance ═══════════════════════════

import copy  # noqa: E402

from app.services.flow_runner import advance, quick_reply_payload, render_text  # noqa: E402


def qr_msg(node_id="n1", text="Quer?", ids=("q1", "q2"), **kw):
    return {"id": node_id, "type": "message", "text": text,
            "quick_replies": [{"id": i, "title": f"Op {i}"} for i in ids], **kw}


def question(node_id="p", text="Qual seu e-mail?", save_as="email", **kw):
    return {"id": node_id, "type": "question", "text": text, "save_as": save_as, **kw}


def image(node_id="i", url="https://x.com/a.png"):
    return {"id": node_id, "type": "image", "url": url}


def delay(node_id="d", hours=2):
    return {"id": node_id, "type": "delay", "hours": hours}


def vcond(node_id="c", mode="var_contains", var="email", value="@"):
    return {"id": node_id, "type": "condition", "mode": mode, "var": var, "value": value}


def g3(nodes, edges, start=None):
    return {"version": 3, "start": start or nodes[0]["id"], "nodes": nodes, "edges": edges}


def types(outcome):
    return [a["type"] for a in outcome.actions]


# ── mensagem com respostas rápidas ──


def fluxo_qr():
    return g3(
        [qr_msg(), msg("sim", "Valeu!"), msg("nao", "Tudo bem"), msg("outro", "Não entendi"), msg("t", "Sumiu?")],
        [edge("n1", "sim", "qr:q1"), edge("n1", "nao", "qr:q2"),
         edge("n1", "outro", "other"), edge("n1", "t", "timeout")],
    )


def test_mensagem_com_respostas_rapidas_envia_e_espera():
    out = advance(fluxo_qr(), "n1", {})
    assert types(out) == ["send_quick_replies"]
    action = out.actions[0]
    assert action["text"] == "Quer?"
    assert action["replies"] == [
        {"id": "q1", "title": "Op q1", "payload": "qr:n1:q1"},
        {"id": "q2", "title": "Op q2", "payload": "qr:n1:q2"},
    ]
    assert out.next_state == {"status": "waiting", "waiting_for": "reply", "node_id": "n1",
                              "resume_in_hours": 23.0}


def test_prazo_da_mensagem_com_respostas_vem_do_no():
    flow = g3([qr_msg(timeout_hours=2.5)], [])
    assert advance(flow, "n1", {}).next_state["resume_in_hours"] == 2.5


def test_resposta_rapida_certa_segue_a_saida_da_opcao():
    out = advance(fluxo_qr(), "n1", {}, {"type": "reply", "text": "Op q2",
                                         "quick_reply_payload": quick_reply_payload("n1", "q2")})
    assert [a["text"] for a in out.actions] == ["Tudo bem"]
    assert out.next_state == {"status": "completed"}
    assert out.context["text"] == "Op q2"  # a resposta vira o "último texto"


def test_texto_livre_segue_other():
    out = advance(fluxo_qr(), "n1", {}, {"type": "reply", "text": "talvez"})
    assert [a["text"] for a in out.actions] == ["Não entendi"]


@pytest.mark.parametrize("payload", ["lixo", "", "qr:n1", "qr:n1:q9", "qr:outro_no:q1", "x:n1:q1"])
def test_payload_invalido_ou_de_outro_no_vira_other(payload):
    out = advance(fluxo_qr(), "n1", {}, {"type": "reply", "text": "x", "quick_reply_payload": payload})
    assert [a["text"] for a in out.actions] == ["Não entendi"]


def test_timeout_segue_a_saida_timeout():
    out = advance(fluxo_qr(), "n1", {}, {"type": "timeout"})
    assert [a["text"] for a in out.actions] == ["Sumiu?"]


def test_saida_sem_aresta_e_o_fim_do_caminho():
    flow = g3([qr_msg()], [])
    out = advance(flow, "n1", {}, {"type": "timeout"})
    assert out.actions == [] and out.next_state == {"status": "completed"}


# ── pergunta ──


def test_pergunta_envia_e_espera_e_salva_a_resposta():
    flow = g3([question(), msg("ok", "Anotei {{email}}")], [edge("p", "ok", "answered")])
    out = advance(flow, "p", {})
    assert [a["text"] for a in out.actions] == ["Qual seu e-mail?"]
    assert out.next_state["waiting_for"] == "reply" and out.next_state["node_id"] == "p"

    out = advance(flow, "p", out.context, {"type": "reply", "text": "  ana@x.com  "})
    assert out.context["vars"] == {"email": "ana@x.com"}
    assert out.context["text"] == "ana@x.com"
    assert [a["text"] for a in out.actions] == ["Anotei ana@x.com"]


def test_pergunta_timeout():
    flow = g3([question(), msg("t", "Sem resposta")], [edge("p", "t", "timeout")])
    out = advance(flow, "p", {}, {"type": "timeout"})
    assert [a["text"] for a in out.actions] == ["Sem resposta"]
    assert out.context["vars"] == {}  # nada foi salvo


def test_evento_num_no_que_nao_espera_encerra(caplog):
    flow = g3([msg("a", "oi")], [])
    with caplog.at_level(logging.WARNING, logger="inboxpilot.flow"):
        out = advance(flow, "a", {}, {"type": "reply", "text": "x"})
    assert out.actions == [] and out.next_state == {"status": "completed"}
    assert "não espera" in caplog.text


# ── condição com variáveis ──


def flow_var(node):
    return g3([question(), node, msg("sim", "SIM"), msg("nao", "NÃO")],
              [edge("p", "c", "answered"), edge("c", "sim", "yes"), edge("c", "nao", "no")])


@pytest.mark.parametrize(("resposta", "esperado"), [("ana@x.com", "SIM"), ("sem arroba", "NÃO"), ("", "NÃO")])
def test_condicao_var_contains(resposta, esperado):
    out = advance(flow_var(vcond()), "p", {}, {"type": "reply", "text": resposta})
    assert [a["text"] for a in out.actions] == [esperado]


@pytest.mark.parametrize(("resposta", "esperado"), [("qualquer", "SIM"), ("  ", "NÃO")])
def test_condicao_var_exists(resposta, esperado):
    out = advance(flow_var(vcond(mode="var_exists")), "p", {}, {"type": "reply", "text": resposta})
    assert [a["text"] for a in out.actions] == [esperado]


def test_condicao_de_variavel_inexistente_e_falsa():
    flow = g3([vcond(), msg("sim", "SIM"), msg("nao", "NÃO")],
              [edge("c", "sim", "yes"), edge("c", "nao", "no")])
    assert [a["text"] for a in advance(flow, "c", {}).actions] == ["NÃO"]
    assert [a["text"] for a in advance(flow, "c", {"vars": {"email": "a@b"}}).actions] == ["SIM"]


def test_text_contains_enxerga_a_ultima_resposta():
    flow = g3([question(), cond("c", "text_contains", "pix"), msg("sim", "SIM"), msg("nao", "NÃO")],
              [edge("p", "c", "answered"), edge("c", "sim", "yes"), edge("c", "nao", "no")])
    out = advance(flow, "p", {"text": "texto do gatilho"}, {"type": "reply", "text": "pago no PIX"})
    assert [a["text"] for a in out.actions] == ["SIM"]


# ── imagem e espera ──


def test_imagem_envia_e_segue():
    flow = g3([image(), msg("a", "depois")], [edge("i", "a")])
    out = advance(flow, "i", {})
    assert out.actions == [
        {"type": "send_image", "node_id": "i", "url": "https://x.com/a.png"},
        {"type": "send_text", "node_id": "a", "text": "depois", "buttons": None},
    ]


def test_espera_guarda_o_proximo_no_e_o_prazo():
    flow = g3([msg("a", "antes"), delay(hours=1.5), msg("b", "depois")], [edge("a", "d"), edge("d", "b")])
    out = advance(flow, "a", {})
    assert [a["text"] for a in out.actions] == ["antes"]
    assert out.next_state == {"status": "waiting", "waiting_for": "timer", "node_id": "b",
                              "resume_in_hours": 1.5}
    # ao vencer, o worker retoma processando o nó guardado
    out = advance(flow, "b", out.context)
    assert [a["text"] for a in out.actions] == ["depois"] and out.next_state == {"status": "completed"}


def test_espera_sem_nada_depois_conclui_na_hora():
    flow = g3([msg("a", "fim"), delay()], [edge("a", "d")])
    assert advance(flow, "a", {}).next_state == {"status": "completed"}


def test_para_na_primeira_espera_e_nao_envia_o_que_vem_depois():
    flow = g3([msg("a", "1"), delay(), msg("b", "2"), delay("d2"), msg("c", "3")],
              [edge("a", "d"), edge("d", "b"), edge("b", "d2"), edge("d2", "c")])
    assert [a["text"] for a in advance(flow, "a", {}).actions] == ["1"]


# ── variáveis no texto ──


def test_render_text():
    ctx = {"username": "ana", "vars": {"email": "a@x.com", "cidade": "Recife"}}
    assert render_text("Oi {{username}}!", ctx) == "Oi ana!"
    assert render_text("{{ email }} / {{cidade}}", ctx) == "a@x.com / Recife"
    assert render_text("{{nao_existe}}|{{username}}", {}) == "|"      # sem variável: vazio
    assert render_text("{{Maiuscula}} {{1abc}} {{a b}}", ctx) == "{{Maiuscula}} {{1abc}} {{a b}}"
    assert render_text("sem variável", ctx) == "sem variável"


def test_variaveis_aplicadas_na_mensagem_na_pergunta_e_em_respostas_rapidas():
    flow = g3([msg("a", "Oi {{username}}"), question(text="{{username}}, e-mail?")],
              [edge("a", "p")])
    out = advance(flow, "a", {"username": "ana"})
    assert [a["text"] for a in out.actions] == ["Oi ana", "ana, e-mail?"]
    out = advance(g3([qr_msg(text="Oi {{username}}, quer?")], []), "n1", {"username": "ana"})
    assert out.actions[0]["text"] == "Oi ana, quer?"


def test_variavel_que_estoura_o_limite_e_cortada_em_bytes():
    flow = g3([msg("a", "{{nome}}")], [])
    out = advance(flow, "a", {"vars": {"nome": "😀" * 400}})
    text = out.actions[0]["text"]
    assert len(text.encode()) <= 1000 and text == "😀" * 250
    out = advance(g3([msg("a", "{{nome}}", BTN)], []), "a", {"vars": {"nome": "x" * 900}})
    assert len(out.actions[0]["text"]) == 640


# ── compatibilidade v2 e pureza ──


def test_grafo_v2_da_o_mesmo_resultado_por_advance_e_por_plan_steps():
    flow = _flow_condicao(cond("c", "text_contains", "preço"))
    ctx = {"text": "qual o preço?"}
    via_advance = [a["text"] for a in advance(flow, "m0", ctx).actions]
    assert via_advance == texts(plan_steps(flow, ctx)) == ["antes", "SIM"]


def test_plan_steps_expoe_respostas_e_imagem():
    flow = g3([image(), qr_msg("q")], [edge("i", "q")])
    steps = plan_steps(flow)
    assert steps[0]["image_url"] == "https://x.com/a.png"
    assert [r["id"] for r in steps[1]["quick_replies"]] == ["q1", "q2"]


def test_advance_nao_modifica_grafo_nem_contexto():
    flow = flow_var(vcond())
    ctx = {"text": "x", "vars": {"a": "1"}}
    f0, c0 = copy.deepcopy(flow), copy.deepcopy(ctx)
    out = advance(flow, "p", ctx, {"type": "reply", "text": "ana@x.com"})
    assert flow == f0 and ctx == c0
    assert out.context["vars"] == {"a": "1", "email": "ana@x.com"}


def test_teto_de_passos_vale_por_chamada(caplog):
    flow = {"nodes": [msg("a", "A"), msg("b", "B")], "edges": [edge("a", "b"), edge("b", "a")], "start": "a"}
    with caplog.at_level(logging.WARNING, logger="inboxpilot.flow"):
        out = advance(flow, "a", {})
    assert len(out.actions) == MAX_STEPS == 50
    assert "limite" in caplog.text


def test_last_node_id_e_o_ultimo_no_processado():
    flow = g3([msg("a", "1"), delay(), msg("b", "2")], [edge("a", "d"), edge("d", "b")])
    assert advance(flow, "a", {}).last_node_id == "d"
    assert advance(flow, "b", {}).last_node_id == "b"
    out = advance(fluxo_qr(), "n1", {}, {"type": "reply", "text": "x", "quick_reply_payload": "qr:n1:q1"})
    assert out.last_node_id == "sim"
