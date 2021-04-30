import discord, copy, math
from discord.ext import commands

import imports.mpk as mpku
from imports.menus import Paginator
import imports.embeds as embeds
from imports.other import getord

from typing import Optional, List
from datetime import datetime, timedelta
from timeit import default_timer
from asyncio import sleep, Lock

import logging
LOG = logging.getLogger('bot')

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
        if not mpku.testgiven(mpk, ['channel']) or not mpk['channel'] or (payl.channel_id in mpk['blacklist']): return
        if typ and ((payl.emoji.name if payl.emoji.is_unicode_emoji() else payl.emoji.id) != mpk['emoji']): return
        LOG.debug(payl.guild_id)
        mpk['amount'] = (6,)
        chl: discord.TextChannel = self.bot.get_channel(mpk['channel'])  
        sbmsg: discord.Message 
        try: sbmsg = await chl.fetch_message(mpk['messages'][str(msg.id)]['sbid'])
        except: sbmsg = None

        rlist: List[discord.Reaction] = []
        LOG.debug("BEGIN " + str(default_timer() - start))
        start = default_timer()
        if (msg.channel == chl) and msg.author.id == self.bot.user.id and msg.embeds and (msg.embeds[0].footer != discord.Embed.Empty):
            aid = msg.embeds[0].footer.text.split()[-1]
            LOG.debug(aid)
            if aid not in mpk['messages']: return
            cid = mpk['messages'][aid]['chn']
            c = self.bot.get_channel(cid)
            if not c: return
            rlist += msg.reactions
            sbmsg = copy.copy(msg)
            try: msg = await c.fetch_message(int(aid))
            except discord.NotFound: return 
        elif sbmsg: rlist += sbmsg.reactions
        LOG.debug("SBMSG " + str(default_timer() - start))
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
        queueret = payl.user_id == msg.author.id
        for reaction in rlist:
            if reaction.emoji == '\u274c' and msg.author.id in (x.id for x in (await reaction.users().flatten())):
                queueret = True
                if sbmsg: await sbmsg.delete()
            if (mpk['emoji'] == (reaction.emoji.id if reaction.custom_emoji else reaction.emoji)):
                async for u in reaction.users():
                    if (u.id in ulist) or u.id == msg.author.id:
                        if u.id == payl.user_id: queueret = True
                        await reaction.remove(u)
                    else: 
                        count += 1
                        ulist.append(u.id)
        if queueret: return 
        LOG.debug("COUNT " + str(default_timer() - start))
        start = default_timer()
        md = mpk['messages'][mid]
        md['author'] = msg.author.id
        md['chn']    = cid
        md['sbid']   = (0,)
        if not md['count']:
            md['count'] = count
        elif typ and md['count'] == count: return
        spstate = ((count >= mpk['amount']) << 1) | msg.pinned
        if typ:
            try: await self.bot.get_cog('Logging').on_sbreact(msg.guild.get_member(payl.user_id), msg, typ == 1)
            except AttributeError: pass
        LOG.debug("MISC  " + str(default_timer() - start))
        start = default_timer()
        mpk.save(False)
        e = await embeds.buildembed(embeds, msg, stardata=(count, spstate, mpk), compare=sbmsg.embeds[0] if sbmsg else None)
        LOG.debug("EMBED " + str(default_timer() - start))
        if sbmsg:
            if not spstate:
                try: await sbmsg.delete()
                except: pass #cover this incase it ever happens for some reason
                return
            try: await sbmsg.edit(embed=e)
            except: pass
            else: return
        if (not spstate) or (not datetime.now() - (msg.created_at) < timedelta(days=60)): return
        made = await chl.send(embed=e)
        md['sbid'] = made.id
        return mpk.save()            
            
    @commands.Cog.listener()
    async def on_guild_channel_pins_update(self, chn: discord.TextChannel, pin: Optional[datetime]):
        if not pin or not (pins := (await chn.pins())) or ((datetime.utcnow() - pin) > timedelta(seconds=10)): return
        msg: discord.Message = pins[0]
        LOG.debug(msg)
        fakepay = discord.RawReactionActionEvent({'message_id': msg.id, 'channel_id': chn.id, 'user_id': 0, 'guild_id': 1}, None, "")
        async with reactlock:
            await self.handlereact(fakepay, 0)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payl):
        start = default_timer()
        async with reactlock:
            await self.handlereact(payl, -1)
        LOG.debug(default_timer() - start)
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payl):
        start = default_timer()
        async with reactlock:
            await self.handlereact(payl, 1)
        LOG.debug(default_timer() - start)

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
        """Configures the starboard."""
        if (ctx.invoked_subcommand == None):
            base = mpku.getmpm('starboard', ctx.guild)
            def fetch(st):
                return base[st] or "*Not set*"  
            embed = discord.Embed(title="Starboard Config", color=self.bot.data['color'])
            if base['leaderboard']['enabled']:
                base['lbe'] = base['leaderboard']['enabled']
                base.save()
            base['lbe'] = (True,)
            lb = 'enabled' if base['lbe'] else 'disabled'
            embed.description = f"**Minimum:** {fetch('amount')}\n**Star:** {fetch('emoji')}\n**Leaderboard:** {lb}\n"
            if not base['channel']: embed.description += "**Channel:** *Not set*\n"
            else: embed.description += f"**Channel:** <#{base['channel']}>"
            if base['blacklist']:
                embed.description += "**Blacklist:**\n"
                for x in base['blacklist']:
                    embed.description += f"> <#{x}>\n"
            await ctx.send(embed=embed)

    @starboard.command(aliases = ("lb",))
    @commands.guild_only()
    async def leaderboard(self, ctx):
        """Gets the starboard's leaderboard (if it's enabled.)"""
        mpk = mpku.getmpm('starboard', ctx.guild)
        if not mpk['emoji']: return
        if mpk['leaderboard']['enabled']:
            mpk['lbe'] = mpk['leaderboard']['enabled']
        mpk['lbe'] = (True,)
        if not mpk['lbe']: return

        tbd = await ctx.send("Generating.. this will take a while..")
        await ctx.trigger_typing()
        lbdict = mpku.DefaultContainer({})
        mpk['blacklist'] = ([],)        
        for x in mpk['messages']:
            md = mpk['messages'][x]
            if md['chn'] in mpk['blacklist']: continue
            #we're gonna recalculate entirely based on reactions
            rlist: List[discord.Reaction] = []
            try: 
                msg: discord.Message = await ctx.guild.get_channel(md['chn']).fetch_message(x)
                if not msg:
                    del mpk['messages'][x]
                    raise Exception()
            except: continue
            rlist += msg.reactions
            if md['sbid']:
                try:    rlist += (await ctx.guild.get_channel(mpk['channel']).fetch_message(md['sbid'])).reactions
                except: pass
            count = 0
            ulist = []
            for reaction in rlist:
                if reaction.emoji == '\u274c' and msg.author.id in (x.id for x in (await reaction.users().flatten())):
                    count = 0
                    break
                if (mpk['emoji'] == (reaction.emoji.id if reaction.custom_emoji else reaction.emoji)):
                    async for u in reaction.users():
                        if not ((u.id in ulist) or u.id == msg.author.id):
                            count += 1
                            ulist.append(u.id)

            aid = str(msg.author.id)
            lbdict[aid] = (0,)
            lbdict[aid] += count

        LOG.debug(f"refreshed leaderboard for {ctx.guild}")

        srtd = sorted(lbdict.items(), key = lambda x : x[1], reverse=True)
        if not srtd: return await tbd.edit(content="Not enough data so cancelled leaderboard calculation.")
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
        """Sets the channel to be used."""
        if not chn: return await ctx.invoke(self.config)
        mpk = mpku.getmpm('starboard', ctx.guild)
        mpk['channel'] = chn.id
        mpk.save()
        await ctx.send(f"Channel {chn.mention} set as starboard channel!")

    @config.command(name = "leaderboard", aliases = ('lb',))
    @commands.guild_only()
    async def lbcfg(self, ctx):
        """Toggles the leaderboard on/off."""
        mpk = mpku.getmpm('starboard', ctx.guild)
        mpk['leaderboard']['enabled'] = (False, not mpk['leaderboard']['enabled'])
        mpk.save()
        await ctx.send(f"Leaderboard has been {'enabled' if mpk['leaderboard']['enabled'] else 'disabled'}.")

    @config.command(aliases = ('setstar',))
    @commands.has_permissions(manage_guild=True)
    async def setemoji(self, ctx):
        """Sets the emoji to be used for starboard."""
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
    
    @config.command(aliases = ('setcount', 'minimum', 'setminimum'))
    @commands.has_permissions(manage_guild=True)
    async def count(self, ctx, count: Optional[int]):
        """Sets the minimum amount of stars needed to get on the starboard."""
        if not count: return await ctx.invoke(self.config)
        mpk = mpku.getmpm('starboard', ctx.guild)
        mpk['amount'] = count
        mpk.save()
        await ctx.send(f"{count} amount of stars is now the minimum!")

    @config.command()
    @commands.has_permissions(manage_guild=True)
    async def blacklist(self, ctx, act, *channel: discord.TextChannel):
        """Add/remove channels to the blacklist. Channels in the blacklist won't get stars."""
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