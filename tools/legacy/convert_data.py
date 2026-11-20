#!/usr/bin/env python3
"""Legacy Unity (2019.x) data -> a newer player (2021.3): give every serialized file type trees and stamp it with the newer version, so the
newer player reads the old objects by field name (SafeBinaryRead).  Objects' bytes are untouched (verified by hash), except the two classes
whose layout changed: PlayerSettings (activeInputHandler) and Shader (rewritten by ../shader2021.py).
<data> must be the ORIGINAL (old-version) files, Metal already injected; it is only read.  Converted copies go to <outdir>/<relative path>.
usage: convert_data.py <data> <original Managed dir> <outdir> [--from 2019.4.39f1] [--to 2021.3.45f1] [--only name,name]   (see docs/LEGACY-UNITY.md)"""
import sys, os, re, argparse, hashlib, collections, UnityPy
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')); import shader2021
from UnityPy.files import SerializedFile
from UnityPy.helpers import Tpk
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.helpers.TypeTreeNode import TypeTreeNode
ap = argparse.ArgumentParser(); ap.add_argument('data'); ap.add_argument('managed'); ap.add_argument('outdir')
ap.add_argument('--from', dest='old', default='2019.4.39f1'); ap.add_argument('--to', dest='new', default='2021.3.45f1'); ap.add_argument('--only', default='')
a = ap.parse_args(); OLD, NEW = a.old.encode() + b'\0', a.new.encode() + b'\0'; assert len(OLD) == len(NEW)
for dirpath, _, files in os.walk(a.data):                       # refuse converted input: re-converting a converted Shader corrupts it
    for f in files:
        p = os.path.join(dirpath, f)
        if f.endswith(('.resS', '.resource', '.json', '.info', '.config')) or os.path.getsize(p) < 64: continue
        with open(p, 'rb') as fh:
            if NEW in fh.read(64): sys.exit(f'{p} already carries {a.new}: point <data> at the original files (a symlink into the app is a trap)')
gen = TypeTreeGenerator(a.old); gen.load_local_dll_folder(a.managed)
env = UnityPy.load(a.data); env.typetree_generator = gen
only = set(filter(None, a.only.split(',')))

def fix(node):
    for n in node.traverse():
        if n.m_TypeFlags is None: n.m_TypeFlags = 1 if n.m_Type == 'Array' else 0
        if n.m_Type == 'TypelessData': n.m_TypeFlags = 1     # like `Array`, the container node carries the array flag (else the engine mis-measures the blob)
        if n.m_RefTypeHash is None: n.m_RefTypeHash = 0
    return node
import dnfile
CLASSES = {}                                              # full class name -> (base full name, names of its string[] fields)
def _full(row): return (row.TypeNamespace.value + '.' if row.TypeNamespace.value else '') + row.TypeName.value
for _f in sorted(os.listdir(a.managed)):
    if not _f.endswith('.dll') or not _f.startswith(('Assembly-CSharp', 'Unity.')): continue     # game scripts only (dnfile is slow)
    try: _pe = dnfile.dnPE(os.path.join(a.managed, _f)); _td = _pe.net.mdtables.TypeDef.rows
    except Exception: continue
    for _r in _td:
        try: _base = _full(_r.Extends.row) if _r.Extends else ''
        except Exception: _base = ''
        CLASSES[_full(_r)] = (_base, {fl.row.Name.value for fl in _r.FieldList if bytes(fl.row.Signature.value) == b'\x06\x1d\x0e'})
