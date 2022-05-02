from dataclasses import dataclass
from typing import List, Union, Optional


class Flatten:

    def flatten(self, *attrs) -> List[Union[int, str]]:
        container = []
        for attr in attrs:
            value = getattr(self, attr)
            if value is not None:
                container.append(value)
        return container


@dataclass
class LeaderboardEntry(Flatten):
    rank: int
    name: str
    roi: str
    profit: str


    def flatten(self, *attrs) -> List[Union[int, str]]:
        container = []
        for attr in attrs:
            value = getattr(self, attr)
            if value is not None:
                container.append(value)
        return container


@dataclass
class CompetitionEntry(Flatten):
    rank: int
    name: str
    roi: str
    back: str
    prize: str

