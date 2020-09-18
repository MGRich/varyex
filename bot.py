import discord, traceback, json, os, sys, subprocess, textwrap, contextlib, base64, lzma, msgpack, github
from discord.ext import commands, tasks
from io import StringIO
import cogs.utils.mpk as mpku
from pathlib import Path
from cogs.utils.menus import Confirm

stable = False
if (len(sys.argv) > 1 and sys.argv[1] == "stable"): data = json.load(open("stable.json"))
else: data = json.load(open("info.json"))

stable = data['stable']
#stable = True
usrout = StringIO()
if stable:
    sys.stderr = usrout 
regout = sys.stdout

def prefix(_bot, message):
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

errored = []

@bot.event
async def on_command_error(ctx: commands.Context, error):
    if hasattr(ctx.command, 'on_error'):
        return

    ignored = (commands.CommandOnCooldown, commands.NotOwner)
    error = getattr(error, 'original', error)
    if isinstance(error, ignored): return
    #if isinstance(error, commands.DisabledCommand):
    #    return await ctx.send(f'{ctx.command} has been disabled.')
    if isinstance(error, commands.NoPrivateMessage):
        try: await ctx.message.author.send('This command cannot be used in Private Messages.')
        except: pass
        return
    #NOW we start being linient
    errored.append([ctx.message.id, 0])
    if isinstance(error, commands.CommandNotFound): return
    if isinstance(error, commands.UserInputError):
        return await ctx.invoke(bot.get_command("help"), ctx.command.root_parent.name if ctx.command.root_parent else ctx.command.name)
    if isinstance(error, commands.MissingPermissions):
        return await ctx.send("You don't have sufficient permissions to run this.")

    if bot.owner == ctx.author:
        return traceback.print_exception(type(error), error, error.__traceback__, file=(sys.stdout if (not stable) else sys.stderr))
    try: await ctx.send(f"Something went wrong! We've DM'd the error to {bot.owner.mention}.")
    except: pass
    embed = discord.Embed(title=f"Error in {ctx.command}")
    st = '\n'.join(traceback.format_exception(type(error), error, error.__traceback__))
    embed.description = f"```py\n{st}\n```"
    embed.description += f"\nServer ID: `{ctx.guild.id}`\nUser ID: `{ctx.author.id}`\nMessage ID: `{ctx.message.id}``"
    try: return await bot.owner.send(embed=embed)
    except: pass

redirect = False
iteration = 0
count = 181
hourcounter = 3600 - 10 
@tasks.loop(seconds=1, reconnect=True)
async def redirloop(): #also the global loop
    ####EDIT LOOP
    global errored
    for i in range(len(errored)):
        errored[i][1] += 1
        if (errored[i][1] > 3): errored[i][0] = 0
    errored = [x for x in errored if x[0]]
    ####STATUS LOOP
    global count, iteration
    count += 1
    last = iteration
    if count > 180:
        count = 0
        iteration += 1
        iteration %= 3
    if last != iteration:
        if iteration == 0: st = f"{len(bot.guilds)} servers"
        elif iteration == 1:
            c = 0
            for x in [x.members for x in bot.guilds]:
                c += len(x) 
            st = f"{c} members"
        elif iteration == 2: st = f"v{data['version']}"
        await bot.change_presence(activity=discord.Activity(name=f"{data['status'].replace('[ch]', st)}", type=0))
    ####BACKUP LOOP
    global hourcounter
    if stable:
        hourcounter += 1
        if hourcounter >= 3600:
            fd = {}
            for p in Path("config").rglob('*.mpk'):
                n = p.parent.name
                if not n in fd: fd[n] = {}
                fd[n][p.stem] = open(p.resolve(), "rb").read()
            f = {'varyexbackup': github.InputFileContent(content=base64.a85encode(lzma.compress(msgpack.packb(fd), format=lzma.FORMAT_ALONE)).decode('ascii'))}
            github.Github(data['key']).get_gist(data['gist']).edit(files=f)
            print("backed up configs")
            hourcounter = 0
    ####REDIRECT
    global redirect, usrout
    s = usrout.getvalue()
    if not s: return
    await bot.owner.send(f"```\n{usrout.getvalue()}```")
    usrout.close()
    usrout = StringIO()
    if stable:
        sys.stderr = usrout
    if redirect:
        sys.stdout = usrout

upd = False
@bot.command()
@commands.is_owner()
async def retrieve(ctx):
    global upd
    c = Confirm("you sure? thisll backup config folder and run update")
    a = await c.prompt(ctx)
    if not a: return
    await bot.logout()
    try: Path("config").rename("configold")
    except: pass
    Path("config").mkdir(exist_ok=True)
    c = github.Github(data['key']).get_gist(data['gist']).files['varyexbackup'].content
    result = msgpack.unpackb(lzma.decompress(base64.a85decode(c), format=lzma.FORMAT_ALONE))
    if ('config' in result):
        for x in result['config']:
            open(f"config/{x}.mpk", "wb").write(result['config'][x])
            print(f"config/{x}.mpk")
        del result['config']
    for x in result:
        for y in result[x]:
            Path(f"config/{x}").mkdir(exist_ok=True)
            open(f"config/{x}/{y}.mpk", "wb").write(result[x][y])
            print(f"config/{x}/{y}.mpk")
    upd = True



@bot.event
async def on_message_edit(before, after):
    global errored
    if (before.content != after.content) and (after.id in [x[0] for x in errored]):
        await bot.process_commands(after)
        errored = [x for x in errored if x[0] != after.id]

@bot.command(hidden=True)
@commands.is_owner()
async def redir(_ctx):
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
async def nomore(_ctx):
    await bot.close()

@bot.command()
@commands.is_owner()
async def update(_ctx):
    global upd
    upd = True
    await bot.logout()
    print("we still work!")

bot.run(data['token'], bot=True, reconnect=True)

if (upd): 
    print("RUNNING UPDATER")
    pid = subprocess.Popen([sys.executable, "updater.py"] + sys.argv[1:], creationflags=0x8).pid
    print("it has run")