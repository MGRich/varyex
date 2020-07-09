import discord, traceback, json, os, sys, subprocess, textwrap, contextlib
from discord.ext import commands, tasks
from io import StringIO
import cogs.utils.mpk as mpku

stable = False
if stable or (len(sys.argv) > 1 and sys.argv[1] == "stable"): data = json.load(open("stable.json"))
else: data = json.load(open("info.json"))

stable = data['stable']
usrout = StringIO()
if stable:
    sys.stderr = usrout 
regout = sys.stdout

def prefix(_unusedbot, message):
    prf = data['prefix'].copy()
    if message.guild:
        con = mpku.MPKManager("misc", message.guild.id).data
        try: 
            con['prefix']
            prf.clear()
            prf.append(con['prefix'])
        except: pass
    
    users = mpku.MPKManager('users', None).data
    try: prf.insert(0, users[str(message.author.id)]['prefix'])
    except: pass
    return prf

#fetch cogs
cgs = []
for x in os.listdir("cogs"):
    if os.path.isfile("cogs/" + x):
        cgs.append(f"cogs.{x[:-3]}")

bot = commands.Bot(command_prefix=prefix, owner_id=data['owner'])
bot.__dict__['data'] = data
commands.Bot.data = property(lambda x: x.__dict__['data'])
bot.remove_command('help')

first = False
print(bot.data)

@bot.event
async def on_ready():
    print(f'\n\nin as: {bot.user.name} - {bot.user.id}\non version: {discord.__version__}\n')
    await bot.change_presence(activity=discord.Activity(name=f"{data['status']} | v!help", type=0))
    global first
    if (not first):
        bot.__dict__['owner'] = bot.get_user(bot.owner_id)
        commands.Bot.owner = property(lambda x: x.__dict__['owner'])
        user = bot.owner
        first = True
        if (os.path.exists("updateout.log")):
            #info = await bot.application_info()
            tmp = open("updateout.log", "r").read()
            await user.send(f"```\n{tmp}```")
            os.remove("updateout.log")
            tmp = open("updateerr.log", "r").read()
            await user.send(f"```\n{tmp}```")
            os.remove("updateerr.log")
        if __name__ == '__main__':
            msg = "```diff\n"
            for cog in cgs:
                try:
                    print(f"attempt to load {cog}") 
                    added = True
                    try: bot.load_extension(cog)
                    except commands.ExtensionAlreadyLoaded:
                        added = False
                        msg += f"~{cog}\n"
                    if (added): msg += f"+{cog}\n"
                    print(f"loaded {cog}")
                except:
                    try: bot.unload_extension(cog)
                    except: pass
                    msg += f"-{cog} !!\n"
                    print("\n-----START {}".format(cog))
                    traceback.print_exc()
                    print("-----END   {}".format(cog))
            await user.send(msg + "```")
    try: redirloop.start()
    except: pass

@bot.event
async def on_command_error(ctx: commands.Context, error):
    if hasattr(ctx.command, 'on_error'):
        return

    ignored = (commands.CommandNotFound, commands.CommandOnCooldown)
    error = getattr(error, 'original', error)
    
    if isinstance(error, ignored): return
    name = ctx.command.root_parent.name if ctx.command.root_parent else ctx.command.name
    if isinstance(error, commands.DisabledCommand):
        return await ctx.send(f'{ctx.command} has been disabled.')
    elif isinstance(error, commands.NoPrivateMessage):
        try: return await ctx.message.author.send('This command cannot be used in Private Messages.')
        except: return
    elif isinstance(error, commands.UserInputError):
        return await ctx.invoke(bot.get_command("help"), name)
    elif isinstance(error, commands.MissingPermissions):
        return await ctx.send("You don't have sufficient permissions to run this.")

    if bot.owner == ctx.author:
        return traceback.print_exception(type(error), error, error.__traceback__, file=(sys.stdout if (not stable) else sys.stderr))
    try: await ctx.send(f"Something went wrong! We've DM'd the error to {bot.owner.mention}.")
    except: pass
    embed = discord.Embed(title=f"Error in {ctx.command}")
    st = '\n'.join(traceback.format_exception(type(error), error, error.__traceback__))
    embed.description = f"```py\n{st}\n```"
    embed.description += f"\nServer ID: {ctx.guild.id}\nUser ID: {ctx.author.id}\nMessage ID: {ctx.message.id}"
    try: return await bot.owner.send(embed=embed)
    except: pass

redirect = False
@tasks.loop(seconds=1, reconnect=True)
async def redirloop():
    global redirect, usrout, stable
    s = usrout.getvalue()
    if not s: return
    await bot.owner.send(f"```\n{usrout.getvalue()}```")
    usrout.close()
    usrout = StringIO()
    if stable:
        sys.stderr = usrout
    if redirect:
        sys.stdout = usrout

@bot.command(hidden=True)
@commands.is_owner()
async def redir(_unusedctx):
    global redirect, regout, usrout, stable
    if redirect:
        sys.stdout = regout
        redirect = False
    else:
        sys.stdout = usrout
        redirect = True

