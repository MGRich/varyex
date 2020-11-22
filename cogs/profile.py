import discord, asyncio, re, aiohttp
from discord.ext import commands, menus, tasks

from cogs.utils.converters import UserLookup, DurationString
from cogs.utils.menus import Confirm, Choice
from cogs.utils.other import getord, timestamp_to_int, datetime_from_int, timestamp_now, iiterate

from typing import Union, Optional
from datetime import datetime, timedelta
import timeago
import pytz
import dateparser
import number_parser as numparser
from humanize import naturaltime
from copy import copy
from lxml import html

import logging
LOG = logging.getLogger('bot')
DUMPCHANNEL = 777709381931892766

REBASE = r'(?P<name>.*) \(%P%(?P<handle>.*)\)'
ACCOUNTS = {
    'twitter': {
        'emoji': 777705359535636481,
        'prefix': '@',
        'link': 'https://twitter.com/[]',
        'type': 0,
        're': REBASE,
        'color': 0x1da1f2,
    },
    'twitch': {
        'emoji': 777763562222911509,
        'link': 'https://twitch.tv/[]',
        'type': 2,
        're': r'(?P<name>\w*) -',
        'color': 0x9146ff,
    },
    'steam': {
        'emoji': 777768944316579860,
        'link': 'https://steamcommunity.com/id/[]',
        'type': 2,
        're': r':: (?P<name>\w*)',
        'color': 0x231f20
    },
    'github': {
        'emoji': 777770141416685588,
        'link': 'https://github.com/[]',
        'type': 2,
        're': r'(?P<name>\w*) -',
        'color': 0x171516
    },
    'youtube': {
        'emoji': 777766517700821023,
        'link': 'https://www.youtube.com/channel/[]',
        'type': 2,
        're': r'(?P<name>.*)',
        'color': 0xff0000
    },
    'reddit': {
        'emoji': 777771510311026688,
        'prefix': 'u/',
        'link': 'https://reddit.com/u/[]',
        'type': 1,
        're': REBASE,
        'color': 0xff4500
    },
    'instagram': {
        'emoji': 777774500926324757,
        'prefix': '@',
        'link': 'https://instagram.com/[]',
        'type': 0,
        're': REBASE,
        'embed': False,
        'color': 0xdf4176
    },
    'soundcloud': {
        'emoji': 777775128448073729,
        'link': 'https://soundcloud.com/[]',
        'type': 2,
        're': r'(?P<name>.*)',
        'color': 0xff5500
    },
    'lastfm': {
        'emoji': 778092674581790720,
        'link': 'https://www.last.fm/user/[]',
        'type': 2,
        're': r'(?P<name>\w*).s Music',
        'color': 0xe31c23,
        'name': 'Last.fm'
    },
    'tumblr': {
        'emoji': 777911052456689684,
        'link': 'https://[].tumblr.com',
        'prefix': '@',
        'type': 0,
        're': r'(?P<name>.*)',
        'embed': True,
        'color': 0x001935
    },
    'deviantart': {
        'emoji': 777913856444989440,
        'link': 'https://deviantart.com/[]',
        'type': 2,
        're': r'(?P<name>\w*) User Profile \|',
        'embed': False,
        'name': 'DeviantArt',
        'color': 0x06cc47
    }
}

def isdst(tz): bool(datetime.now(tz).dst()) #https://stackoverflow.com/a/19968515

