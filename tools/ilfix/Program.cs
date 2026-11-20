// ilfix: find and fix references that an older Unity build's assemblies make into a newer player's UnityEngine modules.
// usage: ilfix report <Managed dir>                    list member/type refs that no longer resolve
//        ilfix fix <Managed dir> <UnityCompat.dll>     rewrite them in place (keeps <dll>.orig), copies UnityCompat.dll into <Managed dir>
// Fixes: type moved to another namespace of the same assembly; UIVertex.uv0-3 Vector2 -> Vector4 (2020+, conversions inserted);
// unresolved static calls on UnityEngine.X -> UnityCompat.X (same name and parameter count, see compat/UnityCompat.cs).
using Mono.Cecil;
using Mono.Cecil.Cil;

var mode = args[0]; var dir = args[1];
if (mode == "il")                                   // ilfix il <dll> <Type full name> [method]: print IL, for reading game code
{
    var md = ModuleDefinition.ReadModule(dir);
    var ty = md.GetTypes().First(t => t.FullName == args[2]);
    foreach (var me in ty.Methods.Where(x => x.HasBody && (args.Length < 4 || x.Name == args[3])))
    { Console.WriteLine($"== {me.FullName}"); foreach (var ins in me.Body.Instructions) Console.WriteLine("  " + ins); }
    return;
}
if (mode == "calls")                                // ilfix calls <dll> <member name>: which methods call it, with the 4 instructions before
{
    var md = ModuleDefinition.ReadModule(dir);
    foreach (var me in md.GetTypes().SelectMany(t => t.Methods).Where(x => x.HasBody))
    {
        var ins = me.Body.Instructions;
        for (int i = 0; i < ins.Count; i++)
            if (ins[i].Operand is MemberReference r && r.Name == args[2])
                Console.WriteLine($"== {me.FullName}\n  " + string.Join("\n  ", ins.Skip(Math.Max(0, i - 4)).Take(Math.Min(i, 4) + 1)));
    }
    return;
}
if (mode == "returnfalse")                          // ilfix returnfalse <dll> <Type full name> <method>: make a bool method return false (keeps <dll>.orig)
{
    var rres = new DefaultAssemblyResolver(); rres.AddSearchDirectory(Path.GetDirectoryName(Path.GetFullPath(dir))!);
    var md = ModuleDefinition.ReadModule(new MemoryStream(File.ReadAllBytes(dir)), new ReaderParameters { AssemblyResolver = rres });
    var me = md.GetTypes().First(t => t.FullName == args[2]).Methods.First(m => m.Name == args[3] && m.ReturnType.FullName == "System.Boolean");
    me.Body.Instructions.Clear(); me.Body.ExceptionHandlers.Clear(); me.Body.Variables.Clear();
    var ip = me.Body.GetILProcessor(); ip.Append(ip.Create(OpCodes.Ldc_I4_0)); ip.Append(ip.Create(OpCodes.Ret));
    if (!File.Exists(dir + ".orig")) File.Copy(dir, dir + ".orig");
    md.Write(dir); Console.WriteLine($"{args[2]}::{args[3]} now returns false"); return;
}
if (mode == "nocompute")                            // ilfix nocompute <dll>: SystemInfo.supportsComputeShaders reads as false inside this assembly
{                                                   // (PostProcessing v2 then uses its fragment-shader fallbacks; the toolkit has no Metal compute shaders)
    var nres = new DefaultAssemblyResolver(); nres.AddSearchDirectory(Path.GetDirectoryName(Path.GetFullPath(dir))!);
    var md = ModuleDefinition.ReadModule(new MemoryStream(File.ReadAllBytes(dir)), new ReaderParameters { AssemblyResolver = nres }); int n = 0;
    foreach (var me in md.GetTypes().SelectMany(t => t.Methods).Where(x => x.HasBody))
        foreach (var ins in me.Body.Instructions)
            if (ins.OpCode == OpCodes.Call && ins.Operand is MethodReference r && r.Name == "get_supportsComputeShaders" && r.DeclaringType.FullName == "UnityEngine.SystemInfo")
            { ins.OpCode = OpCodes.Ldc_I4_0; ins.Operand = null; n++; }
    if (n > 0) { if (!File.Exists(dir + ".orig")) File.Copy(dir, dir + ".orig"); md.Write(dir); }
    Console.WriteLine($"{Path.GetFileName(dir)}: {n} supportsComputeShaders reads -> false");
    return;
}
var res = new DefaultAssemblyResolver(); res.AddSearchDirectory(dir);
var rp = new ReaderParameters { AssemblyResolver = res };
ModuleDefinition? compat = null;
if (mode == "fix") { File.Copy(args[2], Path.Combine(dir, "UnityCompat.dll"), true); compat = ModuleDefinition.ReadModule(Path.Combine(dir, "UnityCompat.dll"), rp); }
var core = res.Resolve(AssemblyNameReference.Parse("UnityEngine.CoreModule")).MainModule;
var v4 = core.GetType("UnityEngine.Vector4");
var toV2 = v4.Methods.Single(m => m.Name == "op_Implicit" && m.ReturnType.Name == "Vector2" && m.Parameters[0].ParameterType.Name == "Vector4");
var toV4 = v4.Methods.Single(m => m.Name == "op_Implicit" && m.ReturnType.Name == "Vector4" && m.Parameters[0].ParameterType.Name == "Vector2");
bool Resolves(MemberReference r) { try { return r is TypeReference t ? t.Resolve() != null : r is MethodReference mr ? mr.Resolve() != null : ((FieldReference)r).Resolve() != null; } catch { return false; } }
bool IsUv(FieldReference f) => f.DeclaringType.FullName == "UnityEngine.UIVertex" && f.Name is "uv0" or "uv1" or "uv2" or "uv3" && f.FieldType.FullName == "UnityEngine.Vector2";

