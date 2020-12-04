import discord
from discord.ext import commands

import cogs.utils.mpk as mpku
from cogs.utils.converters import UserLookup
from typing import Optional
from asyncio import sleep 
from numpy import clip

from datetime import timedelta

import aiohttp, imghdr, io, os, asyncio 
from asyncio.locks import Semaphore
from PIL import Image

import psutil, humanize, platform

import logging
LOG = logging.getLogger('bot')

class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(aliases = ('usrprefix', 'userprefix'))
    async def prefix(self, ctx, prefix: Optional[str] = None):
        """Sets the prefix for either the server or yourself.
        If you set server prefix, you **must have manage guild.**

        `prefix <prefix>`
        `userprefix/usrprefix <prefix>`"""
        try: mpk = mpku.getmpm("misc", ctx.guild.id)
        except AttributeError: mpk = None
        user = False
        users = self.bot.usermpm
        mid = str(ctx.author.id)
        try:
            users[mid]['prefix']
            user = True
        except: pass

        if not prefix:
            if not user:
                return await ctx.send(f"My main prefix here is `{self.bot.command_prefix(self.bot, ctx.message)[0]}`.")
            prefixes = self.bot.command_prefix(self.bot, ctx.message)
            return await ctx.send(f"Your personal prefix is `{prefixes[0]}` and my main prefix here is `{prefixes[1]}`.")
        user = (ctx.invoked_with in {'usrprefix', 'userprefix'}) or (not mpk)
        rem = prefix in {"reset", "off"}
        if user:
            if not rem: users[mid]['prefix'] = prefix
            else:
                try: del users[mid]['prefix']
                except: pass
            users.save()
            if not rem:
                return await ctx.send(f"Your personal prefix is now `{prefix}`!")
            return await ctx.send("Your personal prefix has been reset.")
        if not ctx.author.guild_permissions.manage_guild: return
        if not rem: mpk['prefix'] = prefix
        else:
            del mpk['prefix']
        if mpk: mpk.save()
        if not rem: await ctx.send(f"My prefix here is now `{prefix}`!")
        else: await ctx.send("My prefix here has been reset.")

    @commands.command(aliases=('pfp',))
    async def avatar(self, ctx, user: Optional[UserLookup]):
        """Fetches your own or a user's avatar.

        `avatar/pfp [user]`"""
        if ctx.guild and user:
            user = ctx.guild.get_member(user.id) or user
        elif not user: user = ctx.author
        
        e = discord.Embed(color=(discord.Color(self.bot.data['color']) if user.color == discord.Color.default() else user.color))
        e.set_author(name=f"{user.display_name}'s avatar", icon_url=str(user.avatar_url_as(format='jpg', size=64)))
        e.set_image(url=str(user.avatar_url_as(static_format='png', size=2048)))
        return await ctx.send(embed=e)

    @commands.command()
    async def ping(self, ctx):
        """Checks latency."""
        resp = await ctx.send('Pong! Loading...')
        diff = resp.created_at - ctx.message.created_at
        await resp.edit(content=f'Pong! That took {1000*diff.total_seconds():.1f}ms.')

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def say(self, _ctx, chn: discord.TextChannel, *, funny):
        """Says something in a channel.
        **Must have administrator permission.**

        `say <chn> <text>`"""
        await chn.send(funny)

    @commands.command(aliases = ('about', 'invite'))
    async def info(self, ctx):
        """Shows information about me."""
        #("Members", len(list(self.bot.get_all_members)))
        e = discord.Embed(title="Info", colour=discord.Colour(self.bot.data['color']))
        e.description = f"""**Version:** {self.bot.data['version']}
        **Owned by:** {self.bot.owner.mention}
        __**[Invite link]({discord.utils.oauth_url(str(self.bot.user.id), permissions=discord.Permissions(permissions=268446911))})**__"""
        members = []
        humans = []
        unique = set()
        for x in self.bot.guilds:
            a = [y.id for y in x.members if not y.bot]
            humans += a
            members += a + [y.id for y in x.members if y.bot]
        unique.update(humans)
        members = len(members)
        humans = len(humans)
        unique = len(unique)
        e.add_field(inline=True, name="Stats", value=f"""**Servers:** {len(self.bot.guilds)}
        **Members:**
        > **Total:** {members}
        > **Humans:** {humans}
        > **Unique:** {unique}""")
        e.add_field(inline=True, name="Details", value=f"**CPU:** {psutil.cpu_percent()}%\n**Memory:** {humanize.naturalsize(psutil.Process(os.getpid()).memory_info().rss, binary=True)}\n**Platform:** {platform.system()}")
        e.set_footer(text=f"Made using discord.py version {discord.__version__}", icon_url="https://cdn.discordapp.com/icons/336642139381301249/3aa641b21acded468308a37eef43d7b3.webp")
        await ctx.send(embed=e)
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        try:
            await sleep(20)
            brighten = int(self.bot.data['color'])
            ls = [(brighten >> 16) & 0xFF, (brighten >> 8) & 0xFF, brighten & 0xFF]
            i = 0
            for x in list(ls):
                ls[i] = int(clip(x * 1.3, 0, 255))
                i += 1
            brighten = (ls[0] << 16) | (ls[1] << 8) | ls[2]
            joined = guild.get_member(self.bot.user.id).joined_at
            for x in guild.roles:
                if (joined - x.created_at < timedelta(seconds=1)) and x.managed:
                    return await x.edit(color=brighten)
        except discord.Forbidden: return

    @commands.command()
    async def imgfilter(self, ctx, filter, *links):
        """Applies a filter to images.
        You can send images as links or attachments.
        GIFs are not supported.

        `imgfilter <filter> [links]` where `filter` CONTAINS (ex. `genesis` works):
        > `gen` - Sega Genesis 3-bit filter
        > `565` - RGB565 filter, used for some consoles and other graphics"""
        if (len(ctx.message.attachments) == 0 and not links): return
        ftouse = ""
        if   ("gen" in filter.lower()): ftouse = "gen"
        elif ("565" in filter.lower()): ftouse = "565"
        if not ftouse: return await ctx.send("Invalid filter!")
        images = []
        invalid = []
        total = list(links) + [x.url for x in ctx.message.attachments]
        sem = Semaphore(1)
        tasks = []
        loop = asyncio.get_event_loop()
        async def dl(link):
            LOG.debug(link)
            async with aiohttp.request('GET', link) as resp:
                read = await resp.read()
                if imghdr.what("", h=read) == "gif": invalid.append(link)
                else: 
                    try:
                        im = Image.open(io.BytesIO(read))
                        images.append(im)
                    except: invalid.append(link)
            #except: invalid.append(link)
        for x in total:
            tasks.append(loop.create_task(dl(x)))
        await asyncio.wait(tasks)
        if not images: return await ctx.send("None of the images given are valid.")
        tasks = []
        done = 0
        msg = await ctx.send("Converting, please wait...")
        files = []
        async def imageconv(img):
            nonlocal done, images
            img.convert('RGB')
            map = img.load()
            if ftouse == "gen":
                gencolour = [00, 0x34, 0x57, 0x74, 0x90, 0xAC, 0xCE, 0xFF]
                clrchecks = [0x20, 0x40, 0x60, 0x80, 0xA0, 0xC0, 0xE0, 0xFE]
                for y in range(img.height):
                    for x in range(img.width):
                        tup = list(map[x, y])
                        for ii in range(3):
                            for i in range(8):
                                if (tup[ii] < clrchecks[i]):
                                    tup[ii] = gencolour[i]
                                    break
                        map[x, y] = tuple(tup)
            elif ftouse == "565":
                #first we need to turn into 565
                for y in range(img.height):
                    for x in range(img.width):
                        #LOG.debug(map[x, y])
                        if (len(map[x, y]) == 4):
                            R, G, B, A = map[x, y]
                        else:
                            R, G, B = map[x, y]
                            A = 255
                        val = ((B >> 3) | (G >> 2) << 5 | ((R >> 3) << 11)) & 0xFFFF
                        #now we seperate
                        oR = (val & 0xF800) >> 11
                        oG = (val & 0x7E0) >> 5
                        oB = (val & 0x1F)
                        #and turn back into 888
                        map[x, y] = (((oR * 527 + 23) >> 6), ((oG * 259 + 33) >> 6), ((oB * 527 + 23) >> 6), A)
            async with sem:
                img.save(f"{ctx.message.id}{done}.png")
                files.append(discord.File(f"{ctx.message.id}{done}.png"))
                done += 1
        for x in images:
            tasks.append(loop.create_task(imageconv(x)))
        await asyncio.wait(tasks)
        await msg.delete()
        await ctx.send(files=files)
        for x in range(done):
            os.remove(f"{ctx.message.id}{x}.png")
        await ctx.send(f"Finished {done} images with {len(invalid)} invalid images.")

def setup(bot):
    bot.add_cog(Misc(bot))
