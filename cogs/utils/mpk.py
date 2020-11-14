import discord, umsgpack, os, zlib
from copy import copy


class MPKManager:
    def __init__(self, direct, gid = None, *, raw = False):
        self.path = f"config/{gid}/{direct}.mpk" if gid else f"config/{direct}.mpk"
        self.data: dict = {}
        self.vflags = 1 << 4
        if gid and not os.path.exists(f"config/{gid}/"):
            os.mkdir(f"config/{gid}/")
        if (not os.path.exists(self.path)): return
        with open(self.path, "rb") as f: self.data = umsgpack.load(f)
        try: self.vflags = self.data["_"]
        except: pass
        else: del self.data["_"]
        if not raw: self._filter(False)

    def _filter(self, s, d=None):
        if s: d = d or copy(self.data)
        else: d = self.data
        if s or (self.vflags & 1):
            self._recur(s, d)
        if s: 
            d.update({"_": self.vflags}) #"_" key is reserved for version and flags
            return d

    def _recur(self, s, d):
        if isinstance(d, dict): t = d.items()
        else: t = zip(range(len(d)), d)
        for k, v in t:
            if isinstance(v, (dict, list)): self._recur(s, d[k])
            elif isinstance(v, (umsgpack.Ext if not s else str)):
                r = None
                if not s and (v.type == 0x10):
                    r = zlib.decompress(v.data).decode('utf-16')
                elif s and len(v) > 30:
                    r = umsgpack.Ext(0x10, zlib.compress(v.encode('utf-16'), 9))
                    self.vflags |= 1
                if r: d[k] = r

    def getanddel(self):
        return self.data
    
    def save(self, d=None):
        d = self._filter(True, d)
        with open(self.path, "wb") as f: umsgpack.dump(d, f)

def testgiven(mpk, checks) -> bool:
    if isinstance(mpk, MPKManager):
        mpk = mpk.data
    for x in checks:
        if x not in mpk: return False
    return True 

def getmpm(typ, gid, runchecks: list = None, runtmp: list = None, *, filter = False) -> MPKManager:
    if isinstance(gid, discord.Guild): gid = gid.id
    mpm = MPKManager(typ, gid, raw=(not filter))
    if runchecks:
        file = mpm.data
        i = 0
        for x in runchecks:
            if x not in file: file[x] = runtmp[i]
            i += 1  
    return mpm

