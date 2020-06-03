import discord, json, copy, os, math
from discord.ext import commands
from datetime import datetime
from cogs.utils.SimplePaginator import SimplePaginator as pag
from cogs.utils.embeds import embeds
from asyncio import sleep
from timeit import default_timer
from cogs.utils.mpkmanager import MPKManager


class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.buffer = []


    async def fetchmsg(self, p):
        chl = await self.bot.fetch_channel(p.channel_id)
        return await chl.fetch_message(p.message_id)
    
    def getmpm(self, guild) -> MPKManager:
        return MPKManager("starboard", guild.id)

    def testforguild(self, guild) -> MPKManager:
        mpm = self.getmpm(guild)
        file = mpm.data
        try:
            file['amount']
            file['emoji']
            file['emojiname']
            file['messages']
            file['leaderboard'] #pass all base checks
        except:
            file['amount'] = 6
            file['emoji'] = 11088
            file['emojiname'] = "\u2b50"
            file['messages'] = {}
            file['leaderboard'] = {}
        return mpm

    def getord(self, num):
        st = f"{num}th"
        if ((num % 100) > 10 and (num % 100) < 15): return st
        print(st[-3])
        if (st[-3] == "1"): st = st.replace("th", "st")
        if (st[-3] == "2"): st = st.replace("th", "nd")
        if (st[-3] == "3"): st = st.replace("th", "rd")
        return st

        
    async def handlereact(self, payl, typ):
        msg = await self.fetchmsg(payl)
        mpm = self.testforguild(msg.guild)
        mpk = mpm.data       
        #print(mpk)

        try: 
            if (payl.channel_id in mpk['blacklist']): return
        except: 
            pass

        iden = payl.emoji.name if payl.emoji.is_unicode_emoji() else payl.emoji.id

        if (list(filter(lambda i: i[0] == payl.message_id, self.buffer))):
            try:
                ind = self.buffer.index(list(filter(lambda i: i[0] == payl.message_id, self.buffer))[0])
                self.buffer[ind][1] += (1 if typ else -1)
            except: pass
            print(self.buffer)
            return
        self.buffer.append([payl.message_id, (1 if typ else -1)])
        print(self.buffer)
        ind = self.buffer.index(list(filter(lambda i: i[0] == payl.message_id, self.buffer))[0])


        try: mpk['channel']
        except: return

        pin = False
        try: pin = ord(iden) == mpk['pin']
        except: pass


        #print(ord(iden))
        if pin: #run a COMPLETELY DIFFERENT PROTOCOL
            count = 0
            for reaction in msg.reactions:
                if (iden == (reaction.emoji.id if reaction.custom_emoji else reaction.emoji)):
                    count = reaction.count
            
            if (count >= mpk['amount'] * mpk['pinthr']):
                if (len(await msg.channel.pins()) == 50):
                    await (await msg.channel.pins())[49].unpin()
                await msg.pin()

            return
            

        if (iden != mpk['emoji']): 
            return


        chl = await self.bot.fetch_channel(mpk['channel'])        
        sbstar = False
        fromsb = False
        smpmsg  = None

        #await chl.trigger_typing()
            
        if chl.id == payl.channel_id:
            found = None
            for ids in reversed(list(mpk['messages'].keys())):
                if mpk['messages'][ids]['sbid'] == msg.id:
                    found = ids
                    break

            if found:
                schn = self.bot.get_channel(mpk['messages'][found]['chn'])
                smpmsg = msg
                msg   = await schn.fetch_message(int(found))
                sbstar = True
                fromsb = True
        else:
            try:
                smpmsg = await chl.fetch_message(mpk['messages'][str(msg.id)]['sbid'])
                sbstar = True
            except: pass

        mid = str(msg.id)
        aid = str(msg.author.id)
        cid = msg.channel.id
        reactor = msg.guild.get_member(payl.user_id)
        
        targetm = (smpmsg if fromsb else msg)

        if reactor == msg.author:
            for reaction in targetm.reactions:
                if (iden == (reaction.emoji.id if reaction.custom_emoji else reaction.emoji)):
                    await reaction.remove(reactor)
                    return
        
        if sbstar:
            oppm = (smpmsg if not fromsb else msg)

            #start = default_timer()

            for reaction in targetm.reactions:
                if (iden == (reaction.emoji.id if reaction.custom_emoji else reaction.emoji)):
                    if reactor in await reaction.users().flatten():
                        for oreact in oppm.reactions:
                            if (iden == (oreact.emoji.id if oreact.custom_emoji else oreact.emoji)):
                                if reactor in await oreact.users().flatten():
                                    await reaction.remove(reactor)
                                    return
                                break
                        break
                    break


        count = 0
        reactl = msg.reactions + (smpmsg.reactions if sbstar else [])
        for reaction in reactl:
            if (iden == (reaction.emoji.id if reaction.custom_emoji else reaction.emoji)):
                count += reaction.count

        try: mpk['leaderboard'][aid]
        except: mpk['leaderboard'][aid] = 0

        try:
            mpk['messages'][mid]
            try: mpk['messages'][mid]['spstate']
            except: mpk['messages'][mid]['spstate'] = 0b00
                 
            if not mpk['messages'][mid]['spstate'] & 0b10:
                mpk['leaderboard'][aid] += count 
            else:  
                mpk['leaderboard'][aid] += self.buffer[ind][1]
                print(self.buffer[ind][1])
        except:
            mpk['messages'][mid] = {}
            
            mpk['messages'][mid]['author'] = msg.author.id
            mpk['messages'][mid]['chn']    = cid
            mpk['messages'][mid]['sbid']   = 0
            mpk['messages'][mid]['spstate'] = 0b00
            mpk['leaderboard'][aid] += count     
    
        mpk['messages'][mid]['count']  = count

        if not msg.pinned: mpk['messages'][mid]['spstate'] &= 0b10
        else: mpk['messages'][mid]['spstate'] |= 0b01
        
        if (count >= mpk['amount']):
            mpk['messages'][mid]['spstate'] |= 0b10
            e = await embeds.buildembed(embeds, msg, stardata=[count, mpk['messages'][mid]['spstate'], mpk])
            if (mpk['messages'][mid]['sbid'] == 0):
                if type(e) == list:
                    made = await chl.send(content=e[0], embed=e[1])
                else:
                    made = await chl.send("", embed=e)
                mpk['messages'][mid]['sbid'] = made.id         
            else:
                try:
                    tedit = await chl.fetch_message(mpk['messages'][mid]['sbid'])
                    if type(e) == list:
                        await tedit.edit(content=e[0], embed=e[1])
                    else:
                        await tedit.edit(content="", embed=e)
                except:
                    if type(e) == list:
                        made = await chl.send(content=e[0], embed=e[1])
                    else:
                        made = await chl.send("", embed=e)
                    mpk['messages'][mid]['sbid']   = made.id         
        else:
            await self.removefromboard(msg)
        mpm.save()
    
    async def removefromboard(self, msg):
        try:
            mpm = self.testforguild(msg.guild)
            mpk = mpm.data       
            chl = await self.bot.fetch_channel(mpk['channel'])
            mpk['messages'][str(msg.id)]
        except: return

        info = mpk['messages'][str(msg.id)]
        smpmsg = None
        try: smpmsg = await chl.fetch_message(info['sbid'])
        except: pass
        mpk['messages'][str(msg.id)]['sbid'] = 0
        mpk['messages'][str(msg.id)]['spstate'] &= 0b01
        mpm.save()
        spstate = mpk['messages'][str(msg.id)]['spstate']
        if smpmsg == None: return
        if (not spstate & 0b01) or not msg.pinned:
            await smpmsg.delete()
            return
        print("w" + bin(spstate))
        e = await embeds.buildembed(embeds, msg, stardata=[info['count'], 0b01, embeds])
        if type(e) == list:
            await smpmsg.edit(content=e[0], embed=e[1])
        else:
            await smpmsg.edit(content="", embed=e)
        mpk['messages'][str(msg.id)]['sbid'] = smpmsg.id
        mpm.save()
            
            
    @commands.Cog.listener()
    async def on_guild_channel_pins_update(self, chn: discord.TextChannel, pin):
        #TODO: rewrite the damn thing lmfao
        mpm = self.testforguild(chn.guild)
        mpk = mpm.data
        msgl = await chn.pins()
        
        try: 
            if (chn.id in mpk['blacklist']): return
        except: 
            pass

        try: mpk['channel']
        except: return
        chl = await self.bot.fetch_channel(mpk['channel'])
        
        msg = msgl[0]
        mstr = str(msg.id)
        try:
            mpk['messages'][mstr]
            try:
                mpk['messages'][mstr]['spstate'] |= 0b01 
            except:
                mpk['messages'][mstr]['spstate'] = 0b01 
        except:
            mpk['messages'][mstr] = {}
            
            mpk['messages'][mstr]['author'] = msg.author.id
            mpk['messages'][mstr]['chn']    = chn.id
            mpk['messages'][mstr]['sbid']   = 0
            mpk['messages'][mstr]['count']  = 0
            mpk['messages'][mstr]['spstate'] = 0b01
        
        print(bin(mpk['messages'][mstr]['spstate']))
        
        e = await embeds.buildembed(embeds, msg, stardata=[mpk['messages'][mstr]['count'], mpk['messages'][mstr]['spstate'], mpk])
        if not mpk['messages'][mstr]['sbid']:
            if type(e) == list:
                made = await chl.send(content=e[0], embed=e[1])
            else:
                made = await chl.send("", embed=e)
            mpk['messages'][mstr]['sbid']   = made.id         
        else:
            try:
                tedit = await chl.fetch_message(mpk['messages'][mstr]['sbid'])
                if type(e) == list:
                    await tedit.edit(content=e[0], embed=e[1])
                else:
                    await tedit.edit(content="", embed=e)
            except:
                if type(e) == list:
                    made = await chl.send(content=e[0], embed=e[1])
                else:
                    made = await chl.send("", embed=e)
                mpk['messages'][mstr]['sbid']   = made.id         

    
        mpm.save()
        


    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payl):
        start = default_timer()
        await self.handlereact(payl, False)
        self.buffer = list(filter(lambda a: a[0] != payl.message_id, self.buffer))
        print(self.buffer)
        print(default_timer() - start)
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payl):
        start = default_timer()
        await self.handlereact(payl, True)
        self.buffer = list(filter(lambda a: a[0] != payl.message_id, self.buffer))
        print(self.buffer)
        print(default_timer() - start)

    def savejson(self, dict, gid):
        json.dump(dict, open(f"starboard/{gid}.json", "w"), indent=2)

    @commands.group(aliases = ["sb"])
    async def starboard(self, ctx):
        """Sets up the starboard/views the leaderboard if enabled.
        __This command is entirely run by subcommands.__

        *config/cfg*
        > Configures the starboard.
        > `sb cfg setchannel <channel>`
        > `sb cfg setcount <count>`
        > `sb cfg sethighlight <which>`
        > `sb cfg setemoji`
        > `sb cfg blacklist <channels>`
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
            await ctx.send(f"Minimum: {base['amount']}\nChannel: <#{base['channel']}>\nStar: {base['emoji']}\nMessage count: {len(base['messages'])}")

    @starboard.command(aliases = ["lb"])
    async def leaderboard(self, ctx):
        if (ctx.guild.id == 356533377559429150): return
        tbd = await ctx.send("Generating.. this may take a while..")
        await ctx.trigger_typing()
        mpm = self.testforguild(ctx.guild)
        mpk = mpm.data       
        #return
        srtd = sorted(mpk['leaderboard'].items(), key = lambda x : x[1])
        if not srtd:
            return await tbd.edit("Not enough data so cancelled leaderboard calc.")
        srtd.reverse()
        sleep(0.5)
        groups = []
        ebase = discord.Embed()
        ebase.set_author(name="Leaderboard")
        senderpos = 0
        for t in srtd:
            if str(ctx.author.id) != t[0]: senderpos += 1
            else: break
        try: st = mpk['bchk']
        except: st = 1
        for x in range(st - 1, min(10, len(srtd))): #only search first page, idk what the fuck its doing going all the way to last lmfao
            try:
                first = await ctx.guild.fetch_member(int(srtd[x][0]))
                ebase.colour = first.color
                ebase.set_author(name="Leaderboard", icon_url=first.avatar_url)
                ebase.description = f"{first.display_name} is in {self.getord(x + 1)}!\n*You're in {self.getord(senderpos + 1)}!*"
                break
            except Exception as e: continue
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
            #print(count)
        await tbd.delete()
        return await pag(entries=groups).paginate(ctx)
        
    @config.command()
    @commands.has_permissions(manage_guild=True)
    async def setchannel(self, ctx, chn: discord.TextChannel):
        mpm = self.testforguild(ctx.guild)
        mpk = mpm.data       
        mpk['channel'] = chn.id
        mpm.save()
        await ctx.send(f"Channel {chn.mention} set as starboard channel!")

    @config.command()
    @commands.has_permissions(manage_guild=True)
    async def sethighlight(self, ctx, which: int):
        mpm = self.testforguild(ctx.guild)
        mpk = mpm.data       
        if (which > 3 or which < 0): return
        mpk['bchk'] = which
        mpm.save()
        await ctx.send(f"{self.getord(which)} is now the highlighted leaderboard option!")

    @config.command()
    @commands.has_permissions(manage_guild=True)
    async def setemoji(self, ctx):
        def check(r, u):
            return u.id == ctx.message.author.id
        
        await ctx.send("Please react to this with the emoji you want.")
        em = await self.bot.wait_for('reaction_add', timeout=20.0, check=check)
        mpm = self.testforguild(ctx.guild)
        mpk = mpm.data       
        em = em[0]
        if (not em.custom_emoji): 
            mpk['emoji'] = mpk['emojiname'] = str(em.emoji)
        else: 
            mpk['emoji'] = em.emoji.id
            mpk['emojiname'] = em.emoji.name
        mpm.save()
        await ctx.send("Starboard emoji set!")
    
    @config.command()
    @commands.has_permissions(manage_guild=True)
    async def setcount(self, ctx, count: int):
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