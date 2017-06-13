# modification of python bisect to accept a key argument

def bisect_right(a, x, key=None):
    if key is None:
        key = lambda o: o
    lo = 0
    hi = len(a)
    while lo < hi:
        mid = (lo+hi)//2
        if x < key(a[mid]): hi = mid
        else: lo = mid+1
    return lo

def bisect_left(a, x, key=None):
    if key is None:
        key = lambda o: o
    lo = 0
    hi = len(a)
    while lo < hi:
        mid = (lo+hi)//2
        if key(a[mid]) < x: lo = mid+1
        else: hi = mid
    return lo

def index(a, x):
    'Locate the leftmost index exactly equal to x'
    i = bisect_left(a, x)
    if i != len(a) and a[i] == x:
        return i

def find_lt(a, x, key=None):
    'Find rightmost index less than x'
    i = bisect_left(a, x, key=key)
    if i:
        return i-1

def find_le(a, x, key=None):
    'Find rightmost index less than or equal to x'
    i = bisect_right(a, x, key=key)
    if i:
        return i-1

def find_gt(a, x, key=None):
    'Find leftmost index greater than x'
    i = bisect_right(a, x, key=key)
    if i != len(a):
        return i

def find_ge(a, x, key=None):
    'Find leftmost index greater than or equal to x'
    i = bisect_left(a, x, key=key)
    if i != len(a):
        return i