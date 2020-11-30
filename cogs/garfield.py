import discord, aiohttp, logging
from discord.ext import commands
from cogs.utils.loophelper import trackedloop

import cogs.utils.mpk as mpku

from typing import Union, Optional
from datetime import datetime, timedelta
import re, html
import random
import dateparser

LOG = logging.getLogger("bot")

def limitdatetime(dt):
    return datetime.combine(dt.date(), datetime.min.time())

def htmltomarkup(text):
    text = re.sub(r"<a *href=\"([^\"]*)\">(.*?(?=</a>))</a>", r"[\2](\1)", text)
    text = re.sub(r"<(i|cite|em)>([^<]*)</(i|cite|em)>", "*\\2*", text)
    text = re.sub(r"<u>([^<]*)</u>", "__\\1__", text)
    text = re.sub(r"<(b|strong)>([^<]*)</(b|strong)>", "**\\2**", text)
    text = re.sub(r"<code>(.*?(?=</code>))</code>", "`\\1`", text)
    coderebuild = []
    addtilde = False
    for x in text.splitlines():
        if re.fullmatch(r"<code>", x): 
            addtilde = True
            continue
        if re.fullmatch(r"</code>", x):
            coderebuild[-1] += "`" 
            continue
        if addtilde:
            x = "`" + x
            addtilde = False
        coderebuild.append(x)
    text = '\n'.join(coderebuild)
    text = re.sub("<br>\n*", "\n", text) 
    #1st, lets handle those with an alt so we dont have to deal with them later
    text = re.sub(r"<img.*src=\"([^\"]*)\"(.*(?=alt=))alt=\"([^\"]*)\"[^>]*>", r"[[IMG: \3]](\1)", text)
    #now we can do ones without alt
    text = re.sub(r"<img.*src=\"([^\"]*)\"[^>]*>", r"[[IMG]](\1)", text)
    text = re.sub(r"\[([^\]]*)(\]*)\(\/([^\)]*)\)", "[\\1\\2(https://mezzacotta.net/\\3)", text) #should only be mezzacotta, we should be fine
    text = re.sub(r"<iframe.*?>.*<\/iframe>", "[iframe]", text)
    #lets try and move external markup to the outside
    text = re.sub(r"\[((\*|_)*)([^\1\]]*)\1\](\([^\)]*\))", "\\1[\\3]\\4\\1", text)
    #LOG.debug(text)
    return html.unescape(text).strip()

async def getcode(url):
    try: 
        async with aiohttp.request('HEAD', url) as resp:
            return resp.status
    except: return 408


