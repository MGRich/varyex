import discord
from discord.http import Route
Route.BASE = 'https://discord.com/api/v8'
from discord.ext import commands
import imports.loophelper as loophelper

from imports.menus import Confirm
import imports.profiles #for ext
import imports.mpk as mpku

from logging import _nameToLevel as levels
import logging
from traceback import format_exc
import sys
from io import StringIO
from subprocess import run as subprun
from shutil import rmtree

import os
from pathlib import Path

import base64, lzma, umsgpack, github

import difflib, textwrap, contextlib

from json import load as jload
from dotenv import load_dotenv
load_dotenv()

from imports.main import InteractionsContext, Main, InteractionsContext
#override discord


from website.main import run_app

try:    data = jload(open("stable.json" if sys.argv[1] == "stable" else "info.json"))
except: data = jload(open("info.json"))

stable = data['stable']

if stable: usrout = StringIO()
else: usrout = sys.stderr

t = os.getenv('STOKEN' if stable else 'DTOKEN')

dlog = logging.getLogger('discord')
glog = logging.getLogger('bot')
dlog.setLevel('ERROR')
glog.setLevel('WARN')

for x in dlog.handlers: 
    dlog.removeHandler(x)
for x in glog.handlers:
    glog.removeHandler(x)

handler = logging.StreamHandler(usrout)
handler.setFormatter(logging.Formatter(
    "[%(name)s - %(levelname)s] [%(filename)s/%(lineno)d] %(message)s"))
dlog.addHandler(handler)
glog.addHandler(handler)


if stable:
    sys.stderr = usrout

i = discord.Intents.default()
i.members = True
bot = Main(data, mpku.getmpm('users', None), owner_id=data['owner'], intents=i)
import imports.globals as g
g.BOT = bot

first = False
print(bot.data)

@bot.event
async def on_ready():
    print(
        f'\n\nin as: {bot.user.name} - {bot.user.id}\non version: {discord.__version__}\n')
    global first
    if (not first):
        bot.owner = bot.get_user(bot.owner_id)
        user = bot.owner
        first = True

        if (os.path.exists("updateout.log")):
            await user.send(f"```\n{open('updateout.log').read()}```")
            os.remove("updateout.log")
            await user.send(f"```\n{open('updateerr.log').read()}```")
            os.remove("updateerr.log")

        if __name__ == '__main__':
            msg = "```diff\n"
            for cog in (f"cogs.{x[:-3]}" for x in os.listdir("cogs") if os.path.isfile("cogs/" + x)):
                try:
                    glog.debug(f"attempt to load {cog}")
                    added = True
                    try:
                        bot.load_extension(cog)
                    except commands.ExtensionAlreadyLoaded:
                        added = False
                        msg += f"~{cog}\n"
                    if (added):
                        msg += f"+{cog}\n"
                    glog.debug(f"loaded {cog}")
                except:
                    try: bot.unload_extension(cog)
                    except:
                        pass
                    msg += f"-{cog} !!\n"
                    glog.warn(f"\nERROR FOR {cog}:\n{format_exc()}")                    
            await user.send(msg + "```")
    await bot.get_command("loop").callback(user, "start")
    bot.autostart = True

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.interactions.InteractionType.application_command: return
    channel: discord.TextChannel = interaction.channel or await interaction.user.create_dm()
    cmddata = interaction.data
    out = [cmddata['name']]
    if cmddata['name'] in {"warncfg", "profilecfg"}:
        out[0] = cmddata['name'].split("cfg")[0]
        out.append('cfg' if out[0] == "warn" else 'edit')
            
    wasstring = False
    def appender(option):
        nonlocal wasstring
        if option['type'] == 3:
            out.append(f"\"{option['value']}\"")
            wasstring = True
        else:
            out.append(str(option['value']))
            wasstring = False

    for x in cmddata.get('options', []):
        if x['type'] in {1, 2}:
            out.append(x['name'])
            for y in x.get('options', []):
                if y['type'] == 1:
                    out.append(y['name'])
                    for z in y.get('options', []):
                        appender(z)
                else: appender(y)
        else: appender(x)

    if wasstring:
        out[-1] = out[-1][1:-1]


    fakemsg = discord.Message(state=interaction._state, channel=channel, data=
        {'content': '', 'id': interaction.id, 'attachments': [], 'embeds': [], 
        'pinned': False, 'mention_everyone': False, 'tts': False, 'type': 0, 'edited_timestamp': None})
    fakemsg.author = interaction.user

    out = (await bot.get_prefix(fakemsg))[0] + ' '.join(out)
    fakemsg.content = out

    ctx = await bot.get_context(fakemsg, cls=InteractionsContext)
    ctx.inter = interaction
    await ctx.trigger_typing()
    if not ctx.command:
        return await ctx.send("That command either doesn't exist or isn't loaded!")
    if not isinstance(ctx.channel, discord.abc.User) and not ctx.channel.permissions_for(ctx.me).send_messages:
        return await ctx.send("I can't normally send messages in here!", delete_after=3)
    await bot.invoke(ctx)

