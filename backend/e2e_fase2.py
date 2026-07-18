import asyncio
from app.core.database import SessionLocal, engine
from app import crud
from app.schemas.automation import AutomationCreate

ACC = "demo"  # conta de teste (não polui a conta real)

async def main():
    created = []
    async with SessionLocal() as db:
        try:
            def mk(**kw):
                base = dict(name=kw.pop("name"), trigger=kw.pop("trigger"),
                           reply_message="resposta", account_id=ACC)
                base.update(kw)
                return AutomationCreate(**base)

            specs = [
                mk(name="[t] dm kw",     trigger="dm_keyword",   keyword="quero"),
                mk(name="[t] dm any",    trigger="dm_any"),
                mk(name="[t] story kw",  trigger="story_reply",  keyword="eu quero"),
                mk(name="[t] story any", trigger="story_reply"),
                mk(name="[t] mention",   trigger="story_mention"),
            ]
            for s in specs:
                a = await crud.automation.create(db, s)
                created.append(a.id)
            print("Criadas via ORM (enum round-trip OK):", created)

            def names(ms): return sorted(a.name for a in ms)

            # --- DM ---
            r1 = await crud.automation.find_matching_dm(db, ACC, "eu quero isso")
            r2 = await crud.automation.find_matching_dm(db, ACC, "bom dia")
            # --- Story reply ---
            r3 = await crud.automation.find_matching_story(db, ACC, "eu quero saber")
            r4 = await crud.automation.find_matching_story(db, ACC, "story lindo")
            # --- Story mention ---
            r5 = await crud.automation.find_matching_story_mention(db, ACC)

            checks = [
                ("DM keyword 'eu quero isso' -> dm kw",     names(r1), ["[t] dm kw"]),
                ("DM 'bom dia' -> dm any (fallback)",       names(r2), ["[t] dm any"]),
                ("Story 'eu quero saber' -> story kw",      names(r3), ["[t] story kw"]),
                ("Story 'story lindo' -> story any",        names(r4), ["[t] story any"]),
                ("Mention -> mention",                      names(r5), ["[t] mention"]),
            ]
            ok = True
            for label, got, exp in checks:
                good = got == exp
                ok = ok and good
                print(("  PASS" if good else "  FAIL"), "|", label, "| got:", got)
            print("\nRESULTADO:", "TODOS OK ✅" if ok else "FALHOU ❌")
        finally:
            # limpeza: remove tudo que criei
            for aid in created:
                a = await crud.automation.get(db, aid)
                if a:
                    await crud.automation.delete(db, a)
            print("Limpeza: removidas", len(created), "automações de teste.")
    await engine.dispose()

asyncio.run(main())
