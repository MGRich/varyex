from aiohttp import web
from website.helper import UnifiedRoutes, discordreq, DiscordRoute, checklogin, templated, get_auth
from discord import Permissions
import imports.globals as g
import aiohttp_jinja2 as aiojinja

routes = UnifiedRoutes()

@routes.view("/servers")
@aiojinja.template("guilds.html")
@templated
@checklogin
async def guilds(request: web.Request):
    session, auth = await get_auth(request)
    gl = await discordreq(DiscordRoute('GET', '/users/@me/guilds'), bearer=auth['token'])
    result = []
    idlist = []
    for x in gl:
        guild = g.BOT.get_guild(int(x['id']))
        isin = guild is not None
        perms = Permissions(int(x['permissions']))
        if perms.manage_guild or x['owner']:
            if x['id'] in idlist: continue
            result.append((x['name'], int(x['id']), x['icon'], isin))
            idlist.append(x['id'])
    return {'title': 'Servers', 'gl': result, 'extracss': ['guilds']}

@routes.view("/test")
@checklogin
async def aaa(request: web.Request):
    return web.Response(text="AAAAAAA")