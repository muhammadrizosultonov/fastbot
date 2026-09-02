import logging
from aiogram import Router
from aiogram.types import ChatJoinRequest

from app.services.container import Services

log = logging.getLogger(__name__)
router = Router(name="join_requests")


@router.chat_join_request()
async def join_request(request: ChatJoinRequest, services: Services) -> None:
    # Always record the join request so user passes mandatory subscription check immediately
    await services.subscriptions.record_join_request(request.from_user.id, request.chat.id)

    # Also attempt auto-approval if possible
    try:
        await request.bot.approve_chat_join_request(request.chat.id, request.from_user.id)
    except Exception as e:
        log.debug("Auto-approve chat join request notice for chat %s: %s", request.chat.id, e)
