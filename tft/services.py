import asyncio
import re
import textwrap
import calendar
from datetime import timedelta, datetime, timezone
from typing import List, Optional

import aiohttp
import discord
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from tabulate import simple_separated_format, tabulate
import logging

log = logging.getLogger(__name__
                        )
from tft.schema import LeaderboardEntry, CompetitionEntry

id_pattern = re.compile(r".*/(\d+)")

def parse_leaderboard(html: str) -> List[LeaderboardEntry]:
    container = []
    soup = BeautifulSoup(html, 'html.parser')
    # group by 4 which relates to the leaderboard
    rows = list(zip(*[iter(soup("td"))]*4))

    for idx, row in enumerate(rows):
        rank = idx + 1
        name = row[1].text.strip()
        roi = row[2].text.strip()
        profit = row[3].text.strip()
        container.append(LeaderboardEntry(
            rank=rank,
            name=name,
            roi=roi,
            profit=profit
        ))
    return container


def find_active_competition(html: str) -> Optional[int]:
    soup = BeautifulSoup(html, 'html.parser')
    for item in soup(class_='contest-list_item'):
        status = item.find_next(class_='contest-list_item__label')
        if status is not None and status.text.lower() == 'in progress':
            target = item.find_next(class_='button-colored').attrs['onclick']
            matches = re.findall(id_pattern, target)
            if matches is not None:
                id = matches[0]
                return id


def get_competition_label(soup: BeautifulSoup, label: str) -> Optional[str]:
    for item in soup(class_="label"):
        pool = item.find_next(class_="label_title")
        if pool and pool.text.lower() == label.lower():
            value = item.find_next(class_='label_background-block')
            return value and value.text.strip()

def parse_competition(soup: BeautifulSoup):
    container = []
    for item in soup(id='leaderboardBody'):
        rows = list(zip(*[iter(item("td"))]*5))
        for idx, row in enumerate(rows):
            rank = idx + 1
            name = row[1].text.strip()
            roi = row[2].text.strip()
            back = row[3].text.strip()
            prize = row[4].text.strip()
            container.append(CompetitionEntry(
                rank=rank,
                name=name,
                roi=roi,
                back=back,
                prize=prize
            ))
        return container


async def fetch_page_source(url, logger=None):
    """Polls the TFT Website and gets the html response"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.text()
                return data
    except Exception:
        # The site didn't respond. Wait two minutes and try again
        if logger:
            logger.error(f"Bad response from {url}. Retrying in 2 minutes")
        await asyncio.sleep(120)
        await fetch_page_source(url, logger)


def parse_with_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, 'html.parser')

def make_leaderboard_embed(entries: List[LeaderboardEntry]) -> discord.Embed:
    header = ["Rank", "Nickname", "Return"]
    attrs = ('rank', 'name', 'roi')
    today = datetime.now(timezone.utc)
    month_name = calendar.month_name[today.month]
    values = [ent.flatten(*attrs) for ent in entries]
    tablefmt = simple_separated_format('      ')
    table = tabulate(values, headers=header, colalign=("center",), tablefmt=tablefmt)
    leader = markdown_syntax("fix", entries[0].name)
    table = markdown_syntax("css", table)
    embed = discord.Embed(title=f"The Funded Trader Leaderboard", description=table)
    embed.set_image(url='https://leaderboard.thefundedtraderprogram.com/images/TFT_Logo_Small.png')

    td = last_day_of_month(today) - today
    remaining = friendly_time_delta(td)
    remaining = markdown_syntax("fix", remaining or "Last Day")
    embed.add_field(name=":clock1: Time Remaining", value=remaining, inline=False)
    embed.add_field(name=":trophy: Current Leader", value=leader, inline=False)
    embed.add_field(name=":moneybag: King's/Queen's Profits", value=markdown_syntax("fix", entries[0].profit), inline=False)
    embed.timestamp = datetime.now(timezone.utc)
    return embed

def make_competition_embed(entries: List[CompetitionEntry], pool, contestants) -> discord.Embed:
    header = ["Rank", "Nickname", "Return"]
    attrs = ('rank', 'name', 'roi')
    today = datetime.now(timezone.utc)
    month_name = calendar.month_name[today.month]
    values = [ent.flatten(*attrs) for ent in entries]
    tablefmt = simple_separated_format('   ')
    table = tabulate(values, headers=header, colalign=("center",), tablefmt=tablefmt)
    table = markdown_syntax("css", table)
    embed = discord.Embed(title=f"The {month_name} Competition", description=table)
    embed.set_image(url='https://leaderboard.thefundedtraderprogram.com/images/TFT_Logo_Small.png')

    today = datetime.now(timezone.utc)
    td = last_day_of_month(today) - today
    remaining = friendly_time_delta(td)
    remaining = markdown_syntax("fix", remaining or "Last Day")
    pool = markdown_syntax("fix", pool)
    contestants = markdown_syntax("fix", contestants)
    leader = markdown_syntax("fix", entries[0].name)
    embed.add_field(name=":trophy: Current Leader", value=leader, inline=False)
    embed.add_field(name=":moneybag: Prize Pool", value=pool, inline=False)
    embed.add_field(name=":clock1: Time Remaining", value=remaining, inline=False)
    embed.add_field(name=":people_hugging: Remaining Contestants", value=contestants, inline=False)

    embed.timestamp = datetime.now(timezone.utc)
    return embed

def friendly_time_delta(td: timedelta):
    """
    Taken from https://stackoverflow.com/questions/538666/format-timedelta-to-string
    Just make it more human readable
    Parameters
    ----------
    td_object

    Returns
    -------

    """
    seconds = int(td.total_seconds())
    periods = [
        ('year',        60*60*24*365),
        ('month',       60*60*24*30),
        ('day',         60*60*24),
        ('hour',        60*60),
        ('minute',      60),
        ('second',      1)
    ]

    strings=[]
    for period_name, period_seconds in periods:
        if seconds > period_seconds:
            period_value , seconds = divmod(seconds, period_seconds)
            has_s = 's' if period_value > 1 else ''
            strings.append("%s %s%s" % (period_value, period_name, has_s))

    return ", ".join(strings)


def last_day_of_month(dt):
    return dt.replace(day=1) + relativedelta(months=1) - relativedelta(days=1)


def markdown_syntax(syntax: str, text: str) -> str:
    return textwrap.dedent(f"""```{syntax}
{text}```""").strip()


