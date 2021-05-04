from __future__ import annotations

import aiohttp
from aiohttp import http
from imports.menus import Choice, Confirm
from imports.other import fixml, httpfetch, iiterate
import discord
from discord.ext import commands, menus

import imports.mpk as mpk
import datetime as dt
from datetime import datetime, timedelta
from copy import copy
import pytz, umsgpack, struct
from io import BytesIO
from random import choice
from hashlib import sha256
from re import fullmatch

from html.parser import HTMLParser

from inspect import ismethod, getmembers


from typing import Optional, Set, Union, List, TYPE_CHECKING, Tuple

import imports.globals as g
BOT = None
if TYPE_CHECKING:
    from imports.main import Main
    BOT: Main 

def isdst(tz): bool(datetime.now(tz).dst())

REBASE = r'(?P<name>.*) \(%P%(?P<handle>.*)\)'
ACCOUNTS = {
    'twitter': {
        'emoji': 829807521593557052,
        'prefix': '@',
        'link': 'https://twitter.com/[]',
        'type': 0,
        're': REBASE,
        'color': 0x1da1f2,
    },
    'twitch': {
        'emoji': 829807522348269668,
        'link': 'https://twitch.tv/[]',
        'type': 2,
        're': r'(?P<name>\w*) -',
        'color': 0x9146ff,
        'used': 'https://www.twitch.tv/[]'
    },
    'steam': {
        'emoji': 829807523984965632,
        'link': 'https://steamcommunity.com/id/[]',
        'type': 2,
        're': r':: (?P<name>\w*)',
        'color': 0x231f20
    },
    'github': {
        'emoji': 829807524596678687,
        'link': 'https://github.com/[]',
        'type': 2,
        're': r'(?P<name>\w*) -',
        'color': 0x171516
    },
    'youtube': {
        'emoji': 829807523208101929,
        'link': 'https://www.youtube.com/channel/[]',
        'type': 2,
        're': r'(?P<name>.*)',
        'color': 0xff0000
    },
    'reddit': {
        'emoji': 829807525687590962,
        'prefix': 'u/',
        'link': 'https://reddit.com/u/[]',
        'type': 1,
        're': REBASE,
        'color': 0xff4500,
        'used': 'https://www.reddit.com/user/[]'
    },
    'instagram': {
        'emoji': 829807526735380491,
        'prefix': '@',
        'link': 'https://instagram.com/[]',
        'type': 0,
        're': REBASE,
        'embed': False,
        'color': 0xdf4176
    },
    'soundcloud': {
        'emoji': 829807528128282695,
        'link': 'https://soundcloud.com/[]',
        'type': 2,
        're': r'(?P<name>.*)',
        'color': 0xff5500
    },
    'lastfm': {
        'emoji': 829807530976477194,
        'link': 'https://www.last.fm/user/[]',
        'type': 2,
        're': r'(?P<name>\w*).s Music',
        'color': 0xe31c23,
        'name': 'Last.fm'
    },
    'tumblr': {
        'emoji': 829807528845770825,
        'link': 'https://[].tumblr.com',
        'prefix': '@',
        'type': 0,
        're': r'(?P<name>.*)',
        'embed': True,
        'color': 0x001935
    },
    'deviantart': {
        'emoji': 829807530003660889,
        'link': 'https://deviantart.com/[]',
        'type': 2,
        're': r'(?P<name>\w*) User Profile \|',
        'embed': False,
        'name': 'DeviantArt',
        'color': 0x06cc47
    },
    'pronounspage': {
        'emoji': 829931951481552907,
        'link': 'https://en.pronouns.page/@[]',
        'prefix': '@',
        'type': 1,
        're': r'@(?P<name>\w*)',
        'embed': False,
        'name': 'PronounsPage',
        'color': 0xc71585
    }
}

PAIRS = ("he/him", "she/her", "they/them")
FULLS = ("he/him/his/his/himself", "she/her/her/hers/herself",
         "they/them/their/theirs/themselves")
@umsgpack.ext_serializable(0x21)
class Pronouns():
    __slots__ = ('subject', 'object', 'pos_d', 'pos_p', 'reflex')
    def __init__(self, st: Optional[str] = None) -> None:
        if not st: 
            for i in range(len(self.__slots__)):
                setattr(self, self.__slots__[i], "")
            return
        split = st.split("/")
        if len(split) != 5: return
        for x, i in iiterate(split):
            setattr(self, self.__slots__[i], x)
    def packb(self):
        return '/'.join([getattr(self, x) for x in self.__slots__]).encode('utf-8')
    @staticmethod
    def unpackb(data: bytes):
        return Pronouns(data.decode("utf-8"))
    @property
    def pair(self):
        return self.subject + "/" + self.object
    @property
    def used(self):
        return self.pos_d
    def __eq__(self, o) -> bool:
       try: return self.packb() == o.packb() 
       except: return False
    def __hash__(self) -> int:
        return int(sha256(self.packb()).hexdigest(), 16)
    def __str__(self) -> str:
        return self.pair

