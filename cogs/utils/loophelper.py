from discord.ext import tasks

BOT = None

def trackedloop(*, seconds=0, minutes=0, hours=0, count=None, reconnect=True, loop=None):
    def decorator(func):
        kwargs = {
            'seconds': seconds,
            'minutes': minutes,
            'hours': hours,
            'count': count,
            'reconnect': reconnect,
            'loop': loop
        }
        r = tasks.Loop(func, **kwargs)
        BOT.loops.append(r)
        return r
    return decorator
