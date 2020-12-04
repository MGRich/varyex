import subprocess, sys
while True:
    r = subprocess.run([sys.executable, 'bot.py', 'stable'], stdout=sys.stdout, stderr=sys.stderr, check=False)
    print(r.returncode)
    if not r.returncode: break