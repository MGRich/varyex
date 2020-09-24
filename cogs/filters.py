import discord, re
from discord.ext import commands

import cogs.utils.mpk as mpku
from cogs.utils.embeds import embeds
from cogs.utils.converters import MemberLookup, UserLookup

from datetime import datetime, timedelta

class Filters(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def getmpm(self, guild) -> mpku.MPKManager:
        mpm = mpku.getmpm("filters", guild.id, ['channel', 'filter', 'filterping'], ['0', [], {}])
        mpm.data['filter'] = [x.lower() for x in mpm.data['filter']]
        mpm.data['filterping'] = {x.lower(): mpm.data['filterping'][x] for x in mpm.data['filterping']}
        return mpku.getmpm("filters", guild.id, ['channel', 'filter', 'filterping'], ['0', [], {}])

    @commands.group(aliases = ['f'])
    @commands.has_permissions(manage_messages = True)
    async def filter(self, ctx):
        """Manage filters.
        You **must be able to manage messages.**

        `filter/f`
        `f cfg [add/remove] [phrases]`
        """
        if not (ctx.invoked_subcommand):
            ebase = discord.Embed(title="Current Filters", color=discord.Color(self.bot.data['color']))
            mpk = self.getmpm(ctx.guild).getanddel()
            ebase.set_footer(text=f"Add with {ctx.prefix}f cfg add [phrases]")
            if not mpk['filter']:
                ebase.description = "*No filters.*"
                return await ctx.send(embed=ebase)
            fstr = '`\n`'.join(mpk['filter'])
            ebase.description = f"`{fstr}`"
            await ctx.send(embed=ebase)
    @commands.group(aliases = ['fp'])
    @commands.has_permissions(manage_messages = True)
    async def filterping(self, ctx):
        """Manage filterpings.
        You **must be able to manage messages.**

        `filterping/fp`
        `fp cfg [add/remove] [phrase] <members>` 
        """
        if not (ctx.invoked_subcommand):
            ebase = discord.Embed(title="Current Filterpings", color=discord.Color(self.bot.data['color']))
            ebase.set_footer(text=f"Add with {ctx.prefix}fp cfg add [phrase] [members]")
            mpk = self.getmpm(ctx.guild).getanddel()
            if not mpk['filterping']:
                ebase.description = "*No filterpingss.*"
                return await ctx.send(embed=ebase)
            ch = "*No channel*" if (not mpk['channel']) else f"<#{mpk['channel']}>"
            ebase.description = f"Channel: {ch}\n"
            for entry in mpk['filterping'].items(): 
                plist = []
                for p in entry[1]:
                    plist.append(f"<@{p}>")
                ebase.description += f"{entry[0]} - {', '.join(plist)}\n"
            await ctx.send(embed=ebase)

    @filter.group(name = "config", aliases = ['cfg'])
    async def configf(self, ctx):
        if not (ctx.invoked_subcommand):
            return await ctx.invoke(self.filter)
    @filterping.group(name = "config", aliases = ['cfg'])
    async def configfp(self, ctx):
        if not (ctx.invoked_subcommand):
            return await ctx.invoke(self.filterping)

    @configf.command(name="add")
    async def addf(self, ctx, *strs: str):
        if not strs: return
        mpm = self.getmpm(ctx.guild)
        mpk = mpm.data
        try: mpk['filter']
        except: mpk['filter'] = []
        strs = [(x[1:-1] if ((x[0] == x[-1] == '`') and len(x) > 2) else x) for x in strs] #incase we wanna use ``
        added = []
        for x in strs:
            if x not in mpk['filter']:
                mpk['filter'].append(x)
                added.append(x)
        if len(added) == 0: return await ctx.send("Those phrases were already being filtered, so nothing has changed.")
        mpm.save()
        added = [f"`{x}`" for x in added]
        await ctx.send(f"Added {', '.join(added)} to filters!") 
    @configfp.command(name="add")
    async def addfp(self, ctx, phrase: str, *memb: MemberLookup):
        if not memb: return
        memb = list(memb)
        mpm = self.getmpm(ctx.guild)
        mpk = mpm.data
        try: mpk['filterping']
        except: mpk['filterping'] = {}
        existed = True
        try: mpk['filterping'][phrase]
        except: 
            existed = False
            mpk['filterping'][phrase] = []
        for m in list(memb):
            if not m.id in mpk['filterping'][phrase]: 
                mpk['filterping'][phrase].append(m.id)
            else: memb.remove(m)
        if (len(memb) == 0): return await ctx.send("Everyone on the list was getting pinged by that phrase, so nothing has changed.")
        mpm.save()
        if (not existed):
            return await ctx.send(f"Added `{phrase}` to filterping!")
        else:
            pings = []
            for m in memb:
                pings.append(m.mention)
            return await ctx.send(f"Added {', '.join(pings)} to {phrase}!")
    @configfp.command(name = "remove", aliases = ['delete'])
    async def removefp(self, ctx, phrase: str, *memb: UserLookup):
        if not memb: return
        memb = [x.id for x in memb]
        mpm = self.getmpm(ctx.guild)
        mpk = mpm.data
        try: 
            if not mpk['filterping']: raise ValueError()
        except: return await ctx.send("There's nothing to delete!")
        count = len(memb)
        deleted = False
        try: mpk['filterping'][phrase]
        except: 
            return await ctx.send("That phrase doesn't exist, so nothing was changed.")

        for m in list(memb):
            if m in mpk['filterping'][phrase]: 
                mpk['filterping'][phrase].remove(m)
            else: memb.remove(m)
        if (not count) or (len(mpk['filterping'][phrase]) == 0):
            del(mpk['filterping'][phrase])
            deleted = True
                    
        if (len(memb) == 0): return await ctx.send("No one on the list was getting pinged by that phrase, so nothing has changed.") 
        mpm.save()
        if (deleted):
            await ctx.send(f"Removed `{phrase}` from filterping!")
        else:
            pings = []
            for m in memb:
                pings.append(f"<@{m}>")
            await ctx.send(f"Removed {', '.join(pings)} from {phrase}!")  
    @configf.command(name = "remove", aliases = ['delete'])
    async def removef(self, ctx, *strs: str):
        if not strs: return
        mpm = self.getmpm(ctx.guild)
        mpk = mpm.data
        try: 
            if not mpk['filter']: raise ValueError()
        except: return await ctx.send("There's nothing to delete!")

        strs = [(x[1:-1] if ((x[0] == x[-1] == '`') and len(x) > 2) else x) for x in strs] #incase we wanna use ``
        removed = []
        for x in strs:
            if x in mpk['filter']:
                mpk['filter'].remove(x)
                removed.append(x)
        if len(removed) == 0: return await ctx.send("None of those phrases are filtered, so nothing has changed.")
        mpm.save()
        removed = [f"`{x}`" for x in removed]
        await ctx.send(f"Removed {', '.join(removed)} from filters!") 

    @configfp.command(aliases = ['channel'])
    async def setchannel(self, ctx, chn: discord.TextChannel):
        mpm = self.getmpm(ctx.guild)
        mpm.data['channel'] = chn.id
        mpm.save()
        await ctx.send(f"Set filterping channel to {chn.mention}!")

    @commands.Cog.listener()
    async def on_message(self, msg):
        if (msg.guild == None): return
        mpk = self.getmpm(msg.guild).getanddel()
        hasfp = False
        hasf = False
        
        if mpk['filterping']:
            if (not mpk['channel']): raise Exception()
            try: chn = await self.bot.fetch_channel(mpk['channel'])
            except: pass
            else: hasfp = not msg.author.bot
        
        if mpk['filter']: hasf = not msg.author.bot

        flist = []
        plist = set()

        for entry in mpk['filterping'].items():
            if re.search(entry[0], msg.content, re.IGNORECASE):
                flist.append(entry[0])
                for memb in entry[1]:
                    forceNo = memb in [x.id for x in msg.mentions]
                    if not forceNo:
                        async for message in msg.channel.history(limit=15, after=datetime.utcnow() - timedelta(seconds=30)):
                            if message.author.id == memb:
                                forceNo = True
                                break
                    if (not forceNo) and (memb != msg.author.id): plist.add(f"<@{memb}>")
        
        if hasfp and plist:
            hlist = []
            for x in sorted(flist, key=len):
                smaller = False
                for z in flist:
                    if x == z: continue
                    if x in z:
                        smaller = True
                        break
                if not smaller: hlist.append(x)
                pass

            e = await embeds.buildembed(embeds, msg, focus=hlist)
            e.set_footer(text=f"Focused: {', '.join(flist)}")
            await chn.send(' '.join(plist), embed=e)

        if hasf:
            for x in mpk['filter']:
                if re.search(x, msg.content, re.IGNORECASE):
                    try: return await msg.delete()
                    except discord.Forbidden: return
        

def setup(bot):
    bot.add_cog(Filters(bot))