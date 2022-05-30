from typing import NamedTuple
from pydantic import BaseModel


class FaqCategory(BaseModel):
    name: str
    url: str


class FaqArticle(FaqCategory):
    description = ""

