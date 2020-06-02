import time, subprocess, sys, os
print("hello")
time.sleep(1)
try:
    os.remove("updateout.log")
    os.remove("updateerr.log")
except FileNotFoundError: pass
stout = open("updateout.log", "w+")
stdr = open("updateerr.log", "w+")
subprocess.Popen(['git', 'checkout', 'master'], stdout=stout, stderr=stdr, creationflags=subprocess.CREATE_NO_WINDOW)
subprocess.Popen(['git', 'pull'], stdout=stout, stderr=stdr, creationflags=subprocess.CREATE_NO_WINDOW)
stout.close()
stdr.close()
pid = subprocess.Popen([sys.executable, "bot.py"] + sys.argv[1:], creationflags=0x10).pid