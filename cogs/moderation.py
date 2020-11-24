import discord, timeago, pytimeparse, asyncio
from discord.ext import commands, tasks
from discord.ext.commands import Greedy

import cogs.utils.mpk as mpku
from cogs.utils.menus import Confirm
from cogs.utils.converters import UserLookup, MemberLookup, DurationString
from cogs.utils.other import timeint, timestamp_to_int, datetime_from_int, timestamp_now

from typing import Optional
from copy import copy, deepcopy
from datetime import datetime, timedelta
import pytz
from string import punctuation

import logging
log = logging.getLogger('bot')

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        # pylint: disable=no-member
        self.bot = bot
        self.timeaction.start()

    def cog_unload(self):
        # pylint: disable=no-member
        self.timeaction.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        # pylint: disable=no-member
        if (self.timeaction.get_task()): self.timeaction.cancel()
        self.timeaction.start()

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
        await ctx.message.delete()
        await ctx.channel.purge(limit=count, check=check)
        msg = await ctx.send(f"Purged {count} messages!")
        await msg.delete(delay=3)


    @config.command(name="add", aliases = ('addaction', 'a'))
    @commands.has_permissions(manage_guild=True, ban_members=True) 
    async def aaction(self, ctx, name, typ: Optional[str]):
        if name == "mute": typ = 'gr'
        elif name == "verbal": typ = None
        if (name != "verbal") and typ not in {'gr', 'giverole', 'ban', 'b', 'kick', 'k'}:
            return await ctx.send("Please give a valid type.")
        if   typ == 'giverole': typ = 'gr'
        elif typ == 'ban': typ = 'b'
        elif typ == 'kick': typ = 'k'
        name = name.lower()
        if ' ' in name:
            return await ctx.send("Action names can't have spaces.")
        mpk = mpku.getmpm('moderation', ctx.guild)
        if name in mpk['actions']:
            return await ctx.send("This action already exists! If you want to edit it, remove it and re-add it.")
        def check(m):
            return (m.author == ctx.author) and (m.channel == ctx.channel)
        ret: discord.Message = None
        timed = False
        embed = discord.Embed(title=f"Action Setup - `{name}`", color=self.bot.data['color'])
        embed.description = f"**Name:** `{name}`\n{f'**Type:** `{typ}`' if typ else ''}\n".strip() + "\n"
        embed.set_footer(text="You can type cancel at any time to stop.")
        msg = await ctx.send(embed=embed)
        async def waitfor():
            nonlocal ret
            try: ret = await self.bot.wait_for('message', check=check, timeout=180.0)
            except asyncio.TimeoutError: 
                await ctx.send("Cancelled due to 3 minute timeout.")
                raise commands.CommandNotFound()
            if ret.content == "cancel":
                await ctx.send("Cancelled the addition.")
                raise commands.CommandNotFound() #LOL
            try: await ret.delete()
            except discord.Forbidden: pass
            return ret.content
        if typ: actdict = {'type': typ}
        else: actdict = {}

        if typ == "gr":
            pre = embed.description
            embed.description += "Please send the role this should add (you can use role ID if you don't want to ping.)"
            await msg.edit(embed=embed)
            while True:
                try: role = await commands.RoleConverter().convert(ctx, await waitfor())
                except commands.BadArgument:
                    await (await ctx.send("Please enter a valid role.")).delete(delay=5)
                    continue
                actdict.update({'role': role.id})
                embed.description = pre + f"**Role:** {role.mention}\n"
                break

        if (not name == "mute") and (typ and typ != 'k'):
            pre = embed.description
            timed = await Confirm("Should the action be timed (should it run out automatically)?").prompt(ctx)
            actdict.update({'timed': timed})
            embed.description = pre + f"**Timed:** {'yes' if timed else 'no'}\n"
        elif name == "mute":
            actdict.update({'timed': True})
            embed.description += "**Timed:** yes\n"
            timed = True

        pre = embed.description
        embed.description += f"""Please type the message that would get sent in the channel the user was warned in.
        `[u]` pings the warned user.
        `[r]` posts the reason.
        {'`[t]` posts the time in minutes.' if timed else ''}"""
        await msg.edit(embed=embed)
        good = False
        touse = None
        while not good:
            touse = await waitfor()
            tstring = touse
            tstring = tstring.replace("[u]", ctx.author.mention)
            tstring = tstring.replace("[r]", "pinging mods for no reason")
            if timed: tstring = tstring.replace("[t]", "30 minutes")
            good = await Confirm(f"Is this ok? Your message will appear like this:\n{tstring}").prompt(ctx)
        actdict.update({'msg': touse})
        embed.description = pre + f"**Server MSG:** `{touse}`\n"

        pre = embed.description
        embed.description += f"""Please type the message that would get sent to the user in DMs.
        `[r]` posts the reason.
        {'`[t]` posts the time in minutes.' if timed else ''}"""
        await msg.edit(embed=embed)
        good = False
        while not good:
            touse = await waitfor()
            tstring = touse
            tstring = tstring.replace("[r]", "pinging mods for no reason")
            if timed: tstring = tstring.replace("[t]", "30 minutes")
            good = await Confirm(f"Is this ok? Your message will appear like this:\n{tstring}").prompt(ctx)
        actdict.update({'dmmsg': touse})
        embed.description = pre + f"**DM MSG:** `{touse}`\n"
        await msg.edit(embed=embed)
        mpk['actions'][name] = actdict
        mpk.save()
        await ctx.send("Done!")

    @config.command(aliases=('removeaction', 'remove', 'r'))
    @commands.has_permissions(manage_guild=True, ban_members=True) 
    async def rmaction(self, ctx, action):
        mpk = mpku.getmpm('moderation', ctx.guild)
        if not action in mpk['actions']:
            return await ctx.send("This action doesn't exist!")
        del mpk['actions'][action]
        mpk['offences'] = [x for x in mpk['offences'] if x['action'] != action]
        mpk.save()
        await ctx.send(f"Deleted action `{action}`.")
    
    @config.command(aliases=('track',))
    @commands.has_permissions(manage_guild=True, ban_members=True) 
    async def settrack(self, ctx):
        if ctx.invoked_with == "track": return await ctx.invoke(self.config, None)
        mpk = mpku.getmpm('moderation', ctx.guild)
        #valid = [x for x in mpk['actions'] if x != 'verbal']
        valid = mpk['actions']
        if not valid: return await ctx.send("There are no actions to use! Add some first!")
        embed = discord.Embed(title="Warn Config - Track Setup", color=self.bot.data['color'])
        embed.description = "__**Valid track actions:**__\n"
        for action in valid:
            embed.description += f"> `{action}`\n"
        embed.description += "__**Track:**__\nPost the names of valid actions and it will add to the track.\nPost `stop` once you're done.\n"
        embed.set_footer(text="You can type cancel at any time to stop without saving.")
        pre = embed.description
        def check(m):
            return m.author == ctx.author
        ret: discord.Message = None
        msg = await ctx.send(embed=embed)
        track = []
        async def waitfor():
            nonlocal ret
            ret = await self.bot.wait_for('message', check=check)
            if ret.content == "cancel":
                await ctx.send("Cancelled the track setting.")
                raise commands.CommandNotFound() #LOL
            try: await ret.delete()
            except discord.Forbidden: pass
            return ret.content
        while True:
            l = []
            tracks = ""
            for offence in track:
                timed = bool(mpk['actions'][offence['action']]['timed'])
                tst = ""
                if timed: 
                    if not offence['time']: tst = " (manual revoke)"
                    else: tst = f" ({int(offence['time'])}m)"
                l.append(f"""`{offence['action']}`{tst}""")
            tracks += ' \u2192 '.join(l)
            embed.description = pre + tracks + (" (keeps repeating last offence)" if track else "")
            await msg.edit(embed=embed)
            if (r := await waitfor()) == "stop": break
            if not r in valid: await (await ctx.send("Please send a valid action.")).delete(delay=5)
            else:
                track.append({'action': r})
                try:
                    if mpk['actions'][r]['timed']:
                        td = await ctx.send("Please enter the duration (atleast 5 minutes).")
                        while True:
                            try: 
                                if (not (v := pytimeparse.parse(await waitfor()))): raise ValueError()
                                elif v // 60 < 5: raise ValueError()
                            except ValueError: await (await ctx.send("Please send a valid value.")).delete(delay=5)
                            else:
                                track[-1].update({'time': v // 60})
                                await td.delete()
                                break
                except KeyError: pass
        mpk['offences'] = track
        mpk.save()
        await ctx.send("Done!")  

                
    @commands.command(aliases=('m',))
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True, kick_members=True)
    async def mute(self, ctx, users: Greedy[MemberLookup], *, reason: DurationString):
        """Mutes users for a durarion. **Must be setup.**
        
        `mute/m <users> <duration> <reason>`"""
        if not reason.duration: return await ctx.send("Please set a valid duration.")
        await ctx.invoke(self.verbalwarn, users, reason=reason.string, mute=reason.duration)

    @commands.command(aliases=('vwarn', 'vw'))
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True, kick_members=True)
    async def verbalwarn(self, ctx, users: Greedy[UserLookup], *, reason, mute=0):
        """Verbally warns users. **Must be setup.**
        The user calling it must be able to **manage messages and kick.**
        These are intended to be used as a sort of push saying "don't do that",
        and will never automatically culminate into a warn.

        `verbalwarn/vwarn/vw <users> <reason>`"""
        mpk = mpku.getmpm('moderation', ctx.guild)
        strused = 'mute' if mute else 'verbal'
        if not mpk['actions'][strused]:
            return await ctx.send(f"{strused.title()}s aren't setup! Set it up with `{ctx.prefix}warn cfg add {strused}`")
        if (not users) or (not reason): return
        for user in users:
            uid = str(user.id)

            cnt = len(mpk['users'][uid])

            mpk['users'][uid].append({})
            mpk['users'][uid][cnt]['reason'] = reason + (' (Mute)' if mute else '')
            mpk['users'][uid][cnt]['timestamp'] = timestamp_now()
            mpk['users'][uid][cnt]['who'] = ctx.author.id
            mpk['users'][uid][cnt]['major'] = False

            act = deepcopy(mpk['actions'][strused])

            act['dmmsg'] = act['dmmsg'].replace('[r]', reason)
            act['msg'] = act['msg'].replace('[u]', user.mention)
            act['msg'] = act['msg'].replace('[r]', reason)

            if (mute):
                try: await user.add_roles(ctx.guild.get_role(act['role']), reason=reason)
                except discord.Forbidden:
                    await ctx.send("I'm not able to mute, so this will be counted only as a verbal. Please make sure the mute role is below my role.")
                    await ctx.invoke(self.verbalwarn, users, reason=reason, mute=0)
                    continue
                act['dmmsg'] = act['dmmsg'].replace('[t]', timeint(mute))
                act['msg'] = act['msg'].replace('[t]', timeint(mute))
                mpk['inwarn'][uid] = {'left': 0, 'time': timestamp_to_int(datetime.utcnow() + timedelta(seconds=mute)), 'type': 'mute'}
            if act['dmmsg']:
                try: await user.send(act['dmmsg'])
                except: pass
            await ctx.send(act['msg'])
            mpk.save()
            try: await self.bot.get_cog('Logging').on_warn(user, ctx.guild, mpk['users'][uid][cnt], '`mute`' if mute else None)
            except AttributeError: pass

    @commands.command(aliases=('warnings',))
    @commands.guild_only()
    async def warns(self, ctx, user: Optional[discord.User]):
        """Check warns.
        If no user is given, it will display your own.
        If you give a user, you **must be able to**
        **manage messages and kick.** 
        
        `warns/warnings [user]`"""
        if not user: user = ctx.author
        if (user != ctx.author):
            if (not (ctx.author.guild_permissions.manage_messages and ctx.author.guild_permissions.kick_members)):
                return
        mpk = mpku.getmpm('moderation', ctx.guild)
        #gid = str(ctx.guild.id)
        uid = str(user.id)
        embed = discord.Embed(color=(discord.Color(self.bot.data['color']) if user.color == discord.Color.default() else user.color))
        embed.set_author(name=user.display_name, icon_url=user.avatar_url)
        embed.timestamp = datetime.utcnow()
        embed.title = "Warnings"
        
        desc = ""
        for warn in reversed(mpk['users'][uid]):
            reason = f"*{warn['reason']}*"
            if (warn['major']): reason = f"*{reason}*"
            desc += f"> {reason} - <@{warn['who']}>\n> *{timeago.format(datetime_from_int(warn['timestamp']), datetime.utcnow())}* (Case {mpk['users'][uid].index(warn) + 1})\n> `-------------`\n"
        if not mpk['users'][uid]: desc = "__No warnings!__"
        else: desc = desc[:-18]
        embed.description = desc.strip()
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Moderation(bot))