foreach (var f in Directory.GetFiles(dir, "*.dll").OrderBy(x => x))
{
    var n = Path.GetFileName(f);
    if (n.StartsWith("UnityEngine.") && n.EndsWith("Module.dll") || n.StartsWith("System") || n.StartsWith("Mono.") || n is "mscorlib.dll" or "netstandard.dll" or "UnityCompat.dll") continue;
    ModuleDefinition m;
    try { m = ModuleDefinition.ReadModule(new MemoryStream(File.ReadAllBytes(f)), rp); } catch { continue; }
    if (mode == "report")
    {
        var bad = new SortedSet<string>();
        foreach (var r in m.GetMemberReferences()) if (!(r.DeclaringType is ArrayType) && !Resolves(r)) bad.Add(r.FullName);
        foreach (var t in m.GetTypeReferences()) if (!Resolves(t)) bad.Add("type " + t.FullName);
        if (bad.Count > 0) { Console.WriteLine($"== {n}: {bad.Count}"); foreach (var b in bad) Console.WriteLine("  " + b); }
        continue;
    }
    var log = new List<string>();
    foreach (var t in m.GetTypeReferences())                     // a type that moved namespace inside the same assembly
    {
        if (t.IsNested || Resolves(t) || t.Scope is not AssemblyNameReference an) continue;
        var cands = res.Resolve(an).MainModule.Types.Where(d => d.Name == t.Name && d.IsPublic).ToList();
        if (cands.Count == 1) { log.Add($"type {t.FullName} -> {cands[0].FullName}"); t.Namespace = cands[0].Namespace; }
    }
    var v4r = m.ImportReference(v4); var toV2r = m.ImportReference(toV2); var toV4r = m.ImportReference(toV4);
    var redirected = new Dictionary<string, MethodReference?>();
    foreach (var type in m.GetTypes())
    foreach (var meth in type.Methods.Where(x => x.HasBody))
    {
        var il = meth.Body.GetILProcessor(); var ins = meth.Body.Instructions;
        for (int i = 0; i < ins.Count; i++)
        {
            var x = ins[i];
            if (x.Operand is FieldReference fr && IsUv(fr))
            {
                var nf = new FieldReference(fr.Name, v4r, fr.DeclaringType);
                if (x.OpCode == OpCodes.Ldfld) { x.Operand = nf; il.InsertAfter(x, il.Create(OpCodes.Call, toV2r)); i++; }
                else if (x.OpCode == OpCodes.Stfld) { x.OpCode = OpCodes.Call; x.Operand = toV4r; il.InsertAfter(x, il.Create(OpCodes.Stfld, nf)); i++; }   // keeps branch targets on the conversion
                else if (x.OpCode == OpCodes.Ldflda)
                {
                    x.Operand = nf; var nx = ins[i + 1];
                    if (nx.Operand is FieldReference vf && vf.DeclaringType.FullName == "UnityEngine.Vector2" && vf.Name is "x" or "y")
                        nx.Operand = new FieldReference(vf.Name, vf.FieldType, v4r);
                    else log.Add($"WARNING {meth.FullName}: ldflda {fr.Name} then {nx.OpCode} {nx.Operand}");
                }
                else log.Add($"WARNING {meth.FullName}: {x.OpCode} {fr.Name}");
                log.Add($"uv {x.OpCode} {fr.Name} in {meth.FullName}");
            }
            else if (x.Operand is MethodReference mr && !(mr.DeclaringType is ArrayType) && mr.DeclaringType.Namespace == "UnityEngine" && !Resolves(mr))
            {
                if (!redirected.TryGetValue(mr.FullName, out var to))
                {
                    var ct = compat!.GetType("UnityCompat." + mr.DeclaringType.Name);
                    var c = ct?.Methods.SingleOrDefault(y => y.Name == mr.Name && y.IsStatic && y.Parameters.Count == mr.Parameters.Count + (mr.HasThis ? 1 : 0));
                    redirected[mr.FullName] = to = c == null ? null : m.ImportReference(c);
                    log.Add(to == null ? $"WARNING no UnityCompat stand-in for {mr.FullName}" : $"call {mr.FullName} -> {to.FullName}");
                }
                if (to != null) { x.OpCode = OpCodes.Call; x.Operand = to; }
            }
        }
    }
    if (log.Count == 0) continue;
    foreach (var l in log.Where(l => !l.StartsWith("uv "))) Console.WriteLine($"{n}: {l}");
    Console.WriteLine($"{n}: {log.Count(l => l.StartsWith("uv "))} UIVertex uv accesses rewritten");
    if (!File.Exists(f + ".orig")) File.Copy(f, f + ".orig");
    m.Write(f);
}
