from typing import List, Dict

from discord.ext import commands

from bot.faq.services import get_faq_categories, get_html, get_articles
from mixins.config import ConfigMixin
import discord
import logging


log = logging.getLogger(__name__
                        )
class Faq(ConfigMixin, commands.Cog):

    def __init__(self, bot: commands.Bot):
        super(Faq, self).__init__()
        self.bot = bot
        self.base_url = "https://help.thefundedtraderprogram.com/"
        self.faq_category_url = "https://help.thefundedtraderprogram.com/en"

    async def get_categories(self):
        html = await get_html(self.faq_category_url)
        return await get_faq_categories(html)

    async def get_articles(self, url: str):
        url = self.base_url + url
        html = await get_html(url)
        return await get_articles(html)

    def _save_message(self, message: discord.Message):
        channel_id = message.channel.id
        message_id = message.id
        if self.config_settings.get('faq_messages') is None:
            self.config_settings['faq_messages'] = {}

        if channel_id not in self.config_settings['faq_messages'].keys():
            self.config_settings['faq_messages'][channel_id] = []
        self.config_settings['faq_messages'][channel_id].append(message_id)


    async def _delete_old_messages(self):
        for channel_id, message_ids in self.config_settings.get('faq_messages', {}).items():
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                log.warning(f"Tried to delete old messages but could not find channel id {channel_id}")
                continue
            for msg_id in message_ids:
                message = channel.get_partial_message(msg_id)
                try:
                    await message.delete()
                except (discord.Forbidden, discord.HTTPException):
                    log.warning("Tried to delete message with no permissions")
                except discord.NotFound:
                    log.warning(f"Tried to delete message that did not exist {msg_id}")
                    pass
        self.config_settings['faq_messages'] = {}
        self.save_settings()

    @commands.has_role("Admin")
    @commands.command('faq')
    async def faq(self, ctx: commands.Context):
        await self._delete_old_messages()
        categories = await self.get_categories()
        for category in categories:
            articles = await self.get_articles(category.url)
            text = ''.join([f"[**{a.name}**]({self.base_url + a.url})\n{a.description}\n\n" for a in articles])
            embed = discord.Embed(title=category.name, description=text)
            message = await ctx.send(embed=embed)
            self._save_message(message)
        self.save_settings()



async def setup(bot):
    await bot.add_cog(Faq(bot))


