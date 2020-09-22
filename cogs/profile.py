import discord
from discord.ext import commands, tasks, menus

from cogs.utils.converters import UserLookup
from cogs.utils.menus import Confirm, Choice

from typing import Union, Optional, List
from datetime import datetime
import timeago
import cogs.utils.mpk as mpku
import pytz
import dateparser
from copy import copy

def getord(num):
    st = "th"
    if ((num % 100) > 10 and (num % 100) < 15): return str(num) + st
    n = num % 10
    if   (n == 1): st = st.replace("th", "st")
    elif (n == 2): st = st.replace("th", "nd")
    elif (n == 3): st = st.replace("th", "rd")
    return str(num) + st

fields = ['name', 'realname', 'pronoun', 'birthday', 'bio', 'location', 'tz']
isdst = lambda tz: bool(datetime.now(tz).dst()) #https://stackoverflow.com/a/19968515

class TZMenu(menus.Menu):
    #this is gonna be the weirdest, most disgusting 
    #mesh of a paginator and a poll-like system
    #i have NO idea how else i'd be able to do it
    def __init__(self, tzd, c):
        super().__init__()
        self.tzd = tzd
        for x in ['\u25C0', '\u25B6']:
            self.add_button(menus.Button(x, self.handler))
        for x in range(1, 6):
            self.add_button(menus.Button(str(x) + "\uFE0F\u20E3", self.pick))
        self.ebase = discord.Embed(title="Timezone Selector", color=c)
        self.page = 0
        self.deepl = []
        self.current = tzd
        self.base = tzd
        self.list = [x + "/" if tzd[x] else x for x in tzd]
        self.result = None

    async def pick(self, payload: discord.RawReactionActionEvent):
        if not (payload.member): return
        il = [str(x) + "\uFE0F\u20E3" for x in range(1, 6)]
        try: picked = self.list[self.page * 5 + il.index(payload.emoji.name)]
        except IndexError: return await self.handler(payload)
        self.deepl.append(picked[:-1])
        try: self.current = self.current[self.deepl[-1]]
        except: 
            #we found it 
            self.result = '/'.join(self.deepl) + picked[-1]
            return self.stop()
        self.list = [x + "/" if self.current[x] else x for x in self.current]
        self.page = 0 
        await self.handler(payload)

    async def send_initial_message(self, ctx, channel):
        m = await channel.send(embed=self.ebase)
        fakep = discord.RawReactionActionEvent({'message_id': 0, 'channel_id': 0, 'user_id': 0}, discord.PartialEmoji(name='\u25C0'), "REACTION_ADD")
        self.message = m
        await self.handler(fakep)
        return m

    async def handler(self, payload):
        if (not payload.member) and payload.message_id: return
        pw = self.message.embeds[0]
        pw.set_footer(text="Please wait...")
        await self.message.edit(content="", embed=pw)
        if (payload.member):
            await self.message.remove_reaction(payload.emoji, payload.member)
        c = ""
        max = -(-len(self.list) // 5)
        if payload.emoji.name == '\u25C0':
            self.page -= 1 if self.page > 0 else 0
        elif payload.emoji.name == '\u25B6':
            self.page += 1 if self.page + 1 < max else 0
        elif payload.emoji.name == '\u21A9':
            self.current = self.base
            del self.deepl[-1]
            for x in self.deepl:
                self.current = self.current[x]
            self.page = 0
            self.list = [x + "/" if self.current[x] else x for x in self.current]
            max = -(-len(self.list) // 5)
        try:
            if self.deepl: await self.add_button(menus.Button('\u21A9', self.handler), react=True)
            else: await self.remove_button('\u21A9', react=True)
        except menus.MenuError: pass
        snippet = self.list[self.page * 5:self.page * 5 + 5]
        self.finalize
        e = copy(self.ebase)
        i = 1     
        for x in snippet:
            tzi = ""
            if not x.endswith("/"):
                tz = pytz.timezone((('/'.join(self.deepl) + f"/{x}") if self.deepl else x).replace(' ', '_'))
                dt = datetime.now(tz)
                tzi = f" (currently `{dt.strftime('%m/%d/%y %I:%M%p')}{' DST' if isdst(tz) else ''}`)"
            c += f"{i}\uFE0F\u20E3 `{x}`{tzi}\n"
            i += 1
        e.description = c
        ins = ""
        if self.deepl:
            ins = f" (in {'/'.join(self.deepl)})"
        e.set_footer(text=f"Page {self.page + 1}/{max}{ins}")
        e.timestamp = datetime.utcnow()
        await self.message.edit(content="", embed=e)

    @menus.button('\u23F9')
    async def cancelb(self, _payload):
        self.stop()

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.result


class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tzd = {}
        def rec(cur, startswith):
            stack = '/'.join(startswith)
            for x in cur:
                if not x.startswith(stack): continue
                x = x[len(stack):]
                split = x.split('/')
                if not split[0]: del split[0]
                ld = self.tzd
                for y in startswith:
                    ld = ld[y]
                ld[split[0]] = {}
                if len(split) >= 2:
                    rec(cur, startswith + [split[0]])
    

        rec([x.replace('_', ' ') for x in pytz.common_timezones], [])

    def getmpm(self) -> mpku.MPKManager:
        return mpku.getmpm('users', None)

    @commands.group(aliases = ["userinfo"])
    async def profile(self, ctx: commands.Context, user: Optional[UserLookup]):
        """Edit or get your own or someone else's profule.
        This also includes generic user info such as roles and account creation/server join date.

        `profile/userinfo <user>`"""
        if ctx.invoked_subcommand: return
        if not user: user = ctx.author
        user: discord.User
        e = discord.Embed(title=str(user))
        e.set_thumbnail(url=str(user.avatar_url))
        isguild = bool(ctx.guild)
        bm = ""
        isbot = user.bot
        if isguild:
            m: discord.Member = ctx.guild.get_member(user.id)
            isguild = bool(m)
            if m:
                e.color = m.color if m.color != discord.Color.default() else e.color
                gl = [f" - *{m.nick}*" if m.nick else "", f"**{'Added' if isbot else 'Joined'} at**: {m.joined_at.strftime('%m/%d/%y %I:%M %p')} UTC ({timeago.format(m.joined_at)})\n"]
            try: 
                l = [x for x in (await ctx.guild.bans()) if x.user.id == user.id]
                if l and (ctx.author.permissions_in(ctx.channel).ban_members):
                    be = l[0]
                    if be.reason:
                        bm = f" for reason `{be.reason}`"
                    bm = f" **(is banned{bm})**"
            except discord.Forbidden: pass
        def glp(index):
            nonlocal gl, isguild
            return (gl[index] if isguild else "")
        e.description = f"""{user.mention}{glp(0)}{bm}\n**Created at**: {user.created_at.strftime('%m/%d/%y %I:%M %p')} UTC ({timeago.format(user.created_at)})\n{glp(1)}"""
        if isguild and m.roles[1:]:
            rev = m.roles[1:]
            rev.reverse()
            e.add_field(name=f"Roles ({len(m.roles[1:])})", value=' '.join([x.mention for x in rev]))
        e.set_footer(text=f"ID: {user.id}")
        ##BEGIN PROFILE SHIT
        if isbot: return await ctx.send(embed=e) #botphobia
        pval = ""
        try: mpk = self.getmpm().getanddel()[str(user.id)]['profile']
        except: return await ctx.send(embed=e)
        last: Union[dict, str]
        def getfromprofile(st, notset=False):
            nonlocal last
            try:
                last = mpk[st] 
                if not last: raise Exception()
            except: last = "*Not set*" if notset else None
            return last
        #a lot of repetition for now just as a sketch
        pval += f"**Preferred name**: {getfromprofile('name', True)}\n"
        if (getfromprofile("realname")):
            pval += f"**Real name**: {last}\n"
        getfromprofile("pronoun")
        pnb = "their"
        pval += "**Pronouns**: "
        if not last:
            pval += "*Not set*\n"
        else:
            if (last['custom']): ps = last['value']
            else:
                if   (last['value'] == 0): 
                    ps = "he/him"
                    pnb = "his"
                elif (last['value'] == 1): 
                    ps = "she/her"
                    pnb = "her"
                elif (last['value'] == 2): ps = "they/them" #non-binary (0b10 = 2) :troll
            pval += f"{ps}\n"
        getfromprofile("birthday")
        pval += "**Birthday**: "
        if not last:
            pval += "*Not set*"
        else:
            hasy = True
            curr = ""
            date = ""
            if (len(last) == 4): 
                hasy = False
                dt = datetime.strptime(last, "%d%m")
                date = dt.strftime("%m/%d")
            else:
                dt = datetime.strptime(last, "%d%m%y")
                date = dt.strftime("%m/%d/%y")
            try: tz = pytz.timezone(getfromprofile("tz").replace(' ', '_'))
            except: tz = pytz.timezone("UTC")
            dt = dt.replace(tzinfo=tz)
            now = datetime.now(tz)
            if not hasy: dt = dt.replace(year=now.year)
            else: curr += f" ({timeago.format(dt, now).replace('ago', 'old')})"
            print(dt)
            print(now)
            if now.date() == dt.date(): curr += f" **(It's {pnb} birthday today! \U0001F389)**"
            pval += f"{date}{curr}\n"
        if (getfromprofile("location")):
            pval += f"**Location**: {last}\n"
        pval += "**Timezone**: "
        if not (getfromprofile("tz")):
            pval += "*Not set*\n\n"
        else:
            now = datetime.now(pytz.timezone(last.replace(' ', '_')))
            pval += f"{last} (Currently {now.strftime('%m/%d/%y %I:%M%p')})\n\n"


        getfromprofile("bio")
        if not last:
            pval += "*Bio not set*"
        else: pval += last
        e.add_field(name="Profile", value=pval)   

        if (user.id == ctx.author.id):
            e.set_footer(text=f"Edit/set your profile using {ctx.prefix}profile edit!")
            
        await ctx.send(embed=e)     

    @profile.group()
    async def edit(self, ctx: commands.Context):
        if ctx.invoked_subcommand: return
        try: mpk = self.getmpm().getanddel()[str(ctx.author.id)]['profile']
        except:
            a = await Confirm("Do you want to create a profile? This cannot be undone. (Remember, anyone can view your profile at any time.)", delete_message_after=False).prompt(ctx)
            if a:
                mpm = self.getmpm()
                try: mpm.data[str(ctx.author.id)]
                except: mpm.data[str(ctx.author.id)] = {}
                mpm.data[str(ctx.author.id)]['profile'] = {}
                mpm.save()
                return await ctx.reinvoke(restart=True)
            return await ctx.send("Profile declined.")
        last: Union[str, dict]
        def getfromprofile(st, notset=True):
            nonlocal last
            try:
                last = mpk[st] 
                if not last: raise Exception()
            except: last = "*Not set*" if notset else None
            return last
        embed = discord.Embed(title="Current Profile Properties", color=discord.Color(self.bot.data['color']), timestamp=datetime.utcnow())
        embed.set_footer(text=f"Set a property using {ctx.prefix}profile edit (property)")
        embed.set_author(name=ctx.author.display_name, icon_url=str(ctx.author.avatar_url))
        embed.description = ''
        for x in fields:
            embed.description += f"`{x}`: "
            if x in ('name', 'realname', 'bio', 'tz', 'location'):
                embed.description += f"{getfromprofile(x)}\n"
            else:
                if x == 'birthday':
                    getfromprofile(x, False)
                    if not last: embed.description += "*Not set*"
                    else: 
                        if (len(last) == 4): embed.description += datetime.strptime(last, "%d%m").strftime("%m/%d")
                        else: embed.description += datetime.strptime(last, "%d%m%y").strftime("%m/%d/%y")
                elif x == "pronoun":
                    getfromprofile(x)
                    if not last:
                        embed.description += "*Not set*"
                    else:
                        if (last['custom']): embed.description += last['value']
                        else:
                            if   (last['value'] == 0): embed.description += "he/him"
                            elif (last['value'] == 1): embed.description += "she/her"
                            elif (last['value'] == 2): embed.description += "they/them" #non-binary (0b10 = 2) :troll
                embed.description += '\n'
        await ctx.send(embed=embed)

    @edit.command(aliases = ['setrealname', 'rname'])
    async def realname(self, ctx):
        mpm = self.getmpm()
        try: mpk = mpm.data[str(ctx.author.id)]['profile']
        except: return await ctx.invoke(self.edit)
        await ctx.send("Please type your real name. Remember, everyone can see this, so I recommend a \"nickname\" of sorts.\nIt must be under 40 characters. You can type `cancel` to cancel.")
        def waitforcheck(m):
            return (m.author == ctx.author) and (m.channel == ctx.channel)
        while True:
            ret = await self.bot.wait_for('message', check=waitforcheck)
            if (ret.content == "cancel"):
                await ctx.send("Cancelled name setting.")
                break
            if (len(ret.content) > 40): 
                await (await ctx.send("Please keep it under 40 characters.")).delete(delay=5)
                continue
            mpk['realname'] = ret.content
            mpm.save()
            return await ctx.send("Real name set!")

    @edit.command(aliases = ['setname'])
    async def name(self, ctx):
        mpm = self.getmpm()
        try: mpk = mpm.data[str(ctx.author.id)]['profile']
        except: return await ctx.invoke(self.edit)
        await ctx.send("Please type your preferred name. It must be under 30 characters. You can type `cancel` to cancel.")
        def waitforcheck(m):
            return (m.author == ctx.author) and (m.channel == ctx.channel)
        while True:
            ret = await self.bot.wait_for('message', check=waitforcheck)
            if (ret.content == "cancel"):
                await ctx.send("Cancelled name setting.")
                break
            if (len(ret.content) > 30): 
                await (await ctx.send("Please keep it under 30 characters.")).delete(delay=5)
                continue
            mpk['name'] = ret.content
            mpm.save()
            return await ctx.send("Name set!")

    @edit.command(aliases = ['setlocation', 'loc', 'setloc'])
    async def location(self, ctx):
        mpm = self.getmpm()
        try: mpk = mpm.data[str(ctx.author.id)]['profile']
        except: return await ctx.invoke(self.edit)
        await ctx.send("Please type your location. **Don't** be specific. It must be under 30 characters. You can type `cancel` to cancel.")
        def waitforcheck(m):
            return (m.author == ctx.author) and (m.channel == ctx.channel)
        while True:
            ret = await self.bot.wait_for('message', check=waitforcheck)
            if (ret.content == "cancel"):
                await ctx.send("Cancelled location setting.")
                break
            if (len(ret.content) > 30): 
                await (await ctx.send("Please keep it under 30 characters.")).delete(delay=5)
                continue
            mpk['location'] = ret.content
            mpm.save()
            return await ctx.send("Location set!")


    @edit.command(aliases = ['setbio'])
    async def bio(self, ctx):
        mpm = self.getmpm()
        try: mpk = mpm.data[str(ctx.author.id)]['profile']
        except: return await ctx.invoke(self.edit)
        await ctx.send("Please type up a bio. It must be under 400 characters. You can type `cancel` to cancel.")
        def waitforcheck(m):
            return (m.author == ctx.author) and (m.channel == ctx.channel)
        while True:
            ret = await self.bot.wait_for('message', check=waitforcheck)
            if (ret.content == "cancel"):
                await ctx.send("Cancelled bio setting.")
                break
            if (len(ret.content) > 400): 
                await (await ctx.send("Please keep it under 400 characters.")).delete(delay=5)
                continue
            mpk['bio'] = ret.content
            mpm.save()
            return await ctx.send("Bio set!")

    @edit.command(aliases = ['setbday', 'bday', 'setbirthday'])
    async def birthday(self, ctx):
        mpm = self.getmpm()
        try: mpk = mpm.data[str(ctx.author.id)]['profile']
        except: return await ctx.invoke(self.edit)
        await ctx.send("Please send your birthday. This can include year, but doesn't have to. Send `cancel` to cancel.")
        def waitforcheck(m):
            return (m.author == ctx.author) and (m.channel == ctx.channel)
        while True:
            ret = await self.bot.wait_for('message', check=waitforcheck)
            if (ret.content == "cancel"):
                await ctx.send("Cancelled birthday setting.")
                break
            tod = await ctx.send("Parsing date...")
            try: dt = dateparser.parse(ret.content)
            except: 
                await tod.delete()
                await (await ctx.send("Could not parse date given. Please try again.")).delete(delay=5)
                continue
            a = await Confirm(f"Is {dt.strftime('%B')} {getord(dt.day)} correct?", timeout=None).prompt(ctx)
            if not a:
                await (await ctx.send("Please try again with a different format.")).delete(delay=5)
                continue
            if (dt.year >= dt.utcnow().year):
                mpk['birthday'] = dt.strftime('%d%m')
            else:
                mpk['birthday'] = dt.strftime('%d%m%y')
            mpm.save()
            return await ctx.send("Birthday set!")

    @edit.command(aliases = ['setpronouns', 'setpronoun', 'pronouns'])
    async def pronoun(self, ctx):
        mpm = self.getmpm()
        try: mpk = mpm.data[str(ctx.author.id)]['profile']
        except: return await ctx.invoke(self.edit)
        e = discord.Embed(title="Pronoun Selector", color=discord.Color(self.bot.data['color']))
        e.description = """
        \U0001F468 - he/him
        \U0001F469 - she/her
        \U0001F9D1 - they/them
        \u2754 - other/manually set (varyex will use they/them where pronouns are used)
        """
        e.set_footer(text="This will automatically cancel in 2 minutes.")
        ch = await Choice(e, ['\U0001F468', '\U0001F469', '\U0001F9D1', '\u2754'], timeout=120.0, clear_reactions_after=True).prompt(ctx)
        if ch == 3:
            await ctx.send("Type out what your pronouns to be displayed as.")
            def waitforcheck(m):
                return (m.author == ctx.author) and (m.channel == ctx.channel)
            while True:
                ret = await self.bot.wait_for('message', check=waitforcheck)
                if (len(ret.content) > 50): 
                    await (await ctx.send("Please keep it under 50 characters.")).delete(delay=5)
                    continue
                mpk['pronoun'] = {'value': ret.content, 'custom': True}
                break
        else:
            mpk['pronoun'] = {'value': ch, 'custom': False}
        mpm.save()
        return await ctx.send("Pronouns set!")

    @edit.command(aliases = ['settz', "timezone", "tz"])
    async def settimezone(self, ctx):
        mpm = self.getmpm()
        try: mpk = mpm.data[str(ctx.author.id)]['profile']
        except: return await ctx.invoke(self.edit)
        r = await TZMenu(self.tzd, discord.Color(self.bot.data['color'])).prompt(ctx)
        if r:
            mpk['tz'] = r
            mpm.save()
            return await ctx.send("Timezone set!")
        return await ctx.send("Timezone setting cancelled.")

def setup(bot):
    bot.add_cog(Profile(bot))        
        


