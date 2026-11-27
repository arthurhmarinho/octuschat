"""Rotas de administração: convites, pessoas e links (precisa de TEST_DATABASE_URL)."""

from datetime import datetime, timezone

import pytest

from app import crud
from app.core.config import settings
from tests.conftest import requires_pg
from tests.test_routes_cadastro import (  # noqa: F401  (world é fixture)
    SECRET,
    expire,
    hdr,
    info,
    register,
    world,
)

pytestmark = requires_pg


async def invite(world, ig="@Fulano.IG", name="Fulano", email=None) -> dict:
    r = await world["c"].post("/admin/invites", headers=hdr(world["admin"].id),
                              json={"name": name, "email": email, "ig_username": ig})
    assert r.status_code == 201, r.text
    return r.json()


async def people(world) -> dict:
    r = await world["c"].get("/admin/people", headers=hdr(world["admin"].id))
    assert r.status_code == 200
    return r.json()


async def test_convite_criado_pela_rota_normaliza_e_cadastra(world):
    created = await invite(world, email="Fulano@X.com")
    assert created["invite"]["ig_username"] == "fulano.ig"
    assert created["invite"]["email"] == "fulano@x.com"
    assert "token_hash" not in str(created)
    assert (await register(world, created["token"])).status_code == 200


async def test_link_de_reset_novo_invalida_o_anterior(world):
    async def link():
        r = await world["c"].post(f"/admin/users/{world['other'].id}/reset-link",
                                  headers=hdr(world["admin"].id))
        assert r.status_code == 200 and r.json()["expires_at"]
        return r.json()["token"]

    first = await link()
    second = await link()
    assert (await info(world, first))["valid"] is False
    assert (await info(world, second))["purpose"] == "reset"




@pytest.mark.parametrize("method,path", [
    ("get", "/admin/people"),
    ("get", "/admin/diagnostics"),
    ("post", "/admin/invites"),
    ("post", "/admin/invites/1/meta-added"),
    ("post", "/admin/invites/1/renew"),
    ("delete", "/admin/invites/1"),
    ("post", "/admin/users/1/reset-link"),
])
async def test_nao_admin_recebe_403_em_tudo(world, method, path):
    await invite(world)
    body = {"name": "x", "ig_username": "x"} if path == "/admin/invites" else None
    r = await world["c"].request(method, path, json=body, headers=hdr(world["other"].id))
    assert r.status_code == 403 and r.json() == {"detail": "Só administradores"}
    r = await world["c"].request(method, path, json=body, headers=hdr())
    assert r.status_code == 401


@pytest.mark.parametrize("ig", ["", "@", "com espaço", "a" * 31, "ç", "a/b", "@@a"])
async def test_arroba_invalido(world, ig):
    r = await world["c"].post("/admin/invites", headers=hdr(world["admin"].id),
                              json={"name": "x", "ig_username": ig})
    assert r.status_code == 422


async def test_convite_duplicado_e_email_de_quem_ja_tem_conta(world):
    await invite(world)
    for body in ({"name": "x", "ig_username": "FULANO.ig"},
                 {"name": "x", "ig_username": "nova", "email": "comum@x.com"}):
        r = await world["c"].post("/admin/invites", headers=hdr(world["admin"].id), json=body)
        assert r.status_code == 409