class TZMenu(menus.Menu):
    #this is gonna be the weirdest, most disgusting 
    #mesh of a paginator and a poll-like system
    #i have NO idea how else i'd be able to do it
    def __init__(self, tzd, c):
        super().__init__()
        self.tzd = tzd
        for x in {'\u25C0', '\u25B6'}:
            self.add_button(menus.Button(x, self.handler))
        for x in range(1, 6):
            self.add_button(menus.Button(str(x) + "\uFE0F\u20E3", self.pick))
        self.ebase = discord.Embed(title="Timezone Selector", color=c)
        self.page = 0
        self.deepl = []
        self.current = tzd
        self.base = tzd
        self.list: list 
        self.sortlist()
        self.result = None
        self.user: discord.User

    def sortlist(self):
        self.list = [x + "/" if self.current[x] else x for x in self.current]
        fd = [x for x in self.list if x.endswith("/")]
        tz = [x for x in self.list if not x.endswith("/")]
        fd.sort()
        tz.sort()
        if not (self.deepl):
            #put US/ at the VERY top cause its easier
            fd.remove("US/")
            fd.insert(0, "US/")
        self.list = fd + tz

    async def pick(self, payload: discord.RawReactionActionEvent):
        if payload.event_type == "REACTION_REMOVE": return
        il = [str(x) + "\uFE0F\u20E3" for x in range(1, 6)]
        try: picked = self.list[self.page * 5 + il.index(payload.emoji.name)]
        except IndexError: return await self.handler(payload)
        self.deepl.append(picked[:-1])
        try: self.current = self.current[self.deepl[-1]]
        except: 
            #we found it 
            self.result = '/'.join(self.deepl) + picked[-1]
            return self.stop()
        self.sortlist()       
        self.page = 0 
        await self.handler(payload)

    async def send_initial_message(self, ctx, channel):
        if not ctx.guild:
            await channel.send("Please note that since this is in DMS, you must remove the reactions yourself.")
        m = await channel.send(embed=self.ebase)
        fakep = discord.RawReactionActionEvent({'message_id': 0, 'channel_id': 0, 'user_id': 0}, discord.PartialEmoji(name='\u25C0'), "REACTION_ADD")
        self.message = m
        await self.handler(fakep)
        return m

    async def handler(self, payload):
        if payload.event_type == "REACTION_REMOVE": return
        pw = self.message.embeds[0]
        pw.set_footer(text="Please wait...")
        await self.message.edit(content="", embed=pw)
        try: await self.message.remove_reaction(payload.emoji, self.user)
        except: pass
        c = ""
        pmax = len(self.list) // 5 
        if payload.emoji.name == '\u25C0':
            self.page = max(self.page - 1, 0)
        elif payload.emoji.name == '\u25B6':
            self.page = min(self.page + 1, pmax)
        elif payload.emoji.name == '\u21A9':
            self.current = self.base
            del self.deepl[-1]
            for x in self.deepl:
                self.current = self.current[x]
            self.page = 0
            self.sortlist()
            pmax = len(self.list) // 5
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
        e.set_footer(text=f"Page {self.page + 1}/{pmax}{ins}")
        e.timestamp = datetime.utcnow()
        await self.message.edit(content="", embed=e)

    @menus.button('\u23F9')
    async def cancelb(self, _payload):
        self.stop()

    async def prompt(self, ctx):
        self.user = ctx.author
        await self.start(ctx, wait=True)
        return self.result

