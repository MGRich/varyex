import json, discord, datetime, random, os, time
from discord.ext import commands
from builtins import type as det

class suggestions:
    #def __init__(self, bot):
     #   self.bot = bot

    async def add(self, bot, ctx, type="general", img=None, embed=None, check=True, *args):
        #print(f"{ctx}, {type}, {img}, {embed}, {args}")
        #format embed ahead of time
        if (not json.load(open('info.json'))['stable']) and (check):
            return
        if embed == None:
            embed = discord.Embed(title="Suggestion", colour=discord.Colour(random.randint(0, 16777215)))
        if embed.colour == discord.Embed.Empty:
            embed.colour=discord.Colour(random.randint(0, 16777215))
        if embed.description == discord.Embed.Empty:
            embed.description="No info provided."
        embed.timestamp = datetime.datetime.now()
        e = embed
        if check:
            #print(os.getcwd())
            mpk = json.load(open("suggestions.json"))
            am = str(mpk['count'] + 1)
            mpk['count'] = mpk['count'] + 1
            mpk[am] = {}
            dat = mpk[am]
            #run through basic types
            dat['time'] = time.time()
            dat['author'] = ctx.message.author.id
            imgm = []
            if det(img) == str:
                imgm.append(img)
            else:
                imgm = img
            dat['image'] = imgm
            dat['type'] = type
            dat['content'] = ctx.message.content
            #format basic embed
            e.description = f"{ctx.message.author.name} has given a {type} suggestion, which requires approval.\nMore info:```\n{e.description}\n```\n(For other people reading this, the footer is just a required ID.)"
            e.set_footer(text=am)
        #handle specific types
        if (type == "imggal-img") or (type == "imggal"):
            dat['imggal'] = args[0]
            e.description = e.description + f"\n[IMGGal: {args[0]}]"
        if img != None:
            if det(img) == list:
                e.set_image(url=img[0])
                imgd = '\n'.join(img)
                e.description = e.description + f"\nIncludes multiple images, one shown. List of image urls:\n```{imgd}```"
            else:
                e.set_image(url=img)
        #handle destination
        dest = 465318267410710551
        if type == "imggal-img":
            dest = 465314187527323649
        elif type == "imggal":
            dest = 465315532602605568
        elif type == "moderation":
            dest = 465315853194231810
        elif type == "loli":
            dest = 470787214133952512
        elif type == "bugrep":
            dest = 473183297032159242
        #print(mpk['list'], json.dumps({"h": mpk['list']}))
        dest = bot.get_channel(dest)
        #finally send
        #BUT WAIT THERE'S MORE
        if not check:
            e.title = type.title()
            #handle specific DESC
            e.description = discord.Embed.Empty
            if type == "loli":
                e.description = f"Cute loli sent by {ctx.message.author.name}!" 
            if type == "bugrep":
                e.description = f"Bug description: ```{args[0]}```"
        msg = await dest.send(embed = e)
        if check:
            if mpk['list'] == None:
                mpk['list'] = []
            mpk['list'].append(msg.id)
            json.dump(mpk, open("suggestions.json", "w"), sort_keys=True, indent=2)
            await msg.add_reaction('✅')
            await msg.add_reaction('❌')