PMPK = mpk.getmpm("pronouns", None)
@umsgpack.ext_serializable(0x22)
class UserAccount():
    __slots__ = ('type', 'handle', 'name')

    def __init__(self, type = "", handle = "", name = "") -> None:
        self.type = type
        self.handle = handle
        self.name = name
    def packb(self):
        res = bytearray()
        res.append(list(ACCOUNTS).index(self.type))
        res.extend(len(self.handle).to_bytes(2, 'little'))
        res.extend(self.handle.encode("utf-8"))
        res.extend(self.name.encode("utf-8"))
        return bytes(res)
    @staticmethod
    def unpackb(data: bytes):
        type = list(ACCOUNTS)[data[0]]
        l = int.from_bytes(data[1:3], 'little')
        handle = data[3:l+3].decode("utf-8")
        name = data[l+3:].decode("utf-8")
        return UserAccount(type, handle, name)

    def __str__(self) -> str:
        act = ACCOUNTS[self.type]
        t = act['type']
        try: prefix = act['prefix']
        except: prefix = ''
        display = ""
        if t != 2: display  = f"{prefix}{self.handle}"
        else:      display  = self.name 
        if t == 0: display += f" ({self.name})"
        display = discord.utils.escape_markdown(display)
        link = act['link'].replace('[]', self.handle)
        return f"<:{self.type}:{act['emoji']}> [{display}]({link})"

def get_pronouns(user):
    return UserProfile.fromuser(user).pronouns[0]

def pnoun_list(list, force=False):
    if force or len(list) > 2:
        return ', '.join(x.pair for x in list)
    if len(list) == 2:
        return f"{list[0].subject}/{list[1].subject}"
    return list[0].pair

async def get_pnounspage(handle) -> List[Pronouns]:
    j = (await httpfetch("https://en.pronouns.page/api/profile/get/" + handle, json=True))['en']['pronouns']
    plist = [x for x in sorted(j, key=lambda z: -j[z]) if j[x] not in {2, -1}]
    if not plist: return []
    highest = j[plist[0]]
    output = []
    for x in plist:
        if j[x] < highest: break
        if fullmatch(r"([^/]+\/){4}[^/]+", x):
            output.append(Pronouns(x))
        else:
            try: p = await httpfetch("https://en.pronouns.page/api/pronouns/" + x, json=True)
            except: continue
            else: output.append(Pronouns('/'.join(p['morphemes'].values())))
    return output


