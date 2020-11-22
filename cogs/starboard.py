import discord, copy, math
from discord.ext import commands

import cogs.utils.mpk as mpku
from cogs.utils.menus import Paginator
from cogs.utils.embeds import embeds
from cogs.utils.other import getord

from typing import Optional
from datetime import datetime, timedelta
from timeit import default_timer
from asyncio import sleep, Lock

import logging
log = logging.getLogger('bot')

reactlock = Lock()

class Starboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def handlereact(self, payl: discord.RawReactionActionEvent, typ):
        if not payl.guild_id: return
        if payl.user_id == self.bot.user.id: return
        start = default_timer()
        #typ of 0 is pin, 1 or -1 is star/unstar
        try: msg = await self.bot.get_channel(payl.channel_id).fetch_message(payl.message_id)
        except discord.NotFound: return
        mpk = mpku.getmpm('starboard', msg.guild)
        mpk['count'] = (6,)
        if not mpku.testgiven(mpk, ['channel', 'emoji']) or not mpk['channel'] or (payl.channel_id in mpk['blacklist']): return
        if typ and ((payl.emoji.name if payl.emoji.is_unicode_emoji() else payl.emoji.id) != mpk['emoji']): return

        chl = self.bot.get_channel(mpk['channel'])  

        try: sbmsg = await chl.fetch_message(mpk['messages'][str(msg.id)]['sbid'])
        except: sbmsg = None

        rlist = []
        log.debug("BEGIN " + str(default_timer() - start))
        start = default_timer()
        if (msg.channel == chl) and msg.author.id == self.bot.user.id and msg.embeds and (msg.embeds[0].footer != discord.Embed.Empty):
            aid = msg.embeds[0].footer.text.split()[-1]
            log.debug(aid)
            if aid not in mpk['messages']: return
            cid = mpk['messages'][aid]['chn']
            c = self.bot.get_channel(cid)
            if not c: return
            rlist += msg.reactions
            sbmsg = copy.copy(msg)
            try: msg = await c.fetch_message(int(aid))
            except discord.NotFound: return 
        elif sbmsg: rlist += sbmsg.reactions
        log.debug("SBMSG " + str(default_timer() - start))
        start = default_timer()
        mid = str(msg.id)
        aid = str(msg.author.id)
        cid = msg.channel.id
        #reorder the list, original message should come first
        temp = copy.copy(rlist)
        rlist = msg.reactions
        rlist += temp

        count = 0
        ulist = []
        for reaction in rlist:
            if (mpk['emoji'] == (reaction.emoji.id if reaction.custom_emoji else reaction.emoji)):
                async for u in reaction.users():
                    if (u.id in ulist) or u.id == msg.author.id:
                        await reaction.remove(u)
                    else: 
                        count += 1
                        ulist.append(u.id)
        if payl.user_id == msg.author.id: return 
        log.debug("COUNT " + str(default_timer() - start))
        start = default_timer()
        mpk['leaderboard'][aid] = (0,)  
        mpk['messages'][mid] = ({},)
        msgdata = mpk['messages'][mid]
        if not msgdata:
            msgdata['author'] = msg.author.id
            msgdata['chn']    = cid
            msgdata['sbid']   = 0
            mpk['leaderboard'][aid] += count - typ
        spstate = ((count >= mpk['amount']) << 1) | msg.pinned
        mpk['leaderboard'][aid] += typ
        msgdata['count'] = count
        if typ:
            try: await self.bot.get_cog('Logging').on_sbreact(msg.guild.get_member(payl.user_id), msg, typ == 1)
            except AttributeError: pass
        log.debug("MISC  " + str(default_timer() - start))
        start = default_timer()
        mpk.save(False)
        e = await embeds.buildembed(embeds, msg, stardata=[count, spstate, mpk], compare=sbmsg.embeds[0] if sbmsg else None)
        log.debug("EMBED " + str(default_timer() - start))
        if sbmsg:
            if not spstate:
                try: await sbmsg.delete()
                except discord.NotFound: pass #cover this incase it ever happens for some reason
                return
            try: await sbmsg.edit(embed=e)
            except: pass
            else: return
        if (not spstate) or (not datetime.now() - (msg.created_at) < timedelta(days=60)): return
        made = await chl.send(embed=e)
        msgdata['sbid'] = made.id
        return mpk.save()            
            
    @commands.Cog.listener()
    async def on_guild_channel_pins_update(self, chn: discord.TextChannel, pin: Optional[datetime]):
        if not pin or not (pins := (await chn.pins())) or ((datetime.utcnow() - pin) > timedelta(seconds=10)): return
        msg: discord.Message = pins[0]
        log.debug(msg)
        fakepay = discord.RawReactionActionEvent({'message_id': msg.id, 'channel_id': chn.id, 'user_id': 0, 'guild_id': 1}, None, "")
        async with reactlock:
            await self.handlereact(fakepay, 0)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payl):
        start = default_timer()
        async with reactlock:
            await self.handlereact(payl, -1)
        log.debug(default_timer() - start)
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payl):
        start = default_timer()
        async with reactlock:
            await self.handlereact(payl, 1)
        log.debug(default_timer() - start)

    @commands.group(aliases = ("sb",))
    @commands.guild_only()
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
            raise commands.UserInputError()
    
    @starboard.group(aliases = ("cfg",))
    @commands.has_permissions(manage_messages=True, manage_guild=True)
    @commands.guild_only()
    async def config(self, ctx):
        if (ctx.invoked_subcommand == None):
            base = mpku.getmpm('starboard', ctx.guild)
            def fetch(st):
                return base[st] or "*Not set*"  
            embed = discord.Embed(title="Starboard Config", color=self.bot.data['color'])
            base['leaderboard']['enabled'] = (True,)
            lb = 'enabled' if base['leaderboard']['enabled'] else 'disabled'
            embed.description = f"**Minimum:** {fetch('amount')}\n**Star:** {fetch('emoji')}\n**Leaderboard:** `{lb}`\n"
            if not base['channel']: embed.description += "**Channel:** *Not set*\n"
            else: embed.description += f"**Channel:** <#{base['channel']}>"
            if base['blacklist']:
                embed.description += "**Blacklist:**\n"
                for x in base['blacklist']:
                    embed.description += f"> <#{x}>\n"
            await ctx.send(embed=embed)

    def refreshserver(self, gid):
        mpk = mpku.getmpm('starboard', gid)
        mpk['leaderboard'] = ({},)
        mpk['blacklist'] = ([],)
        mpk['leaderboard']['enabled'] = (True,)
        lbe = mpk['leaderboard']['enabled']
        mpk['leaderboard'] = {'enabled': lbe}
        for x in mpk['messages']:
            msg = mpk['messages'][x]
            if msg['chn'] in mpk['blacklist']: continue
            if (aid := str(msg['author'])) not in mpk['leaderboard']: mpk['leaderboard'][aid] = 0
            mpk['leaderboard'][aid] += msg['count']
        mpk.save()
        log.debug(f"refreshed leaderboard for {gid}")

    @starboard.command(aliases = ("lb",))
    @commands.guild_only()
    async def leaderboard(self, ctx):
        mpk = mpku.getmpm('starboard', ctx.guild)
        mpk['leaderboard']['enabled'] = (True,)
        if not mpk['leaderboard']['enabled']: return
        tbd = await ctx.send("Generating.. this may take a while.. (we're also refreshing the count)")
        self.refreshserver(ctx.guild.id)
        await ctx.trigger_typing()
        cpy = copy.copy(mpk['leaderboard'])
        try: del cpy['enabled']
        except: pass
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
                ebase.description = f"{first.display_name} is in {getord(x + 1)}!\n*You're in {getord(senderpos + 1)}!*"
                break
            except: continue
        if (ebase.colour == discord.Color.default()): ebase.colour = 0xFFAC33
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
        
    @config.command(aliases = ('channel',))
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def setchannel(self, ctx, chn: Optional[discord.TextChannel]):
        if not chn: return await ctx.invoke(self.config)
        mpk = mpku.getmpm('starboard', ctx.guild)
        mpk['channel'] = chn.id
        mpk.save()
        await ctx.send(f"Channel {chn.mention} set as starboard channel!")

    @config.command(name = "leaderboard", aliases = ('lb',))
    @commands.guild_only()
    async def lbcfg(self, ctx):
        mpk = mpku.getmpm('starboard', ctx.guild)
        mpk['leaderboard']['enabled'] = (False, not mpk['leaderboard']['enabled'])
        mpk.save()
        await ctx.send(f"Leaderboard has been {'enabled' if mpk['leaderboard']['enabled'] else 'disabled'}.")

    @config.command(aliases = ('setstar',))
    @commands.has_permissions(manage_guild=True)
    async def setemoji(self, ctx):
        def check(_r, u):
            return u.id == ctx.message.author.id
        
        await ctx.send("Please react to this with the emoji you want.")
        em = await self.bot.wait_for('reaction_add', timeout=20.0, check=check)
        mpk = mpku.getmpm('starboard', ctx.guild)
        em = em[0]
        if (not em.custom_emoji): mpk['emoji'] = mpk['emojiname'] = str(em.emoji)
        else: 
            mpk['emoji'] = em.emoji.id
            mpk['emojiname'] = em.emoji.name
        mpk.save()
        await ctx.send("Starboard emoji set!")
    
    @config.command(aliases = ('setcount',))
    @commands.has_permissions(manage_guild=True)
    async def count(self, ctx, count: Optional[int]):
        if not count: return await ctx.invoke(self.config)
        mpk = mpku.getmpm('starboard', ctx.guild)
        mpk['amount'] = count
        mpk.save()
        await ctx.send(f"{count} amount of stars is now the minimum!")

    @config.command()
    @commands.has_permissions(manage_guild=True)
    async def blacklist(self, ctx, act, *channel: discord.TextChannel):
        if (len(channel) == 0): return
        mpk = mpku.getmpm('starboard', ctx.guild)
        channel = list(channel)
        for chn in channel:
            if (act.startswith("a")): mpk['blacklist'].append(chn.id)
            else: 
                try: mpk['blacklist'].remove(chn.id)
                except: pass
        mpk.save()
        cstr = "" 
        for chn in channel:
            cstr += f", {chn.mention}"
        cstr = cstr[2:]
        await ctx.send(f"Channel(s) {cstr} {'added to' if act.startswith('a') else 'removed from'} blacklist!")


def setup(bot):
    bot.add_cog(Starboard(bot))