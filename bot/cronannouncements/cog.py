import asyncio
import json
from copy import deepcopy
from json import JSONDecodeError
from pathlib import Path

import aiocron
from discord.ext import commands
from discord import app_commands
from typing import Dict, List, TypeAlias, Set
import logging
from bot.cronannouncements.schema import Announcement

AnnouncementStorage: TypeAlias = Dict[int, List[Announcement]]

from mixins.config import ConfigMixin

log = logging.getLogger(__name__)


class CronAnnouncementCog(ConfigMixin, commands.Cog):
    
    def __init__(self, bot: commands.Bot, path: Path, filename='announcements.json'):
        super(CronAnnouncementCog, self).__init__()
        self.bot = bot
        self.jobs: Dict[int, Set[aiocron.Cron]] = {}
        self.path = path
        self.filename = filename
        self.announcements = {}

    async def cog_load(self) -> None:
        await self.start_all_jobs()

    async def cog_unload(self) -> None:
        for guild_id in self.jobs.keys():
            self.stop_jobs(guild_id)

    async def start_all_jobs(self):
        if not self.announcements:
            self.announcements = self._load_announcements_from_file()
        self.start_jobs(*self.announcements)

    @commands.group(name='announcements')
    async def announcements(self, ctx):
        pass

    @announcements.command()
    async def reload(self, ctx: commands.Context):
        self.announcements = self._load_announcements_from_file()
        self.restart_jobs(ctx.guild.id)

    @reload.error
    async def reload_error(self, ctx, error):
        exception = error.original
        if isinstance(exception, JSONDecodeError):
            await ctx.send("JSON file is not properly formatted")

    def _load_announcements_from_file(self) -> List[Announcement]:
        filename = self.path / self.filename
        with filename.open(encoding='utf-8') as f:
            try:
                data = json.load(f)
                return [Announcement(**v) for v in data]
            except JSONDecodeError as e:
                log.error(f"{filename} is improperly formatted JSON {e}")
                raise

    def _add_job(self, guild_id: int, job: aiocron.Cron):
        if guild_id not in self.jobs.keys():
            self.jobs[guild_id] = set()
        self.jobs[guild_id].add(job)

    def _remove_job(self, guild_id: int, job: aiocron.Cron):
        if job in self.jobs.get(guild_id, set()):
            self.jobs[guild_id].remove(job)

    def stop_jobs(self, guild_id: int):
        jobs = self.jobs.get(guild_id, set())
        for job in jobs:
            job.stop()
        log.info(f"Stopped All Jobs for Guild {guild_id}")

    def _start_job(self, announcement: Announcement):
        job = aiocron.Cron(announcement.crontab_fmt, self.make_announcement, args=(announcement,), start=True)
        self._add_job(announcement.guild_id, job)
        log.info("Starting CRON Job {} for Guild {} / Channel {}".format(
            announcement.crontab_fmt,
            announcement.guild_id,
            announcement.channel_id
        ))

    def start_jobs(self, *announcements: Announcement):
        for a in announcements:
            self._start_job(a)

    def get_guild_announcements(self, guild_id: int) -> List[Announcement]:
        announcements = [a for a in self.announcements if a.guild_id == guild_id]
        return announcements

    def restart_jobs(self, guild_id: int):
        log.info(f"Restarting all Jobs for Guild {guild_id}")
        announcements = self.get_guild_announcements(guild_id)
        self.stop_jobs(guild_id)
        self.start_jobs(*announcements)

    async def make_announcement(self, announcement: Announcement):
        guild_id = announcement.guild_id
        channel_id = announcement.channel_id
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            log.warning(f"Found announcement for Guild {guild_id} that the bot is not in")
            return
        channel = guild.get_channel(channel_id)
        if channel is None:
            log.warning(f"Found announcement for Guild {guild_id} that is missing the text channel id {channel_id}")
            return
        await channel.send(announcement.content)

        
async def setup(bot: commands.Bot):
    default = Path(__file__).parents[1] / '/static/'
    try:
        from bot.settings import ANNOUNCEMENT_DIR
    except ImportError:
        ANNOUNCEMENT_DIR = default

    await bot.add_cog(CronAnnouncementCog(bot, ANNOUNCEMENT_DIR))
    
    