@umsgpack.ext_serializable(0x20)
class UserProfile():
    _VERSION = 1

    def __init__(self, data: Union[mpk.DefaultContainer, UserProfile] = None, forceinit = False, uid=0) -> None:
        self.name = ""
        self.realname = ""
        self.location = ""
        self.bio = ""
        self.pronouns: List[Union[Pronouns, str]] = []
        self.accounts: List[UserAccount] = []
        self.birthday: datetime = None
        self.timezone: dt.tzinfo = None

        self._initialized = True
        self.uid = 0
        if uid: self.uid = uid
        if data is None: return
        if data.isblank:
            self._initialized = forceinit
            return

        last = None
        def getfromprofile(st):
            nonlocal last
            last = data[st]
            if not last:
                last = None
            return last
        self.name = getfromprofile("name") or ""
        self.realname = getfromprofile("realname") or ""
        self.location = getfromprofile("location") or ""
        self.bio = getfromprofile("bio") or ""

        #THS CODE ONLY WORKS BECAUSE PRONOUNSPAGE ISNT RELEASED
        #if it were, we'd have to do weird async shit which :((
        if getfromprofile("pronoun"):
            if last['custom']: self.pronouns = [last['value']]
            else:
                double = False
                vused = last['value']
                if (vused & 0b10000):
                    double = True
                    vused &= 0b11  # primary first
                for _ in range(double + 1):
                    self.pronouns.append(Pronouns(FULLS[vused]))
                    vused = last['value'] >> 2 & 0b11
        if getfromprofile("accounts"):
            for type in last:
                for acc in last[type]:
                    self.accounts.append(UserAccount(type, acc['handle'], acc['name']))

        if getfromprofile("tz"):
            self.timezone = pytz.timezone(last.replace(' ', '_'))

        if getfromprofile("birthday"):
            self.birthday = datetime.strptime(last, "%d%m" if len(last) == 4 else "%d%m%y")
            if self.timezone:
                self.birthday = self.birthday.replace(tzinfo=self.timezone)
        self.accounts.sort(key=lambda x: x.type)
        self.save()

    def __bool__(self) -> bool:
        #return bool(sum(bool(getattr(self, x)) for x in self.__slots__))
        return self._initialized

    @property
    def pronoun_to_use(self):
        if not self.pronouns or isinstance(self.pronouns, str):
            return "their"
        return self.pronouns[0].used
    
    @property
    def pronoun_list(self):
        if isinstance(self.pronouns[0], str):
            return self.pronouns[0] 
        return pnoun_list(self.pronouns)

    def save(self):
        global BOT
        BOT = g.BOT
        assert self.uid and BOT
        BOT.usermpm[str(self.uid)]['profile'] = self
        new = False
        for x in self.pronouns:
            if x not in PMPK['list']:
                new = True
                PMPK['list'].append(x)
        if new: PMPK.save()
        BOT.usermpm.save()

    def packb(self):
        out = bytearray()
        #future-proofing by using 10 bytes for the ID
        #out.extend(self.user.id.to_bytes(10, 'little'))
        out.append(self._VERSION)
        def writestring(string):
            if string is None: string = ""
            tw = string.encode("utf-8")
            out.extend(len(tw).to_bytes(2, 'little'))
            out.extend(tw)
        for x in ('name', 'realname', 'location', 'bio'):
            writestring(getattr(self, x))
        if self.pronouns:
            if isinstance(self.pronouns[0], str):
                out.append(1)
                writestring(self.pronouns[0])
            else:
                out.append(0)
                out.extend(len(self.pronouns).to_bytes(1, 'little'))
                for x in self.pronouns:
                    out.extend(PMPK['list'].index(x).to_bytes(2, 'little'))
        else:
            out.append(0)
            out.append(0)
        accs = umsgpack.packb(self.accounts)
        out.extend(len(accs).to_bytes(2, 'little'))
        out.extend(accs)
        writestring(self.timezone.zone if self.timezone else None)
        writestring(self.birthday.strftime("%d%m" if self.birthday.year == 1900 else "%d%m%y") if self.birthday else None)
        return bytes(out)
    
    @staticmethod
    def unpackb(data):
        reader = BytesIO(data)
        ver = reader.read(1)[0]
        #^ compat reasons
        res = UserProfile()
        def readstring():
            len = int.from_bytes(reader.read(2), 'little')
            return reader.read(len).decode('utf-8')
        for x in ('name', 'realname', 'location', 'bio'):
            setattr(res, x, readstring())
        t = reader.read(1)[0]
        if t:
            res.pronouns = [readstring()]
        else:
            l = reader.read(1)[0]
            for _ in range(l):
                res.pronouns.append(PMPK['list'][int.from_bytes(reader.read(2), 'little')])
        btr = int.from_bytes(reader.read(2), 'little')
        res.accounts = umsgpack.unpackb(reader.read(btr))
        try: res.timezone = pytz.timezone(readstring())
        except: pass
        bd = readstring()
        if bd:
            res.birthday = datetime.strptime(bd, "%d%m" if len(bd) == 4 else "%d%m%y")
            if res.timezone:
                res.birthday = res.birthday.replace(tzinfo=res.timezone)
        return res

    @classmethod
    def fromuser(cls, uid: Union[discord.User, int]) -> UserProfile:
        if isinstance(uid, discord.abc.User):
            uid = uid.id
        inp = BOT.usermpm[str(uid)]['profile']
        if isinstance(inp, cls):
            inp.uid = uid
            return inp  
        return cls(inp, uid=uid)     

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
        if payload.event_type == "REACTION_REMOVE":
            return
        il = [str(x) + "\uFE0F\u20E3" for x in range(1, 6)]
        try:
            picked = self.list[self.page * 5 + il.index(payload.emoji.name)]
        except IndexError:
            return await self.handler(payload)
        self.deepl.append(picked[:-1])
        try:
            self.current = self.current[self.deepl[-1]]
        except:
            #we found it
            self.result = pytz.timezone(
                ('/'.join(self.deepl) + picked[-1]).replace(' ', '_'))
            return self.stop()
        self.sortlist()
        self.page = 0
        await self.handler(payload)

    async def send_initial_message(self, ctx, channel):
        if not ctx.guild:
            await ctx.send("Please note that since this is in DMS, you must remove the reactions yourself.")
        m = await ctx.send(embed=self.ebase)
        fakep = discord.RawReactionActionEvent(
            {'message_id': 0, 'channel_id': 0, 'user_id': 0}, discord.PartialEmoji(name='\u25C0'), "REACTION_ADD")
        self.message = m
        await self.handler(fakep)
        return m

    async def handler(self, payload):
        if payload.event_type == "REACTION_REMOVE":
            return
        pw = self.message.embeds[0]
        pw.set_footer(text="Please wait...")
        await self.message.edit(content="", embed=pw)
        try:
            await self.message.remove_reaction(payload.emoji, self.user)
        except:
            pass
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
            if self.deepl:
                await self.add_button(menus.Button('\u21A9', self.handler), react=True)
            else:
                await self.remove_button('\u21A9', react=True)
        except menus.MenuError:
            pass
        snippet = self.list[self.page * 5:self.page * 5 + 5]
        self.finalize
        e = copy(self.ebase)
        i = 1
        for x in snippet:
            tzi = ""
            if not x.endswith("/"):
                tz = pytz.timezone(
                    (('/'.join(self.deepl) + f"/{x}") if self.deepl else x).replace(' ', '_'))
                dt = datetime.now(tz)
                tzi = f" (currently `{dt.strftime('%m/%d/%y %I:%M%p')}{' DST' if isdst(tz) else ''}`)"
            c += f"{i}\uFE0F\u20E3 `{x}`{tzi}\n"
            i += 1
        e.description = c
        ins = ""
        if self.deepl:
            ins = f" (in {'/'.join(self.deepl)})"
        e.set_footer(text=f"Page {self.page + 1}/{pmax + 1}{ins}")
        e.timestamp = datetime.utcnow()
        await self.message.edit(content="", embed=e)

    @menus.button('\u23F9')
    async def cancelb(self, _payload):
        self.stop()

    async def prompt(self, ctx):
        self.user = ctx.author
        await self.start(ctx, wait=True)
        return self.result

