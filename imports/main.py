from __future__ import annotations

import discord
from discord import ui
from discord.enums import MessageType
from discord.ext import commands
from discord.http import Route
from discord import utils
from discord.message import Message
from discord.types.message import MessageActivity
from discord.utils import MISSING, utcnow
from discord.webhook.async_ import AsyncWebhookAdapter, WebhookMessage
from discord.state import ConnectionState
from discord import Interaction
from discord.interactions import InteractionResponse

import imports.mpk as mpku
import imports.globals as g

import asyncio, aiohttp
from datetime import datetime
import sys, traceback, os

import logging
LOG = logging.getLogger('bot')

from typing import List, TYPE_CHECKING, Optional, Union, Dict, Any

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

class ModdedInteraction(Interaction):
    @property
    def channel(self) -> Optional[Messageable]:
        try: return super().channel or self.user.dm_channel
        except: return None

    @utils.cached_slot_property('_cs_response')
    def response(self) -> ModdedResponse:
        return ModdedResponse(self)

class ModdedResponse(InteractionResponse):
    async def edit_message(
        self,
        *,
        content: Optional[Any] = MISSING,
        embed: Optional[discord.Embed] = MISSING,
        embeds: List[discord.Embed] = MISSING,
        attachments: List[discord.Attachment] = MISSING,
        view: Optional[ui.View] = MISSING,
    ) -> None:
        """slightly modded cause thanks rapptz
        """
        if self._responded:
            return

        parent = self._parent
        msg = parent.message
        state = parent._state
        message_id = msg.id if msg else None
        if parent.type is not discord.InteractionType.component:
            return

        # TODO: embeds: List[Embed]?
        payload = {}
        if content is not MISSING:
            if content is None:
                payload['content'] = None
            else:
                payload['content'] = str(content)

        if embed is not MISSING and embeds is not MISSING:
            raise TypeError(
                'cannot mix both embed and embeds keyword arguments')

        if embed is not MISSING:
            if embed is None:
                embeds = []
            else:
                embeds = [embed]

        if embeds is not MISSING:
            payload['embeds'] = [e.to_dict() for e in embeds]

        if attachments is not MISSING:
            payload['attachments'] = [a.to_dict() for a in attachments]

        if view is not MISSING:
            state.prevent_view_updates_for(message_id)
            if view is None:
                payload['components'] = []
            else:
                payload['components'] = view.to_components()

        adapter = discord.webhook.async_.async_context.get()
        await adapter.create_interaction_response(
            parent.id,
            parent.token,
            session=parent._session,
            type=discord.InteractionResponseType.message_update.value,
            data=payload,
        )

        if view not in (MISSING, None) and not view.is_finished():
            state.store_view(view, message_id)

        self._responded = True

#dude i'm actually fucking cracked LOL
class ModdedState(ConnectionState):
    def __init__(self, *, dispatch, handlers, hooks, http, loop, **options):
        super().__init__(dispatch=dispatch, handlers=handlers, hooks=hooks, http=http, loop=loop, **options)
    
    def parse_interaction_create(self, data):
        #copied from super, just changed to use modded interaction
        interaction = ModdedInteraction(data=data, state=self)
        if data['type'] == 3:  # interaction component
            custom_id = interaction.data['custom_id']  # type: ignore
            component_type = interaction.data['component_type']  # type: ignore
            self._view_store.dispatch(component_type, custom_id, interaction)

        self.dispatch('interaction', interaction)

class EphemeralMessage(discord.Message):
    def __init__(self, state: ModdedState, channel: discord.abc.Messageable, data: dict):
        self.channel = channel
        self._state = state
        self.id = utils.time_snowflake(data.get('created_at', utcnow()))
        self._edited_timestamp = None
        self.content = data.get('content', None)
        self.embeds = data.get('embeds', [])
        self.author = g.BOT.user
        self.components = [discord.components._component_factory(d) for d in data.get('components', [])]
        self.type = MessageType.default #i guess?
        #self.flags = 64 #ephemeral
        self.interaction: ModdedInteraction = data.get('interaction') #must be there
        self.pinned = False
        self.reactions = []
        self.tss = data.get('tts', False)

    #NULLED
    async def delete(self, *, delay: Optional[float]) -> None:
        pass #maybe we'll get the ability to later
    async def add_reaction(self, emoji) -> None:
        pass
    async def remove_reaction(self, emoji, member) -> None:
        pass
    async def clear_reaction(self, emoji) -> None:
        pass
    async def clear_reactions(self) -> None:
        pass
    async def pin(self, *, reason) -> None:
        pass
    async def unpin(self, *, reason) -> None:
        pass
    async def edit(self, **options):
        #thanks discord devs
        LOG.error("ATTEMPT TO EDIT EPHEMERAL MESSAGE")        

    
    async def reply(self, content, **kwargs) -> WebhookMessage:
        ephemeral = kwargs.pop('ephemeral', True)
        return await self.interaction.followup.send(content, ephemeral=ephemeral, **kwargs)



        

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

    async def reply(self, content=None, **kwargs):
        if not self._sent or self._ephemeral:
            return await self.send(content, **kwargs)
        return await super().reply(content, **kwargs)

    async def send(self, content=None, ephemeral=None, **kwargs) -> Union[Message, WebhookMessage]:
        webhook = discord.webhook.async_.async_context.get()
        if self._sent:
            if ephemeral is None:
                ephemeral = self._ephemeral
            self._ephemeral = ephemeral
            if not self._ephemeral:
                return await super().send(content, **kwargs)
            return await self.inter.followup.send(content, ephemeral=True, **kwargs)
            
            
        ephemeral = ephemeral or False
        self._sent = True
        if not self._ephemeral:
            self._ephemeral = ephemeral
        
        embeds = MISSING
        if kwargs.get('embed', None):
            embeds = (await sendoverride(self, content=content, embed=kwargs.pop('embed'), returndata=True))['embeds'] or MISSING

        async with aiohttp.ClientSession() as session:
            #if self._thinking:
                #await self.inter.response.edit_message(content=content, embed=kwargs.get('embed', None), view=kwargs.get('view', None))
            #else:
            await self.inter.response.send_message(content, embeds=embeds, ephemeral=self._ephemeral, view=kwargs.get('view', MISSING))
        
        if not self._ephemeral:
            d = await webhook.get_original_interaction_response(self.inter.application_id, self.inter.token, session=self.inter._session)
            return discord.Message(state=self._state, channel=self.channel, data=d)

        d = {
            'content': content or None,
            'embeds': embeds or [],
            'tts': kwargs.get('tts', False),
            'components': kwargs.get('view').to_components() if kwargs.get('view', None) else [],
            'interaction': self.inter
        }
        return EphemeralMessage(self._state, self.channel, d)
        
        

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
    
    def _get_state(self, **options):
        return ModdedState(dispatch=self.dispatch, handlers=self._handlers,
                               hooks=self._hooks, http=self.http, loop=self.loop, **options)

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
