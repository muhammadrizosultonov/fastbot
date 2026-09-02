from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from app.services.container import Services


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, services: Services) -> bool:
        return bool(event.from_user and await services.admins.is_admin(event.from_user.id))
