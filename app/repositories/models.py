from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Movie:
    code: str
    file_id: str
    title: str | None
    caption: str | None
    created_at: datetime | None = None
    category: str = "Boshqa"


@dataclass(frozen=True, slots=True)
class RequiredChannel:
    chat_id: int
    title: str
    invite_link: str | None
    is_join_request: bool
