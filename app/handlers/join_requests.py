from aiogram import Router
from aiogram.types import ChatJoinRequest

from app.services.container import Services

router = Router(name="join_requests")


@router.chat_join_request()
async def join_request(request: ChatJoinRequest, services: Services) -> None:
    # Approval is deliberately explicit in the channel configuration; auto-approve can be enabled per policy later.
    channels = await services.subscriptions.channels()
    if any(channel.chat_id == request.chat.id and channel.is_join_request for channel in channels):
        await request.bot.approve_chat_join_request(request.chat.id, request.from_user.id)
        await services.subscriptions.mark_joined(request.from_user.id, request.chat.id)
