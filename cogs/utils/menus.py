import discord
from discord.ext import menus

from typing import List

class Confirm(menus.Menu):
    def __init__(self, msg, timeout=None, **kwargs):
        super().__init__(timeout=timeout, **kwargs)
        self.msg = msg
        self.result = None

    async def send_initial_message(self, ctx, channel):
        if (type(self.msg) == str):
            return await channel.send(self.msg)
        return await channel.send(embed=self.msg)

    @menus.button('\N{WHITE HEAVY CHECK MARK}')
    async def do_confirm(self, _payload):
        self.result = True
        self.stop()

    @menus.button('\N{CROSS MARK}')
    async def do_deny(self, _payload):
        self.result = False
        self.stop()

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.result

class Choice(menus.Menu):
    def __init__(self, msg, emoji: List[str], **kwargs):
        super().__init__(**kwargs)
        self.msg = msg
        self.emoji = emoji
        self.choice = None
        for x in emoji:
            self.add_button(menus.Button(x, self.onpick))

    async def send_initial_message(self, ctx, channel):
        if (type(self.msg) == str):
            return await channel.send(self.msg)
        return await channel.send(embed=self.msg)        

    async def onpick(self, payload: discord.RawReactionActionEvent):
        self.choice = self.emoji.index(payload.emoji.name)
        self.stop()

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.choice

class Paginator(menus.Menu):
    def __init__(self, embeds: List[discord.Embed], timeout=None, footer=None, title=None, loop=False):
        super().__init__(timeout=timeout, clear_reactions_after=True)
        self.page = 0
        self.max = len(embeds) - 1
        self.loop = loop
        self.embeds = embeds
        for x in list(embeds):
            if footer: embeds[embeds.index(x)].set_footer(text=footer)
            if title: embeds[embeds.index(x)].title = title
    
    def isloop(self):
        return self.loop

    async def send_initial_message(self, ctx, channel):
        return await channel.send(embed=self.embeds[0])
    async def edit(self):
        await self.message.edit(embed=self.embeds[self.page])

    @menus.button('\u23ea', skip_if=isloop)
    async def tofirst(self, payload):
        if not payload.member: return
        self.page = 0
        await self.edit()
        await self.message.remove_reaction("\u23ea", payload.member)
    
    @menus.button('\u25C0')
    async def left(self, payload):
        if not payload.member: return
        self.page -= 1
        if self.page < 0:
            if self.loop: self.page = self.max
            else: self.page = 0
        await self.edit()
        await self.message.remove_reaction("\u25C0", payload.member)

    @menus.button('\u23F9')
    async def stopbutton(self, _payload):
        self.stop()

    @menus.button('\u25B6')
    async def right(self, payload):
        if not payload.member: return
        self.page += 1
        if self.page > self.max:
            if self.loop: self.page = 0
            else: self.page = self.max
        await self.edit()
        await self.message.remove_reaction("\u25B6", payload.member)
    
    @menus.button('\u23e9', skip_if=isloop)
    async def tolast(self, payload):
        if not payload.member: return
        self.page = self.max
        await self.edit()
        await self.message.remove_reaction('\u23e9', payload.member)
