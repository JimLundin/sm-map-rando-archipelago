"""Report ROM byte ranges written by IPS patches and overlaps between two patch sets."""
import sys, glob, os

def ips_ranges(path):
    data = open(path, 'rb').read()
    assert data[:5] == b'PATCH', path
    i = 5
    out = []
    while True:
        off = data[i:i+3]
        if off == b'EOF':
            break
        o = int.from_bytes(off, 'big'); i += 3
        size = int.from_bytes(data[i:i+2], 'big'); i += 2
        if size == 0:
            rle = int.from_bytes(data[i:i+2], 'big'); i += 3
            out.append((o, o + rle))
        else:
            out.append((o, o + size)); i += size
    return out

def pc2snes(a):
    return ((a // 0x8000) | 0x80) << 16 | (a % 0x8000) | 0x8000

def merge(rs):
    rs = sorted(rs)
    m = []
    for s, e in rs:
        if m and s <= m[-1][1]:
            m[-1] = (m[-1][0], max(m[-1][1], e))
        else:
            m.append((s, e))
    return m

if __name__ == '__main__':
    base = sys.argv[1]
    others = sys.argv[2:]
    b = merge(ips_ranges(base))
    for p in sorted(set(sum([glob.glob(o) for o in others], []))):
        for s, e in ips_ranges(p):
            for bs, be in b:
                if s < be and bs < e:
                    print(f"{os.path.basename(p):40s} {pc2snes(max(s,bs)):06X}-{pc2snes(min(e,be)-1):06X}")

def snes2pc(a):
    return ((a >> 16) & 0x7F) * 0x8000 + (a & 0x7FFF)

def used_in(paths, bank, lo, hi):
    rs = []
    for p in paths:
        for s, e in ips_ranges(p):
            rs.append((s, e))
    rs = merge(rs)
    s0, e0 = snes2pc(bank << 16 | lo), snes2pc(bank << 16 | hi) + 1
    used = [(max(s, s0), min(e, e0)) for s, e in rs if s < e0 and s0 < e]
    free = []
    cur = s0
    for s, e in used:
        if s > cur:
            free.append((cur, s))
        cur = max(cur, e)
    if cur < e0:
        free.append((cur, e0))
    return used, free
