import asyncio
import discord
from discord import ui, Interaction
from discord.abc import Messageable
from discord.emoji import Emoji
from discord.ext import menus, commands
from discord.ext.commands import Context
from discord.enums import ButtonStyle, try_enum

from typing import List, Optional, Any, Union
from functools import partial

from discord.partial_emoji import PartialEmoji
from imports.other import iiterate, emoji_to_partial
from imports.main import ModdedInteraction
from emoji import UNICODE_EMOJI


def extra_item_kwargs(**kwargs):
    def decorator(func):
        func.__discord_ui_model_kwargs__.update(kwargs)
        return func
    return decorator


def list_to_buttons(blist: List[Union[str, ui.Button, Emoji]], style=ButtonStyle.secondary):
    res = blist.copy()
    for x, i in iiterate(blist):
        if isinstance(x, ui.Item): continue
        if isinstance(x, Emoji):
            res[i] = ui.Button(style=style, emoji=emoji_to_partial(x))
        elif x:
            if x in UNICODE_EMOJI:
                res[i] = ui.Button(style=style, emoji=x)
            else:
                res[i] = ui.Button(style=style, label=x)
    return res

class ViewMenu(ui.View):
    #hybrid class of a View and a Menu. done so i can fuck around w the menus and not change how they work too much
    def __init__(self, timeout: Optional[float] = 180.0, remove_on_finish=True):
        #not even gonna super init yet
        self.message: discord.Message = None
        self.channel: discord.abc.Messageable = None
        self._author_id = None
        self._event = asyncio.Event()
        self.remove_on_finish = remove_on_finish
        #we super init once we fuck around and check 2 things: 
        #skip_if and disable_if in kwargs for our buttons
        for x, i in iiterate(self.__view_children_items__.copy()):
            x: ui.Button
            k = x.__discord_ui_model_kwargs__
            if 'skip_if' in k and getattr(self, k['skip_if'].__name__)():
                self.__view_children_items__.remove(x)
            if 'disable_if' in k and getattr(self, k['disable_if'].__name__)():
                x.disabled = True
                self.__view_children_items__[i] = x

        super().__init__(timeout=timeout)

    async def send_initial_message(self, ctx: Context, channel: Messageable, ephemeral=False):
        raise NotImplementedError()

    
    def dispatch_timeout(self):
        try:
            super().dispatch_timeout()
            self._event.set()
        except asyncio.InvalidStateError: pass #???

    async def interaction_check(self, interaction: ModdedInteraction) -> bool:
        #can be overriden but usually we won't want it to
        if interaction.message and interaction.message.id != self.message.id:
            return False
        return interaction.user.id == self._author_id

    async def start(self, ctx: Context, *, wait = True, ephemeral=False):
        self.channel = ctx.channel
        self._author_id = ctx.author.id
        if self.message is None:
            self.message = await self.send_initial_message(ctx, ctx.channel, ephemeral)
        self._event.clear()
        if wait: 
            await self._event.wait()
        
    async def stop(self, i: Interaction) -> None: 
        super().stop()
        if self.remove_on_finish:
            i.response._responded = False #force it on
            await i.response.edit_message(view=None)
        self._event.set()

    def get_item(self, query):
        return discord.utils.get(self.children, emoji=query) or discord.utils.get(self.children, label=query)
    
    def amount_in_row(self, row):
        r = 0
        for x in self.children:
            if x.row == row: r += 1
        return r

    def clear_row(self, row):
        for x in self.children.copy():
            if x.row == row: self.remove_item(x)

class Confirm():
    def __init__(self, msg, **kwargs):
        self.msg = msg
        self.kwargs = kwargs

    async def prompt(self, ctx, text=['Yes', 'No'], styles=[ButtonStyle.success, ButtonStyle.grey]):
        b = [ui.Button(style=styles[0], label=text[0]),
             ui.Button(style=styles[1], label=text[1])]

        return not await Choice(self.msg, b, **self.kwargs).prompt(ctx)

class Choice(ViewMenu):
    def __init__(self, msg: discord.Message, buttons: List[Union[str, ui.Button, Emoji]], style=ButtonStyle.secondary, **kwargs):
        super().__init__(**kwargs)
        self.msg = msg
        self.buttons = list_to_buttons(buttons, style)
        self.choice = None
        
        for x in self.buttons:
            if x is None: continue
            x.callback = partial(self.onpick, x)
            self.add_item(x)

    async def send_initial_message(self, ctx, channel, ephemeral=False):
        if (isinstance(self.msg, discord.Message)):
            self.msg: discord.Message = await self.msg.channel.fetch_message(self.msg.id) 
            await self.msg.edit(view=self)
            return self.msg
        if (isinstance(self.msg, str)):
            return await ctx.send(self.msg, view=self, ephemeral=ephemeral)
        return await ctx.send(embed=self.msg, view=self, ephemeral=ephemeral)        

    async def onpick(self, button: ui.Button, interaction: Interaction):
        try: 
            self.choice = [x.custom_id if x else "" for x in self.buttons].index(button.custom_id)
        except: pass
        else: await self.stop(interaction)

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.choice

class Paginator(ViewMenu):
    def __init__(self, embeds: List[discord.Embed], footer=None, title=None, loop=False, **kwargs):
        self.page = 0
        self.max = len(embeds) - 1
        self.loop = loop
        self.embeds = embeds
        super().__init__(**kwargs)
        for x in list(embeds):
            if footer: embeds[embeds.index(x)].set_footer(text=footer)
            if title: embeds[embeds.index(x)].title = title
    
    def isloop(self):
        return self.loop

    async def send_initial_message(self, ctx, channel, ephemeral=False):
        return await ctx.send(embed=self.embeds[0], view=self, ephemeral=ephemeral)
    async def edit(self, interaction: Interaction):
        await interaction.response.edit_message(embed=self.embeds[self.page])

    @extra_item_kwargs(skip_if=isloop)
    @ui.button(style=ButtonStyle.grey, emoji='\u23EA')
    async def tofirst(self, _b, i):
        self.page = 0
        await self.edit(i)

    @ui.button(style=ButtonStyle.grey, emoji='\u25C0')
    async def left(self, _b, i):
        self.page -= 1
        if self.page < 0:
            if self.loop: self.page = self.max
            else: self.page = 0
        await self.edit(i)

    @ui.button(style=ButtonStyle.grey, emoji='\u23F9')
    async def stopbutton(self, _b, i):
        await self.stop(i)

    @ui.button(style=ButtonStyle.grey, emoji='\u25B6')
    async def right(self, _b, i):
        self.page += 1
        if self.page > self.max:
            if self.loop: self.page = 0
            else: self.page = self.max
        await self.edit(i)
    
    @extra_item_kwargs(skip_if=isloop)
    @ui.button(style=ButtonStyle.grey, emoji='\u23E9')
    async def tolast(self, _b, i):
        self.page = self.max
        await self.edit(i)
