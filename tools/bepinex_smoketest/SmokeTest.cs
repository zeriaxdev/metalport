// BepInEx smoke test for metalport ports: proves the plugin loads and that Harmony can patch game code on arm64.
// Build: dotnet build -c Release -p:BepInExCore=<mods dir>/BepInEx/core -p:UnityManaged=<App>.app/Contents/Resources/Data/Managed
using BepInEx;
using HarmonyLib;
using UnityEngine;

[BepInPlugin("metalport.smoketest", "metalport smoke test", "1.0.0")]
public class SmokeTest : BaseUnityPlugin
{
    void Awake()
    {
        Logger.LogInfo($"metalport smoke test loaded: {SystemInfo.processorType}, {System.IntPtr.Size * 8}-bit, Unity {Application.unityVersion}");
        new Harmony("metalport.smoketest").PatchAll();
        Debug.Log("metalport smoke test: Harmony check");   // the patch below tags this line if patching works
    }
}

[HarmonyPatch(typeof(Debug), nameof(Debug.Log), new[] { typeof(object) })]
static class DebugLogPatch
{
    static void Prefix(ref object message)
    {
        if (message is string s && s.StartsWith("metalport smoke test: Harmony check")) message = s + " -> [harmony-patched]";
    }
}
