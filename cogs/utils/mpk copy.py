import discord, msgpack, os, copy

opened = {}
class MPKManager:
    def __init__(self, direct, gid = None):
        self.dictstr = f"{direct}/{gid}"
        self.deleted = False
        opened[self.dictstr] = [self, 1]
        self.path = f"config/{gid}/{direct}.mpk" if gid else f"config/{direct}.mpk"
        self.data: dict = {}
        if gid and not os.path.exists(f"config/{gid}/"):
            os.mkdir(f"config/{gid}/")
        if (not os.path.exists(self.path)): return
        with open(self.path, "rb") as f: self.data = msgpack.load(f)

    def __del__(self):
        if not self.deleted:
            try:
                opened[self.dictstr][1] -= 1   
                if not opened[self.dictstr][1]:
                    del opened[self.dictstr]
                    self.deleted = True
                    self.data = None
            except TypeError: 
                self.deleted = True
                self.data = None #????????
    
    def getanddel(self):
        r = copy.copy(self.data) #use as a fetch
        opened[self.dictstr][1] -= 1   
        if not opened[self.dictstr][1]:
            del opened[self.dictstr]
            self.deleted = True
            self.data = None #save some memory while we're at it
        return r

    def save(self, sub = True):
        with open(self.path, "wb") as f: msgpack.dump(self.data, f)
        if sub:
            opened[self.dictstr][1] -= 1
            if not opened[self.dictstr][1]:
                del opened[self.dictstr]
                self.deleted = True
                self.data = None

def testgiven(mpk, checks) -> bool:
    if type(mpk) == MPKManager:
        mpk = mpk.data
    for x in checks:
        try: mpk[x]
        except: return False
    return True 

def getmpm(typ, gid, runchecks: list = None, runtmp: list = None) -> MPKManager:
    if type(gid) == discord.Guild: gid = gid.id
    dictstr = f"{typ}/{gid}"
    if (dictstr in opened):
        opened[dictstr][1] += 1
        mpm = opened[dictstr][0]
    else: mpm = MPKManager(typ, gid)
    if runchecks:
        file = mpm.data
        i = 0
        for x in runchecks:
            try: file[x]
            except: file[x] = runtmp[i]
            i += 1  
    print(opened)
    return mpm

