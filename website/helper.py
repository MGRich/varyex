import aiohttp
import asyncio

from aiohttp import web
from aiohttp.helpers import BasicAuth
from aiohttp.web import RouteTableDef
from aiohttp_session import Session, get_session

from discord.errors import HTTPException
from discord.http import Route as DiscordRoute, json_or_text
from discord.utils import to_json

from datetime import datetime, timedelta
from typing import Tuple

from imports.other import datetime_from_int, timestamp_now, timestamp_to_int
import imports.globals as g

async def discordreq(route: DiscordRoute, json=None, data=None, headers=None, params=None, bearer=None, repress_auth=False):
    headers = headers or {'Content-Type': 'application/json'} if json else {}
    headers.update({'X-Ratelimit-Precision': 'millisecond'})
    if bearer:
        repress_auth = True
        headers.update({"Authorization": f"Bearer {bearer}"})
    auth = BasicAuth(str(g.BOT.user.id), g.BOT.secret) if not repress_auth else None
    if json:
        data = to_json(json)
    for _ in range(5):
        try:
            async with aiohttp.request(route.method, route.url, headers=headers, auth=auth, data=data, params=params) as r:
                resp = await json_or_text(r)
                
                if r.status == 429: #rrrrrat(elimit)
                    await asyncio.sleep(resp['retry_after'] / 1000.0)
                    continue

                r.raise_for_status()
                return resp
        except Exception as e:
            print(e)
    raise HTTPException(r, resp)

class UnifiedRoutes(RouteTableDef):
    _items = [] 
    def __init__(self) -> None:
        pass

async def get_auth(request) -> Tuple[Session, dict]:
    session = await get_session(request)
    try: g.WEBDICT[session['state']]
    except: return (session, {})
    else: return (session, g.WEBDICT[session['state']])

def checklogin(func):
    async def wrap(request: web.Request):
        session, auth = await get_auth(request)
        if not auth or auth['expires'] < timestamp_now():
            #we expired
            session.invalidate()
            #trash this session
            #request to re-login
            return web.HTTPFound("/login?redir=" + request.path)
        elif (datetime_from_int(auth['expires']) - datetime.utcnow()) < timedelta(days=1):
            #lets renew if we're a day short. shouldn't hurt
            data = {
                'client_id': str(g.BOT.user.id),
                'client_secret': g.BOT.secret,
                'grant_type': 'authorization_code',
                'refresh_token': auth['refresh']
            }

            now = datetime.utcnow()
            r = await discordreq(DiscordRoute('POST', '/oauth2/token'), data=data)
            auth = g.WEBDICT[session['state']]
            auth['token'] = r['access_token']
            auth['expires'] = timestamp_to_int(now + timedelta(seconds=r['expires_in']))
            auth['refresh'] = r['refresh_token']
            session['uid'] = (await discordreq(DiscordRoute('GET', '/users/@me'), bearer=auth['token']))['id']
        return await func(request)
    return wrap
    
def templated(func):
    async def wrap(request: web.Request):
        r = await func(request)
        session = await get_session(request)
        r.update({'bot': g.BOT, 'user': None})
        if 'uid' in session:
            r.update({'user': g.BOT.get_user(int(session['uid']))})
        return r
    return wrap
