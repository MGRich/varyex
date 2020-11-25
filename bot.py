import discord, subprocess
from discord.ext import commands
import cogs.utils.loophelper as loophelper

from cogs.utils.menus import Confirm
import cogs.utils.mpk as mpku

import logging, sys, traceback
from io import StringIO

import os, json
from pathlib import Path

import base64, lzma, umsgpack, github

import difflib, asyncio, textwrap, contextlib
from typing import List

from dotenv import load_dotenv
load_dotenv()

stable = False
if (len(sys.argv) > 1 and sys.argv[1] == "stable"): data = json.load(open("stable.json"))
else: data = json.load(open("info.json"))

stable = data['stable']
usrout = StringIO()
if stable:
    sys.stderr = usrout 

t = os.getenv('STOKEN' if stable else 'DTOKEN')

dlog = logging.getLogger('discord')
glog = logging.getLogger('bot')
dlog.setLevel('ERROR')
glog.setLevel('WARN')
for x, y in zip(dlog.handlers, glog.handlers):
    dlog.removeHandler(x)
    glog.removeHandler(y)
handler = logging.StreamHandler(usrout)
handler.setFormatter(logging.Formatter("[%(name)s - %(levelname)s] [%(filename)s/%(lineno)d] %(message)s"))
dlog.addHandler(handler)
glog.addHandler(handler)

def prefix(bot, message):
    prf = data['prefix'].copy()
    if message.guild:
        con = mpku.getmpm("misc", message.guild)
        if con['prefix']:
            prf.clear()
            prf.append(con['prefix'])
    
    users = bot.usermpm
    if users[str(message.author.id)]['prefix']:
        prf.insert(0, users[str(message.author.id)]['prefix'])
    return prf