class PronounIsland(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.result = Pronouns() 
        self.next = 0
        self.status = 0
        self.skip = False
    def feed(self, data: str) -> Pronouns:
        super().feed(data)
        return self.result
    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if self.next == 5: return
        al = [x[0] for x in attrs]
        if (not self.status and tag == "span" and 'class' in al and attrs[al.index('class')][1] == "sentence"):
            self.status = 1
            self.skip = self.next and ((self.next + 1) & 1)
        elif self.status and tag == "b":
            if self.skip:
                self.skip = False 
                return
            self.status = 2
    def handle_data(self, data: str) -> None:
        if self.next == 5: return
        if self.status == 2:
            setattr(self.result, Pronouns.__slots__[self.next], data.lower())
            self.next += 1
            self.status = 0
        



class PronounSelector(menus.Menu):
    def __init__(self, bot):
        super().__init__()
        self.result: List[Union[Pronouns, str]] = []
        self.dval = 0
        self.bot = bot

        self.embed = discord.Embed(title="Pronoun Selector", color=self.bot.data['color'],
                                   description=fixml("""
            Select the following to add to your pronouns:
            \U0001F468 - he/him
            \U0001F469 - she/her
            \U0001F9D1 - they/them
            \u2754 - manually add (5 forms or pair)
            \U0001F517 - from link
            You may hit \u2705 when you're done.
            
            Currently set: *none*"""))

        for x in ('\U0001F468', '\U0001F469', '\U0001F9D1'):
            self.add_button(menus.Button(x, self.handler))
        self.add_button(menus.Button('\u2754', self.other))
        self.add_button(menus.Button('\U0001F517', self.fromlink))

    def add(self, p):
        self.result.append(p)
        seen = set()
        add = seen.add
        self.result = [x for x in self.result if not (x in seen or add(x))]
    async def send_initial_message(self, ctx, channel):
        return await ctx.send(embed=self.embed)

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.result

    async def editmsg(self):
        self.embed.description = ''.join(self.embed.description.splitlines(
            keepends=True)[:-1]) + f"Currently selected: {pnoun_list(self.result)}"
        await self.message.edit(embed=self.embed)


    async def handler(self, payload):
        if payload.event_type == "REACTION_REMOVE":
            return
        used = ['\U0001F468', '\U0001F469', '\U0001F9D1'].index(payload.emoji.name)
        self.add(Pronouns(FULLS[used]))
        await self.remove_button(payload.emoji.name, react=True)
        await self.editmsg()

    async def other(self, payload):
        if payload.event_type == "REACTION_REMOVE":
            return
        
        td = await self.ctx.send(fixml(f"""
            Please type either a pair (e.g. `{choice(PAIRS)}`) or the 5 forms of the pronoun (`{choice(FULLS)}`).
            If you type pair, they/them will populate the rest of the 5 forms when needed, though this is not recommended."""))
        def check(m):
            return (m.author == self.ctx.author) and (m.channel == self.ctx.channel)

        try: ret = (await self.bot.wait_for('message', check=check, timeout=60.0)).content
        except:
            return await self.ctx.send("Timed out. Please re-select try again.", delete_after=5)
        r = fullmatch(r"(?:[^/]+/[^/]+)(/(?:[^/]+/){2}[^/]+)?", ret)
        if not r:
            return await self.ctx.send("Invalid pronouns. Please re-select and try again.", delete_after=5)
        if not r.groups()[0]:
            ret += "/their/theirs/themselves"
        
        p = Pronouns(ret)

        a = await Confirm(fixml(f"""
            **{p.subject.title()}** gave me **{p.pos_d}** ball, and I gave it back to **{p.object}**.
            **{p.subject.title()}** looked at **{p.reflex}** in the mirror.
            All of these are **{p.pos_p}**.
            
            Are these correct?"""), delete_message_after=True).prompt(self.ctx)
        if not a:
            return await self.ctx.send("Please re-select and try again.", delete_after=5)
        self.add(p)
        await self.ctx.send("Pronouns added! Please continue adding more (or hit \u2705).", delete_after=10)
        await td.delete()
        await self.editmsg()

    async def fromlink(self, payload):
        if payload.event_type == "REACTION_REMOVE":
            return
        await self.ctx.send(fixml(f"""
            Please send a supported link to fetch pronouns from.
            Supported links are:
            > en.pronouns.page links
            > pronouny.xyz links
            > pronoun.is links"""))
        LINKS = ('en.pronouns.page', 'pronouny.xyz', 'pronoun.is')

        def check(m):
            return (m.author == self.ctx.author) and (m.channel == self.ctx.channel)

        try: ret = (await self.bot.wait_for('message', check=check, timeout=60.0)).content
        except:
            return await self.ctx.send("Timed out. Please re-select try again.", delete_after=5)
        try:
            await self.ctx.trigger_typing()
            r: aiohttp.ClientResponse = await httpfetch(ret, 2)
        except:
            return await self.ctx.send("Invalid link or error while fetching. Please re-select try again.", delete_after=5)
        if r.host not in LINKS: 
            return await self.ctx.send("Invalid link. Please re-select try again.", delete_after=5)
        t = LINKS.index(r.host)
        rel = str(r.url.relative())[1:]
        #TODO: wrsp in try
        add = []
        if t == 0:
            if rel[0] == "@":
                add = await get_pnounspage(rel[1:])
            elif fullmatch(r"([^/]+\/){4}[^/]+", rel):
                add.append(Pronouns(rel))
            else:
                p = await httpfetch("https://en.pronouns.page/api/pronouns/" + rel, json=True)
                add.append(Pronouns('/'.join(p['morphemes'].values())))
        elif t == 1:
            if rel.startswith("u/"):
                p = await httpfetch("https://pronouny.xyz/api/users/profile/username/" + rel[2:], 1)
                for x in p['pronouns']:
                    add.append(Pronouns(x['pattern']))
            elif rel.startswith("pronouns/"):
                p = await httpfetch("https://pronouny.xyz/api/pronouns/" + rel[9:], 1)
                add.append(Pronouns(p['pattern']))
            else: raise ValueError("Unknown type of pronouny link.")
        elif t == 2:
            if fullmatch(r"([^/]+\/){4}[^/]+", rel):
                add.append(Pronouns(rel))
            else:
                try:
                    add.append(PronounIsland().feed(await httpfetch(ret)))
                except: raise ValueError("Failed to parse the site.")
        for x in add:
            self.add(x)
        await self.editmsg()
        await self.ctx.send(f"Added **{pnoun_list(add, True)}** to pronouns! Please continue adding more (or hit \u2705).",
            delete_after=10)



    @menus.button('\u23F9')
    async def cancelb(self, _payload):
        self.result = None  # ensure we cancel
        self.stop()
    
    @menus.button('\u2705')
    async def finish(self, _payload):
        self.stop()
