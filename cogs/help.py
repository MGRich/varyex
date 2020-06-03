import discord
from discord.ext import commands
from typing import Optional, Union, List

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def parse(self, cog, command, prefix="v!") -> Union[List[discord.Embed], discord.Embed]:
        if (not cog) and (not command): #v!help
            ret = []
            for x in list(self.bot.cogs):
                ret.append(self.parse(x, None))
            return ret
        if command:
            command = self.bot.get_command(command)
            if not command: return None
            cog = command.cog.qualified_name
            return discord.Embed(title=f"{cog} - {command.name}", color=self.bot.data['color'], description=command.help)
        #cog
        embed = discord.Embed(title=cog, color=self.bot.data['color'], description="")
        for command in self.bot.cogs[cog].walk_commands():
            if command.hidden or (not command.enabled) or (not command.help) or command.parent: continue
            summary = command.help.split('\n')[0]
            aliasstr = ""
            if (command.aliases):
                aliasstr = f" - `{'`, `'.join(command.aliases)}`"
            embed.description += f"`{command.name}` - {summary}{aliasstr}\n"
            embed.set_footer(text = f"Use {prefix}help [command] for more info on a command.")            
        return embed
        
    @commands.command()
    async def help(self, ctx, c: Optional[str] = None):
        if not c:
            embed = discord.Embed(title="Help", color=self.bot.data['color']) 
            for e in self.parse(None, None):
                if e.description:
                    embed.add_field(name=e.title, value=e.description, inline=False)
            embed.set_footer(text = f"Use {ctx.prefix}help [command] for more info on a command.")
            return await ctx.send(embed=embed)
        for x in list(self.bot.cogs):
            if x.lower() == c.lower():
                return await ctx.send(embed=self.parse(x, None, prefix=ctx.prefix))
        embed = self.parse(None, c.lower())
        if not embed:
            await ctx.send("That command doesn't exist!")
            return await ctx.invoke(self.help)
        return await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Help(bot))