@bot.command(aliases=('loop',))
@commands.is_owner()
async def loops(ctx, *loopnames):
    r = "```diff\n"
    action = ""
    llist = bot.loops
    if loopnames:
        action = loopnames[0]
        if action == "auto":
            if not bot.looptask or bot.looptask.cancelled(): bot.looptask = bot.loop.create_task(bot.loopcheckup())
            else: 
                bot.looptask.cancel()
                bot.looptask = None
            return await ctx.send("on" if bot.looptask else "off")

        loopnames = loopnames[1:]
        llist = [x for x in bot.loops if x.coro.__name__ in loopnames] or llist
    if (not action):
        for loop in bot.loops:
            r += f"{'~' if loop.next_iteration else '-'}{loop.coro.__name__}\n"
        return await ctx.send(r + "```")
    if action in {'r', 'restart', 'start'}:
        for loop in llist:
            use = loop.start if action == 'start' else loop.restart
            before = bool(loop.next_iteration)
            try:
                if '.' in loop.coro.__qualname__:
                    use(bot.get_cog(loop.coro.__qualname__.split('.')[0]))
                else: use()
            except RuntimeError: pass
            r += f"{'~' if before else '+'}{loop.coro.__name__}\n"
    elif action in {'c', 'cancel', 'stop'}:
        for loop in llist:
            before = bool(loop.next_iteration)
            loop.cancel()
            r += f"{'-' if before else '~'}{loop.coro.__name__}\n"
    elif action == 'start':
        for loop in llist:
            before = bool(loop.next_iteration)
            if '.' in loop.coro.__qualname__:
                loop.start(bot.get_cog(loop.coro.__qualname__.split('.')[0]))
            else: loop.start()
            r += f"{'~' if before else '+'}{loop.coro.__name__}\n"
    else: return await ctx.send(f"unknown action `{action}`")
    return await ctx.send(r + "```")

iteration = 0
count = 181
hourcounter = 3600 - 30
@loophelper.trackedloop(seconds=1, reconnect=True)
async def mainloop():
    try: await mlcoro()
    except Exception as e:
        glog.error(f"error in mainloop:\n{e}\n{format_exc()}")

async def mlcoro():
    ####EDIT LOOP
    for i in range(len(bot.errlist)):
        bot.errlist[i][1] += 1
        if (bot.errlist[i][1] > 3):
            bot.errlist[i][0] = 0
    bot.errlist = [x for x in bot.errlist if x[0]]
    ####STATUS LOOP
    global count, iteration
    count += 1
    last = iteration
    if count > 180:
        count = 0
        iteration += 1
        iteration %= 3
    if last != iteration:
        if iteration == 0:
            st = f"{len(bot.guilds)} servers"
        elif iteration == 1:
            c = 0
            for y in tuple(x.members for x in bot.guilds):
                c += len([z for z in y if not z.bot])
            st = f"{c} members"
        elif iteration == 2:
            st = f"v{data['version']}"
        await bot.change_presence(activity=discord.Activity(name=f"{data['status'].replace('[ch]', st)}", type=0))
    ####BACKUP LOOP
    global hourcounter
    if stable:
        hourcounter += 1
        if hourcounter >= 3600:
            fd = {}
            #bcks = [x.resolve() for x in Path("config").rglob('*.mbu')]
            for p in Path("config").rglob('*.mpk'):
                if not (n := p.parent.name) in fd:
                    fd[n] = {}
                read = p.resolve()
                #if (read[:-3] + "mbu") in bcks:
                #    read = read[:-3] + "mbu"
                try:
                    fd[n][p.stem] = open(read, "rb").read()
                except FileNotFoundError:
                    fd[n][p.stem] = open(p.resolve(), "rb").read()
            f = {'varyexbackup': github.InputFileContent(content=base64.a85encode(
                lzma.compress(umsgpack.packb(fd), format=lzma.FORMAT_ALONE)).decode('ascii'))}
            github.Github(os.getenv('KEY')).get_gist(
                os.getenv('GIST')).edit(files=f)
            glog.debug("backed up configs")
            hourcounter = 0
    ####REDIRECT
    if not stable: return
    if not (s := usrout.getvalue()):
        return
    usrout.truncate(0)
    usrout.seek(0)
    await bot.owner.send(f"```\n{s}```")

upd = False
@bot.command(aliases = ('get',))
@commands.is_owner()
async def retrieve(ctx):
    global upd
    c = Confirm("you sure? thisll backup config folder and run update")
    if not (await c.prompt(ctx)): return
    await ctx.send("restarting")
    await bot.close()
    upd = True
    try: Path("config").rename("configold")
    except: pass
    Path("config").mkdir(exist_ok=True)
    c = github.Github(os.getenv('KEY')).get_gist(os.getenv('GIST')).files['varyexbackup'].content
    result = umsgpack.unpackb(lzma.decompress(base64.a85decode(c), format=lzma.FORMAT_ALONE))
    if ('config' in result):
        for x in result['config']:
            open(f"config/{x}.mpk", "wb").write(result['config'][x])
            glog.debug(f"config/{x}.mpk")
        del result['config']
    for x in result:
        for y in result[x]:
            Path(f"config/{x}").mkdir(exist_ok=True)
            open(f"config/{x}/{y}.mpk", "wb").write(result[x][y])
            glog.debug(f"config/{x}/{y}.mpk")

