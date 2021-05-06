import discord
from discord.ext import commands

import imports.mpk as mpku

import asyncio, aiohttp
from datetime import datetime
import sys, traceback, os

from typing import List, TYPE_CHECKING


async def sendoverride(self: discord.abc.Messageable, content=None, *, embed: discord.Embed = None, returndata=False, **kwargs):
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


class InteractionsContext(commands.Context):
    def __init__(self, idata: dict = None, **attrs):
        #assert channel
        try:
            super().__init__(**attrs)
        except AttributeError:
            pass  # i THINK all gets caught
        #self.channel: discord.TextChannel = channel
        self._state = self.channel._state  # steal the state so i can send shit
        self.idata = idata
        self.sent = False
        self.thinking = False

    async def reply(self, content=None, **kwargs):  # no replies
        return await self.send(content, **kwargs)

    async def send(self, content=None, **kwargs):
        if self.sent:
            return await super().send(content, **kwargs)
        self.sent = True
        d: dict = await sendoverride(self, content, embed=kwargs.pop('embed', None), returndata=True, **kwargs)
        for x in d.copy():
            if x not in {'content', 'embeds', 'allowed_mentions'}:
                del d[x]

        for i in range(len(d['embeds'])):
            d['embeds'][i] = d['embeds'][i].to_dict()

        async with aiohttp.ClientSession() as session:
            if self.thinking:
                url = f"https://discord.com/api/v8/webhooks/{self.me.id}/{self.idata['token']}/messages/@original"
                r = await session.patch(url, json=d)
            else:
                url = f"https://discord.com/api/v8/interactions/{self.idata['id']}/{self.idata['token']}/callback"
                r = await session.post(url, json={'type': 4, 'data': d})
        if r.status in {200, 201}:
            return discord.Message(state=self._state, channel=self.channel, data=await r.json())
        raise discord.errors.HTTPException(r, await r.json())

    async def trigger_typing(self):
        if self.thinking:
            await super().trigger_typing()
            return
        self.thinking = True
        url = f"https://discord.com/api/v8/interactions/{self.idata['id']}/{self.idata['token']}/callback"
        async with aiohttp.ClientSession() as session:
            await session.post(url, json={'type': 5})


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
            self._connection.parsers["INTERACTION_CREATE"] = self.recieve_interaction
            self.looptask = self.loop.create_task(self.loopcheckup())


        self.owner: discord.User = None
        self.secret = os.getenv("SSECRET" if self.data['stable'] else "DSECRET")

        #assign a custom parser

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

    def recieve_interaction(self, data):
        asyncio.ensure_future(self.handle_interaction(data), loop=self.loop)

    async def handle_interaction(self, data):
        channel: discord.TextChannel = await self.fetch_channel(data['channel_id']) or await (await self.fetch_user(data['user']['id'])).create_dm()

        cmddata = data['data']
        out = [cmddata['name']]
        if cmddata['name'] in {"warncfg", "profilecfg"}:
            out[0] = cmddata['name'].split("cfg")[0]
            out.append('cfg' if out[0] == "warn" else 'edit')

        wasstring = False

        def appender(option):
            nonlocal wasstring
            if option['type'] == 3:
                out.append(f"\"{option['value']}\"")
                wasstring = True
            else:
                out.append(str(option['value']))
                wasstring = False

        for x in cmddata.get('options', []):
            if x['type'] in {1, 2}:
                out.append(x['name'])
                for y in x.get('options', []):
                    if y['type'] == 1:
                        out.append(y['name'])
                        for z in y.get('options', []):
                            appender(z)
                    else:
                        appender(y)
            else:
                appender(x)

        if wasstring:
            out[-1] = out[-1][1:-1]

        fakemsg = discord.Message(state=self._connection, channel=channel, data={
            'content': '', 'id': discord.utils.time_snowflake(datetime.now()), 
            'attachments': [], 'embeds': [], 'pinned': False, 'mention_everyone': False, 
            'tts': False, 'type': 0, 'edited_timestamp': None})
        try: fakemsg._handle_author(data['user'])
        except KeyError: fakemsg._handle_author(data['member']['user'])

        out = (await self.get_prefix(fakemsg))[0] + ' '.join(out)
        print(out)
        fakemsg._handle_content(out)

        ctx = await self.get_context(fakemsg, cls=InteractionsContext)
        ctx.idata = data
        await ctx.trigger_typing()
        await self.invoke(ctx)

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
