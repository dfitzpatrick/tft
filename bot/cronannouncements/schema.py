from pydantic.dataclasses import dataclass
from typing import Any


@dataclass
class Announcement:
    crontab_fmt: str
    guild_id: int
    channel_id: int
    content: str




