import discord, math, re, difflib
from discord.ext import commands, tasks, menus
from datetime import datetime, timedelta
from cogs.utils.embeds import embeds
from typing import Union, List, Optional
import cogs.utils.mpk as mpku
from discord import AuditLogAction

bitlist = ["Message Delete", "Message Edit", "Channel Edits", "Member Joining/Leaving", 
    "Member Updates", "Server Updates", "Role Updates", "Emoji Updates", "Voice Updates",
    "Bans", "Warnings", "Bots can trigger some logs", "Starboard Logging"]
class LogMenu(menus.Menu):
    def __init__(self, gid, datadict, prefix):
        super().__init__(timeout = 30.0, delete_message_after=False, clear_reactions_after=True)
        self.mpk = mpku.MPKManager("moderation", gid)
        self.page = 0
        self.max = math.ceil(float(len(bitlist)) / 5)
        self.color = discord.Color(datadict['color'])
        self.prefix = prefix
        self.shown = 5
        self.message = None

    async def editmessage(self):
        trimmedlist = bitlist[(self.page * 5):(self.page * 5 + 5)]
        self.shown = len(trimmedlist)
        embed = discord.Embed(title = "Log Config", color=self.color, description = "")
        for i in range(len(bitlist)):
            unic = '\u2705' if (self.mpk.data['log']['flags'] >> i) & 1 else '\u26D4'
            num = ""
            if self.page * 5 <= i <= self.page * 5 + 4: 
                ch = i - self.page * 5
                if   ch == 0: num = "\u0031"
                elif ch == 1: num = "\u0032"
                elif ch == 2: num = "\u0033"
                elif ch == 3: num = "\u0034"
                elif ch == 4: num = "\u0035"
            if not num: num = "\U0001F7E6 "
            else: num += "\uFE0F\u20e3 "
            embed.description += f"{num}{bitlist[i]}: {unic}\n"
        embed.set_footer(text="Use the reactions to toggle the flags.")
        return await self.message.edit(content = "", embed=embed)

    async def prompt(self, ctx):
        await self.start(ctx)
    async def send_initial_message(self, ctx, channel):
        ret = self.message = await channel.send("Please wait..")
        await self.editmessage()
        return ret
    async def finalize(self):
        embed = discord.Embed(title = "Log Config - Saved", color=self.color, description = "")
        for i in range(len(bitlist)):
            unic = '\u2705' if (self.mpk.data['log']['flags'] >> i) & 1 else '\u26D4'
            embed.description += f"{bitlist[i]}: {unic}\n"
        await self.message.edit(embed=embed)
        self.mpk.save()

    @menus.button("\U0001F53C") #up
    async def leftpage(self, payload):
        if not payload.member: return
        self.page = max(self.page - 1, 0)
        await self.editmessage()
        await self.message.remove_reaction("\U0001F53C", payload.member)
    @menus.button("\U0001F53D") #down
    async def rightpage(self, payload):
        if not payload.member: return
        self.page = min(self.page + 1, self.max)
        await self.editmessage()
        await self.message.remove_reaction("\U0001F53D", payload.member)
    @menus.button("\u23F9") #stop
    async def stopemote(self, _unusedpayload):
        self.stop()

    @menus.button("\u0031\uFE0F\u20e3") #1
    async def bit1(self, payload):
        if not payload.member: return
        if self.shown >= 1:
            self.mpk.data['log']['flags'] ^= 1 << (self.page * 5 + 0)
            await self.editmessage()    
        await self.message.remove_reaction("\u0031\uFE0F\u20e3", payload.member)
    @menus.button("\u0032\uFE0F\u20e3") #2
    async def bit2(self, payload):
        if not payload.member: return
        if self.shown >= 2:
            self.mpk.data['log']['flags'] ^= 1 << (self.page * 5 + 1)
            await self.editmessage()
        await self.message.remove_reaction("\u0032\uFE0F\u20e3", payload.member)
    @menus.button("\u0033\uFE0F\u20e3") 
    async def bit3(self, payload):
        if not payload.member: return
        if self.shown >= 3:
            self.mpk.data['log']['flags'] ^= 1 << (self.page * 5 + 2)
            await self.editmessage()
        await self.message.remove_reaction("\u0033\uFE0F\u20e3", payload.member)
    @menus.button("\u0034\uFE0F\u20e3") 
    async def bit4(self, payload):
        if not payload.member: return
        if self.shown >= 4:
            self.mpk.data['log']['flags'] ^= 1 << (self.page * 5 + 3)
            await self.editmessage()
        await self.message.remove_reaction("\u0034\uFE0F\u20e3", payload.member)
    @menus.button("\u0035\uFE0F\u20e3") 
    async def bit5(self, payload):
        if not payload.member: return
        if self.shown >= 5:
            self.mpk.data['log']['flags'] ^= 1 << (self.page * 5 + 4)
            await self.editmessage()
        await self.message.remove_reaction("\u0035\uFE0F\u20e3", payload.member)

