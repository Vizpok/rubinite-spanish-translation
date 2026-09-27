"""Parser/escritor del LanguageSourceAsset (I2 Localization) de Rubinite.
Layout real (cada bool va alineado a 4 bytes)."""
import struct

class R:
    def __init__(s, b): s.b, s.p = b, 0
    def align(s): s.p = (s.p + 3) & ~3
    def i32(s): v = struct.unpack_from('<i', s.b, s.p)[0]; s.p += 4; return v
    def i64(s): v = struct.unpack_from('<q', s.b, s.p)[0]; s.p += 8; return v
    def f32(s): v = struct.unpack_from('<f', s.b, s.p)[0]; s.p += 4; return v
    def u8(s): v = s.b[s.p]; s.p += 1; return v
    def str(s):
        n = s.i32(); v = s.b[s.p:s.p+n].decode('utf-8'); s.p += n; s.align(); return v
    def bytes_(s):
        n = s.i32(); v = s.b[s.p:s.p+n]; s.p += n; s.align(); return v
    def strs(s): return [s.str() for _ in range(s.i32())]

class W:
    def __init__(s): s.b = bytearray()
    def align(s):
        while len(s.b) % 4: s.b.append(0)
    def i32(s, v): s.b += struct.pack('<i', v)
    def i64(s, v): s.b += struct.pack('<q', v)
    def f32(s, v): s.b += struct.pack('<f', v)
    def u8(s, v): s.b.append(v)
    def str(s, v):
        e = v.encode('utf-8'); s.i32(len(e)); s.b += e; s.align()
    def bytes_(s, v): s.i32(len(v)); s.b += v; s.align()
    def strs(s, v):
        s.i32(len(v))
        for x in v: s.str(x)

def parse(b):
    r = R(b); d = {}
    d['head'] = b[:28]; r.p = 28          # m_GameObject, m_Enabled(+pad), m_Script
    d['name'] = r.str()
    d['flags3'] = [(r.u8(), r.align())[0] for _ in range(3)]
    terms = []
    for _ in range(r.i32()):
        t = {'Term': r.str(), 'TermType': r.i32(),
             'Languages': r.strs(), 'Flags': r.bytes_(), 'Languages_Touch': r.strs()}
        terms.append(t)
    d['terms'] = terms
    d['CaseInsensitiveTerms'] = r.u8(); r.align()
    d['OnMissingTranslation'] = r.i32()
    d['mTerm_AppName'] = r.str()
    d['languages'] = [{'Name': r.str(), 'Code': r.str(), 'Flags': (r.u8(), r.align())[0]} for _ in range(r.i32())]
    d['IgnoreDeviceLanguage'] = r.u8(); r.align()
    d['tail'] = b[r.p:]                   # resto sin cambios (Google*, Assets)
    return d

def build(d):
    w = W(); w.b += d['head']; w.str(d['name'])
    for f in d['flags3']: w.u8(f); w.align()
    w.i32(len(d['terms']))
    for t in d['terms']:
        w.str(t['Term']); w.i32(t['TermType'])
        w.strs(t['Languages']); w.bytes_(t['Flags']); w.strs(t['Languages_Touch'])
    w.u8(d['CaseInsensitiveTerms']); w.align()
    w.i32(d['OnMissingTranslation']); w.str(d['mTerm_AppName'])
    w.i32(len(d['languages']))
    for l in d['languages']:
        w.str(l['Name']); w.str(l['Code']); w.u8(l['Flags']); w.align()
    w.u8(d['IgnoreDeviceLanguage']); w.align()
    w.b += d['tail']
    return bytes(w.b)
