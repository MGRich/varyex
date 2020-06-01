import msgpack, os

class MPKManager:
    def __init__(self, direct, *gid):
        self.path = f"config/{gid[0]}/{direct}.mpk" if gid else f"config/{direct}.mpk"
        if gid and not os.path.exists(f"config/{gid[0]}/"):
            os.mkdir(f"config/{gid[0]}/")
        if (not os.path.exists(self.path)):
            with open(self.path, "wb") as f: msgpack.dump({}, f)
        self.data = self.load()
        #print(f"JSON MANAGER OPEN {self.path} ----{self.data}----")

    def load(self):
        with open(self.path, "rb") as f: return msgpack.load(f)

    def save(self, dict=None):
        if (not dict): dict = self.data
        with open(self.path, "wb") as f: msgpack.dump(dict, f)
        #print(f"MANAGER SAVE {self.path} ----{dict}----")
