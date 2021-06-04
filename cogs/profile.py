from discord.enums import ButtonStyle
from imports.mpk import DefaultContainer
import discord, asyncio, re, aiohttp
from discord.ext import commands
from discord import ui
from imports.loophelper import trackedloop
from imports.profiles import ACCOUNTS, UserAccount, UserProfile, Pronouns, PronounSelector, TZMenu, get_pnounspage, pnoun_list

#try: del ACCOUNTS['pronounspage']
#except: pass

from imports.converters import UserLookup, DurationString
from imports.menus import Confirm, Choice
from imports.other import getord, timestamp_to_int, timestamp_now, iiterate, httpfetch
from discord.utils import utcnow

from typing import TYPE_CHECKING, Union, Optional, List
from datetime import datetime, timedelta
import timeago
import pytz
import dateparser
import number_parser as numparser
from humanize import naturaltime
from lxml import html

import logging
LOG = logging.getLogger('bot')
dumpchannel = 777709381931892766

# https://stackoverflow.com/a/19968515


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

class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        # pylint: disable=no-member
        global dumpchannel
        self.bot = bot
        self.tzd = {}
        dumpchannel = bot.data['special']['profilechannel']
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


    def cog_unload(self):
        # pylint: disable=no-member
        self.remindloop.cancel()

    @commands.command(aliases = ('remind', 'reminder', 'setreminder', 'setremind'))
    async def remindme(self, ctx: commands.Context, *, ds: DurationString):
        """Sets a reminder that (tries) to DM you.
        If it can't DM you, it will send a message in the channel you set the reminder in.

        `remindme <duration> <message>`""" 
        if not ((d := ds.duration) and (st := ds.string)): return await ctx.send("Please set a valid reminder.")
        if d // 60 == 0: return await ctx.send("Please set a valid duration.")
        mpk = self.bot.usermpm[str(ctx.author.id)]
        mpk['reminders'].append({'len': d / 60, 'time': timestamp_to_int(utcnow() + timedelta(seconds=d)), 'msg': st, 'ch': ctx.channel.id})
        mpk.save()
        await ctx.send("Reminder set!")

    @trackedloop(minutes=1)
    async def remindloop(self):
        mpk = self.bot.usermpm
        changed = False
        cp = self.bot.usermpm.copy()
        for x in cp:
            if not (r := mpk[x]['reminders']): continue
            subtract = 0
            cr = r.copy()
            for reminder, i in iiterate(cr):
                if reminder['time'] <= timestamp_now():
                    changed = True
                    st = f"{naturaltime(timedelta(minutes=reminder['len'])).capitalize()}, you set a reminder: {reminder['msg']}"
                    try: await (await self.bot.fetch_user(int(x))).send(st)
                    except:
                        try: await self.bot.get_channel(int(reminder['ch'])).send(f"<@{x}> {st}")
                        except: pass #could not send reminder
                    del r[i - subtract]
                    subtract += 1
        if changed: mpk.save()
                    


    @commands.group(aliases = ("userinfo", "userprofile"))
    async def profile(self, ctx: commands.Context, user: Optional[UserLookup]):
        """Edit or get your own or someone else's profile.
        This also includes generic user info such as roles and account creation/server join date.

        `profile/userinfo <user>`
        
        **EDITING**
        > `profile edit <property> [text if applicable]`
        > Valid properties are: name, realname, pronoun, location, bio, birthday
        > `profile delete` to delete your profile"""
        if ctx.invoked_subcommand: return
        if not user: user = ctx.author
        user: discord.User
        e = discord.Embed(title=str(user))
        e.set_thumbnail(url=str(user.avatar))
        isguild = bool(ctx.guild)
        bm = ""
        isbot = user.bot
        if isguild:
            m: discord.Member = ctx.guild.get_member(user.id)
            isguild = bool(m)
            if m:
                e.color = m.color if m.color != discord.Color.default() else e.color
                gl = [f" - *{m.nick}*" if m.nick else "", f"**{'Added' if isbot else 'Joined'} at**: {m.joined_at.strftime('%m/%d/%y %I:%M %p')} UTC ({timeago.format(m.joined_at, utcnow())})\n"]
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
        e.description = f"""{user.mention}{' (bot owner) ' if user.id == self.bot.owner.id else ''}{glp(0)}{bm}\n**Created at**: {user.created_at.strftime('%m/%d/%y %I:%M %p')} UTC ({timeago.format(user.created_at, utcnow())})\n{glp(1)}"""
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
        if not (prf := UserProfile.fromuser(user)):
            return await ctx.send(embed=e)
        last: Union[dict, str]
        def getfromprofile(st, notset=False):
            nonlocal last
            last = getattr(prf, st) 
            if not last:
                last = "*Not set*" if notset else None
            return last
        #a lot of repetition for now just as a sketch
        pval += f"**Preferred name**: {getfromprofile('name', True)}\n"
        if (getfromprofile("realname")):
            pval += f"**Real name**: {last}\n"
        getfromprofile("pronouns")
        pval += "**Pronouns**: "
        if not last:
            pval += "*Not set*\n"
        else:
            pval += f"{prf.pronoun_list}\n"
            if isinstance(prf.pronouns[0], str) and user == ctx.author:
                pval += "> **Please reset your pronouns to use the new system.**\n"
        getfromprofile("birthday")
        pval += "**Birthday**: "
        if not last:
            pval += "*Not set*\n"
        else:
            invalid = False
            hasy = last.year != 1900
            curr = ""
            date = ""
            dt: datetime = last
            date = dt.strftime("%m/%d" if not hasy else "%m/%d/%y")
            tz = getfromprofile("timezone") or pytz.timezone("UTC")
            now = datetime.now(tz)
            if hasy:
                dt = dt.replace(tzinfo=tz)
                invalid = now < dt
                c = 0 if invalid else calcyears(dt, now)
                invalid = invalid or c < 13
                if not invalid: curr += f" ({c} years old)" 
            dt = dt.replace(year=now.year)
            LOG.debug(dt)
            LOG.debug(now)
            if now.date() == dt.date(): curr += f"\n> **(It's {prf.pronoun_to_use} birthday today! \U0001F389)**"
            if invalid:
                date = dt.strftime("%m/%d")
                prf.birthday = prf.birthday.replace(year=1900)
                prf.save()
                curr = f"\n> *({'Your' if ctx.author.id == prf.id else prf.pronoun_to_use.title()} birthyear was invalid, so it has been removed.)*"
            pval += f"{date}{curr}\n"

        if (getfromprofile("location")):
            pval += f"**Location**: {last}\n"
        pval += "**Timezone**: "
        if not (getfromprofile("timezone")):
            pval += "*Not set*\n"
        else:
            now = datetime.now(last)
            pval += f"{last.zone.replace('_', ' ')} (Currently `{now.strftime('%m/%d/%y %I:%M%p')}`)\n"

        getfromprofile("accounts")
        if last:
            last.sort(key=lambda x: x.type)
            aval = ""
            for acc in last:
                acc: UserAccount
                aval += str(acc) + "\n" 
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
        """Edit parts of your profile."""
        if ctx.invoked_subcommand: return
        p = self.bot.usermpm[str(ctx.author.id)]['profile']
        if isinstance(p, DefaultContainer) and p.isblank:
            a = await Confirm("Do you want to create a profile? You can delete it later. Remember, anyone can view your profile at any time.", delete_message_after=False).prompt(ctx)
            if not a: return await ctx.send("Profile declined.")
            mpk = self.bot.usermpm
            mpk[str(ctx.author.id)]['profile'] = UserProfile()
            mpk.save()
            return await ctx.reinvoke(restart=True)
            
        raise commands.UserInputError()

    @profile.command(aliases=('erase',))
    async def delete(self, ctx):
        try:
            if self.bot.usermpm[str(ctx.author.id)]['profile'].isblank:
               return await ctx.send("You don't have a profile!")
        except AttributeError: pass
        a = await Confirm("Are you sure you want to delete your profile? This cannot be undone.").prompt(ctx)
        if not a:
            return await ctx.send("Profile deletion declined.")
        mpk = self.bot.usermpm
        del mpk[str(ctx.author.id)]['profile'] 
        mpk.save()
        await ctx.send("Profile deleted.")

    async def _edit(self, ctx, prompts, max, key, pretext):
        if not (prf := UserProfile.fromuser(ctx.author)):
            return await ctx.invoke(self.edit)
        if not pretext: await ctx.send(prompts[0] + " You can type `cancel` to cancel, and `erase` to wipe the field clean.")
        def check(m):
            return (m.author == ctx.author) and (m.channel == ctx.channel)
        while True:
            if pretext: ret = pretext
            else:
                try: ret = (await self.bot.wait_for('message', check=check, timeout=60.0)).content
                except: return
            if (ret.lower() == "cancel"):
                await ctx.send(prompts[2])
                return
            if ret.lower() == "erase":
                await ctx.send(prompts[3])
                setattr(prf, key, "")
                prf.save()
                return
            if (len(ret) > max): 
                await ctx.send(f"Please keep it under {max} characters ({len(ret)}/{max}).", delete_after=5)
                if pretext: 
                    pretext = None
                    await ctx.send(prompts[0])
                continue
            setattr(prf, key, ret)
            prf.save()
            return await ctx.send(prompts[1])

    @edit.command(aliases = ('setrealname', 'rname'))
    async def realname(self, ctx, *, pretext: Optional[str]):
        """Sets your real name."""
        await self._edit(ctx, ["Please type your real name. Remember, **everyone can see this.** It must be under 30 characters.",
            "Real name set!", "Cancelled name setting.", "Erased real name."], 30, 'realname', pretext)

    @edit.command(aliases = ('setname',))
    async def name(self, ctx, *, pretext: Optional[str]):
        """Sets your name."""
        await self._edit(ctx, ["Please type your preferred name. It must be under 30 characters.",
            "Name set!", "Cancelled name setting.", "Erased preferred name."], 30, 'name', pretext)

    @edit.command(aliases = ('setlocation', 'loc', 'setloc'))
    async def location(self, ctx, *, pretext: Optional[str]):
        """Sets your location."""
        await self._edit(ctx, ["Please type your location. **Don't be specific.** It must be under 30 characters.",
            "Location set!", "Cancelled location setting.", "Erased location."], 30, 'location', pretext)

    @edit.command(aliases = ('setbio',))
    async def bio(self, ctx, *, pretext: Optional[str]):
        """Sets your bio."""
        await self._edit(ctx, ["Please type up a bio. It must be under 400 characters.",
            "Bio set!", "Cancelled bio setting.", 'Erased bio.'], 400, 'bio', pretext)


    @edit.command(aliases = ('setbday', 'bday', 'setbirthday'))
    async def birthday(self, ctx):
        """Set your birthday."""
        if not (prf := UserProfile.fromuser(ctx.author)):
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
                await ctx.send("Could not parse date given. Please try again.", delete_after=5)
                continue
            a = await Confirm(f"Is {dt.strftime('%B')} {getord(dt.day)} correct?", timeout=None).prompt(ctx)
            if not a:
                await ctx.send("Please try again with a different format.", delete_after=5)
                await tod.delete()
                continue

            if (dt.year >= utcnow().year):
                prf.birthday = dt.replace(year = 1900)
            else:
                #gonna count to be sure 
                tz = prf.timezone or pytz.timezone("UTC")
                now = datetime.now(tz)
                dt = dt.replace(tzinfo=tz)
                c = 0
                def daterange():
                    for n in range(int((now - dt).days)):
                        yield dt + timedelta(n)
                for x in daterange():
                    if x.day == dt.day and x.month == dt.month:
                        c += 1
                if c < 13:
                    await ctx.send("This birthday is under 13 years old. Please try again.", delete_after=5)
                    await tod.delete()
                    continue
                prf.birthday = dt
            prf.save()
            return await ctx.send("Birthday set!")

    @edit.command(aliases = ('setpronouns', 'setpronoun', 'pronouns'))
    async def pronoun(self, ctx):
        """Set your pronouns."""
        if not (prf := UserProfile.fromuser(ctx.author)):
            return await ctx.invoke(self.edit)
        result = await PronounSelector(self.bot).prompt(ctx)
        if not result:
            return await ctx.send("Cancelled pronoun setting.")
        prf.pronouns = result
        prf.save()
        return await ctx.send("Pronouns set!")

    @edit.command(aliases = ('settz', "timezone", "tz"))
    async def settimezone(self, ctx):
        """Set your timezone."""
        if not (prf := UserProfile.fromuser(ctx.author)):
            return await ctx.invoke(self.edit)
        r = await TZMenu(self.tzd, discord.Color(self.bot.data['color'])).prompt(ctx)
        if r:
            prf.timezone = r
            prf.save()
            return await ctx.send("Timezone set!")
        return await ctx.send("Timezone setting cancelled.")

    @edit.command(aliases = ('account', 'accounts', 'setaccount'))
    async def setaccounts(self, ctx: commands.Context):
        """Setup accounts on your profile."""
        if not (prf := UserProfile.fromuser(ctx.author)):
            return await ctx.invoke(self.edit)
        acclist = prf.accounts

        embed = discord.Embed(title = "Accounts Management", description = "Pick which account you'd like to add/remove.",
            color = self.bot.data['color'] if ctx.author.color == discord.Color.default() else ctx.author.color)
        embed.set_author(name=ctx.author.display_name, icon_url=str(ctx.author.avatar))
        emoji = [self.bot.get_emoji(ACCOUNTS[x]['emoji']) for x in ACCOUNTS]
        msg: discord.Message = await ctx.send(embed=embed)
        a = await Choice(msg, emoji + [ui.Button(style=ButtonStyle.red, label="Cancel")], remove_on_finish=False).prompt(ctx)

        acctype = list(ACCOUNTS)[a]
        data = ACCOUNTS[acctype]
        try: aname = data['name']
        except: aname = acctype.title()
        embed.title += f" - {aname}"
        embed.set_footer(text=aname, icon_url=str(emoji[a].url))
        embed.color = data['color']

        alist = [x for x in acclist if x.type == acctype]
        embed.description = "Current accounts:\n" if alist else "No accounts. Would you like to add one?"
        t = data['type']
        i = 0
        for x in alist:
            s = str(x)
            s = s[len(s.split()[0]) + 1:]
            embed.description += f"#{i + 1}: {s}\n"
            i += 1

        pre = embed.description
        #embed.description += "\nAdd/update using \u2705, remove using \u26D4, cancel using \u274C"
        await msg.edit(embed=embed)

        b = [ui.Button(style=ButtonStyle.success, label="Yes" if not alist else "Add/update" if len(alist) < 3 else "Update"),
             ui.Button(style=ButtonStyle.danger, label="Remove") if alist else None,
             ui.Button(style=ButtonStyle.grey, label="No" if not alist else "Cancel")]

        a = await Choice(msg, b).prompt(ctx)
        if a == 2: return await ctx.send("Cancelled account management.") 
        if a == 1:
            if not alist: return await ctx.send("There's no accounts to delete!")
            em = []
            for x in range(1, len(alist) + 1):
                em.append(str(x) + "\uFE0F\u20E3")
            embed.description = pre + "\nPlease react with the number of which account you want to delete."
            await msg.edit(embed=embed)
            a = await Choice(msg, em).prompt(ctx)
            #deleting is now harder cause of the new system
            #but we can do index bullshittery because of it's constant sorting
            #we find the first index of the correct type:
            ind = [x.type for x in prf.accounts].index(acctype)
            #then we base it off of what we found, since itll always return the first index
            del prf.accounts[ind + a]
            prf.save()
            return await ctx.send(f"Account #{a+1} removed!")
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
                await ctx.send("There should be no spaces. Please try again.", delete_after=5)
                continue
            td = await ctx.send("Verifying...")
            await ctx.channel.trigger_typing()
            try: checkembed = data['embed']
            except: checkembed = True
            tocheck = ""
            url = (data['link'] if 'used' not in data else data['used']).replace('[]', ret)
            try:
                async with aiohttp.request('HEAD', url) as resp:
                    if resp.status != 200 or (not str(resp.url).startswith(url)): raise Exception()
            except: 
                await ctx.send("Invalid URL. Please try again.", delete_after=5)
                continue
            if checkembed: 
                dump = self.bot.get_channel(dumpchannel)                
                keepread = await dump.send(url)
                await asyncio.sleep(.5)
                for i in range(5):
                    keepread = await dump.fetch_message(keepread.id)
                    if keepread.embeds:
                        tocheck = keepread.embeds[0].title
                        await keepread.delete()
                        break
                    await asyncio.sleep(1)
                #i actually despise steam
                if tocheck and acctype == "steam" and not keepread.embeds[0].description:
                    await ctx.send("Invalid URL. Please try again.", delete_after=5)
                    continue
            else: 
                try:
                    tree = html.fromstring(await httpfetch(url))
                    head = None
                    for x in tree:
                        if x.tag == 'head': head = x
                    if head is None: raise Exception()
                    for x in head:
                        if x.tag == 'title': 
                            tocheck = x.text
                            break
                    raise Exception()
                except: pass
            res = data['re']
            try: res = res.replace('%P%', data['prefix'])
            except: pass
            match = re.search(res, tocheck)
            if (not match): 
                await ctx.send("Verification failed. Please try again and check your account spelling.", delete_after=5)
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
        existlist = [x.handle for x in alist]
        if handle in existlist:
            index = existlist.index(handle)
            #same bullshittery from delete
            ind = [x.type for x in prf.accounts].index(acctype)
            prf.accounts[ind + index].name = name
            prf.save()
            return await ctx.send(f"Updated account name for account #{index + 1}!")
        if len(alist) >= 3: return await ctx.send(f"You can't add any more accounts for {aname}!")
        prf.accounts.append(UserAccount(acctype, handle, name))
        prf.save()
        if acctype != "pronounspage":    
            return await ctx.send("Account added!")   
        #pronounspage handling
        embed = msg.embeds[0]
        embed.description = "Account added, please wait..."
        await msg.edit(embed=embed)
        try: output = await get_pnounspage(handle)
        except: 
            embed.description = "API call threw an exception. Account added without prompting for pronouns."
            return await msg.edit(embed=embed)
        if not output: return await ctx.send("No pronouns found. Account added without setting pronouns.")
        embed.description = f"Would you like to set your pronouns to **{pnoun_list(output)}**?"
        await msg.edit(embed=embed)
        a = await Confirm(msg).prompt(ctx)
        if not a:
            return await ctx.send("Account added without setting pronouns.")
        prf.pronouns = output
        prf.save()
        await ctx.send("Account added and pronouns set!")



              

    MONTHS = ['January', 'Febuary', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

    @commands.guild_only()
    @commands.command(aliases = ('bdays', 'bdayboard', 'birthdayboard'))
    async def birthdays(self, ctx: commands.Context):
        """Get a list of birthdays in the server."""
        bdays = []
        for i in range(12): bdays.append([])
        for m in ctx.guild.members:
            m: discord.Member
            if not (prf := UserProfile.fromuser(m)):
                continue
            if not prf.birthday: continue
            tz = prf.timezone or pytz.timezone("UTC")
            now = datetime.now(tz)
            dt = prf.birthday.replace(tzinfo=tz)
            c = calcyears(dt, now)
            invalid = False
            if c < 13:
                invalid = True
            hasy = prf.birthday.year != 1900 and not invalid
            dt = dt.replace(year=now.year)
            out = f"{getord(dt.day)} - <@{m.id}>"
            if hasy:
                out += f" ({c}yrs)"
            if now.date() == dt.date():
                out = f"**{out} \U0001F389**"
            bdays[dt.month - 1].append((out, dt.day))

        embed = discord.Embed(title="Birthdays", color=self.bot.data['color'])
        for x, i in iiterate(bdays):
            x: list
            if not x: continue
            embed.add_field(name=self.MONTHS[i], value='\n'.join(y[0] for y in sorted(x, key=lambda z: z[1])))
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Profile(bot))        
        


