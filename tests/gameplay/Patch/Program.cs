using Mono.Cecil;
using Mono.Cecil.Cil;

var target = Path.GetFullPath(args[0]);
var root = Path.GetFullPath(args[2]);
var expected = Path.Combine(root, "mac/GameplayTest.app/Contents/Resources/Data/Managed/Assembly-CSharp.dll");
if (target != expected || !File.Exists(Path.Combine(root, ".metalport-gameplay-test")))
    throw new ArgumentException("Only the separate gameplay test copy may be changed");
using var resolver = new DefaultAssemblyResolver();
resolver.AddSearchDirectory(Path.GetDirectoryName(target));
using var game = AssemblyDefinition.ReadAssembly(target, new ReaderParameters { AssemblyResolver = resolver });
using var probe = AssemblyDefinition.ReadAssembly(args[1]);
var entry = probe.MainModule.Types.Single(t => t.FullName == "GameplayRuntimeProbe.Entry");
var install = entry.Methods.Single(m => m.Name == "Install");
var dispatch = entry.Methods.Single(m => m.Name == "Dispatch");
var bootstrap = game.MainModule.Types.Single(t => t.Name == "Bootstrap").Methods.Single(m => m.Name == "Start");
bootstrap.Body.GetILProcessor().InsertBefore(bootstrap.Body.Instructions[0], Instruction.Create(OpCodes.Call, game.MainModule.ImportReference(install)));
var palette = game.MainModule.Types.Single(t => t.Name == "ConvertPaletteToLUT").Methods.Single(m => m.Name == "ConvertPalette");
var calls = palette.Body.Instructions.Where(i => i.Operand is MethodReference m && m.DeclaringType.FullName == "UnityEngine.ComputeShader" && m.Name == "Dispatch").ToArray();
if (calls.Length != 1) throw new InvalidOperationException("Expected exactly one game palette dispatch call");
foreach (var call in calls)
    palette.Body.GetILProcessor().InsertBefore(call, Instruction.Create(OpCodes.Call, game.MainModule.ImportReference(dispatch)));
var opcodes = typeof(OpCodes).GetFields().Select(f => f.GetValue(null)).OfType<OpCode>().ToDictionary(op => op.Name);
foreach (var method in new[] { bootstrap, palette })
    foreach (var instruction in method.Body.Instructions)
        if (instruction.OpCode.OperandType == OperandType.ShortInlineBrTarget) instruction.OpCode = opcodes[instruction.OpCode.Name[..^2]];
var temporary = target + ".test.tmp";
game.Write(temporary);
using (var check = AssemblyDefinition.ReadAssembly(temporary))
{
    var methods = check.MainModule.Types.SelectMany(t => t.Methods).Where(m => m.HasBody);
    int hooks = methods.SelectMany(m => m.Body.Instructions).Count(i => i.Operand is MethodReference m && m.DeclaringType.FullName == entry.FullName);
    if (hooks != 2) throw new InvalidOperationException("Gameplay test hook verification failed");
}
File.Move(temporary, target, true);
File.Copy(args[1], Path.Combine(Path.GetDirectoryName(target)!, "GameplayProbe.dll"), false);
Console.WriteLine("Preserved gameplay bootstrap; added diagnostic entry and palette dispatch counter to the clone only.");
