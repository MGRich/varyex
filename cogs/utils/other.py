import humanize
from datetime import timedelta


def getord(num):
    st = "th"
    if ((num % 100) > 10 and (num % 100) < 15): return str(num) + st
    n = num % 10
    if not (n in {1, 2, 3}): return str(num) + st
    if   (n == 1): st = "st"
    elif (n == 2): st = "nd"
    elif (n == 3): st = "rd"
    return str(num) + st

def timeint(num, minutes=False):
    return humanize.naturaldelta(timedelta(seconds=(num * (60 if minutes else 1))))