@bot.command(hidden=True)
@commands.is_owner()
async def redir(ctx, level):
    #pylint: disable=protected-access
    level = difflib.get_close_matches(level.upper(), list(levels))[0]
    glog.setLevel(level)
    await ctx.send(f"set level to {level}")

#@bot.command(hidden=True, aliases=('r', 'rl', 'load', 'unload'))
@bot.command(aliases=('r',))
@commands.is_owner()
async def reload(ctx: commands.Context, *cogs):
    #method = ('r', 'l', 'u').index(ctx.invoked_with[x])
    cogs = set(cogs)
    cgs = set()
    msg = "```diff\n"
    for x in os.listdir("cogs"):
        if os.path.isfile("cogs/" + x):
            cgs.add("cogs.{}".format(x[:-3]))
    mcgs = cgs
    for cg in cogs:
        if "cogs." + cg not in cgs:
            cogs.remove(cg)
    if cogs:
        mcgs = set()
        for x in cogs:
            mcgs.add("cogs." + x)
    for cog in mcgs:
        try:
            glog.debug(f"attempt to load {cog}")
            added = False
            try: bot.unload_extension(cog)
            except commands.ExtensionNotLoaded: 
                added = True
            bot.load_extension(cog)
            if (added): msg += f"+{cog}\n"
            else: msg += f"~{cog}\n"
            glog.debug(f"loaded {cog}")
        except:
            try: bot.unload_extension(cog)
            except: pass
            msg += f"-{cog} !!\n"
            glog.warn(f"\nERROR FOR {cog}:\n{format_exc()}")                    
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
            glog.debug(f"attempt to unload {cog}")
            removed = True
            try: bot.unload_extension(cog)
            except commands.ExtensionNotLoaded: 
                msg += f"~{cog}\n"
                removed = False
            if (removed): msg += f"-{cog}\n"
            glog.debug(f"unloaded {cog}")
        except:
            try: bot.unload_extension(cog)
            except: pass
            msg += f"-{cog} !!\n"
            glog.warn(f"\nERROR FOR {cog}:\n{format_exc()}")                    
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
            glog.debug(f"attempt to load {cog}") 
            added = True
            try: bot.load_extension(cog)
            except commands.ExtensionAlreadyLoaded:
                added = False
                msg += f"~{cog}\n"
            if (added): msg += f"+{cog}\n"
            glog.debug(f"loaded {cog}")
        except:
            try: bot.unload_extension(cog)
            except: pass
            msg += f"-{cog} !!\n"
            glog.warn(f"\nERROR FOR {cog}:\n{format_exc()}")                    
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
        return await ctx.send(f'```py\n{value}{format_exc()}\n```')
    val = out.getvalue()
    if not ret:
        if val is not None:
            return await ctx.send(f"```py\n{val}```")
        try: return await ctx.message.add_reaction('\u2705')
        except: pass
    else:
        lastresult = ret
        await ctx.send(f"```py\n{val}\n{ret}```")

@bot.command(name="c")
@commands.is_owner()
async def nomore(ctx):
    if (stable):
        if not await Confirm("Bitch!").prompt(ctx): return
    await bot.close()

@bot.command()
@commands.is_owner()
async def update(ctx):
    global upd
    upd = True
    await ctx.send("updating")
    await bot.close()


@bot.command()
@commands.is_owner()
async def cmd(ctx, *, command):
    res = subprun(command, shell=True, check=False, capture_output=True)
    val = (res.stdout.decode('utf-8') if res.stdout else "") + \
        (("\n----stderr----\n" + res.stderr.decode('utf-8')) if res.stderr else "")
    if val is not None: return await ctx.send(f"```\n{val}```")
    try: return await ctx.message.add_reaction('\u2705')
    except:
        pass


import threading
from website.main import run_app, get_runner
th = threading.Thread(target=run_app, args=(os.getenv("WEBHOST"), int(os.getenv("WEBPORT")), get_runner()), daemon=True)
th.start()
bot.run(t, reconnect=True)

if (upd): 
    stout = open("updateout.log", "w")
    stdr = open("updateerr.log", "w")
    sys.stdout = stout
    sys.stderr = stdr
    subprun(['git', 'pull'], stdout=stout, stderr=stdr, check=False,
            creationflags=0x08000000 * (sys.platform == 'win32'))
    rmtree("cogs/__pycache__")
    rmtree("imports/__pycache__")
    stout.close()
    stdr.close()
    sys.exit(1)
sys.exit(0)    
