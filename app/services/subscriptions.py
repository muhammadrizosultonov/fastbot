import logging
import orjson
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from redis.asyncio import Redis

from app.repositories.channels import ChannelRepository
from app.repositories.models import RequiredChannel

log = logging.getLogger(__name__)


class SubscriptionService:
    CHANNELS_KEY = "required_channels:v1"
    JOIN_REQUEST_KEY_PREFIX = "join_req:v1:"

    def __init__(self, bot: Bot, redis: Redis, repository: ChannelRepository, ttl: int) -> None:
        self.bot, self.redis, self.repository, self.ttl = bot, redis, repository, ttl

    @staticmethod
    def get_id_variants(chat_id: int | str) -> list[str]:
        raw = str(chat_id).strip()
        variants = {raw}
        # e.g. -1001234567890 -> 1234567890, 1001234567890, -1234567890
        if raw.startswith("-100"):
            without_100 = raw[4:]
            variants.add(without_100)
            variants.add(f"-{without_100}")
            variants.add(raw.lstrip("-"))
        elif raw.startswith("-"):
            without_minus = raw[1:]
            variants.add(without_minus)
            variants.add(f"-100{without_minus}")
            variants.add(f"100{without_minus}")
        else:
            variants.add(f"-{raw}")
            variants.add(f"-100{raw}")
            variants.add(f"100{raw}")
        return list(variants)

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
        variants = self.get_id_variants(chat_id)
        for v in variants:
            await self.redis.set(f"{self.JOIN_REQUEST_KEY_PREFIX}{v}:{user_id}", "1", ex=2_592_000)
            await self.redis.set(f"sub:v1:{v}:{user_id}", "1", ex=2_592_000)
        log.info("Recorded join request for user %s across chat variants: %s", user_id, variants)

    async def is_join_requested(self, user_id: int, chat_id: int) -> bool:
        variants = self.get_id_variants(chat_id)
        keys = [f"{self.JOIN_REQUEST_KEY_PREFIX}{v}:{user_id}" for v in variants]
        vals = await self.redis.mget(*keys)
        return any(v == "1" or v == b"1" for v in vals if v is not None)

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
            if cached == "1" or cached == b"1":
                continue
            if cached == "0" or cached == b"0":
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
            except Exception as e:
                log.debug("Could not verify chat member for user %s in chat %s: %s", user_id, channel.chat_id, e)
                subscribed = False

            await self.redis.set(key, "1" if subscribed else "0", ex=self.ttl)
            if not subscribed:
                missing.append(channel)

        return missing

    async def mark_joined(self, user_id: int, chat_id: int) -> None:
        variants = self.get_id_variants(chat_id)
        for v in variants:
            await self.redis.set(f"{self.JOIN_REQUEST_KEY_PREFIX}{v}:{user_id}", "1", ex=2_592_000)
            await self.redis.set(f"sub:v1:{v}:{user_id}", "1", ex=2_592_000)

    async def invalidate_user(self, user_id: int) -> None:
        channels = await self.channels()
        if channels:
            keys = []
            for channel in channels:
                for v in self.get_id_variants(channel.chat_id):
                    keys.append(f"sub:v1:{v}:{user_id}")
            if keys:
                await self.redis.delete(*keys)
