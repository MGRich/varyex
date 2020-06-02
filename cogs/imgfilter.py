import discord, json, copy, os, math
from discord.ext import commands
from datetime import datetime
from typing import Optional
import timeago

from PIL import Image, UnidentifiedImageError
from io import BytesIO
import requests
from array import array
#from cogs.utils.SimplePaginator import SimplePaginator as pag
#from asyncio import sleep

class IMGFilter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def imgfilter(self, ctx, filter, *links):
        """Applies a filter to images.
        You can send images as links or """
        if (len(ctx.message.attachments) == 0 and not links): return
        #dm = False
        #if (len(ctx.message.attachments) + len(links) > 1): dm = True
        images = []
        invalid = []
        for link in links:
            response = requests.get(link)
            try: images.append(Image.open(BytesIO(response.content)))
            except UnidentifiedImageError: invalid.append(link)
        for attachment in ctx.message.attachments:
            response = requests.get(attachment.url)
            try: images.append(Image.open(BytesIO(response.content)))
            except UnidentifiedImageError: invalid.append(link)
        msg = await ctx.send(f"Converting, please wait... -1/{len(images)} done")
        done = 0
        files = []
        for img in images:
            #if (img.is_animated):

            await msg.edit(content=msg.content.replace(str(done - 1), str(done)))
            img.convert('RGB')
            map = img.load()
            if ("gen" in filter):
                gencolour = [00, 0x34, 0x57, 0x74, 0x90, 0xAC, 0xCE, 0xFF]
                clrchecks = [0x20, 0x40, 0x60, 0x80, 0xA0, 0xC0, 0xE0, 0xFE]
                map = img.load()
                for y in range(img.height):
                    for x in range(img.width):
                        tup = list(map[x, y])
                        for ii in range(3):
                            for i in range(8):
                                if (tup[ii] < clrchecks[i]):
                                    tup[ii] = gencolour[i]
                                    break
                        map[x, y] = tuple(tup)
            elif ("565" in filter):
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


    @commands.command()
    async def ffuffu(self, ctx: discord.ext.commands.Context):
        role = ctx.guild.get_role(401970288746692608)
        chan = ctx.guild.get_channel(485536593491394569)
        await ctx.send("-")
        res = "```diff\n"
        for m in ctx.guild.members:
            if (role in m.roles):
                t = datetime.utcnow()
                async for x in chan.history(limit = 500):
                    if (x.author == m): 
                        t = x.created_at
                        break
                if (t == datetime.utcnow()): res += "-"
                res += f"{m} - {timeago.format(t, datetime.utcnow())}\n"
        res += "```"
        await ctx.send(res)


def setup(bot):
    bot.add_cog(IMGFilter(bot))