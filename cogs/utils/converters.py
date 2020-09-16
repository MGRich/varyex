import discord, re
from discord.ext import commands

class UserLookup(commands.Converter):
    async def convert(self, ctx, argument) -> discord.User:
        try: return await commands.UserConverter().convert(ctx, argument)
        except:
            match = re.match(r'<@!?([0-9]+)>$', argument)
            lookup = argument
            if match: lookup = int(match.group(1))
            else:
                try: lookup = int(argument)
                except: raise commands.BadArgument(argument)
            #only handle mentions and ids
            try: return await ctx.bot.fetch_user(lookup)
            except: raise commands.BadArgument(argument) #TODO: when 1.5 hits upgrade to UserNotFound

class MemberLookup(commands.Converter):
    async def convert(self, ctx, argument) -> discord.Member:
        try: return await commands.MemberConverter().convert(ctx, argument)
        except:
            match = re.match(r'<@!?([0-9]+)>$', argument)
            lookup = argument
            if match: lookup = int(match.group(1))
            else:
                try: lookup = int(argument)
                except: raise commands.BadArgument(argument)
            try: return ctx.guild.get_user(lookup)
            except:
                u = await UserLookup().convert(ctx, argument)
                m = ctx.guild.get_member_named(str(u))
                if not m: raise commands.BadArgument(argument) #TODO: when 1.5 hits upgrade to MemberNotFound
                return m

