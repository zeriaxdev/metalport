#!/usr/bin/env python3
"""Read every object of every serialized file with its type tree; report failures per type.  usage: validate_typetrees.py <data> [name,name]"""
import sys, os, collections, UnityPy
from UnityPy.files import SerializedFile
data=sys.argv[1]; only=set(sys.argv[2].split(',')) if len(sys.argv)>2 else None
env=UnityPy.load(data)
for path,sf in env.files.items():
    if not isinstance(sf,SerializedFile): continue
    name=os.path.basename(path)
    if only and name not in only: continue
    bad=collections.Counter(); ex={}; n=0
    for o in sf.objects.values():
        n+=1
        try: o.read_typetree()
        except Exception as e:
            k=(o.type.name if o.type.name!='MonoBehaviour' else 'MB:'+str(id(o.serialized_type)%100000)); bad[k]+=1; ex.setdefault(k,(o.path_id,str(e)[:90]))
    print(f'{name}: {n} objects, {sum(bad.values())} bad', flush=True)
    for k,c in bad.most_common(8): print('   ',k,c,ex[k])
