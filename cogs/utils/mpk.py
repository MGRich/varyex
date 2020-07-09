import discord, msgpack, os

class MPKManager:
    def __init__(self, direct, gid = None):
        self.path = f"config/{gid}/{direct}.mpk" if gid else f"config/{direct}.mpk"
        self.data: dict = {}
        if gid and not os.path.exists(f"config/{gid}/"):
            os.mkdir(f"config/{gid}/")
        if (not os.path.exists(self.path)): return
        with open(self.path, "rb") as f: self.data = msgpack.load(f)

    def save(self, d=None):
        if (not d): d = self.data
        with open(self.path, "wb") as f: msgpack.dump(d, f)

def testgiven(mpk, checks) -> bool:
    if type(mpk) == MPKManager:
        mpk = mpk.data
    for x in checks:
        if x not in mpk: return False
    return True 

def getmpm(typ, gid, runchecks: list = None, runtmp: list = None) -> MPKManager:
    if type(gid) == discord.Guild: gid = gid.id
    mpm = MPKManager(typ, gid)
    if runchecks:
        file = mpm.data
        i = 0
        for x in runchecks:
            if x not in file: file[x] = runtmp[i]
            i += 1  
    return mpm

