import discord, re, difflib
from typing import List
from discord.ext import commands

CUTOFF = .75
class UserLookup(commands.Converter):
    async def convert(self, ctx: commands.Context, argument) -> discord.User:
        try: return await commands.UserConverter().convert(ctx, argument)
        except:
            match = re.match(r'<@!?([0-9]+)>$', argument)
            lookup = argument
            if match: lookup = int(match.group(1))
            else:
                try: lookup = int(argument)
                except: pass
            #only handle mentions and ids
            try: return await ctx.bot.fetch_user(lookup)
            except:
                if (ctx.guild):
                    mlist: List[discord.Member] = ctx.guild.members
                    fmlist = [x.display_name for x in mlist]
                    matches = difflib.get_close_matches(argument, fmlist, n=1, cutoff=CUTOFF)
                    if not matches:
                        fmlist = [x.name for x in mlist]
                        matches = difflib.get_close_matches(argument, fmlist, n=1, cutoff=CUTOFF)
                    if (matches):
                        member = mlist[fmlist.index(matches[0])]
                        u = ctx.bot.get_user(member.id)
                        if u: return u
                        try: return await ctx.bot.fetch_user(member.id)
                        except: pass #literally how in the fuck

                raise commands.UserNotFound(argument)

class MemberLookup(commands.Converter):
    async def convert(self, ctx: commands.Context, argument) -> discord.Member:
        try: return await commands.MemberConverter().convert(ctx, argument)
        except:
            match = re.match(r'<@!?([0-9]+)>$', argument)
            lookup = argument
            if match: lookup = int(match.group(1))
            else:
                try: lookup = int(argument)
                except: pass
            try: return ctx.guild.get_user(lookup)
            except:
                ctx.guild: discord.Guild
                mlist: List[discord.Member] = ctx.guild.members
                fmlist = [x.display_name for x in mlist]
                matches = difflib.get_close_matches(argument, fmlist, n=1, cutoff=CUTOFF)
                if not matches:
                    fmlist = [x.name for x in mlist]
                    matches = difflib.get_close_matches(argument, fmlist, n=1, cutoff=CUTOFF)
                if (matches):
                    return mlist[fmlist.index(matches[0])]
                raise commands.MemberNotFound(argument)

