import orjson
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from redis.asyncio import Redis

from app.repositories.channels import ChannelRepository
from app.repositories.models import RequiredChannel


class SubscriptionService:
    CHANNELS_KEY = "required_channels:v1"
    JOIN_REQUEST_KEY_PREFIX = "join_req:v1:"

    def __init__(self, bot: Bot, redis: Redis, repository: ChannelRepository, ttl: int) -> None:
        self.bot, self.redis, self.repository, self.ttl = bot, redis, repository, ttl

    async def channels(self) -> list[RequiredChannel]:
        raw = await self.redis.get(self.CHANNELS_KEY)
        if raw:
            try:
                return [RequiredChannel(**item) for item in orjson.loads(raw)]
            except Exception:
                pass
        channels = await self.repository.list_required()
        await self.redis.set(
            self.CHANNELS_KEY,
            orjson.dumps([{"chat_id": x.chat_id, "title": x.title, "invite_link": x.invite_link,
                            "is_join_request": x.is_join_request} for x in channels]).decode(),
            ex=60,
        )
        return channels

    async def invalidate_channels(self) -> None:
        await self.redis.delete(self.CHANNELS_KEY)

    async def record_join_request(self, user_id: int, chat_id: int) -> None:
        # Save for 30 days in Redis (user submitted join request)
        await self.redis.set(f"{self.JOIN_REQUEST_KEY_PREFIX}{chat_id}:{user_id}", "1", ex=2_592_000)
        await self.redis.set(f"sub:v1:{chat_id}:{user_id}", "1", ex=self.ttl)

    async def is_join_requested(self, user_id: int, chat_id: int) -> bool:
        val = await self.redis.get(f"{self.JOIN_REQUEST_KEY_PREFIX}{chat_id}:{user_id}")
        return val == "1"

    async def missing(self, user_id: int) -> list[RequiredChannel]:
        channels = await self.channels()
        if not channels:
            return []

        missing: list[RequiredChannel] = []
        for channel in channels:
            # 1. If user sent a join request to this channel, count as subscribed immediately
            if await self.is_join_requested(user_id, channel.chat_id):
                continue

            key = f"sub:v1:{channel.chat_id}:{user_id}"
            cached = await self.redis.get(key)
            if cached == "1":
                continue
            if cached == "0":
                missing.append(channel)
                continue

            try:
                member = await self.bot.get_chat_member(channel.chat_id, user_id)
                subscribed = member.status in {
                    ChatMemberStatus.MEMBER,
                    ChatMemberStatus.ADMINISTRATOR,
                    ChatMemberStatus.CREATOR,
                    ChatMemberStatus.RESTRICTED,
                }
            except Exception:
                subscribed = False

            await self.redis.set(key, "1" if subscribed else "0", ex=self.ttl)
            if not subscribed:
                missing.append(channel)

        return missing

    async def mark_joined(self, user_id: int, chat_id: int) -> None:
        await self.redis.set(f"{self.JOIN_REQUEST_KEY_PREFIX}{chat_id}:{user_id}", "1", ex=2_592_000)
        await self.redis.set(f"sub:v1:{chat_id}:{user_id}", "1", ex=self.ttl)

    async def invalidate_user(self, user_id: int) -> None:
        channels = await self.channels()
        if channels:
            keys = [f"sub:v1:{channel.chat_id}:{user_id}" for channel in channels]
            await self.redis.delete(*keys)
