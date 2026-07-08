"""Operações de banco para automações."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.automation import Automation, TriggerType
from app.schemas.automation import AutomationCreate, AutomationUpdate


async def create(db: AsyncSession, data: AutomationCreate) -> Automation:
    automation = Automation(**data.model_dump())
    db.add(automation)
    await db.commit()
    await db.refresh(automation)
    return automation


async def get(db: AsyncSession, automation_id: int) -> Automation | None:
    return await db.get(Automation, automation_id)


async def list_by_account(db: AsyncSession, account_id: str) -> list[Automation]:
    result = await db.execute(
        select(Automation).where(Automation.account_id == account_id)
    )
    return list(result.scalars().all())


async def update(
    db: AsyncSession, automation: Automation, data: AutomationUpdate
) -> Automation:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(automation, field, value)
    await db.commit()
    await db.refresh(automation)
    return automation


async def delete(db: AsyncSession, automation: Automation) -> None:
    await db.delete(automation)
    await db.commit()


async def bind_next_posts(db: AsyncSession, account_id: str, media_id: str) -> None:
    """Vincula automações 'próxima publicação' ao 1º post novo (fora do baseline)."""
    if not media_id:
        return
    result = await db.execute(
        select(Automation).where(
            Automation.account_id == account_id,
            Automation.enabled.is_(True),
            Automation.bind_next.is_(True),
            Automation.post_id.is_(None),
        )
    )
    changed = False
    for auto in result.scalars().all():
        baseline = auto.baseline_media_ids or []
        if media_id not in baseline:
            auto.post_id = media_id  # vincula → passa a agir como "específica"
            changed = True
    if changed:
        await db.commit()


async def find_matching(
    db: AsyncSession, account_id: str, text: str, post_id: str | None
) -> list[Automation]:
    """Retorna automações habilitadas cujo gatilho casa com o comentário."""
    result = await db.execute(
        select(Automation).where(
            Automation.account_id == account_id,
            Automation.enabled.is_(True),
        )
    )
    candidates = list(result.scalars().all())

    lowered = (text or "").lower()
    matches: list[Automation] = []
    for auto in candidates:
        # "Próxima publicação" ainda não vinculada não dispara em post algum.
        if auto.bind_next and not auto.post_id:
            continue
        if auto.post_id and auto.post_id != post_id:
            continue
        # Palavras de exclusão: se qualquer uma aparecer, ignora o disparo.
        if auto.exclude_keywords:
            blocked = [w.strip().lower() for w in auto.exclude_keywords.split(",") if w.strip()]
            if any(w in lowered for w in blocked):
                continue
        if auto.trigger == TriggerType.COMMENT_ANY:
            matches.append(auto)
        elif auto.trigger == TriggerType.COMMENT_KEYWORD and auto.keyword:
            if auto.keyword.lower() in lowered:
                matches.append(auto)
    return matches
