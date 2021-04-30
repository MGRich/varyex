#pylint: disable=protected-access
import discord, re, difflib
from typing import List
from discord.ext import commands
from pytimeparse import timeparse

CUTOFF = .75
DAY_IN_SECONDS = 60 * 60 * 24

###############################OVERRIDES
timeparse.YEARS      = r'(?P<years>\d+)\s*(?:ys?|yrs?.?|years?)'
timeparse.MONTHS     = r'(?P<months>\d+)\s*(?:mos?.?|mths?.?|months?)'

timeparse.MULTIPLIERS = dict([
        ('years',   60 * 60 * 24 * 365),
        ('months',  60 * 60 * 24 * 30),
        ('weeks',   60 * 60 * 24 * 7),
        ('days',    60 * 60 * 24),
        ('hours',   60 * 60),
        ('mins',    60),
        ('secs',    1)
        ])

timeparse.TIMEFORMATS = [
    r'{YEARS}\s*{MONTHS}\s*{WEEKS}\s*{DAYS}\s*{HOURS}\s*{MINS}\s*{SECS}'.format(
        YEARS=timeparse.OPTSEP(timeparse.YEARS),
        MONTHS=timeparse.OPTSEP(timeparse.MONTHS),
        WEEKS=timeparse.OPTSEP(timeparse.WEEKS),
        DAYS=timeparse.OPTSEP(timeparse.DAYS),
        HOURS=timeparse.OPTSEP(timeparse.HOURS),
        MINS=timeparse.OPTSEP(timeparse.MINS),
        SECS=timeparse.OPT(timeparse.SECS)),
    r'{MINCLOCK}'.format(
        MINCLOCK=timeparse.MINCLOCK),
    r'{WEEKS}\s*{DAYS}\s*{HOURCLOCK}'.format(
        WEEKS=timeparse.OPTSEP(timeparse.WEEKS),
        DAYS=timeparse.OPTSEP(timeparse.DAYS),
        HOURCLOCK=timeparse.HOURCLOCK),
    r'{DAYCLOCK}'.format(
        DAYCLOCK=timeparse.DAYCLOCK),
    r'{SECCLOCK}'.format(
        SECCLOCK=timeparse.SECCLOCK),
    r'{YEARS}'.format(
        YEARS=timeparse.YEARS),
    r'{MONTHS}'.format(
        MONTHS=timeparse.MONTHS),
    ]

timeparse.COMPILED_TIMEFORMATS = [re.compile(r'\s*' + timefmt + r'\s*$', re.I)
                        for timefmt in timeparse.TIMEFORMATS]


def _interpret_as_minutes(sval, mdict):
    if (    sval.count(':') == 1 
        and '.' not in sval
        and (('hours' not in mdict) or (mdict['hours'] is None))
        and (('days' not in mdict) or (mdict['days'] is None))
        and (('weeks' not in mdict) or (mdict['weeks'] is None))
        and (('months' not in mdict) or (mdict['months'] is None))
        and (('years' not in mdict) or (mdict['years'] is None))
        ):   
        mdict['hours'] = mdict['mins']
        mdict['mins'] = mdict['secs']
        mdict.pop('secs')
    return mdict

timeparse._interpret_as_minutes = _interpret_as_minutes
PARSE = timeparse.timeparse
##################### END OF OVERRIDES

class UserLookup(commands.Converter):
    async def convert(self, ctx: commands.Context, argument) -> discord.User:
        try: return await commands.UserConverter().convert(ctx, argument)
        except:
            match = re.match(r'<@!?([0-9]+)>$', argument)
            lookup = argument
            if match: lookup = int(match.group(1))
            else:
                try: lookup = int(argument)
                except:
                    raise commands.UserNotFound(argument)
            #only handle mentions and ids
            try: return await ctx.bot.fetch_user(lookup)
            except:
                raise commands.UserNotFound(argument)
                #TODO: make this work better, same with members
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


class MemberLookup(commands.Converter):
    async def convert(self, ctx: commands.Context, argument) -> discord.Member:
        r = None
        try: r = await commands.MemberConverter().convert(ctx, argument)
        except: pass
        match = re.match(r'<@!?([0-9]+)>$', argument)
        lookup = argument
        if match: lookup = int(match.group(1))
        else:
            try: lookup = int(argument)
            except:
                raise commands.MemberNotFound(argument)
        try: return r if r else await ctx.guild.fetch_member(lookup)
        except:
            raise commands.MemberNotFound(argument)
            mlist: List[discord.Member] = ctx.guild.members
            fmlist = [x.display_name for x in mlist]
            matches = difflib.get_close_matches(argument, fmlist, n=1, cutoff=CUTOFF)
            if not matches:
                fmlist = [x.name for x in mlist]
                matches = difflib.get_close_matches(argument, fmlist, n=1, cutoff=CUTOFF)
            if (matches):
                return mlist[fmlist.index(matches[0])]

class DurationString:
    def __init__(self, string="", duration=0):
        self.duration = duration
        self.string = string

    @classmethod
    async def convert(cls, _ctx: commands.Context, argument: str):
        flipped = False
        s = argument
        d = 0
        i = 0
        def adjust(use, after):
            r = 0
            if after[-1] == "s" and use.isdigit():
                after = after[:-1]
            if use == "a":
                if after == "day":  r = DAY_IN_SECONDS
            if   after == "week":   r = DAY_IN_SECONDS * 7
            elif after == "month":  r = DAY_IN_SECONDS * 30
            elif after == "year":   r = DAY_IN_SECONDS * 365
            elif after == "decade": r = DAY_IN_SECONDS * 365 * 10
            if use.isdigit():
                r *= int(use)
            return r
        while True:
            slist = re.split(r'(\s+)', s)
            try: r = PARSE(s.split()[i])
            except IndexError: break 
            if not r: 
                try: 
                    use = s.split()[i].lower()
                    if flipped: raise Exception()
                    if use == "tomorrow":
                        r = DAY_IN_SECONDS
                    elif use in {"next", "a"}:
                        r = adjust(use, s.split()[i+1].lower())
                    else:
                        int(use)
                        after = s.split()[i + 1].lower()
                        r = PARSE(use + ' ' + after)
                        if not r: r = adjust(use, after)
                    if not r: raise Exception()
                    del slist[2]
                except: 
                    if flipped: break
                    i = -1
                    flipped = True
                    continue
                            
            d += r
            flipped = True #we will no longer flip cause this is where we are
            del slist[i]
            s = ''.join(slist).strip()
        return cls(s, d)