class Logging(commands.Cog):


    def __init__(self, bot: discord.Client):
        # pylint: disable=no-member
        self.bot = bot
        self.arrow = "\u2192"
        self.invites = {}
        self.setupinv.start()

    @tasks.loop(count=1) #hacky but do not care
    async def setupinv(self):
        print("fetching invites")
        for guild in self.bot.guilds:
            try: self.invites[guild.id] = await guild.invites()
            except discord.Forbidden: pass
        print("done")


    ######FUNCTIONS######
    def getmpm(self, guild) -> mpku.MPKManager:
        return mpku.MPKManager("moderation", guild.id)
    
    def setupjson(self, guild):
        mpm = self.getmpm(guild)
        mpk = mpm.data
        try: mpk['log']
        except: mpk['log'] = {
            'flags': 0b11111111111,
            'channel': 0
        }
        mpm.save()
        return mpk

    def getbit(self, val, pos):
        return bool((val >> (pos - 1)) & 1)
    def toggle(self, val, bits):
        return val ^ bits
    def forceset(self, val, on, pos):
        return val ^ (-on ^ val) & (1 << (pos - 1))

    async def checkbit(self, pos, gid, full = False, holdoff = False) -> Union[discord.TextChannel, mpku.MPKManager]:
        if not gid: return None
        if (type(gid) == int):
            guild = self.bot.get_guild(gid)
            if not guild: return None
        elif (type(gid) == discord.Guild): guild = gid
        try: 
            if not holdoff: 
                self.invites[guild.id] = await guild.invites()
        except discord.Forbidden: pass
        mpk = self.getmpm(guild).data
        try: mpk['log']['flags']
        except: return None
        if (not self.getbit(mpk['log']['flags'], pos)):
            return None
        if full: return self.getmpm(guild)
        else: return (guild.get_channel(mpk['log']['channel']) if mpk['log']['channel'] != 0 else None)
    
    def makebase(self, member, timestamp=None, colortype = 2) -> discord.Embed:
        if not timestamp: timestamp = datetime.utcnow()
        if (type(member) == discord.Member):
            embed = discord.Embed(color=(discord.Color(self.bot.data['color']) if member.color == discord.Color.default() else member.color))
            embed.set_author(name=member.display_name, icon_url=member.avatar_url)
        elif (type(member) == discord.Guild):
            embed = discord.Embed(color=discord.Color(self.bot.data['color']))
            embed.set_author(name=f"{member}", icon_url=str(member.icon_url))
        else:
            embed = discord.Embed(color=discord.Color(self.bot.data['color']))
            embed.set_author(name=f"{member}", icon_url=member.avatar_url)
        if (colortype != 2):
            if (colortype): embed.color = discord.Color(0x59b539)
            else: embed.color = discord.Color(0xdd2e44)
        embed.timestamp = timestamp
        if (type(member) != discord.Guild):
            embed.set_footer(text=f"User ID: {member.id}")

        return embed

    async def getaudit(self, act: Union[AuditLogAction, List[AuditLogAction]], guild: discord.Guild, limit=3, target=None, uselist=False, after=None) -> Union[discord.AuditLogEntry, List[discord.AuditLogEntry]]:
        if (uselist): result = []
        actions = [act]
        if type(act) == list:
            actions = act
        for action in actions:
            async for log in guild.audit_logs(limit=limit, action=action):
                if (((log.target == target) if (type(target) != int) else (log.target.id == target)) if target else True):
                    if (after):
                        if (log.created_at < datetime.utcnow() - timedelta(seconds=5)): continue
                    if (uselist): result.append(log) 
                    else: return log
        return None if not uselist else result
    
    def changestodict(self, changes: discord.AuditLogChanges):
        result = {}
        for changed in iter(changes.before):
            result[changed[0]] = [changed[1]]
        for change in iter(changes.after):
            result[change[0]].append(change[1])
        return result

    def changedicttostr(self, dict, create=False, masklst=None):
        result = ""           
        if not masklst: masklst = [] 
        for val in dict:
            if val in masklst: continue
            if (create != 2) and (dict[val][0] == dict[val][1]): continue
            prestr = ""
            if not create:
                prestr = f"`{dict[val][0]}` *{self.arrow}* "
            after = 1 if create != 2 else 0
            valstr = dict[val][after]
            if type(dict[val][after]) == discord.colour.Colour:
                if dict[val][after] == discord.Color.default():
                    valstr = "(default color)"
            result += f"> **{val.replace('_', ' ').title()}**: {prestr}`{valstr}`\n"
        return result
    
    def permstostr(self, perms, compare = None):
        ret = "```diff\n"
        if not compare:
            for x in iter(perms):
                ret += f"{'+' if x[1] else '-' if x[1] == False else '~'} {x[0].replace('_', ' ').title().replace('Tts', 'TTS')}\n"
        else:
            cmplist = {}
            for x in iter(compare):
                cmplist.update({x[0]: x[1]})
            for x in iter(perms):
                if (x[0] in cmplist) and (x[1] != cmplist[x[0]]):
                    ret += f"{'+' if x[1] else '-' if x[1] == False else '~'} {x[0].replace('_', ' ').title().replace('Tts', 'TTS')}\n"
        if ret == "```diff\n": 
            return None
        return ret + "\n```"
    
    def capitalize(self, stri, cap):
        if (type(cap) == str):
            return re.sub(fr"{cap}(.*:)", fr"{cap.upper()}\1", stri,  flags=re.IGNORECASE)
        else:
            result = stri
            for x in cap:
                result = re.sub(fr"{x}(.*:)", fr"{x.upper()}\1", result,  flags=re.IGNORECASE)
            return result

    ######COMMANDS#######

    @commands.group(aliases=['logs'])
    @commands.has_permissions(manage_guild=True)
    async def log(self, ctx):
        """Sets up logging.
        
        `log/logs`
        `log cfg`
        `log cfg channel/setchannel [channel]`"""
        self.setupjson(ctx.guild)
        if (ctx.invoked_subcommand == None):
            mpk = self.getmpm(ctx.guild).data
            embed = discord.Embed(title = "Log Config", color=discord.Color(self.bot.data['color']), description = "")
            for i in range(len(bitlist)):
                unic = '\u2705' if (mpk['log']['flags'] >> i) & 1 else '\u26D4'
                embed.description += f"{bitlist[i]}: {unic}\n"
            embed.description += f"Channel: <#{mpk['log']['channel']}>" if mpk['log']['channel'] else "Channel: *not set*"
            await ctx.send(embed=embed)
    
    @log.group(aliases = ['cfg'])
    async def config(self, ctx):
        if not ctx.invoked_subcommand:
            await LogMenu(ctx.guild.id, self.bot.data, ctx.prefix).prompt(ctx)

    @config.command(aliases = ['setchannel'])
    @commands.has_permissions(manage_guild=True)
    async def channel(self, ctx, channel: Optional[discord.TextChannel]):
        if not channel: return await ctx.invoke(self.log)
        mpm = self.getmpm(ctx.guild)
        mpm.data['log']['channel'] = channel.id
        mpm.save()
        await ctx.send(f"Log channel set to {channel.mention}!")

    #######EVENTS########
    #@commands.Cog.listener()
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        chn = await self.checkbit(1, message.guild)
        if not chn: return
        if not (await self.checkbit(12, message.guild)):
            if message.author.bot: return
        log = await self.getaudit(AuditLogAction.message_delete, message.guild, after=True)
        embed = await embeds.buildembed(embeds, message, link=False, attachmode=0b11)
        embed.color = discord.Color(0xDC322F)
        embed.title = "Message Deletion"
        embed.timestamp = message.created_at
        try:
            past = (await message.channel.history(limit=1, before=message.created_at).flatten())[0]
            if (past):
                embed.description += f"\n[(jump to message before this)]({past.jump_url})"
        except: pass
        if (log):
            embed.description += f"\n> **Deleted by** {log.user.mention}"
        embed.set_footer(text=f"Message ID: {message.id} | User ID: {message.author.id}")

        await chn.send(embed=embed)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: List[discord.Message]):
        chn = await self.checkbit(1, messages[0].guild)
        if not chn: return
        totaldict = {}
        embed = self.makebase(messages[0].guild, colortype=0)
        log = await self.getaudit(AuditLogAction.message_bulk_delete, messages[0].guild, after=True)
        possible = int(log.extra['count']) if log else 0

        embed.description = ""
        for m in messages:
            if not m.author.id in totaldict:
                totaldict[m.author.id] = 0
            totaldict[m.author.id] += 1 
            if possible: possible -= 1
        for uid in totaldict:
            embed.description += f"<@{uid}>: **{totaldict[uid]}** messages\n"
        if possible:
            embed.description += f"Unknown: **{possible}** messages\n"
        embed.color = discord.Color(0xDC322F)
        embed.title = "Bulk Message Deletion"
        if (log):
            embed.description += f"> **Deleted by** {log.user.mention}"
            embed.set_footer(text=f"User ID: {log.user.id}")

        ttlist = []
        for m in messages:
            ttlist.append(m.created_at)
        first = min(ttlist)
        last = max(ttlist)

        print(first)
        print(last)

        embed.timestamp = first

        try:
            first = (await messages[0].channel.history(limit=1, before=first).flatten())[0]
            if (first): embed.description += f"\n[(message before these)]({first.jump_url})"
        except: pass
        await chn.send(embed=embed)

    
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        guild = self.bot.get_guild(int(payload.guild_id))
        if (payload.cached_message): return
        chn = await self.checkbit(1, guild)
        if not chn: return

        log = await self.getaudit(AuditLogAction.message_delete, guild, after=True)
        ch = guild.get_channel(payload.channel_id)
        if (log):
            embed = self.makebase(log.target, colortype=0)
            embed.description = f"Message by {log.target.mention} deleted by {log.user.mention} in {ch.mention}"
            embed.set_footer(text=f"Message ID: {payload.message_id} | User ID: {log.target.id}")
        else:
            embed = self.makebase(guild, colortype = 0) 
            embed.description = f"Message deleted in {ch.mention}"
            embed.set_footer(text=f"Message ID: {payload.message_id}")
        embed.title = "Message Deletion"
        embed.timestamp = discord.utils.snowflake_time(payload.message_id)

        past = (await ch.history(limit=1, before=embed.timestamp).flatten())[0]
        if (past):
            embed.description += f"\n[(jump to message before this)]({past.jump_url})"
        
        await chn.send(embed=embed)
    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent):
        guild = self.bot.get_guild(payload.guild_id)
        chn = await self.checkbit(1, payload.guild_id)
        if not chn: return
        if len(payload.cached_messages): return
        totallist = payload.message_ids

        log = await self.getaudit(AuditLogAction.message_bulk_delete, guild, after=True)
        ch = guild.get_channel(payload.channel_id)
        embed = self.makebase(guild, colortype=0)
        if log:
            embed.description = f"**{len(totallist)}** messages deleted by {log.user.mention} in {ch.mention}"
            embed.set_footer(text=f"User ID: {log.user.id}")
        else: embed.description = f"**{len(totallist)}** messages deleted in {ch.mention}"
        embed.title = "Bulk Message Deletion"

        ttlist = []
        for m in totallist:
            ttlist.append(discord.utils.snowflake_time(m))
        first = min(ttlist)
        embed.timestamp = first

        try:
            first = (await ch.history(limit=1, before=first).flatten())[0]
            if (first): embed.description += f"\n[(message before these)]({first.jump_url})"
        except: pass
        await chn.send(embed=embed)


    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if (after.author.id == self.bot.user.id): return
        if (before.content == after.content): return
        if not (await self.checkbit(12, after.guild)):
            if after.author.bot: return
        chn = await self.checkbit(2, after.guild)
        if not chn: return
        l = [before.content.splitlines(), after.content.splitlines()]
        embed = self.makebase(after.author)
        embed.title = "Message Edit"

        str = '\n'.join(list(difflib.Differ().compare(l[0], l[1])))
        str = str.replace("? ", "  ")
        if len(str) == 0: return 
        embed.description = f"[(jump to message)]({after.jump_url})\n```diff\n{str}```"
        await chn.send(embed=embed)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        try: payload.data['guild_id']
        except: return
        try: 
            if (payload.data['content'] == ""): return
        except KeyError: return
        guild = self.bot.get_guild(int(payload.data['guild_id']))
        chn = await self.checkbit(2, guild)
        if not chn: return
        if (payload.cached_message): return
        msg = await guild.get_channel(payload.channel_id).fetch_message(payload.message_id)
        embed = self.makebase(msg.author)
        embed.title = "Message Edit"
        embed.description = f"Message edited in <#{payload.channel_id}>\n[(jump to message)]({msg.jump_url})"
        await chn.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.TextChannel):
        chn = await self.checkbit(3, channel.guild)
        if not chn: return
        log = await self.getaudit(AuditLogAction.channel_create, channel.guild, after=True)
        embed = self.makebase(log.user, log.created_at)
        isVoice = type(channel) == discord.VoiceChannel
        isCategory = type(channel) == discord.CategoryChannel
        embed.title = f"Channel Created ({'Voice' if isVoice else 'Text'})"
        if isCategory:
            embed.title = "Category Created"
        embed.description =  (channel.mention + "\n") if not isVoice else ""
        embed.description += f"> **Name**: {channel.name}\n" #thats literally all we fucking have control over when we make a new channel
        if not isCategory: embed.description += f"> **Synced with category**: {channel.permissions_synced}"
        embed.set_footer(text=f"{'Channel' if not isCategory else 'Category'} ID: {channel.id} | {embed.footer.text}")
        if (isCategory) or (not channel.permissions_synced):
            txt = ""
            for x in iter(channel.overwrites):
                append = self.permstostr(channel.overwrites_for(x))
                check = list(append.split("\n"))
                del check[-1]
                del check[0]
                total = True
                for y in check:
                    if not y.startswith('~'):
                        total = False
                        break
                if (not total) and append:
                    txt += x.mention + append
            txt = list(txt.split("\n"))
            for x in list(txt):
                if x.startswith('~'):
                    txt.remove(x)
            embed.add_field(name="Permissions", value='\n'.join(txt).strip())
        await chn.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        chn = await self.checkbit(3, channel.guild)
        if not chn: return
        log = await self.getaudit(AuditLogAction.channel_delete, channel.guild, after=True)
        embed = self.makebase(log.user, log.created_at)
        isVoice = type(channel) == discord.VoiceChannel
        isCategory = type(channel) == discord.CategoryChannel
        embed.title = f"Channel Deleted ({'Voice' if isVoice else 'Text'})"
        if isCategory:
            embed.title = "Category Deleted"
        embed.description = ""
        dic = {
            'name': [channel.name], 
            'position': [channel.position], 
            'synced': [channel.permissions_synced]}
        if not isCategory:
            dic.update({'category': [channel.category]})
        if isVoice:
            dic.update({'bitrate': [channel.bitrate]})
        elif not isCategory:
            dic.update({
                'slowmode_delay': [channel.slowmode_delay], 
                'nsfw': [channel.is_nsfw()], 
                'topic': [channel.topic]})
        embed.description += self.capitalize(self.changedicttostr(dic, create=2), 'NSFW')
        embed.set_footer(text=f"{'Channel' if not isCategory else 'Category'} ID: {channel.id} | {embed.footer.text}")
        if (isCategory) or (not channel.permissions_synced):
            txt = ""
            for x in iter(channel.overwrites):
                append = self.permstostr(channel.overwrites_for(x))
                check = list(append.split("\n"))
                del check[-1]
                del check[0]
                total = True
                for y in check:
                    if not y.startswith('~'):
                        total = False
                        break
                if (not total) and append:
                    txt += x.mention + append
            txt = list(txt.split("\n"))
            for x in list(txt):
                if x.startswith('~'):
                    txt.remove(x)
            embed.add_field(name="Permissions", value='\n'.join(txt).strip())
        await chn.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        chn = await self.checkbit(3, after.guild)
        if not chn: return
        #im going to rip my fucking hair out
        actlist = [AuditLogAction.overwrite_update, AuditLogAction.overwrite_create, AuditLogAction.overwrite_delete, AuditLogAction.channel_update]
        log = await self.getaudit(actlist, after.guild, after=True)
        if not (await self.checkbit(12, after.guild)):
            if log and log.user.bot: return
        if log: embed = self.makebase(log.user, log.created_at)
        else: embed = self.makebase(after.guild) #why is this needed? im not sure myself
        isVoice = type(after) == discord.VoiceChannel
        isCategory = type(after) == discord.CategoryChannel
        embed.title = f"Channel Edited ({'Voice' if isVoice else 'Text'})"
        if isCategory:
            embed.title = "Category Edited"
        embed.description =  after.mention + "\n"
        dic = {
            'name': [before.name, after.name], 
            'position': [before.position, after.position], 
            'synced': [before.permissions_synced, after.permissions_synced]}
        if not isCategory:
            dic.update({'category': [before.category, after.category]})
        if isVoice:
            dic.update({'bitrate': [before.bitrate, after.bitrate]})
        elif not isCategory:
            dic.update({
                'slowmode_delay': [before.slowmode_delay, after.slowmode_delay], 
                'nsfw': [before.is_nsfw(), after.is_nsfw()], 
                'topic': [before.topic, after.topic]})
        if before.position == after.position: del dic['position']
        embed.description += self.capitalize(self.changedicttostr(dic), 'NSFW')
        embed.set_footer(text=f"{'Channel' if not isCategory else 'Category'} ID: {after.id} | {embed.footer.text}")
        pre = []
        for x in iter(before.overwrites):
            pre.append(x)
        if before.overwrites != after.overwrites:
            txt = ""
            for x in iter(after.overwrites):
                if (after.overwrites_for(x) != before.overwrites_for(x)):
                    txt += x.mention + self.permstostr(after.overwrites_for(x), before.overwrites_for(x))
                if x in pre: pre.remove(x)
            if txt:
                embed.add_field(name="Permissions", value=txt.strip())
                txt = ""
            for x in pre:
                txt += x.mention + self.permstostr(before.overwrites_for(x))
            if txt:
                txt = list(txt.split("\n"))
                for x in list(txt):
                    if x.startswith('~'):
                        txt.remove(x)
                embed.add_field(name="Removed", value='\n'.join(txt).strip(), inline = False)
        if (embed.description == after.mention + "\n") and not len(embed.fields): return
        await chn.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        chn = await self.checkbit(4, member.guild, holdoff=True)
        if not chn: return
        log = await self.getaudit(AuditLogAction.invite_create, member.guild)
        invite = None
        positive = False
        attempt = not member.bot
        try: self.invites[member.guild.id]
        except KeyError: attempt = False
        if (attempt): 
            #first check each of the invites
            for inv in self.invites[member.guild.id]:
                invite = discord.utils.find(lambda x: x.code == inv.code, await member.guild.invites()) 
                if (not invite):
                    if (inv.max_uses):
                        #this is MORE THAN LIKELY it
                        positive = True
                        invite = [inv.code, inv.inviter.id]
                        break
                else:
                    if (inv.uses + 1 <= invite.uses): #DEFINITELY it
                        positive = True
                        invite = [invite.code, invite.inviter.id]
                        break
                    else: invite = None
            if (not invite):
                if log: #probably it, most recent
                    invite = [log.after.code, log.user.id]
        self.invites[member.guild.id] = await member.guild.invites()
        embed = self.makebase(member, colortype=1)
        embed.title = "Member Join"
        embed.description = f"User **{member}** joined!"
        if (invite):
            embed.description += f"\n> **Invite code{' (maybe, most recent)' if not positive else ''}**: *{invite[0]}*\n> **Invited by**: *<@{invite[1]}>*"
        
        await chn.send(embed=embed)
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        chn = await self.checkbit(4, member.guild)
        if not chn: return
        embed = self.makebase(member, colortype=0)
        log = await self.getaudit(AuditLogAction.ban, member.guild, target=member.id, after=True)
        if (log): return
        log = await self.getaudit(AuditLogAction.kick, member.guild, target=member.id, after=True)
        if (log):
            print(log.user)
            embed.title = "Member Kick"
            embed.description = f"User **{member.mention}** was kicked!\n> **{'(No reason)' if not log.reason else log.reason}** - *{log.user.mention}*"
        else:
            embed.title = "Member Leave"
            embed.description = f"User **{member.mention}** left."
        await chn.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        chn = await self.checkbit(5, after.guild)
        if not chn: return
        if ((before.nick == after.nick) and (before.roles == after.roles)): return
        rolediff = []
        if (before.roles != after.roles):
            rolediff.append(list(set(before.roles) - set(after.roles))) #removed roles
            rolediff.append(list(set(after.roles) - set(before.roles))) #added roles
        embed = self.makebase(after)
        embed.description = ""
        log = await self.getaudit([AuditLogAction.member_role_update, AuditLogAction.member_update], after.guild, target=after.id, after=True)
        bystr = log and log.user != after
        if (before.nick != after.nick): 
            embed.description += f"**Nickname:** *{before.nick}* {self.arrow} *{after.nick}*"
            if bystr: embed.description += f" - {log.user.mention}"
        elif rolediff:
            msg = ""
            #you can only be given/revoked multiple at a time but not both at the same
            if rolediff[1]:
                msg += f"Given {', '.join([x.mention for x in rolediff[1]])}"
            elif rolediff[0]:
                msg += f"Removed {', '.join([x.mention for x in rolediff[1]])}"
            if msg:
                embed.description += f"{msg}"
                if bystr: embed.description += f" by {log.user.mention}"
        embed.title = "Member Update"
        if not embed.description: return
        await chn.send(embed=embed)

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        for guild in self.bot.guilds:
            chn = await self.checkbit(5, guild)
            if not chn: continue
            if (str(before) == str(after)): continue
            memb = guild.get_member(after.id)
            if not memb: return
            embed = self.makebase(memb)
            if (before.name != after.name): userstr = f"__{memb.name}__"
            else: userstr = f"{memb.name}"
            if (before.discriminator != after.discriminator): discstr = f"__{memb.discriminator}__"
            else: discstr = f"{memb.discriminator}"
            embed.description = f"**{before}** {self.arrow} **{userstr}#{discstr}**"
            embed.title = "User Update"
            await chn.send(embed=embed)
            

    @commands.Cog.listener()
    async def on_guild_update(self, _unusedbefore, after):
        chn = await self.checkbit(6, after)
        if not chn: return
        log = await self.getaudit(AuditLogAction.guild_update, after)
        embed = self.makebase(log.user, log.created_at)
        embed.title = "Server Update"
        embed.description = self.changedicttostr(self.changestodict(log.changes))
        embed.description = self.capitalize(embed.description, "AFK")
        
        await chn.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        chn = await self.checkbit(7, role.guild)
        if not chn: return
        log = await self.getaudit(AuditLogAction.role_create, role.guild, after=True)
        embed = self.makebase(log.user, log.created_at)
        embed.title = "Role Created"
        embed.description =  role.mention + "\n"
        embed.description += self.changedicttostr(self.changestodict(log.changes), create=True, masklst=['colour', 'permissions'])
        embed.set_footer(text=f"Role ID: {role.id} | {embed.footer.text}")
        embed.add_field(name="Permissions", value=self.permstostr(role.permissions))
        await chn.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        chn = await self.checkbit(7, role.guild)
        if not chn: return
        log = await self.getaudit(AuditLogAction.role_delete, role.guild, after=True)
        embed = self.makebase(log.user, log.created_at)
        embed.title = "Role Deletion"
        embed.description = self.changedicttostr(self.changestodict(log.changes), create=2, masklst=['colour', 'permissions'])
        if role.color != discord.Color.default():
            embed.color = role.color
        embed.set_footer(text=f"Role ID: {role.id} | {embed.footer.text}")
        embed.add_field(name="Permissions", value=self.permstostr(role.permissions))
        await chn.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        chn = await self.checkbit(7, after.guild)
        if not chn: return
        log = await self.getaudit(AuditLogAction.role_update, after.guild, after=True)
        if after.id != log.target.id: return
        embed = self.makebase(log.user, log.created_at)
        embed.title = "Role Updated"
        dic = self.changestodict(log.changes)
        embed.description =  after.mention + "\n"
        embed.description += self.changedicttostr(dic, masklst=['colour', 'permissions'])
        if after.color != discord.Color.default():
            embed.color = after.color
        embed.set_footer(text=f"Role ID: {after.id} | {embed.footer.text}")
        if (before.permissions != after.permissions):
            embed.add_field(name="Permissions", value=self.permstostr(after.permissions, before.permissions))
        await chn.send(embed=embed)

    @commands.Cog.listener() 
    async def on_guild_emojis_update(self, guild, before, after):
        chn = await self.checkbit(8, guild)
        if not chn: return
        emoji = None
        if len(before) < len(after):
            emoji = list(set(after) - set(before))[0]
        elif len(before) > len(after):
            emoji = list(set(before) - set(after))[0]
        actlist = [AuditLogAction.emoji_update, AuditLogAction.emoji_create, AuditLogAction.emoji_delete]
        log = await self.getaudit(actlist, guild, after=True)
        if not emoji:
            emoji = log.target
        if log.action == AuditLogAction.emoji_update:
            embed = self.makebase(log.user)
            embed.description = f"> **Name**: `{log.before.name}` {self.arrow} `{log.after.name}`"
        else:
            embed = self.makebase(log.user, colortype=(log.action == AuditLogAction.emoji_create))
            embed.description = f"Emoji `{emoji.name}` {'added' if log.action == AuditLogAction.emoji_create else 'removed'}"
        embed.set_thumbnail(url=str(emoji.url))
        await chn.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        chn = await self.checkbit(9, member.guild)
        if not chn: return
        embed = self.makebase(member)
        catstr = ""
        if after.channel:
            if after.channel.category:
                catstr += f" in category `{after.channel.category.name}`"       
        else:
            if before.channel.category:
                catstr += f" in category `{before.channel.category.name}`"            
            embed.description = f"{member.mention} left channel `{before.channel.name}`{catstr}"
            return await chn.send(embed=embed)    
        if not before.channel:
            embed.description = f"{member.mention} joined channel `{after.channel.name}`{catstr}"
            return await chn.send(embed=embed)
        proplist = [x for x in dir(after) if not x.startswith('_')]
        diffdict = {}
        for x in proplist:
            diffdict[x] = [getattr(before, x, None), getattr(after, x, None)]
        embed.description = self.capitalize(self.changedicttostr(diffdict).replace("Deaf", "Deafen"), 'AFK')
        embed.description += f"> **In channel:** `{after.channel.name}`{catstr}"
        await chn.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        chn = await self.checkbit(10, guild)
        if not chn: return
        embed = self.makebase(user, colortype=0)
        log = await self.getaudit(AuditLogAction.ban, guild, target=user.id, after=True)
        embed.title = "Member Banned"
        embed.description = f"User **{user.mention}** was banned!\n> **{'(No reason)' if not log.reason else log.reason}** - *{log.user.mention}*"
        await chn.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        chn = await self.checkbit(10, guild)
        if not chn: return
        embed = self.makebase(user, colortype=1)
        log = await self.getaudit(AuditLogAction.unban, guild, target=user.id, after=True)
        embed.title = "Member Unbanned"
        embed.description = f"User **{user}** was unbanned!\n> **{'(No reason)' if not log.reason else log.reason}** - *{log.user.mention}*"
        await chn.send(embed=embed)

    async def on_warn(self, user, guild, warn, act):
        chn = await self.checkbit(11, guild)
        if not chn: return
        embed = self.makebase(user, colortype=int(not warn['major']) * 2)
        embed.title = f"{'Verbal ' if not warn['major'] else ''}Warning"
        warner = guild.get_member(warn['who'])
        embed.description = f"**{warn['reason']}** - *{warner.mention}*\n> **Punishment given**: *{act}*"
        
        await chn.send(embed=embed)

    async def on_sbreact(self, user, msg, act):
        chn = await self.checkbit(13, user.guild)
        if not chn: return
        embed = self.makebase(user)
        embed.title = "Starboard React"
        embed.description = f"**{user.mention}** {'added' if act else 'removed'} a star to [this message.]({msg.jump_url})"
        
        await chn.send(embed=embed)

def setup(bot):
    bot.add_cog(Logging(bot))