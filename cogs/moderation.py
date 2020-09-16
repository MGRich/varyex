import discord, timeago, pytimeparse
from discord.ext import commands, tasks
from copy import copy
from datetime import datetime, timedelta
import cogs.utils.mpk as mpku
from discord.ext.commands import Greedy
from typing import Optional
from string import punctuation
from cogs.utils.menus import Confirm
from cogs.utils.converters import UserLookup, MemberLookup
import asyncio

loaded = None

basis1 = ['users', 'inwarn', 'actions', 'offences']
basis2 = [{}, {}, {}, []]

def convert_to_bool(argument): #commands._convert_to_bool
    lowered = argument.lower()
    if lowered in ('yes', 'y', 'true', 't', '1', 'enable', 'on'):
        return True
    if lowered in ('no', 'n', 'false', 'f', '0', 'disable', 'off'):
        return False
    raise commands.BadArgument(lowered + ' is not a recognised boolean option')


def toInt(dt):
    return int(datetime.timestamp(dt) * 1000000)
def now():
    return toInt(datetime.utcnow())    
def fromInt(dt):
    return datetime.fromtimestamp(dt  / 1000000)
def majorWarns(warns):
    return [x for x in warns if (x['major'])]

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
    async def ban(self, ctx, members: commands.Greedy[UserLookup], *, reason: Optional[str] = ""):
        """Bans users.
        Both the bot and the runner **must be able to ban.**

        `ban <members> [reason]`"""
        if not members: return await ctx.send("There are no users in that list (that I could convert.)")
        banlist = []
        for member in members:
            if member == ctx.message.author: continue
            try:
                await ctx.guild.ban(member, reason=reason + (' ' if reason != '' else '') + f"(Banned by {ctx.author})", delete_message_days=0)
                t = f"You have been banned in {ctx.guild} by {ctx.author.mention}"
                if (reason != ""): t += f" for {reason}{'.' if not reason[-1] in punctuation else ''}"
                else: t += '.'
                banlist.append(member.mention)
                if reason:
                    try: await member.send(t)
                    except discord.Forbidden: continue
            except discord.Forbidden: continue
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
                await ctx.guild.ban(member, reason=reason + (' ' if reason != '' else '') + f"(Kicked by {ctx.author})")
                t = f"You have been kicked in {ctx.guild} by {ctx.author.mention}"
                if (reason != ""): t += f" for {reason}{'.' if not reason[-1] in punctuation else ''}"
                else: t += '.'
                try: await member.send(f"You have been kicked in {ctx.guild} by {ctx.author.mention}")
                except discord.Forbidden: pass
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

    @commands.Cog.listener()
    async def on_member_join(self, member):
        mpm = mpku.getmpm('moderation', member.guild)
        mpk = mpm.data
        try: mpk['inwarn'][str(member.id)]
        except: return
        uid = str(member.id)
        if mpk['inwarn'][uid]['left'] != 0:
            mpk['inwarn'][uid]['time'] += now() - mpk['inwarn'][uid]['left']
            mpk['inwarn'][uid]['left'] = 0
        ofc = mpk['offences'][min(len(majorWarns(mpk['users'][uid])), len(mpk['offences'])) - 1]
        act = copy(mpk['actions'][ofc['action']])
        if (act['type'] == "gr"):
            await member.add_roles(member.guild.get_role(act['role']), reason="User rejoined while in punishment.")    
        mpm.save()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        mpm = mpku.getmpm('moderation', member.guild, ['inwarn'], [{}])
        mpk = mpm.data
        try: mpk['inwarn'][str(member.id)]
        except: return
        uid = str(member.id)
        if mpk['inwarn'][uid]['left'] == 0:
            mpk['inwarn'][uid]['left'] = now()

        mpm.save()
    
    @tasks.loop(seconds=30, reconnect=True)
    async def timeaction(self):
        print('we exist')
        for guild in self.bot.guilds:
            changed = False
            #guild = self.bot.get_guild(int(gid))
            #if (guild == None): continue
            mpm = mpku.getmpm('moderation', guild)
            mpk = mpm.data
            if not mpku.testgiven(mpk, ['inwarn', 'offences', 'actions', 'users']): continue
            for uid in list(mpk['inwarn']):
                try: mpk['inwarn'][uid]['time']
                except: continue
                #print(uid)

                try: user = await guild.fetch_member(int(uid))
                except discord.NotFound: user = None 
                print(uid + " " + str(user))
                if not user:
                    if mpk['inwarn'][uid]['left'] == 0:
                        mpk['inwarn'][uid]['left'] = now()
                        changed = True
                    #continue
                elif mpk['inwarn'][uid]['left'] != 0:
                    mpk['inwarn'][uid]['time'] += now() - mpk['inwarn'][uid]['left']
                    mpk['inwarn'][uid]['left'] = 0
                    changed = True
                    continue
                
                try: cnt = len(majorWarns(mpk['users'][uid]))
                except KeyError:
                    del mpk['inwarn'][uid]
                    changed = True
                    continue

                #print(uid)
                if (mpk['inwarn'][uid]['time'] <= now()):
                    print(guild.id)
                    try: print(mpk['users'][uid])
                    except KeyError: print("fuck")
                    if cnt != 0:
                        ofc = mpk['offences'][cnt - 1]
                        act = mpk['actions'][ofc['action']]
                        try:
                            if (act['type'] == "gr"):
                                if not user: continue 
                                await user.remove_roles(guild.get_role(act['role']), reason="Time for warning ran out.")
                            elif (act['type'] == "b"):
                                await guild.unban(discord.Object(int(uid)), reason="Time for warning ran out.")
                        except discord.Forbidden:
                            pass #dm someone who can?
                        except discord.NotFound:
                            pass #oops
                        
                    del(mpk['inwarn'][uid])
                    changed = True
                    if not user:
                        try: user = self.bot.get_user(int(uid))
                        except discord.NotFound: pass  
                    try: await user.send("The above message's time is now over.")
                    except: pass
            if changed: mpm.save()
        print('we exist')

    @commands.command(aliases = ["clearwarns", "rmwarn", "cwarns", "rmw", "cw"])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True, kick_members=True)
    async def removewarn(self, ctx, user: UserLookup, *, case: Optional[str]):
        """Removes a warn or all warns from a user.
        You must be able to **manage messages and kick.**

        `removewarn/rmwarn/rmw <user> <case number/all>`
        `clearwarns/cwarns <user>` (same as doing `rmw` all cases)"""
        if ctx.invoked_with in ['clearwarns', 'cwarns', 'cw']:
            case = "all"
        else: 
            if not case: raise commands.UserInputError()
        all = case == "all"
        if not all:
            try: case = int(case)
            except TypeError: pass #we try again later and see if it matches a warn
            else: 
                if case < 1: return await ctx.send("Please enter a valid case number.")
        mpm = mpku.getmpm('moderation', ctx.guild, ['users'], [{}])
        mpk = mpm.data
        uid = str(user.id)
        try: mpk['users'][uid]
        except: return await ctx.send("That user has no warnings!")
        if all: mpk['users'][uid] = []
        elif type(case) == str:
            casel = [x['reason'].lower() for x in mpk['users'][uid]]
            if case.lower() not in casel: return await ctx.send("Please enter a valid case.")
            case = casel.index(case) + 1
        if (not all):
            try: del(mpk['users'][uid][case - 1])
            except IndexError: return await ctx.send("That user doesn't have that many warns!")
        mpm.save()
        if all: await ctx.send(f"Cleared warnings for {user.mention}!")
        else: await ctx.send(f"Removed case {case} from {user.mention}!")

    @commands.command(aliases = ["ewarn", "ew"])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True, kick_members=True)
    async def editwarn(self, ctx, user: UserLookup, case: int, *, newreason: str):
        """Edits a warn from a user.
        You must be able to **manage messages and kick.**

        `editwarn/ewarn/ew <user> <case number> <new reason>`"""
        mpm = mpku.getmpm('moderation', ctx.guild, ['users'], [{}])
        mpk = mpm.data
        uid = str(user.id)
        try: mpk['users'][uid]
        except: return await ctx.send("That user has no warnings!")
        try: mpk['users'][uid][case - 1]['reason'] = newreason
        except IndexError: return await ctx.send("That user doesn't have that many warns!")
        mpm.save()
        await ctx.send(f"Updated reason for case {case} of {user.mention}!")

    @commands.group(aliases=["w"], invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True, kick_members=True)
    async def warn(self, ctx, user: UserLookup, users: Greedy[UserLookup], *, reason):
        """Warns users and sets up warnings.
        The bot must be able to do the action given, and you must be able to **manage messages and kick.**
        Additionally, to configure it, you must be able to **manage the server and ban.**
        
        `warn/w <users> <reason>`

        *config/cfg*
        `w cfg [action]`
        `w cfg addaction/add/a <name> [type]`
        > **TYPE MUST BE:**
        > `gr` (`giverole`), `b` (`ban`), or `k` (`kick`)
        > **ISN'T NEEDED IF:**
        > `name` is `verbal` or `mute`, as they are considered special
        `w cfg removeaction/rmaction/remove <name>`
        `w cfg settrack/track`"""
        if (ctx.invoked_subcommand): return
        users.insert(0, user)
        mpm = mpku.getmpm('moderation', ctx.guild, basis1, basis2)
        mpk = mpm.data
        if (not users) or (not reason): return
        if not mpk['offences']: return await ctx.send("Warns aren't configured!")
        for user in users:
            uid = str(user.id)
            if uid not in mpk['users']: mpk['users'][uid] = []
            mpk['users'][uid].append({'reason': reason, 'timestamp': now(), 'who': ctx.author.id, 'major': True})

            ofc = mpk['offences'][min(len(majorWarns(mpk['users'][uid])), len(mpk['offences'])) - 1]
            act = copy(mpk['actions'][ofc['action']])

            worked = True
            try:
                if   (act['name'] == "verbal"): pass
                elif (act['type'] == "gr"): await user.add_roles(ctx.guild.get_role(act['role']), reason=reason)
                elif (act['type'] == "k"): await user.kick(reason=reason)
                elif (act['type'] == "b" ): await user.ban(reason=reason)
            except: worked = False

            if (not worked):
                await ctx.send("I'm not able to take action, but the user will be warned.")
                act['dmmsg'] = "I'm not able to take the action I'm told to take, but you are still warned for [r]."
            
            act['dmmsg'] = act['dmmsg'].replace('[r]', reason)
            act['msg'] = act['msg'].replace('[u]', user.mention)
            act['msg'] = act['msg'].replace('[r]', reason)

            if (worked):
                try:
                    if (act['timed']):
                        act['dmmsg'] = act['dmmsg'].replace('[t]', str(ofc['time']))
                        act['msg'] = act['msg'].replace('[t]', str(ofc['time']))
                        if (ofc['time']):
                            mpk['inwarn'][uid] = {}
                            mpk['inwarn'][uid]['left'] = 0
                            mpk['inwarn'][uid]['time'] = toInt(datetime.utcnow() + timedelta(minutes=ofc['time']))
                except KeyError:
                    pass

            if act['dmmsg']:
                try: await user.send(act['dmmsg'])
                except discord.Forbidden: pass
            if (worked): await ctx.send(act['msg'])
            mpm.save()
            try: await self.bot.get_cog('Logging').on_warn(user, ctx.guild, mpk['users'][uid][-1], f"`{ofc['action']}`")
            except AttributeError: pass


    @warn.group(aliases = ['cfg'], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True, ban_members=True) 
    async def config(self, ctx, action: Optional[str]):
        if ctx.invoked_subcommand: return
        mpm = mpku.getmpm('moderation', ctx.guild, ['actions', 'offences'], [{}, []])
        mpk = mpm.data
        embed = discord.Embed(title="Warning Config", color=discord.Color(self.bot.data['color']), description="")
        if action:
            try: a = mpk['actions'][action]
            except: return await ctx.send("That action doesn't exist!")
            embed.title += f" - `{action}`"
            try: a['type']
            except: pass
            else: embed.description = f"**Type:** `{a['type']}`\n"
            try: a['role']
            except: pass
            else: 
                r = ctx.guild.get_role(a['role'])
                if not r: s = "**(Needs to be fixed)**"
                else: s = r.mention
                embed.description += f"**Role:** {s}\n"
            try: a['timed']
            except: pass
            else: embed.description += f"**Timed:** {'yes' if a['timed'] else 'no'}\n"
            embed.description += f"**Server MSG:** `{a['msg']}`\n**DM MSG:** `{a['dmmsg']}`"
            return await ctx.send(embed=embed)
        embed.description += "__**Actions:**__\n"
        if not mpk['actions']: embed.description += f"*No actions.* Use `{ctx.prefix}w {ctx.invoked_with} add [name]`\n"
        else: 
            for action in mpk['actions']:
                embed.description += f"> `{action}`\n"
        if 'mute' not in mpk['actions']:
            embed.description += "*Recommended: `mute`*\n"
        embed.description += "__**Track:**__\n"
        l = []
        if mpk['offences']:
            for offence in mpk['offences']:
                timed = False
                try: timed = mpk['actions'][offence['action']]['timed']
                except KeyError: pass
                tst = ""
                if timed: 
                    if not offence['time']: tst = " (manual revoke)"
                    else: tst = f" ({int(offence['time'])}m)"
                l.append(f"""`{offence['action']}`{tst}""")
            embed.description += ' \u2192 '.join(l)
            embed.description += " (keeps repeating last offence)"
        else: embed.description += f"*No track set!* Use `{ctx.prefix}w {ctx.invoked_with} settrack`"
        await ctx.send(embed=embed)

    @config.command(name="add", aliases = ['addaction', 'a'])
    async def aaction(self, ctx, name, typ: Optional[str]):
        if name == "mute": typ = 'gr'
        elif name == "verbal": typ = None
        if (name != "verbal") and typ not in ['gr', 'giverole', 'ban', 'b', 'kick', 'k']:
            return await ctx.invoke(self.bot.get_command("help"), "wcfg")
        if   typ == 'giverole': typ = 'gr'
        elif typ == 'ban': typ = 'b'
        elif typ == 'kick': typ = 'k'
        name = name.lower()
        if ' ' in name:
            return await ctx.send("Action names can't have spaces.")
        mpm = mpku.getmpm('moderation', ctx.guild, ['actions'], [{}])
        mpk = mpm.data
        if name in mpk['actions']:
            return await ctx.send("This action already exists! If you want to edit it, remove it and re-add it.")
        def check(m):
            return (m.author == ctx.author) and (m.channel == ctx.channel)
        ret: discord.Message = None
        timed = False
        embed = discord.Embed(title=f"Action Setup - `{name}`", color=discord.Color(self.bot.data['color']))
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
            if timed: tstring = tstring.replace("[t]", "30")
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
            if timed: tstring = tstring.replace("[t]", "30")
            good = await Confirm(f"Is this ok? Your message will appear like this:\n{tstring}").prompt(ctx)
        actdict.update({'dmmsg': touse})
        embed.description = pre + f"**DM MSG:** `{touse}`\n"
        await msg.edit(embed=embed)
        mpk['actions'][name] = actdict
        mpm.save()
        await ctx.send("Done!")

    @config.command(aliases=['removeaction', 'remove', 'r'])
    async def rmaction(self, ctx, action):
        mpm = mpku.getmpm('moderation', ctx.guild, ['actions', 'offences'], [{}, []])
        mpk = mpm.data
        if not action in mpk['actions']:
            return await ctx.send("This action doesn't exist!")
        del mpk['actions'][action]
        mpk['offences'] = [x for x in mpk['offences'] if x['action'] != action]
        mpm.save()
        await ctx.send(f"Deleted action `{action}`.")
    
    @config.command(aliases=['track'])
    async def settrack(self, ctx):
        if ctx.invoked_with == "track": return await ctx.invoke(self.config, None)
        mpm = mpku.getmpm('moderation', ctx.guild, ['actions', 'offences'], [{}, []])
        mpk = mpm.data
        #valid = [x for x in mpk['actions'] if x != 'verbal']
        valid = mpk['actions']
        if not valid: return await ctx.send("There are no actions to use! Add some first!")
        embed = discord.Embed(title="Warn Config - Track Setup", color=discord.Color(self.bot.data['color']))
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
                timed = False
                try: timed = mpk['actions'][offence['action']]['timed']
                except KeyError: pass
                tst = ""
                if timed: 
                    if not offence['time']: tst = " (manual revoke)"
                    else: tst = f" ({int(offence['time'])}m)"
                l.append(f"""`{offence['action']}`{tst}""")
            tracks += ' \u2192 '.join(l)
            embed.description = pre + tracks + (" (keeps repeating last offence)" if track else "")
            await msg.edit(embed=embed)
            r = await waitfor()
            if r == "stop": break
            if not r in valid: await (await ctx.send("Please send a valid action.")).delete(delay=5)
            else:
                track.append({'action': r})
                try:
                    if mpk['actions'][r]['timed']:
                        td = await ctx.send("Please enter the duration in minutes (or 0 if manual).")
                        while True:
                            try: 
                                dur = int(await waitfor())
                                if dur < 0: raise ValueError()
                            except ValueError: await (await ctx.send("Please send a valid value.")).delete(delay=5)
                            else:
                                track[-1].update({'time': dur})
                                await td.delete()
                                break
                except KeyError: pass
        mpk['offences'] = track
        mpm.save()
        await ctx.send("Done!")  

                
    @commands.command(aliases=['m'])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True, kick_members=True)
    async def mute(self, ctx, users: Greedy[UserLookup], duration, *, reason):
        """Mutes users for a durarion. **Must be setup.**
        
        `mute/m <users> <duration> <reason>`"""
        duration = pytimeparse.parse(duration)
        if not duration: return await ctx.send("Please set a valid duration.")
        await ctx.invoke(self.verbalwarn, users, reason=reason, mute=duration)

    @commands.command(aliases=['vwarn', 'vw'])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True, kick_members=True)
    async def verbalwarn(self, ctx, users: Greedy[UserLookup], *, reason, mute=0):
        """Verbally warns users. **Must be setup.**
        The user calling it must be able to **manage messages and kick.**
        These are intended to be used as a sort of push saying "don't do that",
        and will never automatically culminate into a warn.

        `verbalwarn/vwarn/vw <users> <reason>`"""
        mpm = mpku.getmpm('moderation', ctx.guild, basis1, basis2)
        mpk = mpm.data
        strused = 'mute' if mute else 'verbal'
        try: mpk['actions'][strused]
        except: return await ctx.send(f"{strused.title()}s aren't setup! Set it up with `{ctx.prefix}warncfg add {strused}`")
        if (not users) or (not reason): return
        for user in users:
            uid = str(user.id)
            try: mpk['users'][uid]
            except: mpk['users'][uid] = []

            cnt = len(mpk['users'][uid])

            mpk['users'][uid].append({})
            mpk['users'][uid][cnt]['reason'] = reason + (' (Mute)' if mute else '')
            mpk['users'][uid][cnt]['timestamp'] = now()
            mpk['users'][uid][cnt]['who'] = ctx.author.id
            mpk['users'][uid][cnt]['major'] = False

            act = copy(mpk['actions'][strused])

            act['dmmsg'] = act['dmmsg'].replace('[r]', reason)
            act['msg'] = act['msg'].replace('[u]', user.mention)
            act['msg'] = act['msg'].replace('[r]', reason)

            if (mute):
                try: await user.add_roles(ctx.guild.get_role(act['role']), reason=reason)
                except discord.Forbidden:
                    await ctx.send("I'm not able to mute, so this will be counted as a verbal. Please make sure the mute role is below my role.")
                    return await ctx.invoke(self.verbalwarn, users, reason=reason, mute=0)
                mute = float(mute) / 60
                act['dmmsg'] = act['dmmsg'].replace('[t]', str(int(mute)))
                act['msg'] = act['msg'].replace('[t]', str(int(mute)))
                mpk['inwarn'][uid] = {}
                mpk['inwarn'][uid]['left'] = 0
                mpk['inwarn'][uid]['time'] = toInt(datetime.utcnow() + timedelta(minutes=mute))
            if act['dmmsg']:
                try: await user.send(act['dmmsg'])
                except: pass
            await ctx.send(act['msg'])
            mpm.save()
            try: await self.bot.get_cog('Logging').on_warn(user, ctx.guild, mpk['users'][uid][cnt], None)
            except AttributeError: pass

    @commands.command(aliases=['warnings'])
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
        mpm = mpku.getmpm('moderation', ctx.guild, ['users'], [{}])
        mpk = mpm.data
        #gid = str(ctx.guild.id)
        uid = str(user.id)
        embed = discord.Embed(color=(discord.Color(self.bot.data['color']) if user.color == discord.Color.default() else user.color))
        embed.set_author(name=user.display_name, icon_url=user.avatar_url)
        embed.timestamp = datetime.utcnow()
        embed.title = "Warnings"

        try: mpk['users'][uid]
        except: mpk['users'][uid] = []
        
        desc = ""
        for warn in reversed(mpk['users'][uid]):
            reason = f"*{warn['reason']}*"
            if (warn['major']): reason = f"*{reason}*"
            desc += f"> {reason} - <@{warn['who']}>\n> *{timeago.format(fromInt(warn['timestamp']), datetime.utcnow())}* (Case {mpk['users'][uid].index(warn) + 1})\n> `-------------`\n"
        if not mpk['users'][uid]: desc = "__No warnings!__"
        else: desc = desc[:-18]
        embed.description = desc.strip()
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Moderation(bot))