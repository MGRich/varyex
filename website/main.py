import sys, os
sys.path.append(os.getcwd()) #for name == main

from collections import namedtuple
from aiohttp import web
import asyncio
import threading
import ssl, logging

from typing import TYPE_CHECKING

import aiohttp
import imports.globals as g

from aiohttp_session import setup, get_session, session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage
import aiohttp_jinja2 as aiojinja
from hashlib import sha256
import jinja2
from yarl import URL

#from website.helper import discordreq, DiscordRoute, UnifiedRoutes, templated

#WEBSITE IMPORTSSSS
#from website.routes import guilds, auth

routes = web.RouteTableDef()
LOG = logging.getLogger('bot')

@routes.view("/")
@aiojinja.template("index.html")
async def wh(request):
    s = str(URL.build(scheme="https", host="discord.com", path="/api/oauth2/authorize", query={
        'client_id': g.BOT.user.id,
        "permissions": "268446911"
    })) + "&scope=bot%20applications.commands"
    return {'invite': s}

@routes.view("/assets/{path:.*}")
async def get_asset(request: web.Request):
    try:
        path = "website/assets/" + request.match_info['path']
    except: raise web.HTTPUnauthorized()
    if not os.path.isfile(path) or not os.path.relpath(os.path.realpath(path)).replace("\\", "/").startswith("website/assets/"):
        raise web.HTTPUnauthorized()
    return web.FileResponse(path)

def get_runner():
    app = web.Application()
    secret_key = sha256(g.BOT.secret.encode('utf-8')).digest()
    setup(app, EncryptedCookieStorage(secret_key))
    aiojinja.setup(app, loader=jinja2.FileSystemLoader('website/templates'))
    app.add_routes(routes)
    return web.AppRunner(app)

def run_app(ip, port, runner):
    try:
        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ctx.load_cert_chain('website/https/security.crt',
                            'website/https/security.key')
    except:
        LOG.error("COULDN'T LOAD SSL KEYS!!!! SITE WILL NOT RUN")
        return
    g.WEBDICT['ROOT'] = "https://" + ip
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop) #is this fine? discord is currently running parallel...
    #turns out it is? prolly threadbased
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, ip, port, ssl_context=ctx)
    if __name__ == '__main__':
        print('starting')
    loop.run_until_complete(site.start())
    loop.run_forever()

if __name__ == '__main__':
    #os.chdir(os.getcwd() + "/../")
    from dotenv import load_dotenv
    load_dotenv()
    from imports.main import Main
    from imports.mpk import getmpm
    import discord
    from json import load as jload
    try:
        data = jload(open("stable.json" if sys.argv[1] == "stable" else "info.json"))
    except:
        data = jload(open("info.json"))
    stable = data['stable']
    #we're starting a MINIMAL client
    #i don't have like ANY control
    i = discord.Intents.default()
    i.members = True
    bot = Main(data, getmpm('users', None),
               owner_id=data['owner'], intents=i, activity=discord.Game("WEB ONLY MODE"), status=discord.Status.dnd, webonly=True)
    t = os.getenv('STOKEN' if stable else 'DTOKEN')
    g.BOT = bot
    import threading
    threading.Thread(target=run_app, args=(os.getenv("WEBHOST"), os.getenv("WEBPORT"), get_runner())).start()
    bot.run(t, bot=True, reconnect=True)
