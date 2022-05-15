from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class Announcement:
    crontab_fmt: str
    guild_id: int
    channel_id: int
    content: str




