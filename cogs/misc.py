import discord, dateparser, aiohttp, re
from discord.ext import commands, tasks
import cogs.utils.mpk as mpku
from typing import Optional, Union
from datetime import datetime, timedelta
from asyncio import sleep
from numpy import clip

def limitdatetime(dt):
    return datetime.combine(dt.date(), datetime.min.time())

class Miscellaneous(commands.Cog):
    def __init__(self, bot: commands.Bot):
        # pylint: disable=no-member
        self.bot = bot
        self.firstrun = True
        self.garfloop.start()

    def cog_unload(self):
        # pylint: disable=no-member
        self.garfloop.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        # pylint: disable=no-member
        if (self.garfloop.get_task()): self.garfloop.cancel()
        self.garfloop.start()

    @commands.command(aliases = ['usrprefix', 'userprefix'])
    async def prefix(self, ctx, prefix: Optional[str] = None):
        """Sets the prefix for either the server or yourself.
        If you set server prefix, you **must have manage guild.**

        `prefix <prefix>`
        `userprefix/usrprefix <prefix>`"""
        mpm = mpku.MPKManager("misc", ctx.guild.id)
        mpk = mpm.data
        user = False
        users = mpku.MPKManager("users", None)
        mid = str(ctx.author.id)
        try:
            users.data[mid]['prefix']
            user = True
        except: pass

        if not prefix:
            if not user:
                return await ctx.send(f"My main prefix here is `{self.bot.command_prefix(self.bot, ctx.message)[0]}`.")
            prefixes = self.bot.command_prefix(self.bot, ctx.message)
            return await ctx.send(f"Your personal prefix is `{prefixes[0]}` and my main prefix here is `{prefixes[1]}`.")
        user = ctx.invoked_with in ['usrprefix', 'userprefix']
        rem = prefix in ["reset", "off"]
        if user:
            try: users.data[mid]
            except: users.data[mid] = {}
            if not rem: users.data[mid]['prefix'] = prefix
            else:
                try: del users.data[mid]['prefix']
                except: pass
            users.save()
            if not rem:
                return await ctx.send(f"Your personal prefix is now `{prefix}`!")
            return await ctx.send("Your personal prefix has been reset.")
        if not ctx.author.guild_permissions.manage_guild: return
        if not rem: mpk['prefix'] = prefix
        else:
            try: del mpk['prefix']
            except: pass
        mpm.save()
        if not rem: await ctx.send(f"My prefix here is now `{prefix}`!")
        else: await ctx.send("My prefix here has been reset.")

    @commands.command()
    async def ping(self, ctx):
        """Checks latency."""
        resp = await ctx.send('Pong! Loading...')
        diff = resp.created_at - ctx.message.created_at
        await resp.edit(content=f'Pong! That took {1000*diff.total_seconds():.1f}ms.')

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def say(self, _unusedctx, chn: discord.TextChannel, *, funny):
        """Says something in a channel.
        **Must have administrator permission.**

        `say <text>`"""
        await chn.send(funny)

    @commands.command(aliases = ['about', 'invite'])
    async def info(self, ctx):
        """Shows information about me."""
        #("Members", len(list(self.bot.get_all_members)))
        e = discord.Embed(title="Info", colour=discord.Colour(self.bot.data['color']))
        e.description = f"""**Version:** {self.bot.data['version']}
        **Owned by:** {self.bot.owner.mention}
        **Stats:** {len(self.bot.guilds)} servers, unsharded
        [__**Invite link**__]({discord.utils.oauth_url(str(self.bot.user.id), permissions=discord.Permissions(permissions=268446911))})"""
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
                    return await x.edit(color=discord.Color(brighten))
        except discord.Forbidden: return
    ##########################################GARFIELD############################################
    async def getcode(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                return resp.status
    
    async def calcstripfromdate(self, date: Union[datetime, int], sromg): 
        attempts = 0
        if not sromg: 
            while attempts <= 10:
                url = f"http://strips.garfield.com/iimages1200/{date.year}/ga{date.strftime('%y%m%d')}.gif"
                if (await self.getcode(url)) == 200: return (url, limitdatetime(date))
                url = f"https://d1ejxu6vysztl5.cloudfront.net/comics/garfield/{date.year}/{date.strftime('%Y-%m-%d')}.gif"
                if (await self.getcode(url)) == 200: return (url, limitdatetime(date))
                date -= timedelta(days=1)
                attempts += 1
        else:
            #this is the day it started being consistent (i hope)
            if type(date) != int:
                stripnum = (date - datetime(2010, 1, 25)).days + 251
            else: stripnum = date
            maxnum = (datetime.utcnow() - datetime(2010, 1, 25)).days + 251
            while attempts <= 10:
                url = f"https://www.mezzacotta.net/garfield/comics/{stripnum:04}.png"
                if (await self.getcode(url)) == 200: return (url, limitdatetime(datetime.utcnow()) - timedelta(days=(maxnum - stripnum)))
                stripnum -= 1
                attempts += 1
        return (-1, datetime.utcnow())

    def htmltomarkup(self, text):
        text = re.sub(r"<a *href=\"([^\"]*)\">([^<]*)</a>", r"[\2](\1)", text)
        text = re.sub(r"<i>([^<]*)</i>", "*\\1*", text)
        return re.sub(r"<b>([^<]*)</b>", "**\\1**", text).replace("<br>", "\n")
    async def formatembed(self, url, s, d, day=None):
        embed = discord.Embed(title=f"{'Daily ' if d else ''}{'SROMG' if s else 'Garfield'} Comic", colour=discord.Color(0xfe9701))
        if s: 
            num = url.split('/')[-1][:-4]
            embed.set_footer(text=f"Strip #{int(num)}")
            js = None
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"https://garfield-comics.glitch.me/~SRoMG/?comic={num}") as resp: #TODO: if and when zulu changes this, change how this works
                        js = (await resp.json())['data']
            except: pass
            if not js:
                embed.description = f"View the details of the strip [here.](https://www.mezzacotta.net/garfield/?comic={num})"
            else:
                embed.title = f"SROMG | {js['name']}"
                embed.url = f"http://www.mezzacotta.net/garfield/?comic={num}"
                embed.description = self.htmltomarkup(js['authorWrites'].split("Original strip")[0])
                tr = self.htmltomarkup(js['transcription'].replace("\n", "").replace("{", "*").replace("}", "*"))
                tl = []
                for x in tr.splitlines():
                    tl.append(re.sub(r"([^:]*):", r"**\1**:", x))
                embed.add_field(name="Transcription", value='\n'.join(tl))
                embed.set_author(name=js['author']['name'], url=f"https://www.mezzacotta.net/garfield/author.php?author={js['author']['number']}'")
                if (js['originalStrips']):
                    embed.description += f"\n\n*Original strip{'s' if len(js['originalStrips']) > 1 else ''}: "
                    for x in js['originalStrips']: 
                        formatted = re.sub(r'..([^-]*)-([^-]*)-(.*)', r'\2/\3/\1', x['strip'])
                        embed.description += f"[{formatted}]({x['href']}), "
                    embed.description = embed.description[:-2] + "*"
                embed.set_footer(text=f"Strip #{int(num)} | API by LiquidZulu")
        else:
            embed.set_footer(text=f"Strip from {day.month}/{day.day}/{day.year}")
        embed.set_image(url=url)
        return embed
        
    @commands.command(aliases=['gstrip', 'garf', 'sromg'])
    async def garfield(self, ctx: commands.Context, *, date: Optional[str]):
        """Shows a Garfield or SROMG strip. You can also subscribe to daily strips (including DMs).
        Subscribing to a **channel** (not DMs) requires you to have **manage channel** for that channel.

        `garfield/gstrip/g/sromg [date]`
        `g/sromg sub/subscribe`"""
        await ctx.trigger_typing()
        isSROMG = ctx.message.content.startswith(f"{ctx.prefix}sromg")
        num = 0
        if not date:
            date = limitdatetime((datetime.utcnow() + timedelta(days=1)))
        elif date.startswith("sub"):
            if ctx.guild:
                if not ctx.author.permissions_in(ctx.channel).manage_channels: raise commands.MissingPermissions(["manage_channel"])
                mpm = mpku.getmpm("misc", ctx.guild)
                mpk = mpm.data
            else:
                mpm = mpku.MPKManager('users', None)
                mpk = mpm.data[str(ctx.author.id)]
            try: mpk['garfield']
            except: mpk['garfield'] = {'g': 0, 's': 0}
            check = 's' if isSROMG else 'g'
            if (not mpk['garfield'][check]) or (ctx.guild and mpk['garfield'][check] != ctx.channel.id):
                mpk['garfield'][check] = ctx.channel.id if ctx.guild else 1
                mpm.save()
                return await ctx.send(f"{'This channel' if ctx.guild else 'You'} will now recieve {'SROMG' if isSROMG else 'Garfield'} strips daily!")
            mpk['garfield'][check] = 0
            mpm.save()
            return await ctx.send(f"{'This channel' if ctx.guild else 'You'} will no longer recieve {'SROMG' if isSROMG else 'Garfield'} strips.")
        else:
            if isSROMG: 
                try: num = int(date)
                except: pass
                else: 
                    if num <= 0:
                        return await ctx.send("Please send a valid SROMG strip #.")
            if not num:
                msg = await ctx.send("Parsing date...")
                date = dateparser.parse(date, settings={'STRICT_PARSING': True})
                await msg.delete()
                if not date: return await ctx.send("Could not parse the date given.")
                if date > datetime.utcnow() + timedelta(days=1): return await ctx.send("Please send a date that is not in the far future (1 day max).")
        if not num: 
            while (date > (datetime.utcnow() + timedelta(days=1))): date -= timedelta(days=1)
        else: date = num
        url, date = await self.calcstripfromdate(date, isSROMG)
        if (url == -1):
            return await ctx.send("Could not find that strip.")
        await ctx.send(embed=await self.formatembed(url, isSROMG, False, date))

    @tasks.loop(minutes=5, reconnect=True)
    async def garfloop(self):
        print("gstart")
        gurl, gdate = await self.calcstripfromdate(datetime.utcnow() + timedelta(days=1), False)
        surl, sdate = await self.calcstripfromdate(datetime.utcnow() + timedelta(days=1), True)
        if self.firstrun:
            self.firstrun = False
            self.lastdate = gdate
            self.lastsromg = sdate
            return
        shown = 0b00
        if (gurl != -1) and gdate > self.lastdate:
            shown |= 0b01
            self.lastdate = gdate
        if (surl != -1) and sdate > self.lastsromg:
            shown |= 0b10
            self.lastsromg = sdate
        print(shown)
        #if not shown: return
        #first we check guilds cause thats easy
        for guild in self.bot.guilds:
            guild: discord.Guild
            try: mpk = mpku.getmpm('misc', guild).data['garfield']
            except: continue
            if (shown & 0b01) and mpk['g']:
                chn = guild.get_channel(mpk['g'])
                if chn:
                    await chn.send(embed=await self.formatembed(gurl, False, True, gdate))
            if (shown & 0b10) and mpk['s']:
                chn = guild.get_channel(mpk['s'])
                if chn:
                    await chn.send(embed=await self.formatembed(surl, True, True, sdate))
        mpkr = mpku.MPKManager("users", None).data
        for uid in mpkr:
            try: mpk = mpkr[uid]['garfield']
            except: continue
            user: discord.User = self.bot.get_user(uid)
            if not user: user = await self.bot.fetch_user(uid)
            if not user: continue
            if (shown & 0b01) and mpk['g']:
                try: await user.send(embed=await self.formatembed(gurl, False, True, gdate))
                except: continue
            if (shown & 0b10) and mpk['s']:
                try: await user.send(embed=await self.formatembed(surl, True, True, sdate))
                except: continue


def setup(bot):
    bot.add_cog(Miscellaneous(bot))