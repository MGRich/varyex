import discord, umsgpack, os, zlib, shutil
from copy import deepcopy

from typing import Union

class DefaultContainer:
    def __init__(self, data = None, parent = None):
        self._data: Union[list, dict] = data
        self._parent = parent

    @property
    def isblank(self):
        return self._data is None
    @property
    def _isdict(self):
        return isinstance(self._data, dict)

    def _settype(self, t):
        if not self._data: self._data = None
        elif self._data is not None: 
            if isinstance(t, str) and isinstance(self._data, list):
                raise ValueError("data is not a dict")
            if isinstance(t, (int, slice)) and self._isdict:
                raise ValueError("data is not a list")
            if not isinstance(t, (str, int, slice)):
                raise KeyError(f"invalid type ({type(t).__name__} is not str, int, or slice obj)")
            return
        if isinstance(t, str): 
            self._data = {}
            return 
        if isinstance(t, (int, slice)):
            self._data = []
            return
        raise KeyError(f"invalid type ({type(t).__name__} is not str, int, or slice obj)")

    def __bool__(self):
        return bool(self._data)
    def __len__(self):
        if not self._data: return 0
        return len(self._data)
    def __contains__(self, value):
        if not self._data: return False
        return self._data.__contains__(value)
    def __iter__(self):
        return iter(self._data or ())
    
    def __getitem__(self, key):
        self._settype(key)
        try: self._data[key]
        except KeyError: #no IndexError handling 
            self._data[key] = DefaultContainer(parent=self)
            return self._data[key]
        if isinstance(self._data[key], (dict, list)):
            self._data[key] = DefaultContainer(self._data[key], self)
        return self._data[key]
    def __setitem__(self, key, value):
        self._settype(key)
        if (isinstance(value, (dict, list))):
            self._data[key] = DefaultContainer(value, self)
            return
        if isinstance(value, tuple):
            try: self._data[key]
            except: self._data[key] = value[0]
            else: 
                if len(value) > 1: self._data[key] = value[1]
            return
        self._data[key] = value        
    def __delitem__(self, key):
        self._settype(key)
        del self._data[key]
    
    ##list funcs
    def append(self, item):
        self._settype(0)
        return self._data.append(item)
    def remove(self, item):
        self._settype(0)
        return self._data.remove(item)
    def index(self, item):
        self._settype(0)
        return self._data.index(item)
    ##dict funcs
    def update(self, d):
        self._settype("")
        return self._data.update(d)
    ##flexible
    def clear(self):
        if not self._data: return
        self._data.clear()
    def keys(self):
        #iffy on this one but i'll allow it?
        if not self._data: return []
        if self._isdict: return self._data.keys()
        return range(len(self._data))
    def items(self):
        #items can actually be used flexibily for both (after all, it's key-value, and list "keys" are ints)
        if not self._data: return []
        if self._isdict: return self._data.items()
        return zip(range(len(self._data)), self._data)
    def values(self):
        if not self._data: return []
        if self._isdict: return self._data.values()
        return self._data

    def copy(self):
        #when we copy, it is its own seperate branch
        #we will not recursively copy parents
        if not self._data: return DefaultContainer()
        return DefaultContainer(deepcopy(self._data)) 

    def save(self, d=None):
        if not self._parent: raise ValueError("no parent to fall back to")
        self._parent.save(d)
    
class MPKManager(DefaultContainer):
    def __init__(self, direct, gid = None):
        super().__init__()
        self.path = f"config/{gid}/{direct}.mpk" if gid else f"config/{direct}.mpk"
        self.vflags = 1 << 4
        if gid and not os.path.exists(f"config/{gid}/"):
            os.mkdir(f"config/{gid}/")
        if (not os.path.exists(self.path)): return
        try:
            with open(self.path, "rb") as f: self._data = umsgpack.load(f)
        except umsgpack.InsufficientDataException: pass #fuuck dude, we lost the data
        try: self.vflags = self._data["_"]
        except: pass
        else: del self._data["_"]
        self._filter(False)

    def _filter(self, s, d=None):
        if s: d = d or deepcopy(self._data)
        else: d = self._data
        if s or (self.vflags & 1):
            self._recur(s, d)
        if s: 
            d.update({"_": self.vflags}) #"_" key is reserved for version and flags
            return d

    def _recur(self, s, d):
        #pylint: disable=protected-access
        if isinstance(d, (dict, DefaultContainer)): t = d.items()
        else: t = zip(range(len(d)), d)
        for k, v in t:
            if v is None: d[k] = DefaultContainer() #migitate whenever it does this
            if isinstance(v, (dict, list)): 
                self._recur(s, d[k])
            elif isinstance(v, DefaultContainer):
                if s: d[k] = v._data or [] 
                self._recur(s, d[k])
            elif isinstance(v, (umsgpack.Ext if not s else str)):
                r = None
                if not s and (v.type == 0x10):
                    r = zlib.decompress(v.data).decode('utf-16')
                elif s and len(v) > 30:
                    r = umsgpack.Ext(0x10, zlib.compress(v.encode('utf-16'), 9))
                    self.vflags |= 1
                if r: d[k] = r

    def save(self, d=None):
        copied = True
        try: shutil.copyfile(self.path, self.path[:-4] + ".mbu")
        except: copied = False
        d = self._filter(True, d)
        try: 
            with open(self.path, "wb") as f: umsgpack.dump(d, f)
        except: shutil.copyfile(self.path[:-4] + ".mbu", self.path) #oh fuck.
        else: 
            if copied: os.unlink(self.path[:-4] + ".mbu") 

def testgiven(mpk, checks) -> bool:
    for x in checks:
        if x not in mpk: return False
    return True 

def getmpm(typ, gid) -> MPKManager:
    if isinstance(gid, discord.Guild): gid = gid.id
    mpm = MPKManager(typ, gid)
    return mpm

