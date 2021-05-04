from aiohttp import web
import asyncio
import threading
import os, ssl, logging

from typing import TYPE_CHECKING

import aiohttp
import imports.globals as g

from aiohttp_session import setup, get_session, session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage
import base64
from cryptography import fernet

from website.helper import discordreq, DiscordRoute, UnifiedRoutes
from imports.other import timestamp_now, timestamp_to_int
from datetime import datetime, timedelta

#WEBSITE IMPORTSSSS
from website.views import guilds


routes = UnifiedRoutes()
LOG = logging.getLogger('bot')
ROOT = ""

@routes.view("/")
async def wh(request):
    return web.Response(text=f"parallel running! bot in as {g.BOT.user.name}")

@routes.view("/oauth")
async def oauth(request: web.Request):
    session = await get_session(request)
    data = {
        'grant_type': 'authorization_code',
        'code': request.query['code'],
        'redirect_uri': os.getenv("WEBRD")
    }
    
    now = datetime.utcnow()
    r = await discordreq(DiscordRoute('POST', '/oauth2/token'), data=data)
    session['token'] = r['access_token']
    session['expires'] = timestamp_to_int(now + timedelta(seconds=r['expires_in']))
    session['refresh'] = r['refresh_token'] 
    

    return web.HTTPFound("/servers" if 'redir' not in request.query else request.query['redir'])

def get_runner():
    app = web.Application()
    fernet_key = fernet.Fernet.generate_key()
    secret_key = base64.urlsafe_b64decode(fernet_key)
    setup(app, EncryptedCookieStorage(secret_key))
    app.add_routes(routes)
    return web.AppRunner(app)

def run_app(ip, port, runner):
    global ROOT 
    try:
        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ctx.load_cert_chain('website/https/security.crt',
                            'website/https/security.key')
    except:
        LOG.error("COULDN'T LOAD SSL KEYS!!!! SITE WILL NOT RUN")
        return
    ROOT = "https://" + ip
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop) #is this fine? discord is currently running parallel...
    #turns out it is? prolly threadbased
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, ip, port, ssl_context=ctx)
    loop.run_until_complete(site.start())
    loop.run_forever()
