#from datetime import datetime

def getord(num):
    st = "th"
    if ((num % 100) > 10 and (num % 100) < 15): return str(num) + st
    n = num % 10
    if not (n in {1, 2, 3}): return str(num) + st
    if   (n == 1): st = st.replace("th", "st")
    elif (n == 2): st = st.replace("th", "nd")
    elif (n == 3): st = st.replace("th", "rd")
    return str(num) + st