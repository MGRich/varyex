import discord
from discord.ext import menus

from datetime import datetime, timedelta
from copy import copy
import pytz

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
        'emoji': 829807531915345920,
        'link': 'https://en.pronouns.page/@[]',
        'prefix': '@',
        'type': 1,
        're': r'@(?P<name>\w*)',
        'embed': False,
        'name': 'PronounsPage',
        'color': 0xc71585
    }
}


# https://stackoverflow.com/a/19968515
def isdst(tz): bool(datetime.now(tz).dst())

def calcyears(dt: datetime, now):
    c = -1  # ALWAYS hits once, this is easier management
    if dt.day == 29 and dt.month == 2:
        # treat good ol leap year as march for the unfortunate out there
        dt = dt.replace(day=1, month=3)

    def daterange():
        for n in range(int((now - dt).days)):
            yield dt + timedelta(n)
    for x in daterange():
        if x.date() == dt.replace(year=x.year).date():
            c += 1
    if now.date() == dt.replace(year=now.year).date():
        c += 1
    return c


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
            self.result = '/'.join(self.deepl) + picked[-1]
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


class PronounSelector(menus.Menu):
    def __init__(self, bot):
        super().__init__()
        self.result = {}
        self.dval = 0
        self.double = 2
        self.bot = bot

        self.embed = discord.Embed(title="Pronoun Selector", color=self.bot.data['color'],
                                   description="""
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
        return await ctx.send(embed=self.embed)

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        return self.result

    async def handler(self, payload):
        if payload.event_type == "REACTION_REMOVE":
            return
        used = ['\u2642', '\u2640', '\U0001F9D1'].index(payload.emoji.name)
        n = ((self.double % 2) * 2)
        self.dval = (self.dval & ~(0b11 << n)) | (used << n)
        self.result = {'value': self.dval, 'custom': False}
        if (self.double >= 2):
            self.stop()
        else:
            self.double += 1
            await self.remove_button(payload.emoji.name, react=True)
            self.embed.description = ''.join(self.embed.description.splitlines(
                keepends=True)[:-1]) + f"Currently selected: {pronounstrings(self.result)[0]}"
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
        self.result = {}  # ensure we cancel
        self.stop()


def pronounstrings(d):
    ps = ""
    used = "their"
    if (d['custom']):
        if type(d['value']) == str:
            ps = d['value']
        else:
            used = d['value']['use']
            ps = ', '.join([d['value']['list']])
    else:
        double = False
        vused = d['value']
        if (vused & 0b10000):
            double = True
            vused &= 0b11  # primary first
        if (vused == 0):
            ps = "he/him"
            used = "his"
        elif (vused == 1):
            ps = "she/her"
            used = "her"
        elif (vused == 2):
            ps = "they/them"  # non-binary (0b10 = 2) :troll
        if (double):
            #we modify just after the /
            ps = ps.split('/')[0] + '/'
            vused = (d['value'] >> 2) & 0b11
            if (vused == 0):
                ps += "he"
            elif (vused == 1):
                ps += "she"
            elif (vused == 2):
                ps += "they"
    return (ps, used)
