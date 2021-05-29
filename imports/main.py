import discord
from discord.ext import commands
from discord.http import Route
from discord.utils import MISSING

import imports.mpk as mpku

import asyncio, aiohttp
from datetime import datetime
import sys, traceback, os

from typing import List, TYPE_CHECKING

async def typingoverride(self: discord.abc.Messageable, ephemeral=False):
    return await self.ogtyping()

async def sendoverride(self: discord.abc.Messageable, content=None, *, embed: discord.Embed = None, returndata=False, ephemeral=False, **kwargs):
    #TODO: more than just desc
    if not embed:
        if not returndata:
            return await self.ogsend(content, **kwargs)
        else:
            kwargs.update({'content': content, 'embeds': []})
            return kwargs
    embeds = [embed]
    while len(embed.description) > 2048:
        copy = discord.Embed(color=embed.color, timestamp=embed.timestamp)
        copy.set_image(url=embed.image.url)
        copy.set_footer(text=embed.footer.text, icon_url=embed.footer.icon_url)
        for field in embed.fields:
            copy.add_field(name=field.name, value=field.value,
                           inline=field.inline)
        embed.set_footer()
        embed.set_image(url=embed.Empty)
        embed.clear_fields()
        embed.timestamp = embed.Empty
        desc: str = embed.description
        count = 0
        for x in desc.splitlines():
            if count + len(x) > 2048:
                break
            count += len(x)
        copy.description = embed.description[count:]
        embed.description = embed.description[:count]
        embeds.append(copy)
        embed = embeds[-1]
    if returndata:
        kwargs.update({'content': content, 'embeds': embeds})
        return kwargs
    files = kwargs.pop('file', None) or kwargs.pop('files', None)
    r = await self.ogsend(content, embed=embeds[0], **kwargs)
    if len(embeds) == 1:
        return r
    for e in embeds[1:-1]:
        await self.ogsend(embed=e)
    if files:
        if isinstance(files, (list, tuple, set)):
            return await self.ogsend(embed=embeds[-1], files=files)
        return await self.ogsend(embed=embeds[-1], file=files)
    return await self.ogsend(embed=embeds[-1])

from discord.abc import Messageable
Messageable.ogsend = Messageable.send
Messageable.send = sendoverride

Messageable.ogtyping = Messageable.trigger_typing
Messageable.trigger_typing = typingoverride

class InteractionsContext(commands.Context):
    def __init__(self, interaction: discord.Interaction = None, **attrs):
        #assert channel
        try:
            super().__init__(**attrs)
        except AttributeError:
            pass  # i THINK all gets caught
        #self.channel: discord.TextChannel = channel
        self._state = self.channel._state  # steal the state so i can send shit
        self.inter = interaction
        self._sent = False
        self._ephemeral = False
        self._thinking = False

    async def reply(self, content=None, **kwargs):  # no replies
        return await self.send(content, **kwargs)

    async def send(self, content=None, ephemeral=None, **kwargs):
        webhook = discord.webhook.async_.async_context.get()
        if self._sent:
            if ephemeral is None:
                ephemeral = self._ephemeral
            else:
                self._ephemeral = ephemeral
            #if not self._ephemeral:
            if True:
                return await super().send(content, **kwargs)
            #TODO: epemeral handling?
            d = kwargs
            if content:
                d.update({'content': content})
            
        ephemeral = ephemeral or False
        self._sent = True
        if not self._ephemeral:
            self._ephemeral = ephemeral

        async with aiohttp.ClientSession() as session:
            #if self._thinking:
                #await self.inter.response.edit_message(content=content, embed=kwargs.pop('embed', None), view=kwargs.pop('view', None))
            #else:
            await self.inter.response.send_message(content, embed=kwargs.pop('embed', MISSING), ephemeral=self._ephemeral)
        
        d = await webhook.get_original_interaction_response(self.inter.application_id, self.inter.token, session=self.inter._session)
        return discord.Message(state=self._state, channel=self.channel, data=d)
        

    async def trigger_typing(self, ephemeral=False):
        return
        if self._thinking:
            if ephemeral:
                await super().trigger_typing()
            return
        self._thinking = True
        self._ephemeral = ephemeral
        await self.inter.response.defer(ephemeral=ephemeral)


