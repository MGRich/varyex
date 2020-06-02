import discord, json, traceback
from discord.ext import commands, tasks
from cogs.utils.SimplePaginator import SimplePaginator as pag
from cogs.utils.mpkmanager import MPKManager
from typing import Optional
from datetime import datetime, timedelta
from asyncio import sleep
import dateparser, timeago, requests, os
from numpy import clip

class Miscellaneous(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(aliases = ['usrprefix', 'userprefix'])
    async def prefix(self, ctx, prefix: Optional[str] = None):
        """Sets the prefix for either the server or yourself.
        If you set server prefix, you **must have manage guild.**

        `prefix <prefix>`
        `userprefix/usrprefix <prefix>`"""
        mpm = MPKManager("misc", ctx.guild.id)
        mpk = mpm.data
        user = False
        users = MPKManager("users")
        mid = str(ctx.author.id)
        try:
            users.data[mid]['prefix']
            user = True
        except: pass

        if not prefix:
            if not user:
                return await ctx.send(f"My main prefix here is `{self.bot.command_prefix(self.bot, ctx.message)[0]}`.")
            else:
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
            else:
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
    async def say(self, ctx, chn: discord.TextChannel, *, funny):
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
        **Invite link:** (not yet)"""
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

    def calcstripfromdate(self, date: datetime, sromg): 
        if not sromg: 
            while True:
                url = f"https://d1ejxu6vysztl5.cloudfront.net/comics/garfield/{date.year}/{date.strftime('%Y-%m-%d')}.gif"
                if requests.head(url).status_code == 200: return url
                date -= timedelta(days=1)
        else:
            days = (date - datetime(2010, 1, 25)).days
            #this is the day it started being consistent (i hope)
            stripnum = days + 250
            while True:
                url = f"https://www.mezzacotta.net/garfield/comics/{stripnum}.png"
                if requests.head(url).status_code == 200: return url
                stripnum -= 1

    @commands.command(aliases=['gstrip', 'g', 'sromg'], hidden=True)
    async def garfield(self, ctx: commands.Context, *, date: Optional[str]):
        if not date:
            date = datetime.utcnow() + timedelta(days=1)
            date = datetime.combine(date.date(), datetime.min.time()) #get rid of the time
        else:
            msg = await ctx.send("Parsing date...")
            date = dateparser.parse(date, settings={'STRICT_PARSING': True})
            await msg.delete()
            if not date: return await ctx.send("Could not parse the date given.")
            if date > datetime.utcnow() + timedelta(days=1): return await ctx.send("Please send a date that is not in the far future (1 day max).")
        isSROMG = ctx.message.content.startswith(f"{ctx.prefix}sromg")
        url = self.calcstripfromdate(date, isSROMG)
        if (date > datetime.utcnow()): date -= timedelta(days=1)
        embed = discord.Embed(title=f"{'Garfield' if not isSROMG else 'SROMG'} Comic", colour=discord.Color(0xfe9701))
        embed.set_footer(text=f"Strip from {timeago.format(date, datetime.utcnow())} | {date.month}/{date.day}/{date.year}")
        embed.set_image(url=url)
        await ctx.send(embed=embed)

    @tasks.loop(minutes=3) #hacky but do not care
    async def garfloop(self):
        gids = []
        for x in os.listdir("config"):
            if os.path.isfile(f"config/{x}/misc.json"):
                gids.append(x)
        for gid in gids:
            guild = self.bot.get_guild(int(gid))
            if (guild == None): continue
            #we dont need a json manager we're literally only gonna read
            dat = json.load(open(f"config/{gid}/misc.json"))
            try: dat['garfield']
            except: continue
            try: 
                dat['garfield']['channel']
                setting = dat['garfield']['setting']
            except: continue
            if not setting & 0b100:
                try: dat['garfield']['time']
                except: continue       
            chn = guild.get_channel(dat['garfield']['channel'])
            date = datetime.utcnow() + timedelta(days=1)
            date = datetime.combine(date.date(), datetime.min.time()) #get rid of the time
            gembed = sembed = None
            gembed 
            chn 
            sembed
            if setting & 0b001:
                date -= timedelta(days=1)
                url = f"https://d1ejxu6vysztl5.cloudfront.net/comics/garfield/{date.year}/{date.strftime('%Y-%m-%d')}.gif"
                if requests.head(url).status_code == 200: continue
                url = self.calcstripfromdate(date, False)
                embed = discord.Embed(title="Garfield Comic", colour=discord.Color(0xfe9701))
                embed.set_footer(text=f"Strip from {timeago.format(date, datetime.utcnow())} | {date.month}/{date.day}/{date.year}")
                embed.set_image(url=url)

 

def setup(bot):
    bot.add_cog(Miscellaneous(bot))