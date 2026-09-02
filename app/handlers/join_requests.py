import logging
from aiogram import Router
from aiogram.types import ChatJoinRequest

from app.services.container import Services

log = logging.getLogger(__name__)
router = Router(name="join_requests")


@router.chat_join_request()
async def join_request(request: ChatJoinRequest, services: Services) -> None:
    log.info(
        "📩 ChatJoinRequest update received! User ID: %s (%s), Chat ID: %s (%s)",
        request.from_user.id,
        request.from_user.full_name,
        request.chat.id,
        request.chat.title,
    )
    # Record join request in bot cache so user passes mandatory subscription check immediately
    await services.subscriptions.record_join_request(request.from_user.id, request.chat.id)