SIMPLE = {k.split('.')[-1]: k for k in CLASSES}
def script_nodes(sample):
    mb = sample.parse_monobehaviour_head(); sc = mb.m_Script.deref_parse_as_object()
    full = f'{sc.m_Namespace}.{sc.m_ClassName}' if sc.m_Namespace else sc.m_ClassName
    asm = sc.m_AssemblyName if sc.m_AssemblyName.endswith('.dll') else sc.m_AssemblyName + '.dll'
    nodes = gen.get_nodes(asm, full)
    if not nodes: raise ValueError(f'no nodes for {full} in {asm}')
    def sfields(owner):                                   # string[] field names of a class, its bases included
        c = owner if owner in CLASSES else SIMPLE.get(owner.split('.')[-1], owner); out = set()
        while c in CLASSES: out |= CLASSES[c][1]; c = CLASSES[c][0]
        return out
    flat = []; skip = -1; stack = {}                      # the generator types `string[]` fields as plain `string`: rewrite them as vector<string>
    for b in nodes:
        if b.m_Level <= skip: skip = -1
        if skip >= 0: continue
        stack[b.m_Level] = b
        owner = full if b.m_Level == 1 else (stack[b.m_Level - 1].m_Type if b.m_Level - 1 in stack else '')
        if b.m_Type == 'string' and b.m_Level >= 1 and owner not in ('Array', '') and b.m_Name in sfields(owner):
            L = b.m_Level; skip = L
            for lv, ty, nm, mf in ((0, 'vector', b.m_Name, 0x8000), (1, 'Array', 'Array', 0xc000), (2, 'int', 'size', 0), (2, 'string', 'data', 0x8000),
                                   (3, 'Array', 'Array', 0x4001), (4, 'int', 'size', 1), (4, 'char', 'data', 1)):
                flat.append(TypeTreeNode(L + lv, ty, nm, 0, 1, m_MetaFlag=mf))
        else:
            mf = b.m_MetaFlag
            if b.m_Level == 1 and b.m_Name == 'm_Enabled': mf |= 0x4000    # generator puts this header's align flag on m_Script instead: m_Script then reads 3 bytes early
            flat.append(TypeTreeNode(b.m_Level, b.m_Type, b.m_Name, 0, 1, m_MetaFlag=mf))
    root = TypeTreeNode.from_list(flat)
    for n in list(root.traverse()):                       # the generator emits `string` without children; the engine reads it as Array<char>
        if n.m_Type == 'string' and not n.m_Children:
            arr = TypeTreeNode(n.m_Level + 1, 'Array', 'Array', 0, 1, m_MetaFlag=0x4001)
            arr.m_Children = [TypeTreeNode(n.m_Level + 2, 'int', 'size', 0, 1, m_MetaFlag=0x1), TypeTreeNode(n.m_Level + 2, 'char', 'data', 0, 1, m_MetaFlag=0x1)]
            n.m_Children = [arr]; n.m_MetaFlag = (n.m_MetaFlag & ~0x4000) | 0x8000
    for i, n in enumerate(root.traverse()): n.m_Index = i
    def size(n):
        if n.m_Type in ('string', 'Array', 'TypelessData') or n.m_Type.startswith(('vector', 'map', 'set')): n.m_ByteSize = -1
        elif not n.m_Children: n.m_ByteSize = PRIM.get(n.m_Type, -1)
        else:
            ss = [size(c) for c in n.m_Children]; n.m_ByteSize = sum(ss) if all(s >= 0 for s in ss) else -1
            if any(d.m_MetaFlag & 0x4000 for d in n.traverse() if d is not n):   # padding is not in the sum: like Unity, flag it and size it as variable
                n.m_MetaFlag |= 0x8000; n.m_ByteSize = -1
            return n.m_ByteSize
        for c in n.m_Children: size(c)
        return n.m_ByteSize
    size(root)
    for n in root.traverse():                             # containers too (vector/Array/string) carry kAnyChildUsesAlignBytes
        if any(d.m_MetaFlag & 0x4000 for d in n.traverse() if d is not n): n.m_MetaFlag |= 0x8000
    return fix(root), full
PRIM = {'int': 4, 'unsigned int': 4, 'float': 4, 'double': 8, 'bool': 1, 'char': 1, 'SInt8': 1, 'UInt8': 1, 'SInt16': 2, 'short': 2, 'UInt16': 2,
        'unsigned short': 2, 'SInt32': 4, 'UInt32': 4, 'SInt64': 8, 'UInt64': 8, 'long long': 8, 'unsigned long long': 8, 'FileSize': 8}
