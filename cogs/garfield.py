import discord, logging
from discord.ext import commands
from imports.loophelper import trackedloop

import imports.mpk as mpku
from imports.other import httpfetch, urlisOK
from discord.utils import utcnow

from typing import Union, Optional, List, Tuple, TYPE_CHECKING
from datetime import datetime, timedelta, timezone
import re
from html.parser import HTMLParser
import random
import dateparser


from imports.main import Main

LOG = logging.getLogger("bot")

def limitdatetime(dt):
    return datetime.combine(dt.date(), datetime.min.time())


def getadditive(tag, attrs):
    if tag in {'b', 'strong'}:
        return '**'
    if tag in {'i', 'cite', 'em'}:
        return '*'
    if tag in {'u'}:
        return '__'
    if tag in {'code'}:
        return '`'
    if tag == "img":
        #check if there's alt
        alt = None
        img = None
        for t, d in attrs:
            if t == 'alt':
                alt = d
            elif t == 'src':
                img = d
        if alt:
            return f"[[IMG: {alt}]]({img})"
        return f"[[IMG]]({img})"
    #as have to be handled seperately
    if tag == 'iframe':
        return '[iframe]'
    return ""


class SROMGParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.data = {'title': None, 'description': "", 'ogstrips': [],
                     'author': None, 'transcript': "", 'image': None, 'number': 0}
        self.fetch = None
        self.pcount = 0
        self.PS = {'author': 6, 'tscript': 7, 'desc': 9}
        self.lasttag = None

    async def getdata(self, url):
        self.feed(await httpfetch(url, headers={"Connection": "Upgrade", "Upgrade": "http/1.1"}))
        if self.data['description'] and self.data['description'].splitlines()[-1].startswith("[["):
            self.data['description'] = '\n'.join(
                self.data['description'].splitlines()[:-1]).strip()
        return self.data

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self.pcount += int(tag == 'p')
        if tag == 'h2' and not self.data['title']:
            self.fetch = 'title'
        elif tag == 'img' and not self.data['image']:
            for t, d in attrs:
                if t != 'src':
                    continue
                if not d.startswith('/garfield/comics/'):
                    break
                self.data['image'] = "https://www.mezzacotta.net" + d
        elif self.pcount == self.PS['tscript'] and tag == 'p':
            self.fetch = 'transcript'
        elif self.pcount == self.PS['author'] and tag == 'a':
            self.fetch = 'author'
            link = None
            for t, d in attrs:
                if t != 'href':
                    continue
                link = "https://www.mezzacotta.net" + d
            self.data['author'] = {'link': link}
        elif self.pcount == self.PS['desc']:
            self.fetch = 'description'

        if self.fetch:
            self.lasttag = (tag, attrs)
            if self.fetch == 'description': 
                if tag == 'div':
                    self.fetch = None
                    self.pcount += 1
                elif tag != 'a':
                    self.data['description'] += getadditive(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if self.fetch == 'description':
            if tag in {'a', 'img'}:
                return
            self.data['description'] += getadditive(tag, None)
        elif self.fetch == 'ogstrips' and tag == 'p':
            self.fetch = None

    def handle_data(self, data: str) -> None:
        if not self.fetch:
            if (self.pcount == self.PS['tscript']):
                self.data['transcript'] += data
            return
        if self.fetch == 'ogstrips':
            if self.lasttag[0] != 'a':
                return
            link = None
            for t, d in self.lasttag[1]:
                if t != 'href':
                    continue
                link = d
            self.data['ogstrips'].append({'date': data, 'link': link})
            self.lasttag = ('b',)
            return
        elif self.fetch == 'author':
            self.data['author']['name'] = data.strip()
        elif self.fetch == 'description':
            #print(self.getpos(), data, self.lasttag)
            if data.startswith("Original strip"):
                self.fetch = 'ogstrips'
            else:
                data = discord.utils.escape_markdown(data)
                if self.lasttag[0] != 'a':
                    self.data['description'] += data
                else:
                    link = None
                    for t, d in self.lasttag[1]:
                        if t != 'href':
                            continue
                        if d.startswith("/"):
                            link = "https://www.mezzacotta.net" + d
                        else:
                            link = d
                    self.data['description'] += f"[{data}]({link})"
                    self.lasttag = ('b',)
            return
        elif self.fetch == 'title':
            self.data['title'] = data
            self.data['number'] = int(data.split()[1][:-1])
        else:
            if self.data[self.fetch]:
                self.data[self.fetch] += data
            else:
                self.data[self.fetch] = data
        self.fetch = None

    def error(self, message: str) -> None:
        return



class Garfield(commands.Cog):
    def __init__(self, bot: Main):
        # pylint: disable=no-member
        self.bot = bot
        self.firstrun = True
        self.lastsromg = self.lastdate = 0

    def cog_unload(self):
        # pylint: disable=no-member
        self.garfloop.cancel()
        
    async def calcstripfromdate(self, date: Union[datetime, int]) -> Tuple[int, datetime]: 
        attempts = 0
        while attempts <= 5:
            url = f"https://d1ejxu6vysztl5.cloudfront.net/comics/garfield/{date.year}/{date.strftime('%Y-%m-%d')}.gif"
            if (await urlisOK(url)): return (url, limitdatetime(date))
            #url = f"http://strips.garfield.com/iimages1200/{date.year}/ga{date.strftime('%y%m%d')}.gif"
            #if (await getcode(url)) == 200: return (url, limitdatetime(date)) #currently frozen
            for fn in {'gif', 'jpg', 'png'}:
                url = f"http://picayune.uclick.com/comics/ga/{date.year}/ga{date.strftime('%y%m%d')}.{fn}"
                if (await urlisOK(url)): return (url, limitdatetime(date))
            date -= timedelta(days=1)
            attempts += 1
        return (-1, utcnow())

    async def calcsromg(self, di: Union[datetime, int]):
        direct = type(di) == int
        if not direct:
            stripnum = (di - datetime(2010, 1, 25)).days + 251
        else: stripnum = di
        if stripnum == -1:
            return await SROMGParser().getdata("https://www.mezzacotta.net/garfield/")
        d = await SROMGParser().getdata(f"https://www.mezzacotta.net/garfield/?comic={stripnum}")
        if stripnum and direct and d['number'] != stripnum: return -1
        return d

    async def formatembed(self, url, s, d, day=None):
        embed = discord.Embed(title=f"{'Daily ' if d else ''}{'SROMG' if s else 'Garfield'} Comic", colour=0xfe9701)
        if s: 
            js: dict = url
            num = str(js['number'])
            embed.set_footer(text=f"Strip #{int(num)}")
            embed.set_image(url=js['image'])
            embed.title = f"{'Daily ' if d else ''}SROMG | {js['title']}"
            embed.url = f"http://www.mezzacotta.net/garfield/?comic={num}"
            authordesc = js['description']
            tr = '\n'.join(js['transcript'].splitlines()[:11])
            tl = []
            toadd = "*[visit SROMG page for rest]*" #keep here just in case
            linecount = 0
            for x in tr.splitlines():
                if re.fullmatch(r"({|\().*(}|\))", x): 
                    t = "*" + x[1:-1] + "*" 
                else: t = re.sub(r"^([^:]*):", r"**\1**:", x, 1)
                linecount += 1
                over = (len('\n'.join(tl)) > 1024 - len(toadd))
                if (linecount > 10) or over:
                    if (over): tl = tl[:-1]
                    tl.append(toadd)
                    break
                tl.append(t)
            embed.add_field(name="Transcription", value='\n'.join(tl))
            embed.set_author(name=js['author']['name'], url=js['author']['link'])
            ogstrips = toadd = ""
            if (js['ogstrips']):
                ogstrips += f"\n*Original strip{'s' if len(js['ogstrips']) > 1 else ''}: "
                for x in js['ogstrips'][:8]: 
                    formatted = re.sub(r'..([^-]*)-([^-]*)-(.*)', r'\2/\3/\1', x['date'])
                    if (formatted == "11/17/17") and d: 
                        return discord.Embed(title="SROMG", description = f"it's a radish strip, who cares\n[here's the strip]({embed.url})", color=0xfe9701)
                    ogstrips += f"[{formatted}]({x['link']}), "
                if js['ogstrips'][8:]:
                    ogstrips += f"{len(js['ogstrips'][8:])} more  "
                ogstrips = ogstrips[:-2] + "*"
            if len(authordesc) > (2048 - len(ogstrips)):
                toadd = "*[visit SROMG page for rest]*"
                authordesc = ''.join(tuple((x + ".") for x in (authordesc[:(2048 - len(ogstrips) - len(toadd)) - 2].split('.'))[:-1]))
            embed.description = authordesc + (("\n" + toadd) if toadd else "") + "\n" + ogstrips
            embed.set_footer(text=f"Strip #{int(num)}")
        else:
            embed.set_image(url=url)
            isfallback = 'picayune' in url
            embed.set_footer(text=f"Strip from {day.month}/{day.day}/{day.year}")
        return embed
        
    @commands.Cog.listener()
    async def on_message(self, m: discord.Message):
        return
        if not re.fullmatch("show (comic|sromg|strip)", m.content.lower()): return
        await m.channel.trigger_typing()
        s = m.content.split()[1] == "sromg"
        if not s: url, date = await self.calcstripfromdate(utcnow() + timedelta(days=1))
        else: 
            url = await self.calcsromg(-1)
            date = None
        await m.channel.send(embed=await self.formatembed(url, s, False, date))    
            
    @commands.command(aliases=('gstrip', 'garf', 'sromg'))
    async def garfield(self, ctx: commands.Context, *, date: Optional[str]):
        """Shows a Garfield or SROMG strip. You can also subscribe to daily strips (including DMs).
        Subscribing to a **channel** (not DMs) requires you to have **manage channel** for that channel.

        `garfield/gstrip/g/sromg [date]`
        `g/sromg sub/subscribe`
        `g/sromg random`"""
        await ctx.trigger_typing()
        isSROMG = ctx.invoked_with == "sromg"
        num = None
        if not date:
            if not isSROMG: date = limitdatetime((utcnow() + timedelta(days=1)))
        elif date.startswith("sub"):
            if ctx.guild:
                if not ctx.author.permissions_in(ctx.channel).manage_channels: raise commands.MissingPermissions(["manage_channel"])
                mpk = mpku.getmpm("misc", ctx.guild)
            else:
                mpk = self.bot.usermpm[str(ctx.author.id)]
            mpk['garfield'] = ({'g': 0, 's': 0},)
            check = 's' if isSROMG else 'g'
            if (not mpk['garfield'][check]) or (ctx.guild and mpk['garfield'][check] != ctx.channel.id):
                mpk['garfield'][check] = ctx.channel.id if ctx.guild else 1
                mpk.save()
                return await ctx.send(f"{'This channel' if ctx.guild else 'You'} will now recieve {'SROMG' if isSROMG else 'Garfield'} strips daily!")
            mpk['garfield'][check] = 0
            mpk.save()
            return await ctx.send(f"{'This channel' if ctx.guild else 'You'} will no longer recieve {'SROMG' if isSROMG else 'Garfield'} strips.")
        elif date == "random":
            if isSROMG:
                num = 0
            else:
                start = datetime(1978, 6, 19, tzinfo=timezone.utc)
                delt = utcnow() - start #https://stackoverflow.com/questions/553303/
                intd = (delt.days * 24 * 60 * 60) + delt.seconds
                date = start + timedelta(seconds=random.randrange(intd))
        else:
            if isSROMG: 
                try: num = int(date)
                except: pass
                else: 
                    if num <= 0:
                        return await ctx.send("Please send a valid SROMG strip #.")
            if not num:
                msg = await ctx.send("Parsing date...")
                date = dateparser.parse(date, settings={'STRICT_PARSING': True})
                await msg.delete()
                if not date: return await ctx.send("Could not parse the date given.")
                date = date.replace(tzinfo=timezone.utc)
                if date > utcnow() + timedelta(days=1): return await ctx.send("Please send a date that is not in the far future (1 day max).")
        if num is None and date: 
            date = date.replace(tzinfo=timezone.utc) #just to be sure
            while (date > (utcnow() + timedelta(days=1))): date -= timedelta(days=1)
        else: date = num
        if isSROMG:
            return await ctx.send(embed=await self.formatembed(await self.calcsromg(-1 if date is None else date), True, False))
            #except: return await ctx.send("Could not find that SROMG strip.")
        url, date = await self.calcstripfromdate(date)
        if (url == -1):
            return await ctx.send("Could not find that strip.")
        await ctx.send(embed=await self.formatembed(url, isSROMG, False, date))

    @trackedloop(minutes=5, reconnect=True)
    async def garfloop(self):
        LOG.debug("gstart")
        gurl, gdate = await self.calcstripfromdate(utcnow() + timedelta(days=1))
        sdata = await self.calcsromg(-1)
        gembed = sembed = None
        if self.firstrun:
            if -1 == gurl or (type(sdata) == int and sdata == -1): return
            self.lastdate = gdate
            self.lastsromg = sdata['number']
            self.firstrun = False
            return
        if (gurl != -1) and gdate > self.lastdate:
            gembed = await self.formatembed(gurl, False, True, gdate)
            self.lastdate = gdate
        if (sdata != -1):
            if (snum := sdata['number']) > self.lastsromg:
                sembed = await self.formatembed(sdata, True, True)
                self.lastsromg = snum
        if not (gembed or sembed): return
        #first we check guilds cause thats easy
        for guild in self.bot.guilds:
            guild: discord.Guild
            if not (mpk := mpku.getmpm('misc', guild)['garfield']): continue
            if gembed and mpk['g']:
                try: await guild.get_channel(mpk['g']).send(embed=gembed)
                except: pass #pass because diff channels
            if sembed and mpk['s']:
                try: await guild.get_channel(mpk['s']).send(embed=sembed)
                except: pass
        mpkr = self.bot.usermpm.copy()
        for uid in mpkr:
            mpk = mpkr[uid]['garfield']
            user: discord.User = self.bot.get_user(uid) or await self.bot.fetch_user(uid)
            if not user: continue
            if gembed and mpk['g']:
                try: await user.send(embed=gembed)
                except: continue #continue because 1 channel
            if sembed and mpk['s']:
                try: await user.send(embed=sembed)
                except: continue

def setup(bot):
    bot.add_cog(Garfield(bot))