async def test_status_das_pessoas(world):
    c, admin = world["c"], world["admin"]
    pending = await invite(world, ig="pendente", name="Pendente")
    expired = await invite(world, ig="vencido", name="Vencido")
    await expire(world, expired["invite"]["id"])
    waiting = await invite(world, ig="aguarda", name="Aguarda")
    await register(world, waiting["token"], email="aguarda@x.com", name="Aguarda")
    async with world["sessions"]() as db:
        await crud.account.upsert(db, "d1", "enc", username="do_dono", owner_user_id=admin.id)
        await crud.account.upsert(db, "c1", "enc", username="ok", owner_user_id=world["other"].id)
        broken = await crud.account.upsert(db, "c2", "enc", username="quebrada",
                                           owner_user_id=world["other"].id)
        broken.token_invalid_at = datetime.now(timezone.utc)
        await crud.account.upsert(db, "orfa", "enc", username="sem_dono")

    body = await people(world)
    assert body["meta_app_id"] == "1234567890"
    by_name = {p["name"]: p for p in body["people"]}
    assert set(by_name) == {"Dono", "Comum", "Aguarda", "Pendente"}  # vencido some
    assert by_name["Dono"]["status"] == "active" and by_name["Dono"]["is_self"] is True
    assert by_name["Comum"]["status"] == "needs_reconnect"
    assert {a["username"] for a in by_name["Comum"]["accounts"]} == {"ok", "quebrada"}
    assert by_name["Comum"]["invite_id"] is None
    waiting_row = by_name["Aguarda"]
    assert waiting_row["status"] == "awaiting_instagram" and waiting_row["kind"] == "user"
    assert waiting_row["ig_username"] == "aguarda" and waiting_row["last_login_at"]
    assert waiting_row["invite_id"] == waiting["invite"]["id"]
    row = by_name["Pendente"]
    assert (row["status"], row["kind"], row["user_id"]) == ("pending", "invite", None)
    assert row["invite_id"] == pending["invite"]["id"] and row["expires_at"]
    assert "token" not in str(body)
    # marcar "Já adicionei" depois do cadastro
    r = await c.post(f"/admin/invites/{waiting_row['invite_id']}/meta-added", headers=hdr(admin.id))
    assert r.status_code == 200 and r.json()["meta_tester_added_at"]
    by_name = {p["name"]: p for p in (await people(world))["people"]}
    assert by_name["Aguarda"]["meta_tester_added"] is True


async def test_meta_app_id_com_cara_errada_nao_vai_na_resposta(world, monkeypatch):
    monkeypatch.setattr(settings, "meta_app_id", "segredo-colado-no-campo-errado")
    r = await world["c"].get("/admin/people", headers=hdr(world["admin"].id))
    assert r.json()["meta_app_id"] is None and "segredo-colado" not in r.text


async def test_renew_invalida_o_token_antigo(world):
    c, admin = world["c"], world["admin"]
    created = await invite(world)
    old_id = created["invite"]["id"]
    await c.post(f"/admin/invites/{old_id}/meta-added", headers=hdr(admin.id))
    r = await c.post(f"/admin/invites/{old_id}/renew", headers=hdr(admin.id))
    assert r.status_code == 200
    fresh = r.json()
    assert fresh["token"] != created["token"] and fresh["invite"]["meta_tester_added_at"]
    assert (await info(world, created["token"]))["valid"] is False
    assert (await info(world, fresh["token"]))["valid"] is True
    assert (await register(world, created["token"])).status_code == 410
    # o antigo (cancelado) não se renova nem se cancela de novo
    assert (await c.post(f"/admin/invites/{old_id}/renew", headers=hdr(admin.id))).status_code == 404
    assert (await c.delete(f"/admin/invites/{old_id}", headers=hdr(admin.id))).status_code == 404
    # usado também não
    assert (await register(world, fresh["token"])).status_code == 200
    used = fresh["invite"]["id"]
    assert (await c.post(f"/admin/invites/{used}/renew", headers=hdr(admin.id))).status_code == 404
    assert (await c.delete(f"/admin/invites/{used}", headers=hdr(admin.id))).status_code == 404


async def test_reset_link_nao_vale_para_si_nem_para_quem_nao_existe(world):
    admin = world["admin"]
    r = await world["c"].post(f"/admin/users/{admin.id}/reset-link", headers=hdr(admin.id))
    assert r.status_code == 400
    r = await world["c"].post("/admin/users/999999/reset-link", headers=hdr(admin.id))
    assert r.status_code == 404


async def test_diagnostics_lista_os_problemas_sem_os_valores(world, monkeypatch):
    monkeypatch.setattr(settings, "meta_app_id", "valor-que-nao-pode-vazar")
    r = await world["c"].get("/admin/diagnostics", headers=hdr(world["admin"].id))
    assert r.status_code == 200
    assert any(p.startswith("META_APP_ID") for p in r.json()["problems"])
    assert "valor-que-nao-pode-vazar" not in r.text and SECRET not in r.text