class Main(commands.Bot):
    errlist = []
    autostart = False

    def __init__(self, data, userdata, *args, webonly=False, **kwargs):
        super().__init__(*args, command_prefix=lambda x, y: (), **kwargs)
        self.data: dict = data
        self.usermpm: mpku.DefaultContainer = userdata
        self.webonly = webonly
        if webonly:
            for x in self.commands:
                self.remove_command(x.name)
        else:
            self.loops: List[discord.ext.tasks.Loop] = []
            self.remove_command("help")
            self.looptask = self.loop.create_task(self.loopcheckup())

        self.owner: discord.User = None
        self.secret = os.getenv("SSECRET" if self.data['stable'] else "DSECRET")

    async def get_prefix(self, message):
        if self.webonly: return ()
        prf = self.data['prefix'].copy()
        if message.guild:
            con = mpku.getmpm("misc", message.guild)
            if con['prefix']:
                prf = [con['prefix']]

        users = self.usermpm
        if users[str(message.author.id)]['prefix']:
            prf.insert(0, users[str(message.author.id)]['prefix'])
        return prf

    async def loopcheckup(self):
        while True:
            try:
                # every 5 minutes preform a loop checkup
                await asyncio.sleep(300)
                for loop in self.loops:
                    if not loop.next_iteration:
                        if '.' in loop.coro.__qualname__:
                            loop.start(self.get_cog(
                                loop.coro.__qualname__.split('.')[0]))
                        else:
                            loop.start()
                        await self.owner.send(f"restarted loop `{loop.coro.__name__}`")
            except asyncio.CancelledError:
                break
            except:
                pass

    def dispatch(self, event_name, *args, **kwargs):
        if self.webonly: return
        return super().dispatch(event_name, *args, **kwargs)

    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, 'on_error'):
            return

        error = getattr(error, 'original', error)
        if isinstance(error, (commands.CommandOnCooldown, commands.NotOwner)):
            return
        #if isinstance(error, commands.DisabledCommand):
        #    return await ctx.send(f'{ctx.command} has been disabled.')
        if isinstance(error, commands.NoPrivateMessage):
            try: await ctx.send('This command cannot be used in Private Messages.')
            except: pass
            return
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send("You don't have sufficient permissions to run this.")
        if isinstance(error, commands.BotMissingPermissions):
            return await ctx.send("I don't have sufficient permissions to run this.")
        if isinstance(error, asyncio.TimeoutError):
            return await ctx.send("Prompt above timed out. Please redo the command.")
        #NOW we start being linient
        self.errlist.append([ctx.message.id, 0])
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.UserInputError):
            return await ctx.invoke(self.get_command("help"), ctx.command.root_parent.name if ctx.command.root_parent else ctx.command.name)

        if self.owner == ctx.author:
            return traceback.print_exception(type(error), error, error.__traceback__, file=(sys.stdout if (not self.data['stable']) else sys.stderr))
        try: await ctx.send(f"Something went wrong! I've DM'd the error to {self.owner.mention} (my owner.)")
        except: pass
        embed = discord.Embed(title=f"Error in {ctx.command}")
        st = '\n'.join(traceback.format_exception(
            type(error), error, error.__traceback__))
        embed.description = f"```py\n{st}\n```"
        embed.description += f"User ID: `{ctx.author.id}` {ctx.author.mention}\nChannel ID: `{ctx.channel.id}` {ctx.channel.mention if isinstance(ctx.channel, discord.abc.GuildChannel) else '(DM)'}"
        try: return await self.owner.send(embed=embed)
        except: pass

    @property
    def stable(self):
        return self.data['stable']
