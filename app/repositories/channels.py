import asyncpg

from app.repositories.models import RequiredChannel


class ChannelRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def list_required(self) -> list[RequiredChannel]:
        rows = await self.pool.fetch(
            """SELECT chat_id, title, invite_link, is_join_request
               FROM required_channels WHERE is_active ORDER BY sort_order, id"""
        )
        return [RequiredChannel(**dict(row)) for row in rows]

    async def add(self, channel: RequiredChannel) -> None:
        await self.pool.execute(
            """INSERT INTO required_channels (chat_id, title, invite_link, is_join_request)
               VALUES ($1,$2,$3,$4)
               ON CONFLICT (chat_id) DO UPDATE SET title=EXCLUDED.title, invite_link=EXCLUDED.invite_link,
                   is_join_request=EXCLUDED.is_join_request, is_active=true""",
            channel.chat_id, channel.title, channel.invite_link, channel.is_join_request,
        )

    async def deactivate(self, chat_id: int) -> bool:
        result = await self.pool.execute("UPDATE required_channels SET is_active=false WHERE chat_id=$1", chat_id)
        return result.endswith("1")