class PronounSelector(menus.Menu):
    def __init__(self, bot):
        super().__init__()
        self.result = {}
        self.dval = 0
        self.double = 2
        self.bot = bot

        self.embed = discord.Embed(title="Pronoun Selector", color=self.bot.data['color'], 
            description =  """
            \U00002642 - he/him
            \U00002640 - she/her
            \U0001F9D1 - they/them
            \U0001F465 - double (primary and secondary out of main 3)
            \u2754 - other/manually set (varyex will use they/them where pronouns are used)""")

        for x in {'\u2642', '\u2640', '\U0001F9D1'}:
            self.add_button(menus.Button(x, self.handler))
        self.add_button(menus.Button('\U0001F465', self.doublemethod))
        self.add_button(menus.Button('\u2754', self.otherstop))

    async def send_initial_message(self, ctx, channel):
        return await channel.send(embed=self.embed)

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.result
    
    async def handler(self, payload):
        if payload.event_type == "REACTION_REMOVE": return
        used = ['\u2642', '\u2640', '\U0001F9D1'].index(payload.emoji.name)
        n = ((self.double % 2) * 2)
        self.dval = (self.dval & ~(0b11 << n)) | (used << n)  
        self.result = {'value': self.dval, 'custom': False}
        if (self.double >= 2): self.stop()
        else:
            self.double += 1
            await self.remove_button(payload.emoji.name, react=True)
            self.embed.description = ''.join(self.embed.description.splitlines(keepends=True)[:-1]) + f"Currently selected: {pronounstrings(self.result)[0]}"
            await self.message.edit(embed=self.embed)
            if (self.double >= 2):
                self.stop()
            
    async def doublemethod(self, _payload):
        self.double = 0
        await self.remove_button('\U0001F465', react=True)
        await self.remove_button('\u2754', react=True)
        self.embed.description = """
            \U00002642 - he/him
            \U00002640 - she/her
            \U0001F9D1 - they/them

            Select 2 options one after the other.
            Currently selected: *none*"""
        await self.message.edit(embed=self.embed)
        self.dval |= 0b11100

    async def otherstop(self, _payload):
        self.result = {'value': '', 'custom': True}
        self.stop()

    @menus.button('\u23F9')
    async def cancelb(self, _payload):
        self.result = {} #ensure we cancel
        self.stop()

def pronounstrings(d):
    ps = ""
    used = "their"
    if (d['custom']): ps = d['value']
    else:
        double = False
        vused = d['value']
        if (vused & 0b10000): 
            double = True
            vused &= 0b11 #primary first
        if   (vused == 0): 
            ps = "he/him"
            used = "his"
        elif (vused == 1): 
            ps = "she/her"
            used = "her"
        elif (vused == 2): ps = "they/them" #non-binary (0b10 = 2) :troll
        if (double):
            #we modify just after the /
            ps = ps.split('/')[0] + '/'
            vused = (d['value'] >> 2) & 0b11
            if   (vused == 0): ps += "he"
            elif (vused == 1): ps += "she"
            elif (vused == 2): ps += "they"
    return (ps, used)

