from typing import Optional, List
from bs4 import BeautifulSoup
import aiohttp

from bot.faq.schema import FaqCategory, FaqArticle


async def get_html(url: str) -> Optional[str]:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, raise_for_status=True) as resp:
            return await resp.text(encoding='utf-8')


async def get_faq_categories(html: str) -> List[FaqCategory]:
    container = []
    soup = BeautifulSoup(html, 'html.parser')

    for item in soup(class_="g__space"):
        url = item("a")[0]['href']
        name = item.find_next(class_="t__h3").text
        container.append(
            FaqCategory(name=name, url=url)
        )
    return container

async def get_articles(html: str) -> List[FaqArticle]:
    container = []
    soup = BeautifulSoup(html, 'html.parser')

    for article_link in soup.find_all("a", class_="t__no-und"):
        url = article_link['href']
        name = article_link.find_next("span", class_="c__primary").text
        description = article_link.find_next("span", class_="paper__preview").text
        container.append(FaqArticle(name=name, url=url, description=description))
    return container