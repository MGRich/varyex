import discord
from discord.ext import commands, menus

import cogs.utils.mpk as mpku
from cogs.utils.converters import UserLookup, MemberLookup, DurationString
from cogs.utils.other import timeint, timestamp_to_int
from cogs.utils.menus import Confirm 

from typing import Optional
from datetime import datetime, timedelta
import pytz
from string import punctuation

import logging
LOG = logging.getLogger('bot')

def setupjson(guild):
    mpk = mpku.getmpm("moderation", guild.id)
    mpk['log'] = ({'flags': 0b11111111111, 'channel': 0 },)
    mpk.save()
    return mpk

def getbit(val, pos):
    return bool((val >> (pos - 1)) & 1)
def toggle(val, bits):
    return val ^ bits
def forceset(val, on, pos):
    return val ^ (-on ^ val) & (1 << (pos - 1))


bitlist = ("Message Delete", "Message Edit", "Channel Edits", "Member Joining/Leaving", 
    "Member Updates", "Server Updates", "Role Updates", "Emoji Updates", "Voice Updates",
    "Bans", "Warnings", "Bots can trigger some logs", "Starboard Logging")
class LogMenu(menus.Menu):
    def __init__(self, gid, datadict, prefix):
        super().__init__(timeout = 30.0, delete_message_after=False, clear_reactions_after=True)
        self.mpk = mpku.getmpm("moderation", gid)
        self.page = 0
        self.max = len(bitlist) // 5
        self.color = datadict['color']
        self.prefix = prefix
        self.shown = 5
        self.message = None
        for x in {"\U0001F53C", "\U0001F53D"}:
            self.add_button(menus.Button(x, self.movepage))
        for x in range(1, 6):
            self.add_button(menus.Button(str(x) + "\uFE0F\u20E3", self.pick))

    async def editmessage(self):
        trimmedlist = bitlist[(self.page * 5):(self.page * 5 + 5)]
        self.shown = len(trimmedlist)
        embed = discord.Embed(title = "Log Config", color=self.color, description = "")
        for i in range(len(bitlist)):
            unic = '\u2705' if (self.mpk['log']['flags'] >> i) & 1 else '\u26D4'
            ch = -1
            if self.page * 5 <= i <= self.page * 5 + 4: 
                ch = i - self.page * 5
            if ch == -1: num = "\U0001F7E6 "
            else: num = f"{str(ch + 1)}\uFE0F\u20e3 "
            embed.description += f"{num}{bitlist[i]}: {unic}\n"
        embed.set_footer(text="Use the reactions to toggle the flags.")
        return await self.message.edit(content = "", embed=embed)

    async def prompt(self, ctx):
        await self.start(ctx)
        
    async def send_initial_message(self, ctx, channel):
        ret = self.message = await channel.send("Please wait..")
        await self.editmessage()
        return ret

    async def finalize(self, _t):
        embed = discord.Embed(title = "Log Config - Saved", color=self.color, description = "")
        for i in range(len(bitlist)):
            unic = '\u2705' if (self.mpk['log']['flags'] >> i) & 1 else '\u26D4'
            embed.description += f"{bitlist[i]}: {unic}\n"
        await self.message.edit(embed=embed)
        self.mpk.save()

    async def movepage(self, payload):
        if not payload.member: return
        await self.message.remove_reaction(payload.emoji, payload.member)
        if (payload.emoji.name == "\U0001F53C"):
            self.page = max(self.page - 1, 0)
        else:
            self.page = min(self.page + 1, self.max)
        LOG.debug(self.max)
        LOG.debug(self.page)
        await self.editmessage()
    
    @menus.button("\u23F9") #stop
    async def stopemote(self, _payload):
        await self.finalize(False)
        self.stop()

    async def pick(self, payload: discord.RawReactionActionEvent):
        if not payload.member: return
        await self.message.remove_reaction(payload.emoji, payload.member)
        if self.shown >= (picked := [str(x) + "\uFE0F\u20E3" for x in range(1, 6)].index(payload.emoji.name)) + 1:
            self.mpk['log']['flags'] ^= 1 << (self.page * 5 + picked)
            await self.editmessage()  

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, members: commands.Greedy[UserLookup], *, reason: Optional[DurationString] = ""):
        """Bans users.
        Both the bot and the runner **must be able to ban.**

        `ban <members> [reason]`"""
        if not members: return
        if reason != "":
            time = reason.duration
            reason = reason.string
        else:
            time = 0
            reason = ""
        d = datetime.now(tz=pytz.timezone("US/Eastern"))
        af = d.day == 1 and d.month == 4
        if af: time = 5 * 60
        if time:
            mpk = mpku.getmpm('moderation', ctx.guild)

        banlist = []
        for member in members:
            if member == ctx.message.author and not af: continue
            try:
                await ctx.guild.ban(member, reason=(f'{reason} ' if reason else '') + f"(Banned by {ctx.author})", delete_message_days=0)
                t = f"You have been banned in {ctx.guild}"
                if time:
                    t += f" for {timeint(time)}"
                    uid = str(member.id)
                    mpk['inwarn'][uid] = {'left': 0, 'time': timestamp_to_int(datetime.utcnow() + timedelta(seconds=time)), 'type': 'ban'}
                if (reason != ""): t += f" for {reason}{'.' if not reason[-1] in punctuation else ''}"
                else: t += '.'
                if af: t += " (happy april fools!)"
                banlist.append(member.mention)
                if reason:
                    try: await member.send(t)
                    except: continue
            except discord.Forbidden: continue
        if time: mpk.save()
        if not banlist:
            return await ctx.send("I was not able to ban any users.")
        await ctx.send(f"User{'s' if len(banlist) > 1 else ''} {', '.join(banlist)} successfully banned.")

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, members:commands.Greedy[UserLookup], *, reason: Optional[str] = ""):
        """Unbans users.
        Both the bot and the runner **must be able to unban.**

        `unban <members> [reason]`"""
        if not members: return
        ubanlist = []
        for member in members:
            if member == ctx.message.author: continue
            try:
                await ctx.guild.unban(member, reason=reason + (" " if reason != "" else "") + f"(Unbanned by {ctx.author})")
                ubanlist.append(member.mention)
            except discord.Forbidden: continue
        if not ubanlist: 
            return await ctx.send("I was not able to unban any of those users somehow? (This should never appear.)")
        
        await ctx.send(f"User{'s' if len(ubanlist) > 1 else ''} {', '.join(ubanlist)} successfully unbanned.")

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, members:commands.Greedy[MemberLookup], *, reason: Optional[str] = ""):
        """Kicks users.
        Both the bot and the runner **must be able to kick.**

        `kick <members> [reason]`"""
        if not members: return
        banlist = []
        for member in members:
            if member == ctx.message.author: continue
            try:
                await ctx.guild.kick(member, reason=reason + (' ' if reason != '' else '') + f"(Kicked by {ctx.author})")
                t = f"You have been kicked in {ctx.guild} by {ctx.author.mention}"
                if (reason != ""): t += f" for {reason}{'.' if not reason[-1] in punctuation else ''}"
                else: t += '.'
                try: await member.send(f"You have been kicked in {ctx.guild} by {ctx.author.mention}")
                except: pass
                banlist.append(member.mention)
            except discord.Forbidden: continue
        
        await ctx.send(f"User{'s' if len(banlist) > 1 else ''} {', '.join(banlist)} successfully kicked.")

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True, read_message_history=True)
    async def purge(self, ctx: commands.Context, count = 100, member: Optional[MemberLookup] = None):
        """Purges messages.

        `purge [count (default 100)] [member]`"""
        def check(msg):
            if member:
                return msg.author == member
            return True
        if count >= 100:
            if not (await Confirm(f"Are you sure you want to purge {count} messages?", clear_reactions_after=True).prompt(ctx)):
                return
        await ctx.message.delete()
        await ctx.channel.purge(limit=count, check=check)
        msg = await ctx.send(f"Purged {count} messages!")
        await msg.delete(delay=3)

