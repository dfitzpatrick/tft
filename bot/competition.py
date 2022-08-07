import asyncio
import logging
from copy import deepcopy
from typing import Optional, Dict, NamedTuple, Union, Any

import aiohttp
import discord
from discord.ext import commands, tasks

from mixins.config import ConfigMixin
from tft.schema import CompetitionEntry
from tft.services import fetch_page_source, find_active_competition, parse_with_soup, \
    get_competition_label, parse_competition, make_competition_embed

log = logging.getLogger(__name__)


class MessageInfo(NamedTuple):
    channel_id: int
    message_id: int


class CompetitionCog(ConfigMixin, commands.Cog):
    _update_minutes = 10

    def __init__(self, bot: commands.Bot):
        super(CompetitionCog, self).__init__()
        self.bot = bot
        self.competition_list_url = "https://competitions.thefundedtraderprogram.com/"
        self.competition_details_url = "https://competitions.thefundedtraderprogram.com/competition/{id}"
        self.embed: Optional[discord.Embed] = None
        self._task: Optional[asyncio.Task] = None
        self.guild_map: Dict[str, MessageInfo] = {}

    def _task_callback(self, future: asyncio.Future):
        if future.exception():
            raise future.exception()

    async def _fetch_saved_message(self, guild_id: int, message_info: MessageInfo) -> Optional[discord.PartialMessage]:
        """Fetch the message or update our settings that the message is gone
        This attempts to grab it from cache first, or an API call"""
        guild = self.bot.get_guild(guild_id)
        if guild is not None:
            channel = guild.get_channel(message_info.channel_id)
            if channel is not None:
                message = channel.get_partial_message(message_info.message_id)
                return message


    async def _delete_message(self, message: Union[discord.PartialMessage, discord.Message]):
        """Facilitates safe deleting of a Discord Message"""
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            log.info(f"Failed to delete message {message.id}")
            pass

    async def _new_message(self, guild_id: int, message_info: MessageInfo):
        """Updates the bots settings on the new interactive leaderboard and removes any older leaderboard
        that may exist in the discord guild"""
        old_info = self.get_saved_message_info(guild_id)
        if old_info is not None:
            old_message = await self._fetch_saved_message(guild_id, old_info)
            if old_message is not None:
                await self._delete_message(old_message)
        self.config_settings[str(guild_id)] = message_info
        self.save_settings()

    async def _update_guild_message(self, guild_id: int, message_info: MessageInfo, embed: discord.Embed):
        """Updates the embed with the new polled information."""
        message = await self._fetch_saved_message(guild_id, message_info)
        if message is None:
            del self.config_settings[str(guild_id)]
            self.save_settings()
            return
        try:
            await message.edit(embed=embed)
        except discord.NotFound:
            del self.config_settings[str(guild_id)]
            self.save_settings()

    async def fetch_competition_rankings(self, competition_id: int, start: int = 0, length: int = 10):
        def convert(o: Dict[str, Any], rank: int) -> CompetitionEntry:
            return CompetitionEntry(
                rank=rank,
                name=o['nickname'],
                roi=o['returnPct'],
                back=o['backPct'],
                prize=o['prize']
            )
        container = []
        target = "{}/leaderboard/getleaderboarddata".format(self.competition_list_url)
        headers = {
            "accept": "application/json"
        }
        data = {
            "competitionId": competition_id,
            "start": start,
            "length": length
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(target, data=data) as resp:
                    resp = await resp.json()
                    for idx, o in enumerate(resp.get('data', [])):
                        container.append(convert(o, idx+1))
        except Exception as e:
            log.error("Could not fetch competition listings")
            log.error(e)
        return container



    async def update(self):
        """Fetches HTML from TFT and parses it, and generates an embed."""
        log.info("Updating Embed from TFT site.")
        competition_list_html = await fetch_page_source(self.competition_list_url, log)
        competition_id = find_active_competition(competition_list_html)
        if competition_id is None:
            return

        competition_html = await fetch_page_source(self.competition_details_url.format(id=competition_id), log)
        # We cache the soup object in here since the result is so large.
        soup = parse_with_soup(competition_html)
        prize_pool = get_competition_label(soup, "prize pool") or "Not Found"
        remaining_contestants = get_competition_label(soup, "remaining contestants") or "Not Found"
        entries = await self.fetch_competition_rankings(competition_id)
        embed = make_competition_embed(entries, prize_pool, remaining_contestants)
        embed.set_footer(text=f"Updated every {self._update_minutes} minutes")
        self.embed = embed

    def get_saved_message_info(self, guild_id: int) -> Optional[MessageInfo]:
        """Helper function that converts our dictionary back to a Named Tuple.
        The bot uses this information for recovery. When serializing new settings to disk,
        we keep with the JSON standards which makes Python-specific objects like Named Tuple get lost.
        This converts it back into one if needed."""
        o = self.config_settings.get(str(guild_id))
        if o is not None and not isinstance(o, MessageInfo):
            # It is a list from json serialization
            return MessageInfo(channel_id=o[0], message_id=o[1])
        return o

    @tasks.loop(minutes=_update_minutes)
    async def update_task(self):
        """The actual polling task. To change the time, change _update_minutes at the top of this file"""
        await self.bot.wait_until_ready()
        await self.update()
        for guild_id in deepcopy(list(self.config_settings.keys())):
            guild_id = int(guild_id)
            message_info = self.get_saved_message_info(guild_id)
            await self._update_guild_message(guild_id, message_info, self.embed)

    async def cog_load(self) -> None:
        """Waits until the cache is loaded with guilds and then launches our task process"""
        await self.bot.wait_until_ready()
        log.info("Starting TFT Polling Task")
        self._task = self.update_task.start()
        self._task.add_done_callback(self._task_callback)

    async def cog_unload(self) -> None:
        if not self._task.done():
            self._task.cancel()

    @commands.has_role("Admin")
    @commands.command(name='competition')
    async def competition_cmd(self, ctx: commands.Context):
        """Fetches the Top 10 Leaderboard information from The Funded Trader"""
        await ctx.trigger_typing()
        if self.embed is None:
            await self.update()

        if self.embed is None:
            await ctx.send("No Competitions found.")
            return
        message = await ctx.send(embed=self.embed)
        message_info = MessageInfo(channel_id=ctx.channel.id, message_id=message.id)
        await self._new_message(ctx.guild.id, message_info)

    @competition_cmd.error
    async def leaderboard_error(self, ctx, error):
        name = ctx.author.display_name
        guild = ctx.guild.name

        if isinstance(error, commands.MissingPermissions):
            log.warning(f"{name} tried to use !competition in guild: {guild} without manage channels permissions")
        else:
            log.error(error)

async def setup(bot: commands.Bot):
    await bot.add_cog(CompetitionCog(bot))
