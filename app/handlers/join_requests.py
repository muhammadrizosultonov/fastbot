import logging
from aiogram import Router
from aiogram.types import ChatJoinRequest

from app.services.container import Services

log = logging.getLogger(__name__)
router = Router(name="join_requests")


@router.chat_join_request()
async def join_request(request: ChatJoinRequest, services: Services) -> None:
    # Record join request in bot cache so user passes mandatory subscription check immediately.
    # We do NOT auto-approve so join requests accumulate in the channel for the admin.
    await services.subscriptions.record_join_request(request.from_user.id, request.chat.id)
