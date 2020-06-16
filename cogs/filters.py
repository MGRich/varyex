import discord, re
from discord.ext import commands
from cogs.utils.embeds import embeds
from datetime import datetime, timedelta
from cogs.utils.mpkmanager import MPKManager
from typing import Optional

class Filters(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def getmpm(self, guild) -> MPKManager:
        return MPKManager("filters", guild.id)


    @commands.group(aliases = ["filterping", "fp", 'f'])
    @commands.has_permissions(manage_messages = True)
    async def filter(self, ctx):
        """Manage filters/filterpings.
        You **must be able to manage messages.**

        `filter/f`
        `filterping/fp`
        `f cfg [add/remove] [phrases]`
        `fp cfg [add/remove] [phrase] <members>` 
        """
        isfp = ctx.invoked_with in ['fp', 'filterping']
        strused = 'filterping' if isfp else 'filter'
        if not (ctx.invoked_subcommand):
            ebase = discord.Embed(title=f"Current {strused.title()}s", color=discord.Color(self.bot.data['color']))
            mpm = self.getmpm(ctx.guild)
            mpk = mpm.data
            ebase.set_footer(text=f"Add with {ctx.prefix}{ctx.invoked_with} cfg add {'[phrase] [members]' if isfp else '[phrases]'}")
            try: mpk[strused]
            except:
                ebase.description = "*No data.*"
                return await ctx.send(embed=ebase)
            ebase.description = ""
            if isfp:
                for entry in mpk['filterping'].items(): 
                    #print(entry)
                    plist = []
                    for p in entry[1]:
                        plist.append(f"<@{p}>")
                    ebase.description += f"{entry[0]} - {', '.join(plist)}\n"
            else:
                fstr = '`\n`'.join(mpk['filter'])
                ebase.description = f"`{fstr}`"
            await ctx.send(embed=ebase)
    

    @filter.group(aliases = ['cfg'])
    async def config(self, ctx):
        if not (ctx.invoked_subcommand):
            return await ctx.invoke(self.filter)

    @config.command()
    async def add(self, ctx, phrase: str, *users: Optional[str]):
        isfp = ctx.message.content.split()[0][len(ctx.prefix):] in ['fp', 'filterping']
        strused = 'filterping' if isfp else 'filter'
        mpm = self.getmpm(ctx.guild)
        mpk = mpm.data
        try: mpk[strused]
        except: mpk[strused] = ({} if isfp else [])
        
        if isfp:
            existed = True
            if len(users) == 0: return
            memb = [await commands.MemberConverter().convert(ctx, x) for x in users]
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
        else:
            if (users): strs = list(users)
            else: strs = []
            strs.append(phrase)
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

    @config.command(aliases = ['delete'])
    async def remove(self, ctx, phrase: str, *users: Optional[str]):
        isfp = ctx.message.content.split()[0][len(ctx.prefix):] in ['fp', 'filterping']
        strused = 'filterping' if isfp else 'filter'
        mpm = self.getmpm(ctx.guild)
        mpk = mpm.data
        try: mpk[strused]
        except: return await ctx.send("There's nothing to delete!")

        if isfp:
            memb = [await commands.MemberConverter().convert(ctx, x) for x in users]
            count = len(memb)
            deleted = False

            try: mpk['filterping'][phrase]
            except: 
                return await ctx.send("That phrase doesn't exist, so nothing was changed.")

            for m in list(memb):
                if m.id in mpk['filterping'][phrase]: 
                    mpk['filterping'][phrase].remove(m.id)
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
                    pings.append(m.mention)
                await ctx.send(f"Removed {', '.join(pings)} from {phrase}!")  
        else:
            if (users): strs = list(users)
            else: strs = []
            strs.append(phrase)
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



    @commands.Cog.listener()
    async def on_message(self, msg):
        if (msg.guild == None): return
        if (msg.channel.id == 356560338390351872): return #REMS SPECIAL CASE
        mpm = self.getmpm(msg.guild)
        mpk = mpm.data
        hasfp = False
        hasf = False
        try:
            mpk['filterping']
            mpk['channel']
            hasfp = not msg.author.bot
        except: pass
        try:
            mpk['filter']
            hasf = not msg.author.bot
        except: pass

        flist = []
        plist = []

        if hasfp:
            for entry in mpk['filterping'].items():
                if re.search(entry[0], msg.content, re.IGNORECASE):
                    flist.append(entry[0])
                    for memb in entry[1]:
                        forceNo = memb in [x.id for x in msg.mentions]
                        if not forceNo:
                            async for message in msg.channel.history(limit=10, after=datetime.utcnow() - timedelta(seconds=30)):
                                if message.author.id == memb:
                                    forceNo = True
                                    break
                        if (not forceNo) and ((not memb in plist) and memb != msg.author.id): plist.append(memb)
            
            if (not len(flist)) or (not len(plist)): return
            
            i = 0
            for p in plist:
                plist[i] = f"<@{p}>"
                i += 1

            chn = await self.bot.fetch_channel(mpk['channel'])
            e = await embeds.buildembed(embeds, msg, focus=flist)
            e.set_footer(text=f"Focused: {', '.join(flist)}")
            await chn.send(' '.join(plist), embed=e)
        if hasf:
            for x in mpk['filter']:
                if re.search(x, msg.content, re.IGNORECASE):
                    return await msg.delete()
        

def setup(bot):
    bot.add_cog(Filters(bot))