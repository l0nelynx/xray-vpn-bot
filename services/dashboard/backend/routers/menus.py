from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from ..auth import get_current_user
from ..database.models import MenuScreen, MenuButton
from ..database.session import async_session
from ..schemas.menus import (
    MenuScreenSchema, MenuScreenCreate, MenuScreenUpdate,
    MenuButtonSchema, MenuButtonCreate, MenuButtonUpdate,
    ButtonReorderRequest,
)
from ..cache_utils import bump_cache_version

router = APIRouter(prefix="/api/menus", tags=["menus"])


def _validate_button(button: MenuButton) -> None:
    if button.button_type not in {"callback", "url", "webapp", "tariff"}:
        raise HTTPException(400, "Unsupported button type")
    if not button.text_ru.strip() or not button.text_en.strip():
        raise HTTPException(400, "RU and EN text are required")
    if button.button_type == "tariff":
        button.callback_data = None
        button.url = None
    elif button.button_type in {"url", "webapp"}:
        if not (button.url or "").strip():
            raise HTTPException(400, "URL is required")
        button.callback_data = None
    elif not (button.callback_data or "").strip():
        raise HTTPException(400, "Callback data is required")


@router.get("/screens", response_model=list[MenuScreenSchema])
async def list_screens(_: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(MenuScreen)
            .options(selectinload(MenuScreen.buttons))
            .order_by(MenuScreen.id)
        )
        screens = result.scalars().all()
        return [MenuScreenSchema.model_validate(s) for s in screens]


@router.get("/screens/{screen_id}", response_model=MenuScreenSchema)
async def get_screen(screen_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(MenuScreen)
            .options(selectinload(MenuScreen.buttons))
            .where(MenuScreen.id == screen_id)
        )
        screen = result.scalar_one_or_none()
        if not screen:
            raise HTTPException(404, "Screen not found")
        return MenuScreenSchema.model_validate(screen)


@router.post("/screens", response_model=MenuScreenSchema)
async def create_screen(body: MenuScreenCreate, _: str = Depends(get_current_user)):
    async with async_session() as session:
        screen = MenuScreen(
            slug=body.slug,
            name=body.name,
            message_text_ru=body.message_text_ru,
            message_text_en=body.message_text_en,
            is_system=body.is_system,
            is_active=body.is_active,
        )
        session.add(screen)
        await session.commit()

        result = await session.execute(
            select(MenuScreen)
            .options(selectinload(MenuScreen.buttons))
            .where(MenuScreen.id == screen.id)
        )
        await bump_cache_version()
        return MenuScreenSchema.model_validate(result.scalar_one())


@router.put("/screens/{screen_id}", response_model=MenuScreenSchema)
async def update_screen(screen_id: int, body: MenuScreenUpdate, _: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(MenuScreen).where(MenuScreen.id == screen_id)
        )
        screen = result.scalar_one_or_none()
        if not screen:
            raise HTTPException(404, "Screen not found")

        for field in ("slug", "name", "message_text_ru", "message_text_en", "is_active"):
            val = getattr(body, field, None)
            if val is not None:
                setattr(screen, field, val)

        await session.commit()

        result = await session.execute(
            select(MenuScreen)
            .options(selectinload(MenuScreen.buttons))
            .where(MenuScreen.id == screen_id)
        )
        await bump_cache_version()
        return MenuScreenSchema.model_validate(result.scalar_one())


@router.delete("/screens/{screen_id}")
async def delete_screen(screen_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(MenuScreen).where(MenuScreen.id == screen_id)
        )
        screen = result.scalar_one_or_none()
        if not screen:
            raise HTTPException(404, "Screen not found")
        if screen.is_system:
            raise HTTPException(400, "Cannot delete system screen")

        screen.is_active = False
        await session.commit()
    await bump_cache_version()
    return {"ok": True}


@router.post("/screens/{screen_id}/buttons", response_model=MenuButtonSchema)
async def create_button(screen_id: int, body: MenuButtonCreate, _: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(MenuScreen).where(MenuScreen.id == screen_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(404, "Screen not found")

        button = MenuButton(
            screen_id=screen_id,
            text_ru=body.text_ru,
            text_en=body.text_en,
            callback_data=body.callback_data,
            url=body.url,
            row=body.row,
            col=body.col,
            sort_order=body.sort_order,
            button_type=body.button_type,
            is_active=body.is_active,
        )
        _validate_button(button)
        session.add(button)
        await session.commit()
        await session.refresh(button)
        await bump_cache_version()
        return MenuButtonSchema.model_validate(button)


@router.put("/buttons/{button_id}", response_model=MenuButtonSchema)
async def update_button(button_id: int, body: MenuButtonUpdate, _: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(MenuButton).where(MenuButton.id == button_id)
        )
        button = result.scalar_one_or_none()
        if not button:
            raise HTTPException(404, "Button not found")

        for field, val in body.model_dump(exclude_unset=True).items():
            setattr(button, field, val)
        _validate_button(button)

        await session.commit()
        await session.refresh(button)
        await bump_cache_version()
        return MenuButtonSchema.model_validate(button)


@router.delete("/buttons/{button_id}")
async def delete_button(button_id: int, _: str = Depends(get_current_user)):
    async with async_session() as session:
        result = await session.execute(
            select(MenuButton).where(MenuButton.id == button_id)
        )
        button = result.scalar_one_or_none()
        if not button:
            raise HTTPException(404, "Button not found")

        await session.delete(button)
        await session.commit()
    await bump_cache_version()
    return {"ok": True}


@router.put("/screens/{screen_id}/buttons/reorder")
async def reorder_buttons(screen_id: int, body: ButtonReorderRequest, _: str = Depends(get_current_user)):
    ids = [item.id for item in body.items]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "Duplicate button in reorder request")
    async with async_session() as session:
        existing = set(
            (
                await session.execute(
                    select(MenuButton.id).where(
                        MenuButton.screen_id == screen_id,
                        MenuButton.id.in_(ids),
                    )
                )
            ).scalars().all()
        )
        if existing != set(ids):
            raise HTTPException(404, "Button not found on this screen")
        for item in body.items:
            await session.execute(
                update(MenuButton)
                .where(MenuButton.id == item.id, MenuButton.screen_id == screen_id)
                .values(row=item.row, col=item.col, sort_order=item.sort_order)
            )
        await session.commit()
    await bump_cache_version()
    return {"ok": True}
