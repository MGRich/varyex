import discord, dateparser, aiohttp, re, random, html, imghdr, io, os
from discord.ext import commands, tasks
import cogs.utils.mpk as mpku
from typing import Optional, Union
from datetime import datetime, timedelta
from asyncio import sleep
from numpy import clip
from PIL import Image

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
    #print(text)
    return html.unescape(text).strip()

async def getcode(url):
    print(f"try {url}")
    try: 
        async with aiohttp.request('HEAD', url) as resp:
            print(resp.status)
            return resp.status
    except:
        print(408)
        return 408  


class Miscellaneous(commands.Cog):
    def __init__(self, bot: commands.Bot):
        # pylint: disable=no-member
        self.bot = bot
        self.firstrun = True
        self.lastsromg = self.lastdate = 0
        self.garfloop.start()

    def cog_unload(self):
        # pylint: disable=no-member
        self.garfloop.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        # pylint: disable=no-member
        if (self.garfloop.get_task()): self.garfloop.cancel()
        self.garfloop.start()

    @commands.command(aliases = ['usrprefix', 'userprefix'])
    async def prefix(self, ctx, prefix: Optional[str] = None):
        """Sets the prefix for either the server or yourself.
        If you set server prefix, you **must have manage guild.**

        `prefix <prefix>`
        `userprefix/usrprefix <prefix>`"""
        mpm = mpku.MPKManager("misc", ctx.guild.id)
        mpk = mpm.data
        user = False
        users = mpku.MPKManager("users", None)
        mid = str(ctx.author.id)
        try:
            users.data[mid]['prefix']
            user = True
        except: pass

        if not prefix:
            if not user:
                return await ctx.send(f"My main prefix here is `{self.bot.command_prefix(self.bot, ctx.message)[0]}`.")
            prefixes = self.bot.command_prefix(self.bot, ctx.message)
            return await ctx.send(f"Your personal prefix is `{prefixes[0]}` and my main prefix here is `{prefixes[1]}`.")
        user = ctx.invoked_with in ['usrprefix', 'userprefix']
        rem = prefix in ["reset", "off"]
        if user:
            try: users.data[mid]
            except: users.data[mid] = {}
            if not rem: users.data[mid]['prefix'] = prefix
            else:
                try: del users.data[mid]['prefix']
                except: pass
            users.save()
            if not rem:
                return await ctx.send(f"Your personal prefix is now `{prefix}`!")
            return await ctx.send("Your personal prefix has been reset.")
        if not ctx.author.guild_permissions.manage_guild: return
        if not rem: mpk['prefix'] = prefix
        else:
            try: del mpk['prefix']
            except: pass
        mpm.save()
        if not rem: await ctx.send(f"My prefix here is now `{prefix}`!")
        else: await ctx.send("My prefix here has been reset.")

    @commands.command()
    async def ping(self, ctx):
        """Checks latency."""
        resp = await ctx.send('Pong! Loading...')
        diff = resp.created_at - ctx.message.created_at
        await resp.edit(content=f'Pong! That took {1000*diff.total_seconds():.1f}ms.')

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def say(self, _unusedctx, chn: discord.TextChannel, *, funny):
        """Says something in a channel.
        **Must have administrator permission.**

        `say <chn> <text>`"""
        await chn.send(funny)

    @commands.command(aliases = ['about', 'invite'])
    async def info(self, ctx):
        """Shows information about me."""
        #("Members", len(list(self.bot.get_all_members)))
        e = discord.Embed(title="Info", colour=discord.Colour(self.bot.data['color']))
        e.description = f"""**Version:** {self.bot.data['version']}
        **Owned by:** {self.bot.owner.mention}
        **Stats:** {len(self.bot.guilds)} servers, unsharded
        __**[Invite link]({discord.utils.oauth_url(str(self.bot.user.id), permissions=discord.Permissions(permissions=268446911))})**__"""
        e.set_footer(text=f"Made using discord.py version {discord.__version__}", icon_url="https://cdn.discordapp.com/icons/336642139381301249/3aa641b21acded468308a37eef43d7b3.webp")
        await ctx.send(embed=e)
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        try:
            await sleep(20)
            brighten = int(self.bot.data['color'])
            ls = [(brighten >> 16) & 0xFF, (brighten >> 8) & 0xFF, brighten & 0xFF]
            i = 0
            for x in list(ls):
                ls[i] = int(clip(x * 1.3, 0, 255))
                i += 1
            brighten = (ls[0] << 16) | (ls[1] << 8) | ls[2]
            joined = guild.get_member(self.bot.user.id).joined_at
            for x in guild.roles:
                if (joined - x.created_at < timedelta(seconds=1)) and x.managed:
                    return await x.edit(color=discord.Color(brighten))
        except discord.Forbidden: return
    ##########################################GARFIELD############################################
    async def calcstripfromdate(self, date: Union[datetime, int], sromg): 
        attempts = 0
        if not sromg: 
            while attempts <= 5:
                url = f"https://d1ejxu6vysztl5.cloudfront.net/comics/garfield/{date.year}/{date.strftime('%Y-%m-%d')}.gif"
                if (await getcode(url)) == 200: return (url, limitdatetime(date))
                #url = f"http://strips.garfield.com/iimages1200/{date.year}/ga{date.strftime('%y%m%d')}.gif"
                #if (await getcode(url)) == 200: return (url, limitdatetime(date)) #currently frozen
                for fn in ['gif', 'jpg', 'png']:
                    url = f"http://picayune.uclick.com/comics/ga/{date.year}/ga{date.strftime('%y%m%d')}.{fn}"
                    if (await getcode(url)) == 200: return (url, limitdatetime(date))
                date -= timedelta(days=1)
                attempts += 1
        else:
            #this is the day it started being consistent (i hope)
            if type(date) != int:
                stripnum = (date - datetime(2010, 1, 25)).days + 251
            else: stripnum = date
            maxnum = (datetime.utcnow() - datetime(2010, 1, 25)).days + 251
            while attempts <= 10:
                for x in ['png', 'gif', 'jpg']:
                    url = f"https://www.mezzacotta.net/garfield/comics/{stripnum:04}.{x}"
                    if (await getcode(url)) == 200: return (url, limitdatetime(datetime.utcnow()) - timedelta(days=(maxnum - stripnum)))
                stripnum -= 1
                attempts += 1
        return (-1, datetime.utcnow())

    
    async def formatembed(self, url, s, d, day=None):
        embed = discord.Embed(title=f"{'Daily ' if d else ''}{'SROMG' if s else 'Garfield'} Comic", colour=discord.Color(0xfe9701))
        if s: 
            num = url.split('/')[-1][:-4]
            embed.set_footer(text=f"Strip #{int(num)}")
            js = None
            try:
                async with aiohttp.request('GET', f"https://garfield-comics.glitch.me/~SRoMG/?comic={num}") as resp: #TODO: if and when zulu changes this, change how this works
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
                        ogstrips += f"[{formatted}]({x['href']}), "
                    if js['originalStrips'][8:]:
                        ogstrips += f"{len(js['originalStrips'][8:])} more  "
                    ogstrips = ogstrips[:-2] + "*"
                if len(authordesc) > (2048 - len(ogstrips)):
                    toadd = "*[visit SROMG page for rest]*"
                    authordesc = ''.join([(x + ".") for x in (authordesc[:(2048 - len(ogstrips) - len(toadd)) - 2].split('.'))[:-1]])
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
            
    @commands.command(aliases=['gstrip', 'garf', 'sromg'])
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
                mpm = mpku.getmpm("misc", ctx.guild)
                mpk = mpm.data
            else:
                mpm = mpku.MPKManager('users', None)
                mpk = mpm.data[str(ctx.author.id)]
            try: mpk['garfield']
            except: mpk['garfield'] = {'g': 0, 's': 0}
            check = 's' if isSROMG else 'g'
            if (not mpk['garfield'][check]) or (ctx.guild and mpk['garfield'][check] != ctx.channel.id):
                mpk['garfield'][check] = ctx.channel.id if ctx.guild else 1
                mpm.save()
                return await ctx.send(f"{'This channel' if ctx.guild else 'You'} will now recieve {'SROMG' if isSROMG else 'Garfield'} strips daily!")
            mpk['garfield'][check] = 0
            mpm.save()
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

    @tasks.loop(minutes=5, reconnect=True)
    async def garfloop(self):
        print("gstart")
        gurl, gdate = await self.calcstripfromdate(datetime.utcnow() + timedelta(days=1), False)
        surl, _sdate = await self.calcstripfromdate(datetime.utcnow() + timedelta(days=1), True)
        gembed = sembed = None
        if self.firstrun:
            if (surl == -1) or (gurl == -1): return
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
            snum = int(surl.split('/')[-1][:-4])
            if snum > self.lastsromg:
                shown |= 2
                sembed = await self.formatembed(surl, True, True)
                self.lastsromg = snum
        print(shown)
        #if not shown: return
        #first we check guilds cause thats easy
        for guild in self.bot.guilds:
            guild: discord.Guild
            try: mpk = mpku.getmpm('misc', guild).data['garfield']
            except: continue
            if (shown & 0b01) and mpk['g']:
                chn = guild.get_channel(mpk['g'])
                if chn:
                    await chn.send(embed=gembed)
            if (shown & 0b10) and mpk['s']:
                chn = guild.get_channel(mpk['s'])
                if chn:
                    await chn.send(embed=sembed)
        mpkr = mpku.MPKManager("users", None).data
        for uid in mpkr:
            try: mpk = mpkr[uid]['garfield']
            except: continue
            user: discord.User = self.bot.get_user(uid)
            if not user: user = await self.bot.fetch_user(uid)
            if not user: continue
            if (shown & 0b01) and mpk['g']:
                try: await user.send(embed=gembed)
                except: continue
            if (shown & 0b10) and mpk['s']:
                try: await user.send(embed=sembed)
                except: continue

    @commands.command()
    async def imgfilter(self, ctx, filter, *links):
        """Applies a filter to images.
        You can send images as links or attachments.
        GIFs are not supported.

        `imgfilter <filter> [links]` where `filter` CONTAINS (ex. `genesis` works):
        > `gen` - Sega Genesis 3-bit filter
        > `565` - RGB565 filter, used for some consoles and other graphics"""
        if (len(ctx.message.attachments) == 0 and not links): return
        ftouse = ""
        if   ("gen" in filter.lower()): ftouse = "gen"
        elif ("565" in filter.lower()): ftouse = "565"
        if not ftouse: return await ctx.send("Invalid filter!")
        images = []
        invalid = []
        total = list(links) + [x.url for x in ctx.message.attachments]
        for link in total:
            #try:
            print(link)
            async with aiohttp.request('GET', link) as resp:
                read = await resp.read()
                if imghdr.what("", h=read) == "gif": invalid.append(link)
                else: 
                    images.append(Image.open(io.BytesIO(read)))
            #except: invalid.append(link)
        msg = await ctx.send("Converting, please wait...")
        done = 0
        files = []
        for img in images:
            await msg.edit(content=f"Converting, please wait... {str(done)}/{len(images)} done")
            img.convert('RGB')
            map = img.load()
            if ftouse == "gen":
                gencolour = [00, 0x34, 0x57, 0x74, 0x90, 0xAC, 0xCE, 0xFF]
                clrchecks = [0x20, 0x40, 0x60, 0x80, 0xA0, 0xC0, 0xE0, 0xFE]
                for y in range(img.height):
                    for x in range(img.width):
                        tup = list(map[x, y])
                        for ii in range(3):
                            for i in range(8):
                                if (tup[ii] < clrchecks[i]):
                                    tup[ii] = gencolour[i]
                                    break
                        map[x, y] = tuple(tup)
            elif ftouse == "565":
                #first we need to turn into 565
                for y in range(img.height):
                    for x in range(img.width):
                        #print(map[x, y])
                        if (len(map[x, y]) == 4):
                            R, G, B, A = map[x, y]
                        else:
                            R, G, B = map[x, y]
                            A = 255
                        val = ((B >> 3) | (G >> 2) << 5 | ((R >> 3) << 11)) & 0xFFFF
                        #now we seperate
                        oR = (val & 0xF800) >> 11
                        oG = (val & 0x7E0) >> 5
                        oB = (val & 0x1F)
                        #and turn back into 888
                        map[x, y] = (((oR * 527 + 23) >> 6), ((oG * 259 + 33) >> 6), ((oB * 527 + 23) >> 6), A)
            img.save(f"{ctx.message.id}{done}.png")
            files.append(discord.File(f"{ctx.message.id}{done}.png"))
            done += 1
        await msg.delete()
        await ctx.send(files=files)
        for x in range(done):
            os.remove(f"{ctx.message.id}{x}.png")




def setup(bot):
    bot.add_cog(Miscellaneous(bot))