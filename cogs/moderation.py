import discord
from discord.ext import commands, tasks
from asyncio import sleep
import traceback, json, time, copy, os
from datetime import datetime, timedelta
import timeago
from cogs.utils.mpkmanager import MPKManager
#import ..util.suggestions
from discord.ext.commands import Greedy
from typing import Optional
from string import punctuation

data = json.load(open("info.json"))
loaded = None

class Moderation(commands.Cog):
    def __init__(self, bot):
        # pylint: disable=no-member
        self.bot = bot
        self.current = current + 1
        #self.json['inwarn'] = {}
        #sleep()
        self.timeaction.start()
        #lp = False
        #try:
        #    for ()

    def cog_unload(self):
        # pylint: disable=no-member
        self.timeaction.cancel()

    def getmpm(self, guild) -> MPKManager:
        return MPKManager("moderation", guild.id)

    def testforguild(self, guild) -> MPKManager:
        mpm = self.getmpm(guild)
        file = mpm.data
        try:
            file['offences']
            file['actions']
            file['users']
            file['inwarn']
        except:
            file['offences'] = {}
            file['actions'] = {}
            file['users'] = {}
            file['inwarn'] = {}
        return mpm

    
    @commands.command()
    @commands.is_owner()    
    async def ro(self, ctx):
        # pylint: disable=no-member
        self.timeaction.cancel()
        self.timeaction.start()
    
    @commands.command()
    @commands.is_owner()
    async def stp(self, ctx):
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
    async def ban(self, ctx, members:commands.Greedy[discord.User], *, reason: Optional[str] = ""):
        """Bans users.
        Both the bot and the runner **must be able to ban.**

        `ban <members> [reason]`"""
        if len(members) == 0: return
        banlist = []
        for member in members:
            if member == ctx.message.author: continue
            try:
                await ctx.guild.ban(member, reason=reason + (' ' if reason != '' else '') + f"(Banned by {ctx.author})", delete_message_days=0)
                t = f"You have been banned in {ctx.guild} by {ctx.author.mention}"
                if (reason != ""): t += f" for {reason}{'.' if not reason[-1] in punctuation else ''}"
                else: t += '.'
                try: await member.send(t)
                except discord.Forbidden: continue
                banlist.append(member.mention)
            except discord.Forbidden: continue
        if len(banlist) == 0:
            return await ctx.send("I was not able to ban any users.")
        await ctx.send(f"User{'s' if len(banlist) > 1 else ''} {', '.join(banlist)} successfully banned.")

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, members:commands.Greedy[discord.User], *, reason: Optional[str] = ""):
        """Unbans users.
        Both the bot and the runner **must be able to unban.**

        `unban <members> [reason]`"""
        if len(members) == 0: return
        ubanlist = []
        for member in members:
            if member == ctx.message.author: continue
            try:
                await ctx.guild.unban(member, reason=reason + (" " if reason != "" else "") + f"(Unbanned by {ctx.author})")
                ubanlist.append(member.mention)
            except discord.Forbidden: continue
        
        await ctx.send(f"User{'s' if len(ubanlist) > 1 else ''} {', '.join(ubanlist)} successfully unbanned.")

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, members:commands.Greedy[discord.Member], *, reason: Optional[str] = ""):
        """Kicks users.
        Both the bot and the runner **must be able to kick.**

        `kick <members> [reason]`"""
        #if len(args) == 0:
        #    await ctx.send("Please list a valid to ban.")
        #    return
        #try:
        #    memb = ctx.message.raw_mentions[0]
        #except:
        #    memb = int(args[0])
        if len(members) == 0: return
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
    async def purge(self, ctx: commands.Context, count = 100, member: Optional[discord.Member] = None):
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

    def now(self):
        return self.toInt(datetime.utcnow())    
    def toInt(self, dt):
        return int(datetime.timestamp(dt) * 1000000)
    def fromInt(self, dt):
        return datetime.fromtimestamp(dt  / 1000000)

    def majorWarns(self, warns):
        return list(filter(lambda x: (x['major']), warns))
    

    @commands.Cog.listener()
    async def on_member_join(self, member):
        mpm = self.testforguild(member.guild)
        mpk = mpm.data
        try: mpk['inwarn'][str(member.id)]
        except: return
        uid = str(member.id)
        if mpk['inwarn'][uid]['left'] != 0:
            mpk['inwarn'][uid]['time'] += self.now() - mpk['inwarn'][uid]['left']
            mpk['inwarn'][uid]['left'] = 0
        ofc = mpk['offences'][str(len(mpk['users'][uid]))]
        act = copy.deepcopy(mpk['actions'][ofc['action']])
        if (act['type'] == "gr"):
            await member.add_roles(member.guild.get_role(act['role']), reason="User rejoined while in punishment.")    
        mpm.save()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        mpm = self.testforguild(member.guild)
        mpk = mpm.data
        try: mpk['inwarn'][str(member.id)]
        except: return
        uid = str(member.id)
        if mpk['inwarn'][uid]['left'] == 0:
            mpk['inwarn'][uid]['left'] = self.now()

        mpm.save()
    
    @tasks.loop(seconds=30, reconnect=True)
    async def timeaction(self):
        print('we exist')
        gids = []
        for x in os.listdir("config"):
            if os.path.isfile(f"config/{x}/moderation.mpk"):
                gids.append(x)
        for gid in gids:
            changed = False
            guild = self.bot.get_guild(int(gid))
            if (guild == None): continue
            mpm = self.testforguild(guild)
            mpk = mpm.data
            for uid in list(mpk['inwarn']):
                try: mpk['inwarn'][uid]['time']
                except: continue
                #print(uid)

                try: user = await guild.fetch_member(uid)
                except discord.NotFound: user = None 
                print(uid + " " + str(user))
                if user == None:
                    if mpk['inwarn'][uid]['left'] == 0:
                        mpk['inwarn'][uid]['left'] = self.now()
                        changed = True
                    continue
                if mpk['inwarn'][uid]['left'] != 0:
                    mpk['inwarn'][uid]['time'] += self.now() - mpk['inwarn'][uid]['left']
                    mpk['inwarn'][uid]['left'] = 0
                    changed = True
                    continue
                
                try: cnt = len(self.majorWarns(mpk['users'][uid]))
                except KeyError:
                    del mpk['inwarn'][uid]
                    changed = True
                    continue

                #print(uid)
                if (mpk['inwarn'][uid]['time'] <= self.now()):
                    print(gid)
                    try: print(mpk['users'][uid])
                    except KeyError: print("fuck")
                    if cnt != 0:
                        ofc = mpk['offences'][str(cnt)]
                        #print(ofc)
                        act = copy.deepcopy(mpk['actions'][ofc['action']])
                        #print(act)
                        if (act['type'] == "gr"):
                            await user.remove_roles(guild.get_role(act['role']), reason="Time for warning ran out.")    
                        
                    del(mpk['inwarn'][uid])
                    changed = True
                    try: await user.send("The above message's time is now over.")
                    except: pass
            if changed: mpm.save()
        print('we exist')

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True, kick_members=True)
    async def clearwarns(self, ctx, user: discord.Member):
        mpm = self.testforguild(ctx.guild)
        mpk = mpm.data
        uid = str(user.id)
        mpk['users'][uid] = []
        mpm.save()
        await ctx.send(f"Cleared warnings for {user.mention}!")

    @commands.command(aliases=["w"])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True, kick_members=True)
    async def warn(self, ctx, users: Greedy[discord.Member], *, reason):
        """Warns users.
        The bot must be able to do the action given, and
        the user calling it must be able to **manage messages and kick.**
        
        `warn/w <users> <reason>`"""
        mpm = self.testforguild(ctx.guild)
        mpk = mpm.data
        if (len(reason) == 0): return
        for user in users:
            uid = str(user.id)
            try:
                mpk['users'][uid]
            except:
                mpk['users'][uid] = []

            cnt = len(mpk['users'][uid])

            mpk['users'][uid].append({})
            mpk['users'][uid][cnt]['reason'] = reason
            mpk['users'][uid][cnt]['timestamp'] = self.now()
            mpk['users'][uid][cnt]['who'] = ctx.author.id
            mpk['users'][uid][cnt]['major'] = True

            ofc = mpk['offences'][str(len(self.majorWarns(mpk['users'][uid])))]
            act = copy.deepcopy(mpk['actions'][ofc['action']])

            worked = True
            try:
                if   (act['type'] == "gr"): await user.add_roles(ctx.guild.get_role(act['role']), reason=reason)
                elif (act['type'] == "k"): await user.kick(reason=reason)
                elif (act['type'] == "b" ): await user.ban(reason=reason)
            except: 
                worked = False
                #print(e.with_traceback())

            if (not worked):
                await ctx.send("I'm not able to take action, but the user will be warned.")
                act['dmmsg'] = "I'm not able to take the action I'm told to take, but you are still warned for [r]."
            
            act['dmmsg'] = act['dmmsg'].replace('[r]', reason)
            act['msg'] = act['msg'].replace('[u]', user.mention)

            if (worked):
                try:
                    if (act['timed']):
                        act['dmmsg'] = act['dmmsg'].replace('[t]', str(ofc['time']))
                        act['msg'] = act['msg'].replace('[t]', str(ofc['time']))

                        mpk['inwarn'][uid] = {}
                        mpk['inwarn'][uid]['left'] = 0
                        mpk['inwarn'][uid]['time'] = self.toInt(datetime.utcnow() + timedelta(minutes=ofc['time']))
                except KeyError:
                    pass

            if (act['dmmsg'] != ""):
                try: await user.send(act['dmmsg'])
                except discord.Forbidden: pass
            if (worked): await ctx.send(act['msg'])

        mpm.save()
        await self.bot.cogs['Logging'].on_warn(user, mpk['users'][uid][cnt], ofc['action'].title())

    @commands.command(aliases=['vwarn', 'vw'])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True, kick_members=True)
    async def verbalwarn(self, ctx, users: Greedy[discord.Member], *, reason):
        """Warns users but does not apply punishment.
        The user calling it must be able to **manage messages and kick.**
        These are intended to be used as a sort of push saying "don't do that",
        and will never automatically culminate into a warn.

        `verbalwarn/vwarn/vw <users> <reason>`"""
        mpm = self.testforguild(ctx.guild)
        mpk = mpm.data
        try: mpk['actions']['verbal']
        except: return
        if (len(reason) == 0): return
        for user in users:
            uid = str(user.id)
            try:
                mpk['users'][uid]
            except:
                mpk['users'][uid] = []

            cnt = len(mpk['users'][uid])

            mpk['users'][uid].append({})
            mpk['users'][uid][cnt]['reason'] = reason
            mpk['users'][uid][cnt]['timestamp'] = self.now()
            mpk['users'][uid][cnt]['who'] = ctx.author.id
            mpk['users'][uid][cnt]['major'] = False

            act = copy.deepcopy(mpk['actions']['verbal'])

            act['dmmsg'] = act['dmmsg'].replace('[r]', reason)
            act['msg'] = act['msg'].replace('[u]', user.mention)

            if (act['dmmsg'] != ""):
                try: await user.send(act['dmmsg'])
                except: pass
            await ctx.send(act['msg'])

        await self.bot.cogs['Logging'].on_warn(user, mpk['users'][uid][cnt], None)
        
        mpm.save()


    @commands.command(aliases=['warnings'])
    @commands.guild_only()
    async def warns(self, ctx, user: Optional[discord.Member]):
        """Check warns.
        If no user is given, it will display your own.
        If you give a user, you **must be able to**
        **manage messages and kick.** 
        
        `warns/warnings [user]`"""
        if (len(user) == 0): user = ctx.author
        else: user = user[0]
        if (user != ctx.author):
            if (not (ctx.author.guild_permissions.manage_messages and ctx.author.guild_permissions.kick_members)):
                return
        mpm = self.testforguild(ctx.guild)
        mpk = mpm.data
        #gid = str(ctx.guild.id)
        uid = str(user.id)
        embed = discord.Embed(color=(discord.Color(0x6CAD9C) if user.color == discord.Color.default() else user.color))
        embed.set_author(name=user.display_name, icon_url=user.avatar_url)
        embed.timestamp = datetime.utcnow()
        embed.title = f"Warnings"

        try: mpk['users'][uid]
        except: mpk['users'][uid] = []
        
        desc = ""
        if (len(mpk['users'][uid]) == 0): desc = "__No warnings!__"
        for warn in reversed(mpk['users'][uid]):
            who = await ctx.guild.fetch_member(warn['who'])
            reason = f"*{warn['reason']}*"
            if (warn['major']): reason = f"*{reason}*"
            desc += f"> {reason} - {who.mention}\n> *{timeago.format(self.fromInt(warn['timestamp']), datetime.utcnow())}*\n> `-------------`\n"
        if (len(mpk['users'][uid]) != 0): desc = desc[:-18]
        embed.description = desc
        await ctx.send(embed=embed)

current = 0

def setup(bot):
    bot.add_cog(Moderation(bot))