#!/usr/bin/env python3
"""Unity 2019 keeps the assembly list and the RuntimeInitializeOnLoad methods inside globalgamemanagers; Unity 2021+ players read them from
ScriptingAssemblies.json and RuntimeInitializeOnLoads.json in the Data folder.  Build both from the old serialized objects.
usage: make_json.py <original globalgamemanagers> <player Managed dir with the new UnityEngine*.dll set> <out Data dir>"""
import sys, os, json, UnityPy
gg, managed, out = sys.argv[1:4]
env = UnityPy.load(gg); mm = rm = None
for o in env.objects:
    if o.type.name == 'MonoManager': mm = o.read_typetree()
    if o.type.name == 'RuntimeInitializeOnLoadManager': rm = o.read_typetree()
old = dict(zip(mm['m_AssemblyNames'], mm['m_AssemblyTypes']))
eng = sorted((f for f in os.listdir(managed) if f.startswith('UnityEngine.') and f.endswith('.dll') and old.get(f, 2) == 2), key=lambda f: (f != 'UnityEngine.dll', f))
names = eng + [n for n, t in old.items() if t != 2 and n not in eng and os.path.exists(os.path.join(managed, n))]
types = [2] * len(eng) + [old[n] for n in names[len(eng):]]
json.dump({'names': names, 'types': types}, open(os.path.join(out, 'ScriptingAssemblies.json'), 'w'), separators=(',', ':'))
ci, mi = rm['m_ClassInfos'], rm['m_ClassMethodInfos']; asm = rm['m_AssemblyNames']; root = []
LISTS = [('m_BeforeUnityMethodExecutionOrders', 1, True), ('m_BeforeMethodExecutionOrders', 1, False), ('m_AfterUnityMethodExecutionOrders', 0, True), ('m_AfterMethodExecutionOrders', 0, False),
         ('m_AfterAssembliesLoadedUnityMethodExecutionOrders', 2, True), ('m_AfterAssembliesLoadedMethodExecutionOrders', 2, False),
         ('m_BeforeSplashScreenUnityMethodExecutionOrders', 3, True), ('m_BeforeSplashScreenMethodExecutionOrders', 3, False),
         ('m_SubsystemRegistrationUnityMethodExecutionOrders', 4, True), ('m_SubsystemRegistrationMethodExecutionOrders', 4, False)]
for key, load, unity in LISTS:
    for idx in rm[key]:
        m = mi[idx]; c = ci[m['m_ClassIndex']]
        root.append({'assemblyName': asm[c['m_AssemblyNameIndex']], 'nameSpace': c['m_NamespaceName'], 'className': c['m_ClassName'],
                     'methodName': m['m_MethodName'], 'loadTypes': load, 'isUnityClass': bool(c['m_IsUnityClass'])})
json.dump({'root': root}, open(os.path.join(out, 'RuntimeInitializeOnLoads.json'), 'w'), separators=(',', ':'))
print(f'{len(names)} assemblies ({len(eng)} engine), {len(root)} runtime-init methods')