class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
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

    @commands.command(aliases = ('remind', 'reminder', 'setreminder', 'setremind'))
    async def remindme(self, ctx: commands.Context, *, ds: DurationString):
        if not ((d := ds.duration) and (st := ds.string)): return await ctx.send("Please set a valid duration.")
        mpk = self.bot.usermpm[str(ctx.author.id)]

    @tasks.loop(minutes=1)
    async def remindloop(self):
        mpk = self.bot.usermpm
        for x in mpk:
            if not (r := mpk[x]['reminders']): continue
            subtract = 0
            for reminder, i in iiterate(r):
                if reminder['time'] <= timestamp_now():
                    st = f"{naturaltime(timedelta(minutes=reminder['len']))}, you set a reminder: {reminder['msg']}"
                    try: await (await self.bot.fetch_user(int(x))).send(st)
                    except:
                        try: await self.bot.get_channel(int(reminder['ch'])).send(f"<@{x}> {st}")
                        except: pass #could not send reminder
                    del r[i - subtract]
                    subtraft += 1
                    


    @commands.group(aliases = ("userinfo", "userprofile"))
    async def profile(self, ctx: commands.Context, user: Optional[UserLookup]):
        """Edit or get your own or someone else's profile.
        This also includes generic user info such as roles and account creation/server join date.

        `profile/userinfo <user>`
        
        **EDITING**
        > `profile edit <property> [text if applicable]`
        > Valid properties are: name, realname, pronoun, location, bio, birthday"""
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
                gl = [f" - *{m.nick}*" if m.nick else "", f"**{'Added' if isbot else 'Joined'} at**: {m.joined_at.strftime('%m/%d/%y %I:%M %p')} UTC ({timeago.format(m.joined_at, datetime.utcnow())})\n"]
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
        e.description = f"""{user.mention}{' (bot owner) ' if user.id == self.bot.owner.id else ''}{glp(0)}{bm}\n**Created at**: {user.created_at.strftime('%m/%d/%y %I:%M %p')} UTC ({timeago.format(user.created_at, datetime.utcnow())})\n{glp(1)}"""
        if isguild and m.roles[1:]:
            rev = m.roles[1:]
            rev.reverse()
            e.add_field(name=f"Roles ({len(m.roles[1:])})", value=' '.join([x.mention for x in rev]), inline=False)
        bt = ""
        if (user.id == ctx.author.id):
            bt = f"Edit/set your profile using {ctx.prefix}profile edit! | "
        e.set_footer(text=f"{bt}ID: {user.id}")
        ##BEGIN PROFILE SHIT
        if isbot: return await ctx.send(embed=e) #botphobia
        pval = ""
        if not (mpk := self.bot.usermpm[str(user.id)]['profile']):
            return await ctx.send(embed=e)
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
            ps, pnb = pronounstrings(last)
            pval += f"{ps}\n"
        getfromprofile("birthday")
        pval += "**Birthday**: "
        if not last:
            pval += "*Not set*\n"
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
            LOG.debug(dt)
            LOG.debug(now)
            if now.date() == dt.date(): curr += f" **(It's {pnb} birthday today! \U0001F389)**"
            pval += f"{date}{curr}\n"
        if (getfromprofile("location")):
            pval += f"**Location**: {last}\n"
        pval += "**Timezone**: "
        if not (getfromprofile("tz")):
            pval += "*Not set*\n"
        else:
            now = datetime.now(pytz.timezone(last.replace(' ', '_')))
            pval += f"{last} (Currently {now.strftime('%m/%d/%y %I:%M%p')})\n"

        getfromprofile("accounts")
        #last = {'twitter': [{'handle': 'rmg_rich', 'name': 'RMGRich'}, {'handle': 'rmgrich', 'name': 'rmgrich'}], 'twitch': [{'name': 'RMGBread', 'handle': 'rmgbread'}], 'youtube': [{'handle': 'UC9ecwl3FTG66jIKA9JRDtmg', 'name': 'SiIvaGunner'}]}
        if last:
            aval = ""
            for acc in last:
                t = ACCOUNTS[acc]['type']
                emoji = self.bot.get_emoji(ACCOUNTS[acc]['emoji'])
                try: prefix = ACCOUNTS[acc]['prefix']
                except: prefix = ''
                for x in last[acc]:
                    handle = x['handle']
                    name = x['name']
                    display = ""
                    if t != 2: display  = f"{prefix}{handle}"
                    else:      display  = name 
                    if t == 0: display += f" ({name})"
                    display = discord.utils.escape_markdown(display)
                    link = ACCOUNTS[acc]['link'].replace('[]', x['handle'])
                    aval += f"{emoji} [{display}]({link})\n"
            if aval: e.add_field(name="Accounts", value=aval)

        pval += "\n"

        getfromprofile("bio")
        if not last:
            pval += "*Bio not set*"
        else: pval += last
        e.add_field(name="Profile", value=pval, inline=False)   

        await ctx.send(embed=e)     

    @profile.group(aliases = ("set",))
    async def edit(self, ctx: commands.Context):
        if ctx.invoked_subcommand: return
        if self.bot.usermpm[str(ctx.author.id)]['profile'].isblank:
            a = await Confirm("Do you want to create a profile? This cannot be undone. (Remember, anyone can view your profile at any time.)", delete_message_after=False).prompt(ctx)
            if not a: return await ctx.send("Profile declined.")
            mpk = self.bot.usermpm
            mpk[str(ctx.author.id)]['profile'] = {}
            mpk.save()
            return await ctx.reinvoke(restart=True)
            
        raise commands.UserInputError()

    async def _edit(self, ctx, prompts, max, key, pretext):
        mpm = self.bot.usermpm
        if (mpk := mpm[str(ctx.author.id)]['profile']).isblank:
            return await ctx.invoke(self.edit)
        if not pretext: await ctx.send(prompts[0])
        def waitforcheck(m):
            return (m.author == ctx.author) and (m.channel == ctx.channel)
        while True:
            if pretext: ret = pretext
            else:
                try: ret = (await self.bot.wait_for('message', check=waitforcheck, timeout=60.0)).content
                except: return
            if (ret.lower() == "cancel"):
                await ctx.send(prompts[2])
                return
            if (len(ret) > max): 
                await (await ctx.send(f"Please keep it under {max} characters ({len(ret)}/{max}).")).delete(delay=5)
                if pretext: 
                    pretext = None
                    await ctx.send(prompts[0])
                continue
            mpk[key] = ret
            mpm.save()
            return await ctx.send(prompts[1])

    @edit.command(aliases = ('setrealname', 'rname'))
    async def realname(self, ctx, *, pretext: Optional[str]):
        await self._edit(ctx, ["Please type your real name. Remember, everyone can see this, so I recommend a \"nickname\" of sorts.\nIt must be under 30 characters. You can type `cancel` to cancel.",
            "Real name set!", "Cancelled name setting."], 30, 'realname', pretext)

    @edit.command(aliases = ('setname',))
    async def name(self, ctx, *, pretext: Optional[str]):
        await self._edit(ctx, ["Please type your preferred name. It must be under 30 characters. You can type `cancel` to cancel.",
            "Name set!", "Cancelled name setting."], 30, 'name', pretext)

    @edit.command(aliases = ('setlocation', 'loc', 'setloc'))
    async def location(self, ctx, *, pretext: Optional[str]):
        await self._edit(ctx, ["Please type your location. **Don't be specific.** It must be under 30 characters. You can type `cancel` to cancel.",
            "Location set!", "Cancelled location setting."], 30, 'location', pretext)

    @edit.command(aliases = ('setbio',))
    async def bio(self, ctx, *, pretext: Optional[str]):
        await self._edit(ctx, ["Please type up a bio. It must be under 400 characters. You can type `cancel` to cancel.",
            "Bio set!", "Cancelled bio setting."], 400, 'bio', pretext)


    @edit.command(aliases = ('setbday', 'bday', 'setbirthday'))
    async def birthday(self, ctx):
        mpm = self.bot.usermpm
        if (mpk := mpm[str(ctx.author.id)]['profile']).isblank:
            return await ctx.invoke(self.edit)
        await ctx.send("Please send your birthday. This can include year, but doesn't have to. Send `cancel` to cancel.")
        def waitforcheck(m):
            return (m.author == ctx.author) and (m.channel == ctx.channel)
        while True:
            try: ret = await self.bot.wait_for('message', check=waitforcheck, timeout=60.0)
            except: return
            if (ret.content.lower() == "cancel"):
                await ctx.send("Cancelled birthday setting.")
                break
            tod = await ctx.send("Parsing date...")
            dt = dateparser.parse(ret.content)
            if not dt: 
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

    @edit.command(aliases = ('setpronouns', 'setpronoun', 'pronouns'))
    async def pronoun(self, ctx):
        mpm = self.bot.usermpm
        if (mpk := mpm[str(ctx.author.id)]['profile']).isblank:
            return await ctx.invoke(self.edit)
        result = await PronounSelector(self.bot).prompt(ctx)
        if not result:
            return await ctx.send("Cancelled pronoun setting.")
        elif result['custom']:
            await ctx.send("Please type out your preferred pronouns (under 50 chars). Type `cancel` to cancel.")
            def waitforcheck(m):
                return (m.author == ctx.author) and (m.channel == ctx.channel)
            while True:
                try: ret = await self.bot.wait_for('message', check=waitforcheck, timeout=60.0)
                except: return
                if (ret.content.lower() == "cancel"):
                    return await ctx.send("Cancelled pronoun setting.")
                if (len(ret.content) > 50): 
                    await (await ctx.send("Please keep it under 50 characters.")).delete(delay=5)
                    continue
                result.update({'value': ret.content})
                mpm.save()
                break
        mpk['pronoun'] = result
        mpm.save()
        return await ctx.send("Pronouns set!")

    @edit.command(aliases = ('settz', "timezone", "tz"))
    async def settimezone(self, ctx):
        mpm = self.bot.usermpm
        if (mpk := mpm[str(ctx.author.id)]['profile']).isblank:
            return await ctx.invoke(self.edit)
        r = await TZMenu(self.tzd, discord.Color(self.bot.data['color'])).prompt(ctx)
        if r:
            mpk['tz'] = r
            mpm.save()
            return await ctx.send("Timezone set!")
        return await ctx.send("Timezone setting cancelled.")

    @commands.Cog.listener()
    async def on_message(self, m: discord.Message):
        return
        if (m.author.id == self.bot.user.id) or not m.guild: return
        perms: discord.Permissions = m.channel.permissions_for(m.guild.me)
        if not (perms.read_message_history and perms.add_reactions and perms.send_messages and perms.manage_messages): return

        try: tz = self.bot.usermpm[str(m.author.id)]['profile']['tz'].replace(' ', '_')
        except: return

        dt = None
        split = numparser.parse(m.content).split()
        ddp = dateparser.DateDataParser(languages=['en'], settings={'TIMEZONE': tz, 'TO_TIMEZONE': 'UTC'})

        for i in range(len(split)):
            dt = None
            total = ""
            num = i
            worked = False
            flip = False
            while True:
                try:
                    if (num < 0): raise IndexError()
                    if flip: total = split[num] + ' ' + total
                    else: total += ' ' + split[num]
                    parsed = ddp.get_date_data(total)
                    if not (parsed and parsed['date_obj'] and (flip or parsed['period'] == 'day')): 
                        raise IndexError()
                except IndexError:
                    if flip:
                        worked = parsed['period'] == 'day' 
                        dt = parsed['date_obj']
                        break
                    flip = True
                    num = i - 1
                    continue
                worked = parsed['period'] == 'day'
                dt = parsed['date_obj']
                num += -1 if flip else 1 
                if (num < 0): break
            if not worked: continue
            try: int(total)
            except: break

        if not dt: return
        await m.add_reaction('\u23f0')
        

        def check(r, u):
            return u == m.author and str(r.emoji) == '\u23f0'

        try: await self.bot.wait_for('reaction_add', timeout=1.5, check=check)
        except asyncio.TimeoutError: 
            return await m.remove_reaction('\u23f0', m.guild.me)
        else: 
            await m.remove_reaction('\u23f0', m.guild.me)
            await m.remove_reaction('\u23f0', m.author)

        e = discord.Embed(timestamp = dt, color=self.bot.data['color'])
        e.set_footer(text="Date above in local time")
        await m.channel.send(embed=e)

    @commands.guild_only()
    @edit.command(aliases = ('account', 'accounts', 'setaccount'))
    async def setaccounts(self, ctx: commands.Context):
        mpm = self.bot.usermpm
        if (mpk := mpm[str(ctx.author.id)]['profile']).isblank:
            return await ctx.invoke(self.edit)
        accdict = mpk['accounts']

        embed = discord.Embed(title = "Accounts Management", description = "Pick which account you'd like to add/remove.",
            color = self.bot.data['color'] if ctx.author.color == discord.Color.default() else ctx.author.color)
        embed.set_author(name=ctx.author.display_name, icon_url=str(ctx.author.avatar_url_as(format='jpg', size=64)))
        emoji = [self.bot.get_emoji(ACCOUNTS[x]['emoji']) for x in ACCOUNTS]
        msg = await ctx.send(embed=embed)
        a = await Choice(msg, emoji).prompt(ctx)

        acctype = list(ACCOUNTS)[a]
        data = ACCOUNTS[acctype]
        try: aname = data['name']
        except: aname = acctype.title()
        embed.title += f" - {aname}"
        embed.set_footer(text=aname, icon_url=str(emoji[a].url))
        embed.color = data['color']

        alist = accdict[acctype]
        embed.description = "Current accounts:\n" if alist else "*No accounts.*\n"
        t = data['type']
        i = 0
        for x in alist:
            handle = x['handle']
            name = x['name']
            display = ""
            if t != 2: display  = f"{data['prefix']}{handle}"
            else:      display  = name 
            if t == 0: display += f" ({name})"
            display = discord.utils.escape_markdown(display)
            link = data['link'].replace('[]', x['handle'])
            embed.description += f"#{i + 1}: [{display}]({link})\n"
            i += 1

        pre = embed.description
        embed.description += "\nAdd using \u2705, remove using \u26D4, cancel using \u274C\nIf you need to update a name, just add one of the same handle."
        await msg.edit(embed=embed)

        a = await Choice(msg, ['\u2705', '\u26D4', '\u274C']).prompt(ctx)
        if a == 2: return await ctx.send("Cancelled account management.") 
        if a == 1:
            if not alist: return await ctx.send("There's no accounts to delete!")
            em = []
            for x in range(1, len(alist) + 1):
                em.append(str(x) + "\uFE0F\u20E3")
            embed.description = pre + "\nPlease react with the number of which account you want to delete."
            await msg.edit(embed=embed)
            a = await Choice(msg, em).prompt(ctx)
            del alist[a]
            mpm.save()
            return await ctx.send(f"Account #{a+1} removed!")
        if len(alist) >= 3: return await ctx.send(f"You can't add any more accounts for {aname}!")
        await ctx.send(f"Please send your {aname} handle (the text that goes in `[]` for `{data['link']}`.)")
        handle = name = ""
        td = None
        def waitforcheck(m):
            return (m.author == ctx.author) and (m.channel == ctx.channel)
        while True:
            try: 
                if td: await td.delete()
            except: td = None
            ret = (await self.bot.wait_for('message', check=waitforcheck, timeout=20.0)).content
            if re.search(r'\s', ret):
                await (await ctx.send("There should be no spaces. Please try again.")).delete(delay=5)
                continue
            td = await ctx.send("Verifying...")
            await ctx.channel.trigger_typing()
            try: checkembed = data['embed']
            except: checkembed = True
            tocheck = ""
            url = data['link'].replace('[]', ret)
            try:
                async with aiohttp.request('HEAD', url) as resp:
                    if resp.status != 200 or (not str(resp.url).startswith(url)): raise Exception()
            except: 
                await (await ctx.send("Invalid URL. Please try again.")).delete(delay=5)
                continue
            if checkembed: 
                dump = self.bot.get_channel(DUMPCHANNEL)                
                keepread = await dump.send(url)
                await asyncio.sleep(.5)
                for i in range(5):
                    keepread = await dump.fetch_message(keepread.id)
                    if keepread.embeds:
                        tocheck = keepread.embeds[0].title
                        await keepread.delete()
                        break
                    await asyncio.sleep(1)
            else: 
                try:
                    async with aiohttp.request('GET', url) as resp:
                        tree = html.fromstring(await resp.text())
                    head = None
                    for x in tree:
                        if x.tag == 'head': head = x
                    if head is None: raise Exception()
                    for x in head:
                        if x.tag == 'title': tocheck = x.text
                    raise Exception()
                except: pass
            res = data['re']
            try: res = res.replace('%P%', data['prefix'])
            except: pass
            match = re.search(res, tocheck)
            if (not match): 
                await (await ctx.send("Verification failed. Please try again and check your account spelling.")).delete(delay=5)
                continue
            try: name = match.group("name")
            except: name = ret
            try: handle = match.group("handle")
            except: 
                if name.lower() == ret.lower():
                    handle = name
                else: handle = ret
            break
        await td.delete()
        existlist = [x['handle'] for x in alist]
        if handle in existlist:
            index = existlist.index(handle)
            alist[index].update({'name': name})
            mpm.save()
            return await ctx.send(f"Updated account name for account #{index + 1}!")
        alist.append({'handle': handle, 'name': name})
        mpm.save()
        await ctx.send("Account added!")            


def setup(bot):
    bot.add_cog(Profile(bot))        
        