@bot.command(hidden=True, aliases=['r', 'rl'])
@commands.is_owner()
async def reload(ctx, *cogs):
    cogs = list(cogs)
    cgs = []
    msg = "```diff\n"
    for x in os.listdir("cogs"):
        if os.path.isfile("cogs/" + x):
            cgs.append("cogs.{}".format(x[:-3]))
    mcgs = cgs
    for cg in cogs:
        if "cogs." + cg not in cgs:
            cogs.remove(cg)
    if len(cogs) != 0:
        for x, y in enumerate(cogs):
            cogs[x] = "cogs." + y
        mcgs = cogs
    for cog in mcgs:
        try:
            print(f"attempt to load {cog}")
            added = False
            try: bot.unload_extension(cog)
            except commands.ExtensionNotLoaded: 
                added = True
            bot.load_extension(cog)
            if (added): msg += f"+{cog}\n"
            else: msg += f"~{cog}\n"
            print(f"loaded {cog}")
        except:
            try: bot.unload_extension(cog)
            except: pass
            msg += f"-{cog} !!\n"
            print("\n-----START {}".format(cog))
            traceback.print_exc()
            print("-----END   {}".format(cog))
    await ctx.send(msg + "```")

@bot.command(hidden=True)
@commands.is_owner()
async def unload(ctx, *cogs):
    cogs = list(cogs)
    cgs = []
    msg = "```diff\n"
    for x in os.listdir("cogs"):
        if os.path.isfile("cogs/" + x):
            cgs.append("cogs.{}".format(x[:-3]))
    mcgs = cgs
    for cg in cogs:
        if "cogs." + cg not in cgs:
            cogs.remove(cg)
    if len(cogs) != 0:
        for x, y in enumerate(cogs):
            cogs[x] = "cogs." + y
        mcgs = cogs
    for cog in mcgs:
        try:
            print(f"attempt to unload {cog}")
            removed = True
            try: bot.unload_extension(cog)
            except commands.ExtensionNotLoaded: 
                msg += f"~{cog}\n"
                removed = False
            if (removed): msg += f"-{cog}\n"
            print(f"unloaded {cog}")
        except:
            try: bot.unload_extension(cog)
            except: pass
            msg += f"-{cog} !!\n"
            print("\n-----START {}".format(cog))
            traceback.print_exc()
            print("-----END   {}".format(cog))
    await ctx.send(msg + "```")

@bot.command(hidden=True)
@commands.is_owner()
async def load(ctx, *cogs):
    cogs = list(cogs)
    cgs = []
    msg = "```diff\n"
    for x in os.listdir("cogs"):
        if os.path.isfile("cogs/" + x):
            cgs.append("cogs.{}".format(x[:-3]))
    mcgs = cgs
    for cg in cogs:
        if "cogs." + cg not in cgs:
            cogs.remove(cg)
    if len(cogs) != 0:
        for x, y in enumerate(cogs):
            cogs[x] = "cogs." + y
        mcgs = cogs
    for cog in mcgs:
        try:
            print(f"attempt to load {cog}") 
            added = True
            try: bot.load_extension(cog)
            except commands.ExtensionAlreadyLoaded:
                added = False
                msg += f"~{cog}\n"
            if (added): msg += f"+{cog}\n"
            print(f"loaded {cog}")
        except:
            try: bot.unload_extension(cog)
            except: pass
            msg += f"-{cog} !!\n"
            print("\n-----START {}".format(cog))
            traceback.print_exc()
            print("-----END   {}".format(cog))
    await ctx.send(msg + "```")

lastresult = None

@bot.command(name="eval", hidden=True)
@commands.is_owner()
async def _eval(ctx, *, evl):
    global lastresult
    env = {
        'bot': bot,
        'ctx': ctx,
        '_': lastresult
    }
    env.update(globals())
    if evl.startswith("```"):
        evl = evl[3:-3]
        if evl.startswith("py"):
            evl = evl[2:]
    evl = evl.strip()
    out = StringIO()

    funcwrap = f"async def evalfunc():\n{textwrap.indent(evl, '  ')}"

    try: exec(funcwrap, env)
    except Exception as err:
        return await ctx.send(f'```py\n{err.__class__.__name__}: {err}\n```')

    evalfunc = env['evalfunc']
    try:
        with contextlib.redirect_stdout(out):
            ret = await evalfunc()
    except:
        value = out.getvalue()
        return await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
    val = out.getvalue()
    if not ret:
        if val:
            return await ctx.send(f"```py\n{val}```")
        try: return await ctx.message.add_reaction('\u2705')
        except: pass
    else:
        lastresult = ret
        await ctx.send(f"```py\n{val}\n{ret}```")

@bot.command(name="c")
@commands.is_owner()
async def nomore(_unusedctx):
    await bot.close()

upd = False
@bot.command()
@commands.is_owner()
async def update(_unusedctx):
    global upd
    upd = True
    await bot.logout()
    print("we still work!")

bot.run(data['token'], bot=True, reconnect=True)

if (upd): 
    print("RUNNING UPDATER")
    pid = subprocess.Popen([sys.executable, "updater.py"] + sys.argv[1:], creationflags=0x8).pid
    print("it has run")