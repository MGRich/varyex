from datetime import datetime, timedelta
import aiohttp, asyncio
from aiohttp import web
from aiohttp.helpers import BasicAuth
from aiohttp.web import RouteTableDef
from discord.errors import HTTPException
from discord.http import Route as DiscordRoute, json_or_text
from discord.utils import to_json
from aiohttp_session import get_session

from imports.other import datetime_from_int, timestamp_now, timestamp_to_int
import os
import imports.globals as g

import requests

async def discordreq(route: DiscordRoute, json=None, data=None, headers=None, params=None, bearer=None, repress_auth=False):
    headers = headers or {'Content-Type': 'application/json'} if json else {}
    headers.update({'X-Ratelimit-Precision': 'millisecond'})
    if bearer:
        repress_auth = True
        headers.update({"Authorization": f"Bearer {bearer}"})
    auth = BasicAuth(str(g.BOT.user.id), g.BOT.secret) if not repress_auth else None
    if json:
        data = to_json(json)
    for tries in range(5):
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

def checklogin(func):
    async def wrap(request: web.Request):
        session = await get_session(request)
        #del session['token']
        if 'token' not in session or session['expires'] < timestamp_now():
            #we expired
            try:
                del session['token']
                del session['expires']
                del session['refresh']
            except: pass
            #trash this session
            #TODO: add body
            raise web.HTTPUnauthorized(reason="Session expired.")
        elif (datetime_from_int(session['expires']) - datetime.utcnow()) < timedelta(days=1):
            #lets renew if we're a day short. shouldn't hurt
            data = {
                'client_id': str(g.BOT.user.id),
                'client_secret': g.BOT.secret,
                'grant_type': 'authorization_code',
                'refresh_token': session['refresh']
            }

            now = datetime.utcnow()
            r = await discordreq(DiscordRoute('POST', '/oauth2/token'), data=data)
            session['token'] = r['access_token']
            session['expires'] = timestamp_to_int(now + timedelta(seconds=r['expires_in']))
            session['refresh'] = r['refresh_token']
        return await func(request)
    return wrap


