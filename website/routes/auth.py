from aiohttp import web
import aiohttp
from website.helper import discordreq, DiscordRoute, UnifiedRoutes, get_auth

import os
from imports.other import timestamp_now, timestamp_to_int
from datetime import datetime, timedelta
import base64
from yarl import URL

import imports.globals as g

routes = UnifiedRoutes()


@routes.view("/login")
async def getlogin(request: web.Request):
    session, auth = await get_auth(request)
    if 'redir' in request.query:
        session['redir'] = request.query['redir']
    if auth: 
        #already logged in how tf are we HERE
        return web.HTTPFound("/servers" if 'redir' not in session else session['redir'])
    session['state'] = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8')

    return web.HTTPFound(str(URL.build(scheme="https", host="discord.com", path="/api/oauth2/authorize", query={
        'response_type': 'code',
        'client_id': g.BOT.user.id,
        "state": session['state'],
        "redirect_uri": os.getenv("WEBRD"),
        "prompt": "none"
    })) + "&scope=identify%20guilds")
    #we add the + just to force space
    

@routes.view("/oauth")
async def oauth(request: web.Request):
    session, auth = await get_auth(request)
    redir = session.pop('redir', None)
    if redir: session.changed()
    if auth:
        #we're already authed!
        return web.HTTPFound("/servers" if not redir else redir)
    if 'state' not in request.query or session['state'] != request.query['state']:
        raise web.HTTPUnauthorized()
    data = {
        'grant_type': 'authorization_code',
        'code': request.query['code'],
        'redirect_uri': os.getenv("WEBRD")
    }

    now = datetime.utcnow()
    r = await discordreq(DiscordRoute('POST', '/oauth2/token'), data=data)
    auth = {}
    auth['token'] = r['access_token']
    auth['expires'] = timestamp_to_int(
        now + timedelta(seconds=r['expires_in']))
    auth['refresh'] = r['refresh_token']
    session['uid'] = (await discordreq(DiscordRoute('GET', '/users/@me'), bearer=auth['token']))['id']
    g.WEBDICT[session['state']] = auth

    return web.HTTPFound("/servers" if not redir else redir)