###################################LOG CONFIG############################
    @commands.group(aliases=('logs',))
    @commands.has_permissions(manage_guild=True)
    async def log(self, ctx):
        """Sets up logging.
        
        `log/logs`
        `log cfg`
        `log cfg channel/setchannel [channel]`"""
        setupjson(ctx.guild)
        if (ctx.invoked_subcommand == None):
            mpk = mpku.getmpm("moderation", ctx.guild.id)
            embed = discord.Embed(title = "Log Config", color=self.bot.data['color'], description = "")
            for i in range(len(bitlist)):
                unic = '\u2705' if (mpk['log']['flags'] >> i) & 1 else '\u26D4'
                embed.description += f"{bitlist[i]}: {unic}\n"
            embed.description += f"Channel: <#{mpk['log']['channel']}>" if mpk['log']['channel'] else "Channel: *not set*"
            await ctx.send(embed=embed)
    
    @log.group(aliases = ('cfg',))
    async def config(self, ctx):
        """Sets up logging."""
        if not ctx.invoked_subcommand:
            await LogMenu(ctx.guild.id, self.bot.data, ctx.prefix).prompt(ctx)

    @config.command(aliases = ('setchannel',))
    @commands.has_permissions(manage_guild=True)
    async def channel(self, ctx, channel: Optional[discord.TextChannel]):
        """Set the channel for logs."""
        if not channel: return await ctx.invoke(self.log)
        mpk = mpku.getmpm("moderation", ctx.guild.id)
        mpk['log']['channel'] = channel.id
        mpk.save()
        await ctx.send(f"Log channel set to {channel.mention}!")

    @config.command()
    @commands.has_permissions(manage_guild=True)
    async def toggle(self, ctx):
        """Toggle certain parts of logging."""
        ctx.invoked_subcommand = None
        await self.config(ctx)

def setup(bot):
    bot.add_cog(Moderation(bot))
