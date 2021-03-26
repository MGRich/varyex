import json, requests, os, time
from dotenv import load_dotenv
load_dotenv()

STABLE = True
if not STABLE: url = "https://discord.com/api/v8/applications/619011194141016064/commands"
else: url = "https://discord.com/api/v8/applications/619009622593896478/commands"

t = os.getenv('STOKEN' if STABLE else 'DTOKEN')
if t is None: exit()

j = json.load(open("slashlist.json"))
headers = {"Authorization": f"Bot {t}"}
print(headers)

for x in j:
    r = requests.post(url, json=x, headers=headers)
    print(r.status_code)
    if r.status_code == 429:
        print("ratelimit", r.json()['retry_after'])
        time.sleep(r.json()['retry_after'] + 2)
        r = requests.post(url, json=x, headers=headers)
    if r.status_code not in {200, 201}:
        print(f"{x['name']} failed: {r.text}")
    else:
        print(f"{x['name']} registered")