class Garfield(commands.Cog):
    def __init__(self, bot: commands.Bot):
        # pylint: disable=no-member
        self.bot = bot
        self.firstrun = True
        self.lastsromg = self.lastdate = 0

    def cog_unload(self):
        # pylint: disable=no-member
        self.garfloop.cancel()
        
    async def calcstripfromdate(self, date: Union[datetime, int], sromg): 
        attempts = 0
        if not sromg: 
            while attempts <= 5:
                url = f"https://d1ejxu6vysztl5.cloudfront.net/comics/garfield/{date.year}/{date.strftime('%Y-%m-%d')}.gif"
                if (await getcode(url)) == 200: return (url, limitdatetime(date))
                #url = f"http://strips.garfield.com/iimages1200/{date.year}/ga{date.strftime('%y%m%d')}.gif"
                #if (await getcode(url)) == 200: return (url, limitdatetime(date)) #currently frozen
                for fn in {'gif', 'jpg', 'png'}:
                    url = f"http://picayune.uclick.com/comics/ga/{date.year}/ga{date.strftime('%y%m%d')}.{fn}"
                    if (await getcode(url)) == 200: return (url, limitdatetime(date))
                date -= timedelta(days=1)
                attempts += 1
        else:
            #this is the day it started being consistent (i hope)
            if not isinstance(date, int):
                stripnum = (date - datetime(2010, 1, 25)).days + 251
            else: stripnum = date
            maxnum = (datetime.utcnow() - datetime(2010, 1, 25)).days + 251
            while attempts <= 10:
                for x in {'png', 'gif', 'jpg'}:
                    url = f"https://www.mezzacotta.net/garfield/comics/{stripnum:04}.{x}"
                    if (await getcode(url)) == 200: return (url, limitdatetime(datetime.utcnow()) - timedelta(days=(maxnum - stripnum)))
                stripnum -= 1
                attempts += 1
        return (-1, datetime.utcnow())

    
    async def formatembed(self, url, s, d, day=None):
        embed = discord.Embed(title=f"{'Daily ' if d else ''}{'SROMG' if s else 'Garfield'} Comic", colour=0xfe9701)
        if s: 
            num = url.split('/')[-1][:-4]
            embed.set_footer(text=f"Strip #{int(num)}")
            js = None
            try:
                async with aiohttp.request('GET', f"https://garfield-comics.glitch.me/~SRoMG/?comic={num}") as resp:
                    js = (await resp.json())['data']
            except: pass
            if not js:
                embed.description = f"View the details of the strip [here.](https://www.mezzacotta.net/garfield/?comic={num})"
            else:
                embed.title = f"{'Daily ' if d else ''}SROMG | {js['name']}"
                embed.url = f"http://www.mezzacotta.net/garfield/?comic={num}"
                authordesc = htmltomarkup(js['authorWrites'].split("Original strip")[0])
                tr = re.sub("<br>\n*", "\n", js['transcription'].replace("*", "\\*").replace("\n", "")) 
                tr = htmltomarkup('\n'.join(tr.splitlines()[:11]))
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
                embed.set_author(name=js['author']['name'], url=f"https://www.mezzacotta.net/garfield/author.php?author={js['author']['number']}'")
                ogstrips = toadd = ""
                if (js['originalStrips']):
                    ogstrips += f"\n*Original strip{'s' if len(js['originalStrips']) > 1 else ''}: "
                    for x in js['originalStrips'][:8]: 
                        formatted = re.sub(r'..([^-]*)-([^-]*)-(.*)', r'\2/\3/\1', x['strip'])
                        if (formatted == "11/17/17"): 
                            return discord.Embed(title="SROMG", description = f"it's a radish strip, who cares\n[here's the strip]({embed.url})", color=0xfe9701)
                        ogstrips += f"[{formatted}]({x['href']}), "
                    if js['originalStrips'][8:]:
                        ogstrips += f"{len(js['originalStrips'][8:])} more  "
                    ogstrips = ogstrips[:-2] + "*"
                if len(authordesc) > (2048 - len(ogstrips)):
                    toadd = "*[visit SROMG page for rest]*"
                    authordesc = ''.join(tuple((x + ".") for x in (authordesc[:(2048 - len(ogstrips) - len(toadd)) - 2].split('.'))[:-1]))
                embed.description = authordesc + (("\n" + toadd) if toadd else "") + "\n" + ogstrips
                embed.set_footer(text=f"Strip #{int(num)} | API by LiquidZulu")
        else:
            isfallback = 'picayune' in url
            embed.set_footer(text=f"Strip from {day.month}/{day.day}/{day.year}{' (fallback CDN)' if isfallback else ''}")
        embed.set_image(url=url)
        return embed
        
    @commands.Cog.listener()
    async def on_message(self, m):
        if re.fullmatch("show (comic|sromg|strip)", m.content):
            await m.channel.trigger_typing()
            s = m.content.split()[1] == "sromg"
            url, date = await self.calcstripfromdate(datetime.utcnow() + timedelta(days=1), s)
            await m.channel.send(embed=await self.formatembed(url, s, False, date))    
            
    @commands.command(aliases=('gstrip', 'garf', 'sromg'))
    async def garfield(self, ctx: commands.Context, *, date: Optional[str]):
        """Shows a Garfield or SROMG strip. You can also subscribe to daily strips (including DMs).
        Subscribing to a **channel** (not DMs) requires you to have **manage channel** for that channel.

        `garfield/gstrip/g/sromg [date]`
        `g/sromg sub/subscribe`
        `g/sromg random`"""
        await ctx.trigger_typing()
        isSROMG = ctx.message.content.startswith(f"{ctx.prefix}sromg")
        num = 0
        if not date:
            date = limitdatetime((datetime.utcnow() + timedelta(days=1)))
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
                num = random.randrange(1, self.lastsromg + 1)
            else:
                start = datetime(1978, 6, 19)
                delt = datetime.utcnow() - start #https://stackoverflow.com/questions/553303/
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
                if date > datetime.utcnow() + timedelta(days=1): return await ctx.send("Please send a date that is not in the far future (1 day max).")
        if not num: 
            while (date > (datetime.utcnow() + timedelta(days=1))): date -= timedelta(days=1)
        else: date = num
        url, date = await self.calcstripfromdate(date, isSROMG)
        if (url == -1):
            return await ctx.send("Could not find that strip.")
        await ctx.send(embed=await self.formatembed(url, isSROMG, False, date))

    @trackedloop(minutes=5, reconnect=True)
    async def garfloop(self):
        LOG.debug("gstart")
        gurl, gdate = await self.calcstripfromdate(datetime.utcnow() + timedelta(days=1), False)
        surl, _sdate = await self.calcstripfromdate(datetime.utcnow() + timedelta(days=1), True)
        gembed = sembed = None
        if self.firstrun:
            if -1 in {surl, gurl}: return
            self.lastdate = gdate
            self.lastsromg = int(surl.split('/')[-1][:-4])
            self.firstrun = False
            return
        shown = 0
        if (gurl != -1) and gdate > self.lastdate:
            shown |= 1
            gembed = await self.formatembed(gurl, False, True, gdate)
            self.lastdate = gdate
        if (surl != -1):
            if (snum := int(surl.split('/')[-1][:-4])) > self.lastsromg:
                shown |= 2
                sembed = await self.formatembed(surl, True, True)
                self.lastsromg = snum
        LOG.debug(shown)
        #if not shown: return
        #first we check guilds cause thats easy
        for guild in self.bot.guilds:
            guild: discord.Guild
            try: mpk = mpku.getmpm('misc', guild)['garfield']
            except: continue
            if (shown & 0b01) and mpk['g']:
                chn = guild.get_channel(mpk['g'])
                try: await chn.send(embed=gembed)
                except: pass
            if (shown & 0b10) and mpk['s']:
                chn = guild.get_channel(mpk['s'])
                try: await chn.send(embed=sembed)
                except: pass
        mpkr = self.bot.usermpm.copy()
        for uid in mpkr:
            mpk = mpkr[uid]['garfield']
            user: discord.User = self.bot.get_user(uid)
            if not user: user = await self.bot.fetch_user(uid)
            if not user: continue
            if (shown & 0b01) and mpk['g']:
                try: await user.send(embed=gembed)
                except: continue
            if (shown & 0b10) and mpk['s']:
                try: await user.send(embed=sembed)
                except: continue

def setup(bot):
    bot.add_cog(Garfield(bot))