import discord, json, copy, os, math
from discord.ext import commands
from datetime import datetime
from cogs.utils.mpkmanager import MPKManager
#from cogs.utils.SimplePaginator import SimplePaginator as pag
#from asyncio import sleep

class Cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def getmpm(self, guild) -> MPKManager:
        return MPKManager("cog", guild.id)

def setup(bot):
    bot.add_cog(Cog(bot))