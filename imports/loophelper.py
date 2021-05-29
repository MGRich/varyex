from discord.ext import tasks
import imports.globals as g 
from discord.utils import MISSING

def trackedloop(*, seconds=0, minutes=0, hours=0, count=None, reconnect=True, loop=None):
    BOT = g.BOT
    def decorator(func):
        kwargs = {
            'seconds': seconds,
            'minutes': minutes,
            'hours': hours,
            'count': count,
            'reconnect': reconnect,
            'loop': loop
        }
        if func.__name__ in (l := [x.coro.__name__ for x in BOT.loops]):
            i = l.index(func.__name__)
            oloop = BOT.loops[i]
            del BOT.loops[i]
            oloop.cancel()
        r = tasks.Loop(func, time=MISSING, **kwargs)
        BOT.loops.append(r)
        if BOT.autostart: BOT.loop.create_task(BOT.get_command("loop").callback(BOT.owner, "start", func.__name__))
        return r
    return decorator