cache = {}
for path, sf in list(env.files.items()):
    if not isinstance(sf, SerializedFile): continue
    rel = os.path.relpath(path, a.data) if os.path.isabs(path) else path
    name = os.path.basename(rel)
    if only and name not in only: continue
    before = {o.path_id: hashlib.sha1(o.get_raw_data()).digest() for o in sf.objects.values()}
    samples = {}
    for o in sf.objects.values():
        t = o.serialized_type
        if t.class_id == 114 and id(t) not in samples: samples[id(t)] = o
    stats = collections.Counter(); fails = []
    for t in sf.types:
        try:
            if t.class_id == 114:
                key = (t.script_id, t.old_type_hash)
                if key not in cache:
                    for s in [o for o in sf.objects.values() if o.serialized_type is t][:50]:     # a few objects may point at a missing script (PathID 0)
                        try: cache[key] = script_nodes(s)[0]; break
                        except Exception as e: err = e
                    else:
                        if 'PPtr' not in str(err): raise err
                        cache[key] = fix(Tpk.get_typetree_node(114, sf.version)); stats['missing_script'] += 1
                t.node = cache[key]; stats['script'] += 1
            else:
                t.node = fix(Tpk.get_typetree_node(t.class_id, sf.version)); stats['native'] += 1
            t.type_dependencies = ()
        except Exception as e: fails.append((t.class_id, str(e)[:100]))
    if fails: print(f'{name}: FAILED types {fails[:6]} (+{max(0, len(fails) - 6)})'); continue
    for o in sf.objects.values():     # 2020+ replaced PlayerSettings' two new-Input-System bools with activeInputHandler (0 old, 1 new, 2 both); missing = 0 = no mouse/keyboard for the new Input System
        if o.serialized_type.class_id != 129: continue
        tt = o.read_typetree(check_read=False); n = o.serialized_type.node   # 2019.4.39 data has one trailing bool the TPK layout lacks (dropped; 2021 has no such field)
        if 'activeInputHandler' in tt or 'enableNativePlatformBackendsForNewInputSystem' not in tt: continue
        flat = [TypeTreeNode(c.m_Level, c.m_Type, c.m_Name, c.m_ByteSize, c.m_Version, m_MetaFlag=c.m_MetaFlag) for c in n.traverse()]   # fresh copy: Tpk nodes may be cached
        n = o.serialized_type.node = fix(TypeTreeNode.from_list(flat + [TypeTreeNode(1, 'int', 'activeInputHandler', 4, 1, m_MetaFlag=0)]))
        for i, c in enumerate(n.traverse()): c.m_Index = i
        tt['activeInputHandler'] = (1 if tt['disableOldInputManagerSupport'] else 2) if tt['enableNativePlatformBackendsForNewInputSystem'] else 0
        before[o.path_id] = hashlib.sha1(o.save_typetree(tt)).digest(); stats['activeInputHandler'] = tt['activeInputHandler']
    shaders = [o for o in sf.objects.values() if o.serialized_type.class_id == 48]
    if shaders:                       # 2021 Shader layout differs (parameters, keywords, blob entries): rewrite, not just re-describe
        trees = [(o, o.read_typetree()) for o in shaders]
        n21 = fix(Tpk.get_typetree_node(48, tuple(int(x) for x in re.findall(r'\d+', a.new))))
        for o, _ in trees: o.serialized_type.node = n21
        for o, tt in trees: before[o.path_id] = hashlib.sha1(o.save_typetree(shader2021.convert(tt, n21))).digest()
        stats['shader2021'] = len(trees)
    sf._enable_type_tree = True
    out = bytearray(sf.save()); chk = UnityPy.load(bytes(out)); sf2 = next(iter(chk.files.values()))
    bad = [p for p, o in sf2.objects.items() if hashlib.sha1(o.get_raw_data()).digest() != before.get(p)]
    assert not bad and len(sf2.objects) == len(before), f'{name}: objects changed {bad[:5]}'
    own = sf.unity_version.encode() + b'\0'; j = out.find(own, 0, 64)      # a file may carry another patch version than --from (e.g. 2019.4.38f1)
    assert j > 0 and len(own) == len(NEW), f'{name}: cannot stamp version {sf.unity_version}'
    out[j:j + len(NEW)] = NEW
    dst = os.path.join(a.outdir, rel); os.makedirs(os.path.dirname(dst), exist_ok=True); open(dst, 'wb').write(out)
    print(f'{name}: ok {len(before)} objects identical, {dict(stats)}', flush=True)
