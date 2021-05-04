from aiohttp import web
from aiohttp_session import get_session
from website.helper import UnifiedRoutes, discordreq, DiscordRoute, checklogin
from discord import Permissions
import imports.globals as g

routes = UnifiedRoutes()

@routes.view("/servers")
@checklogin
async def guilds(request: web.Request):
    session = await get_session(request)
    gl = await discordreq(DiscordRoute('GET', '/users/@me/guilds'), bearer=session['token'])
    result = set()
    for x in gl:
        guild = g.BOT.get_guild(int(x['id']))
        isin = guild is not None
        if x['owner']: 
            result.add(((x['name'], int(x['id']), x['icon']), isin))
        perms = Permissions(int(x['permissions']))
        if perms.manage_guild:
            result.add(((x['name'], int(x['id']), x['icon']), isin))
    return web.Response(text=str(result))
