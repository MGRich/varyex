import discord, copy, math
from discord.ext import commands
from cogs.utils.embeds import embeds
from asyncio import sleep
from timeit import default_timer
from cogs.utils.mpkmanager import MPKManager
from cogs.utils.menus import Paginator
from typing import Optional
from datetime import datetime, timedelta

class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.buffer = []


    async def fetchmsg(self, p) -> discord.Message:
        chl = await self.bot.fetch_channel(p.channel_id)
        return await chl.fetch_message(p.message_id)
    
    def getmpm(self, guild) -> MPKManager:
        return MPKManager("starboard", guild.id)

    def testforguild(self, guild, runchecks: list = None, runtmp: list = None) -> MPKManager:
        mpm = self.getmpm(guild)
        if runchecks:
            file = mpm.data
            i = 0
            for x in runchecks:
                try: file[x]
                except: file[x] = runtmp[i]
                i += 1  
        return mpm

    def testgiven(self, mpk, checks) -> bool:
        for x in checks:
            try: mpk[x]
            except: return False
        return True

    def getord(self, num):
        st = "th"
        if ((num % 100) > 10 and (num % 100) < 15): return str(num) + st
        n = num % 10
        if   (n == 1): st = st.replace("th", "st")
        elif (n == 2): st = st.replace("th", "nd")
        elif (n == 3): st = st.replace("th", "rd")
        return str(num) + st

        
    async def handlereact(self, payl: discord.RawReactionActionEvent, typ):
        try: msg = await self.fetchmsg(payl)
        except discord.NotFound: return
        mpm = self.testforguild(msg.guild, ['blacklist', 'count'], [[], 6])
        mpk = mpm.data       
        if not self.testgiven(mpk, ['channel', 'emoji']) or not mpk['channel'] or (payl.channel_id in mpk['blacklist']): return
        iden = payl.emoji.name if payl.emoji.is_unicode_emoji() else payl.emoji.id
        if (iden != mpk['emoji']): return

        chl = await self.bot.fetch_channel(mpk['channel'])                    
        try: sbmsg = await chl.fetch_message(mpk['messages'][str(msg.id)]['sbid'])
        except: sbmsg = None

        mid = str(msg.id)
        aid = str(msg.author.id)
        cid = msg.channel.id
        reactor = msg.guild.get_member(payl.user_id)
        print(reactor)

        for reaction in msg.reactions:
            if (iden == (reaction.emoji.id if reaction.custom_emoji else reaction.emoji)):
                if reactor == msg.author: return await reaction.remove(reactor)
                break

        count = 0
        for reaction in msg.reactions:
            if (iden == (reaction.emoji.id if reaction.custom_emoji else reaction.emoji)):
                count += reaction.count
                break

        try: mpk['leaderboard'][aid]
        except: mpk['leaderboard'][aid] = 0

        try:
            mpk['messages'][mid]
            try: mpk['messages'][mid]['spstate']
            except: mpk['messages'][mid]['spstate'] = 0b00
                 
            if not mpk['messages'][mid]['spstate'] & 0b10: mpk['leaderboard'][aid] += count 
            else:  mpk['leaderboard'][aid] += typ
        except:
            mpk['messages'][mid] = {}
            
            mpk['messages'][mid]['author'] = msg.author.id
            mpk['messages'][mid]['chn']    = cid
            mpk['messages'][mid]['sbid']   = 0
            mpk['messages'][mid]['spstate'] = 0b00
            mpk['leaderboard'][aid] += count     
    
        mpk['messages'][mid]['count'] = count

        if not msg.pinned: mpk['messages'][mid]['spstate'] &= 0b10
        else: mpk['messages'][mid]['spstate'] |= 0b01
        
        try: await self.bot.get_cog('Logging').on_sbreact(reactor, msg, typ == 1)
        except AttributeError: pass

        if (count >= mpk['amount']):
            mpk['messages'][mid]['spstate'] |= 0b10
            mpm.save()
            e = await embeds.buildembed(embeds, msg, stardata=[count, mpk['messages'][mid]['spstate'], mpk], compare=sbmsg.embeds[0] if sbmsg else None)
            if sbmsg:
                try: return await sbmsg.edit(embed=e)
                except: pass
            if not datetime.now() - (msg.created_at) < timedelta(days=60): return mpm.save()
            made = await chl.send(embed=e)
            mpk['messages'][mid]['sbid'] = made.id
            return mpm.save()
        return await self.removefromboard(msg)
    
    async def oldthing(self):
        #pylint: disable=undefined-variable, used-before-assignment, unused-variable
        #if i ever decided to reimplement this: OPTIMIZE IT.

        chl = await self.bot.fetch_channel(mpk['channel'])        
        fromsb = False
        sbmsg = None
            
        if payl.user_id == self.bot.user.id and chl.id == payl.channel_id:
            found = None
            default_timer()
            for ids in reversed(list(mpk['messages'])):
                if mpk['messages'][ids]['sbid'] == msg.id:
                    found = ids
                    break
            if found:
                schn = self.bot.get_channel(mpk['messages'][found]['chn'])
                sbmsg = msg
                msg = await schn.fetch_message(int(found))
                fromsb = True
        else: sbmsg = await chl.fetch_message(mpk['messages'][str(msg.id)]['sbid'])

        mid = str(msg.id)
        aid = str(msg.author.id)
        cid = msg.channel.id
        reactor = msg.guild.get_member(payl.user_id)    
        targetm = (sbmsg if fromsb else msg)

        for reaction in targetm.reactions:
            if (iden == (reaction.emoji.id if reaction.custom_emoji else reaction.emoji)):
                if reactor == msg.author: return await reaction.remove(reactor)
                if sbmsg and (reactor in await reaction.users().flatten()):
                    oppm = (msg if fromsb else sbmsg)
                    for oreact in oppm.reactions:
                        if (iden == (oreact.emoji.id if oreact.custom_emoji else oreact.emoji)):
                            if reactor in await oreact.users().flatten(): return await reaction.remove(reactor)
                break



    async def removefromboard(self, msg):
        mpm = self.testforguild(msg.guild)
        mpk = mpm.data       
        chl = await self.bot.fetch_channel(mpk['channel'])
        try: info = mpk['messages'][str(msg.id)]
        except: return

        smpmsg = None
        try: smpmsg = await chl.fetch_message(info['sbid'])
        except: pass
        info['spstate'] &= 0b01
        if smpmsg == None: return mpm.save()
        if (not info['spstate'] & 0b01) or not msg.pinned:
            await smpmsg.delete()
            return
        e = await embeds.buildembed(embeds, msg, stardata=[info['count'], 0b01, embeds], compare=smpmsg.embeds[0])
        try: await smpmsg.edit(embed=e)
        except discord.Forbidden: await chl.send(embed=e)
        mpm.save()
            
            
    @commands.Cog.listener()
    async def on_guild_channel_pins_update(self, chn: discord.TextChannel, _unusedpin):
        mpm = self.testforguild(chn.guild)
        mpk = mpm.data
        msgl = await chn.pins()
        if not mpk['pins']: return
        if (chn.id in mpk['blacklist']): return
        try: mpk['channel']
        except: return
        chl = await self.bot.fetch_channel(mpk['channel'])
        
        msg = msgl[0]
        mstr = str(msg.id)
        try:
            mpk['messages'][mstr]
            try: mpk['messages'][mstr]['spstate'] |= 0b01 
            except: mpk['messages'][mstr]['spstate'] = 0b01 
        except:
            mpk['messages'][mstr] = {}
            
            mpk['messages'][mstr]['author'] = msg.author.id
            mpk['messages'][mstr]['chn']    = chn.id
            mpk['messages'][mstr]['sbid']   = 0
            mpk['messages'][mstr]['count']  = 0
            mpk['messages'][mstr]['spstate'] = 0b01
        mpm.save()
        try: tedit = await chl.fetch_message(mpk['messages'][mstr]['sbid'])
        except discord.NotFound: tedit = None
        e = await embeds.buildembed(embeds, msg, stardata=[mpk['messages'][mstr]['count'], mpk['messages'][mstr]['spstate'], mpk], compare=tedit.embeds[0] if tedit else None)
        if tedit:
            try: return await tedit.edit(embed=e)
            except: pass
        made = await chl.send(embed=e)
        mpk['messages'][mstr]['sbid'] = made.id
        mpm.save()
        
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payl):
        start = default_timer()
        await self.handlereact(payl, -1)
        print(default_timer() - start)
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payl):
        start = default_timer()
        await self.handlereact(payl, 1)
        print(default_timer() - start)

    @commands.group(aliases = ["sb"])
    async def starboard(self, ctx):
        """Sets up the starboard/views the leaderboard if enabled.
        __This command is entirely run by subcommands.__

        *config/cfg*
        > Configures the starboard.
        > `sb cfg channel [channel]`
        > `sb cfg count/minimum [count]`
        > `sb cfg leaderboard (toggles on/off)`
        > `sb cfg setstar/setemoji`
        > `sb cfg blacklist <add/remove> <channels>`
        *leaderboard/lb*
        > Views the leaderboard.
        > `sb leaderboard`
        """
        if (ctx.invoked_subcommand == None):
            await ctx.invoke(self.bot.get_command("help"), "sb")
    
    @starboard.group(aliases = ["cfg"])
    @commands.has_permissions(manage_messages=True, manage_guild=True)
    async def config(self, ctx):
        if (ctx.invoked_subcommand == None):
            base = self.testforguild(ctx.guild).data
            def fetch(st):
                try: return base[st]
                except: return "*Not set*"
            embed = discord.Embed(title="Starboard Config", color=discord.Color(self.bot.data['color']))
            embed.description = f"**Minimum:** `{fetch('amount')}`\n**Star:** {fetch('emoji')}\n**Leaderboard:** `{'enabled' if base['leaderboard']['enabled'] else 'disabled'}`\n**Channel:** <#{fetch('channel')}>\n"
            if self.testgiven(base, 'blacklist') and base['blacklist']:
                embed.description += "**Blacklist:**\n"
                for x in base['blacklist']:
                    embed.description += f"> <#{x}>\n"
            await ctx.send(embed=embed)

    @starboard.command(aliases = ["lb"])
    async def leaderboard(self, ctx):
        mpm = self.testforguild(ctx.guild)
        mpk = mpm.data       
        if not (mpk['leaderboard']['enabled']): return
        tbd = await ctx.send("Generating.. this may take a while..")
        await ctx.trigger_typing()
        cpy = copy.copy(mpk['leaderboard'])
        del cpy['enabled']
        srtd = sorted(cpy.items(), key = lambda x : x[1])
        if not srtd: return await tbd.edit(content="Not enough data so cancelled leaderboard calculation.")
        srtd.reverse()
        await sleep(0.5)
        groups = []
        ebase = discord.Embed()
        ebase.set_author(name="Leaderboard")
        senderpos = 0
        for t in srtd:
            if str(ctx.author.id) != t[0]: senderpos += 1
            else: break
        for x in range(min(10, len(srtd))): #only search first page, idk what the fuck its doing going all the way to last lmfao
            try:
                first = await ctx.guild.fetch_member(int(srtd[x][0]))
                ebase.colour = first.color
                ebase.set_author(name="Leaderboard", icon_url=first.avatar_url)
                ebase.description = f"{first.display_name} is in {self.getord(x + 1)}!\n*You're in {self.getord(senderpos + 1)}!*"
                break
            except: continue
        if (ebase.colour == discord.Color.default()): ebase.colour = discord.Color(0xFFAC33)
        count = 1
        page = 1
        txb = []
        cb = []
        
        for t in srtd:
            if (t[0] == str(ctx.author.id)):
                txb.append(f"_`{count}.` <@{t[0]}>_ \u25C0")
                cb.append(f"_`{t[1]}`_")
            else: 
                txb.append(f"`{count}.` <@{t[0]}>")
                cb.append(f"`{t[1]}`")
            if (count % 10 == 0) or (count == len(srtd)):
                e = copy.deepcopy(ebase)
                e.add_field(name="Users", value='\n'.join(txb), inline=True)
                e.add_field(name="Count", value='\n'.join(cb), inline=True)
                e.set_footer(text=f"Page {page} of {math.ceil(len(srtd) / 10)}")
                groups.append(e)
                txb = []
                cb = []
                page += 1
            count += 1
        await tbd.delete()
        return await Paginator(groups).start(ctx)
        
    @config.command(aliases = ['channel'])
    @commands.has_permissions(manage_guild=True)
    async def setchannel(self, ctx, chn: Optional[discord.TextChannel]):
        if not chn: return await ctx.invoke(self.config)
        mpm = self.testforguild(ctx.guild)
        mpk = mpm.data       
        mpk['channel'] = chn.id
        mpm.save()
        await ctx.send(f"Channel {chn.mention} set as starboard channel!")

    @config.command(name = "leaderboard", aliases = ['lb'])
    async def lbcfg(self, ctx):
        mpm = self.testforguild(ctx.guild)
        mpk = mpm.data       
        mpk['leaderboard']['enabled'] ^= True
        mpm.save()
        await ctx.send(f"Leaderboard has been {'enabled' if mpk['leaderboard']['enabled'] else 'disabled'}.")

    @config.command(aliases = ['setstar'])
    @commands.has_permissions(manage_guild=True)
    async def setemoji(self, ctx):
        def check(_unusedr, u):
            return u.id == ctx.message.author.id
        
        await ctx.send("Please react to this with the emoji you want.")
        em = await self.bot.wait_for('reaction_add', timeout=20.0, check=check)
        mpm = self.testforguild(ctx.guild)
        mpk = mpm.data       
        em = em[0]
        if (not em.custom_emoji): mpk['emoji'] = mpk['emojiname'] = str(em.emoji)
        else: 
            mpk['emoji'] = em.emoji.id
            mpk['emojiname'] = em.emoji.name
        mpm.save()
        await ctx.send("Starboard emoji set!")
    
    @config.command(aliases = ['setcount'])
    @commands.has_permissions(manage_guild=True)
    async def count(self, ctx, count: Optional[int]):
        if not count: return await ctx.invoke(self.config)
        mpm = self.testforguild(ctx.guild)
        mpk = mpm.data       
        mpk['amount'] = count
        mpm.save()
        await ctx.send(f"{count} amount of stars is now the minimum!")

    @config.command()
    @commands.has_permissions(manage_guild=True)
    async def blacklist(self, ctx, act, *channel: discord.TextChannel):
        mpm = self.testforguild(ctx.guild)
        mpk = mpm.data       
        if (len(channel) == 0): return
        try: mpk['blacklist']
        except: mpk['blacklist'] = []
        channel = list(channel)
        for chn in channel:
            if (act.startswith("a")): mpk['blacklist'].append(chn.id)
            else: 
                try: mpk['blacklist'].remove(chn.id)
                except: pass
        mpm.save()
        cstr = "" 
        for chn in channel:
            cstr += f", {chn.mention}"
        cstr = cstr[2:]
        await ctx.send(f"Channel(s) {cstr} {'added to' if act.startswith('a') else 'removed from'} blacklist!")

    #@config.command()
    #@commands.has_permissions(administrator=True)
    #async def funny(self, ctx):
    #    async for msg in ctx.channel.history(limit = 50):
    #        await msg.pin()




def setup(bot):
    bot.add_cog(Starboard(bot))