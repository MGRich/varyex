import json, discord, datetime, random, os, time
from discord.ext import commands
import re

class embeds:

    async def buildembed(self, msg, stardata = None, focus = None, dcolor = 0xAC6AD7, link=True, attachmode=0b10):
        """
        stardata = [count, acount, spstate]
        focus is focused word for filterping
        """

        if (stardata):
            jsn = stardata[2]
            count = stardata[0]
            spstate = stardata[1]
            dcolor = 0xFFAC33
                    
        
        embed = discord.Embed(color=(discord.Color(dcolor) if msg.author.color == discord.Color.default() else msg.author.color))
        embed.set_author(name=msg.author.display_name, icon_url=msg.author.avatar_url)
        embed.timestamp = msg.created_at
        desc = [msg.content]

        done = False
        for attachment in msg.attachments:
            try: 
                if (not list(os.path.splitext(attachment.filename))[1].lower() in [".png", ".wempm", ".gif", ".jpg", ".jpeg", ".webp"]) or done: raise Exception()
                if (not attachmode): raise Exception()
                else:
                    if (attachmode & 1):
                        embed.set_image(url=attachment.proxy_url)
                    else:
                        embed.set_image(url=attachment.url)
                done = True
            except: desc.append(f"\n[{attachment.filename}]")
        if (desc[0].startswith("\n")): desc[0] = desc[0][1:]

        if re.fullmatch("<@.+>", ''.join(desc)): desc.append("\n(jump to message)")
        desc = ''.join(desc)
        if (desc == "" and link): desc = "(jump to message)"
        if (link): embed.description = f"[{desc}]({msg.jump_url})"
        else: embed.description = f"{msg.channel.mention}\n{desc}"
        #now that we're done, existing embed time
        #setup footer
        
        if (stardata):
            if spstate & 0b10:
                embed.description = f"<#{msg.channel.id}>\n[{desc}]({msg.jump_url})"
                ftxt = [f"{count} {jsn['emojiname']}{'s' if count != 1 else ''}"]
            else:
                ftxt = [f"\U0001F4CC Pinned in #{msg.channel.name}"]
            if spstate == 0b11:
                ftxt.append("/\U0001F4CC Pinned")

        if (focus):
            for substr in focus:
                desc = re.sub(fr'({substr})', r"**\1**", desc, flags=re.IGNORECASE)
            embed.description = f"<#{msg.channel.id}>\n[{desc}]({msg.jump_url})"
        
        mcpair = False
        content = ""

        if (len(msg.embeds) != 0):
            e = msg.embeds[0]
            #print(msg.embeds[0].thumbnail.url)
            #print(embed.video)
            embed.title = e.title
            typ = ""
            if (e.color != discord.Color.default() and e.color != e.Empty): embed.colour = e.color
            #SPECIAL SPECIFIERS
            #print(e.provider.name)
            #print(e.thumbnail.url)
            try:
                if (stardata):
                    if "https://twitter.com/" in e.url: typ = "twitter"
                    if "https://www.youtube.com/" == e.provider.url: typ = "yt"
                    if "Twitch" == e.provider.name: typ = "twitch"
                    if "GameBanana" == e.provider.name: typ = "gb"
            except: pass
            #SPECIAL HANDLING   
            if typ == "twitter":
                embed.colour = discord.Color(0x1DA1F2)
                if e.description != e.Empty:
                    embed.add_field(name="Tweet", value=f"**__{e.author.name}__** {'*(multiple images)*' if len(msg.embeds) > 1 else ''}\n{e.description}")
                
                if len(e.fields) != 0: 
                    ftxt.append(" [")
                    for field in e.fields:
                        emo = None
                        if "Likes" == field.name: emo = "\u2764"
                        if "Retweets" == field.name: emo = "\U0001F501"
                        if "Tweets" == field.name: emo = "\U0001F426"
                        if "Followers" == field.name: emo = "\U0001F465"
                        if not emo: continue

                        ftxt.append(f"{field.value} {emo} ")

                    ftxt = [''.join(ftxt)[:-1] + "]"]

                if (e.author.icon_url != e.Empty):
                    embed.set_thumbnail(url=e.author.icon_url)
                if (e.image.url != e.Empty):
                    embed.set_image(url=e.image.url)
                if (e.thumbnail.url != e.Empty):
                    if e.description == e.Empty:
                        embed.set_thumbnail(url=e.thumbnail.url)
                    else:
                        embed.set_image(url=e.thumbnail.url)

            if typ == "yt":
                try:
                    if (e.author.name == e.Empty): raise ValueError()
                    ftxt.append(f" | Uploaded by {e.author.name}")
                    embed.add_field(name="Description", value=e.description)
                    embed.set_image(url=e.thumbnail.url)
                except: ftxt.append(" | [bad YT embed]")
            if typ == "twitch":
                embed.colour = discord.Color(0x9147FF)
                titlesplit = e.title.split(' - ')
                try: typ = ("clip" if titlesplit[2] == "Twitch Clips" else "vod")
                except: typ = "vod" if "/videos/" in e.url else "channel"
                descsplit = e.description.split(' - ')
                if typ == "clip": 
                    ftxt.append(f" | {titlesplit[1]}")
                    embed.description += f"\n*{descsplit[1]}*"
                    embed.title = titlesplit[0]
                    embed.set_image(url=e.thumbnail.url)
                if typ == "vod":
                    embed.description += f"\n*VOD of {descsplit[0]} playing {descsplit[1]}*"
                    embed.set_image(url=e.thumbnail.url)
                if typ == "channel":
                    embed.add_field(name="Stream Info", value=f"**__{titlesplit[0]}__**\n{e.description}")
                    embed.set_thumbnail(url=e.thumbnail.url)
            if typ == "gb":
                ##############PARSE EMBED DATA###############
                data = {} #yes its that fucking complex
                data['tease'] = e.description.split("...")[0]
                if (data['tease'] == e.description): data['tease'] = None
                data['author'] = e.description.split(", sumpmitted by ")[1]
                data['name'] = e.title.split("[")[0][:-1]
                data['full'] = e.title.split("[")[1].split("]")[0]  
                data['type'] = e.title.split("[")[2].split("]")[0].split(" Mods")[0]
                if (data['type'] == "Mods"): data['type'] = "Mod"
                if (data['type'] == "Requests"): data['type'] = "Request"
                if (data['type'] == "Works In Progress"): data['type'] = "WIP"
                data['short'] = e.description.split(f"A {data['full']} (")[1].split(")")[0]
                data['category'] = e.description.split(" in the ")[1].split(" category")[0]

                #####finally
                embed.colour = discord.Color(0xE6D85E)
                embed.set_image(url=e.thumbnail.url)
                embed.title = f"{data['name']} | {data['full']}"
                if (data['tease']): ftxt.append(f" | \"{data['tease']}\"") 
                ftxt.append(f" | {data['short']} {data['category']} {data['type']} by {data['author']}")

            if typ == "":
                try:
                    if (e.image.url == e.Empty): raise NameError() 
                    #print(e.image.url) 
                    embed.set_image(url=e.image.url)
                except:
                    try: 
                        if (e.thumbnail.url == e.Empty): raise NameError() 
                        embed.set_image(url=e.thumbnail.url)
                    except: pass
                if (e.description != e.Empty): embed.add_field(name="Description", value=e.description)

        #finalize
        if (stardata):
            if (spstate & 0b10) and type(jsn['emoji']) == int: # and (jsn['emoji'] >= 0xFFFFFFFF)): # \UFFFFFFFF isn valid but covering bases anyway
                embed.set_footer(text=''.join(ftxt), icon_url=f"https://cdn.discordapp.com/emojis/{jsn['emoji']}.png")
            else:
                embed.set_footer(text = ''.join(ftxt))

        if mcpair:
            return [content, embed]
        return embed