class Main(commands.Bot):
    def __init__(self, data, userdata, lh, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = data
        self.usermpm = userdata
        self.loops: List[discord.ext.tasks.Loop] = []
        self.looptask = self.loop.create_task(self.loopcheckup())
        self.remove_command("help")

        self.owner = None
        lh.BOT = self

    async def loopcheckup(self):
        while True:
            try:   
                await asyncio.sleep(300) #every 5 minutes preform a loop checkup
                for loop in self.loops:
                    if not loop.next_iteration:
                        if '.' in loop.coro.__qualname__:
                            loop.start(bot.get_cog(loop.coro.__qualname__.split('.')[0]))
                        else: loop.start()
                        await self.owner.send(f"restarted loop `{loop.coro.__name__}`")
            except asyncio.CancelledError: break
            except: pass

    
#fetch cogs
cgs = []
for x in os.listdir("cogs"):
    if os.path.isfile("cogs/" + x):
        cgs.append(f"cogs.{x[:-3]}")
intents = discord.Intents.default()
intents.members = True 
intents.presences = True
bot = Main(data, mpku.getmpm('users', None), loophelper, command_prefix=prefix, owner_id=data['owner'], intents=intents)

first = False
print(bot.data)

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

@bot.event
async def on_ready():
    print(f'\n\nin as: {bot.user.name} - {bot.user.id}\non version: {discord.__version__}\n')
    global first
    if (not first):
        bot.owner = bot.get_user(bot.owner_id)
        user = bot.owner
        first = True
        if (os.path.exists("updateout.log")):
            #info = await bot.application_info()
            tmp = open("updateout.log").read()
            await user.send(f"```\n{tmp}```")
            os.remove("updateout.log")
            tmp = open("updateerr.log").read()
            await user.send(f"```\n{tmp}```")
            os.remove("updateerr.log")
        if __name__ == '__main__':
            msg = "```diff\n"
            for cog in cgs:
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
                    print("\n-----START {}".format(cog), file=sys.stderr)
                    traceback.print_exc()
                    print("-----END   {}".format(cog), file=sys.stderr)
            await user.send(msg + "```")
    await bot.get_command("loop").callback(user, "start")

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
    if isinstance(error, commands.MissingPermissions):
        return await ctx.send("You don't have sufficient permissions to run this.")
    if isinstance(error, commands.BotMissingPermissions):
        return await ctx.send("I don't have sufficient permissions to run this.")
    if isinstance(error, asyncio.TimeoutError):
        return await ctx.send("Prompt above timed out. Please redo the command.")
    #NOW we start being linient
    errored.append([ctx.message.id, 0])
    if isinstance(error, commands.CommandNotFound): return
    if isinstance(error, commands.UserInputError):
        return await ctx.invoke(bot.get_command("help"), ctx.command.root_parent.name if ctx.command.root_parent else ctx.command.name)

    if bot.owner == ctx.author:
        return traceback.print_exception(type(error), error, error.__traceback__, file=(sys.stdout if (not stable) else sys.stderr))
    try: await ctx.send(f"Something went wrong! We've DM'd the error to {bot.owner.mention}.")
    except: pass
    embed = discord.Embed(title=f"Error in {ctx.command}")
    st = '\n'.join(traceback.format_exception(type(error), error, error.__traceback__))
    embed.description = f"```py\n{st}\n```"
    embed.description += f"User ID: `{ctx.author.id}` {ctx.author.mention}\nChannel ID: `{ctx.channel.id}` {ctx.channel.mention if isinstance(ctx.channel, discord.TextChannel) else '(DM)'}"
    try: return await bot.owner.send(embed=embed)
    except: pass

iteration = 0
count = 181
hourcounter = 3600 - 30
@loophelper.trackedloop(seconds=1, reconnect=True)
async def mainloop():
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
            for y in tuple(x.members for x in bot.guilds):
                c += len([z for z in y if not z.bot]) 
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
                if not (n := p.parent.name) in fd: fd[n] = {}
                fd[n][p.stem] = open(p.resolve(), "rb").read()
            f = {'varyexbackup': github.InputFileContent(content=base64.a85encode(lzma.compress(umsgpack.packb(fd), format=lzma.FORMAT_ALONE)).decode('ascii'))}
            github.Github(os.getenv('KEY')).get_gist(os.getenv('GIST')).edit(files=f)
            glog.debug("backed up configs")
            hourcounter = 0
    ####REDIRECT
    global usrout
    if not (s := usrout.getvalue()): return
    usrout.close()
    usrout = StringIO()
    for x, y in zip(dlog.handlers, glog.handlers):
        dlog.removeHandler(x)
        glog.removeHandler(y)
    handler.setStream(usrout)
    dlog.addHandler(handler)
    glog.addHandler(handler)
    await bot.owner.send(f"```\n{s}```")
    if stable:
        sys.stderr = usrout

upd = False
@bot.command(aliases = ('get',))
@commands.is_owner()
async def retrieve(ctx):
    global upd
    c = Confirm("you sure? thisll backup config folder and run update")
    if not (await c.prompt(ctx)): return
    await ctx.send("restarting")
    await bot.logout()
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
    upd = True



@bot.event
async def on_message_edit(before, after):
    global errored
    if (before.content != after.content) and (after.id in {x[0] for x in errored}):
        await bot.process_commands(after)
        errored = [x for x in errored if x[0] != after.id]

@bot.command(hidden=True)
@commands.is_owner()
async def redir(ctx, level):
    #pylint: disable=protected-access
    level = difflib.get_close_matches(level.upper(), list(logging._nameToLevel))[0]
    glog.setLevel(level)
    await ctx.send(f"set level to {level}")

@bot.command(hidden=True, aliases=('r', 'rl'))
@commands.is_owner()
async def reload(ctx, *cogs):
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
            print("\n-----START {}".format(cog), file=sys.stderr)
            traceback.print_exc()
            print("-----END   {}".format(cog), file=sys.stderr)
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
            print("\n-----START {}".format(cog), file=sys.stderr)
            traceback.print_exc()
            print("-----END   {}".format(cog), file=sys.stderr)
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
            print("\n-----START {}".format(cog), file=sys.stderr)
            traceback.print_exc()
            print("-----END   {}".format(cog), file=sys.stderr)
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
    await bot.logout()

bot.run(t, bot=True, reconnect=True)

if (upd): 
    pid = subprocess.Popen([sys.executable, "updater.py"] + sys.argv[1:], creationflags=0x8).pid
