import discord
from discord.ext import menus

from typing import List, Union

class Confirm(menus.Menu):
    def __init__(self, msg, timeout=None, **kwargs):
        super().__init__(timeout=timeout, **kwargs)
        self.msg = msg
        self.result = None

    async def send_initial_message(self, ctx, channel):
        if (isinstance(self.msg, str)):
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
    def __init__(self, msg: discord.Message, emoji: List[str], **kwargs):
        super().__init__(**kwargs)
        self.msg = msg
        self.emoji = emoji
        self.choice = None
        for x in emoji:
            self.add_button(menus.Button(x, self.onpick))

    async def send_initial_message(self, ctx, channel):
        if (isinstance(self.msg, discord.Message)):
            self.msg = await self.msg.channel.fetch_message(self.msg.id)
            try: 
                for x in self.msg.reactions: await x.clear()
            except discord.Forbidden: 
                await (await self.msg.channel.send("(I can't remove reactions. Please make sure I can manage messages!)")).delete(delay=5) 
            return self.msg
        if (isinstance(self.msg, str)):
            return await channel.send(self.msg)
        return await channel.send(embed=self.msg)        

    async def onpick(self, payload: discord.RawReactionActionEvent):
        try: 
            if payload.emoji.is_custom_emoji():
                self.choice = [x.id for x in self.emoji].index(payload.emoji.id)
            else:
                self.choice = self.emoji.index(payload.emoji.name)
        except: pass
        else: self.stop()

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
