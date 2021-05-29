import humanize
from datetime import timedelta, datetime, timezone
from aiohttp import request as aioreq

def utcnow():
    return datetime.now(timezone.utc)

def getord(num):
    st = "th"
    if ((num % 100) > 10 and (num % 100) < 15): return str(num) + st
    n = num % 10
    if not (n in {1, 2, 3}): return str(num) + st
    if   (n == 1): st = "st"
    elif (n == 2): st = "nd"
    elif (n == 3): st = "rd"
    return str(num) + st

def timeint(num, minutes=False):
    return humanize.naturaldelta(timedelta(seconds=(num * (60 if minutes else 1))))

def timestamp_to_int(dt):
    return int(datetime.timestamp(dt) * 1000000)
def timestamp_now():
    return timestamp_to_int(utcnow())    
def datetime_from_int(dt):
    return datetime.fromtimestamp(dt  / 1000000)

def iiterate(i, iafter = True):
    if iafter: return zip(i, range(len(i)))
    return zip(range(len(i)), i)

def fixml(st):
    return '\n'.join([x.strip() for x in st.split('\n')])

async def httpfetch(url, json=False, headers=None):
    async with aioreq('GET', url, headers=headers) as r:
        if (json == 2): return r
        return (await r.json()) if json else (await r.text())
    
async def getcode(url):
    try:
        async with aioreq('HEAD', url) as resp:
            return resp.status
    except:
        return 408

async def urlisOK(url):
    return (await getcode(url)) in {200, 201}
