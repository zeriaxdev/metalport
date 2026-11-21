using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;
using GraphicsSettings = SettingsMenu.Components.Pages.GraphicsSettings;

namespace GameplayRuntimeProbe
{
    public static class Entry
    {
        public static int Dispatches;
        public static void Dispatch() { Dispatches++; }
        public static void Install()
        {
            GraphicsSettings.disabledComputeShaders = Environment.GetEnvironmentVariable("GAMEPLAY_COMPUTE_MODE") == "off";
            var go = new GameObject("Isolated gameplay compute comparison");
            UnityEngine.Object.DontDestroyOnLoad(go);
            go.AddComponent<Runner>();
        }
    }
    [Serializable] public class Result
    {
        public bool success, disabledCompute, postCompute;
        public int paletteDispatches, lightingBuffers;
        public string mode, unity, device, backend, scene, error, cameraName, cameraPosition, cameraAngles;
        public List<string> captures = new List<string>();
        public List<string> bootScenes = new List<string>();
        public List<string> imageChecks = new List<string>();
        public float gamma, precision;
        public List<string> engineErrors = new List<string>();
    }
    public sealed class Runner : MonoBehaviour
    {
        readonly Result result = new Result();
        bool finished;
        float began;
        string output;
        string lastScene;
        void Awake()
        {
            began = Time.realtimeSinceStartup;
            output = Environment.GetEnvironmentVariable("GAMEPLAY_OUTPUT");
            result.mode = Environment.GetEnvironmentVariable("GAMEPLAY_COMPUTE_MODE");
            AudioListener.pause = true; AudioListener.volume = 0;
            Application.logMessageReceived += (text, stack, type) => {
                if (type == LogType.Error || type == LogType.Exception || type == LogType.Assert) result.engineErrors.Add(text);
            };
        }
        void Update()
        {
            if (SceneHelper.CurrentScene != lastScene) { lastScene = SceneHelper.CurrentScene; result.bootScenes.Add(lastScene); }
            if (!finished && Time.realtimeSinceStartup - began > 60) Finish(false, "60-second scene timeout");
        }
        IEnumerator Start()
        {
            var run = Run();
            while (true)
            {
                bool more;
                try { more = run.MoveNext(); }
                catch (Exception error) { Finish(false, error.ToString()); yield break; }
                if (!more) break;
                yield return run.Current;
            }
            Finish(true, null);
        }
        static void Require(bool ok, string message) { if (!ok) throw new InvalidOperationException(message); }
        IEnumerator Run()
        {
            while (SceneHelper.CurrentScene != "Main Menu" || Time.realtimeSinceStartup - began < 4) yield return null;
            SceneHelper.LoadScene("Level 0-1", true);
            while (SceneHelper.CurrentScene != "Level 0-1" || Time.realtimeSinceStartup - began < 12) yield return null;
            var post = MonoSingleton<PostProcessV2_Handler>.Instance;
            Require(post != null && post.mainCam != null && post.virtualCam != null, "Gameplay cameras are unavailable");
            result.unity = Application.unityVersion; result.device = SystemInfo.graphicsDeviceName;
            result.backend = SystemInfo.graphicsDeviceType.ToString(); result.scene = SceneHelper.CurrentScene;
            result.disabledCompute = GraphicsSettings.disabledComputeShaders;
            result.postCompute = post.usedComputeShadersAtStart;
            result.cameraName = post.mainCam.name;
            result.cameraPosition = post.mainCam.transform.position.ToString("F3");
            result.cameraAngles = post.mainCam.transform.eulerAngles.ToString("F3");
            result.gamma = Shader.GetGlobalFloat("_Gamma"); result.precision = Shader.GetGlobalFloat("_ColorPrecision");
            Require(result.disabledCompute == (result.mode == "off"), "Saved compute setting did not reach the running scene");
            Require(result.postCompute == !result.disabledCompute, "Post-processing initialized with a different compute setting");
            var field = typeof(StaticSceneOptimizer).GetField("cbGlobalLightsData", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
            Require(field != null, "Lighting-buffer diagnostic field is unavailable");
            foreach (var optimizer in UnityEngine.Object.FindObjectsOfType<StaticSceneOptimizer>())
                if (field.GetValue(optimizer) is ComputeBuffer buffer && buffer.count > 0) result.lightingBuffers++;
            Require(result.lightingBuffers > 0, "CPU-populated wall lighting buffers were lost");
            for (int i = 0; i < 3; i++) yield return null;
            Capture(post, "normal");
            Time.timeScale = 0;
            var palette = new Texture2D(32, 32, TextureFormat.RGBA32, false, true);
            palette.name = "Metalport synthetic palette";
            var colors = new[] { Color.black, Color.white, new Color(.1f, .1f, .25f), Color.cyan,
                                 Color.magenta, new Color(1, .5f, 0), Color.red, Color.green };
            var pixels = new Color[1024]; for (int i = 0; i < pixels.Length; i++) pixels[i] = colors[i % colors.Length];
            palette.filterMode = FilterMode.Point; palette.wrapMode = TextureWrapMode.Clamp;
            palette.SetPixels(pixels); palette.Apply();
            int before = Entry.Dispatches;
            post.ApplyMapColorPalette(palette);
            for (int i = 0; i < 4; i++) yield return null;
            result.paletteDispatches = Entry.Dispatches - before;
            Require(result.mode == "on" ? result.paletteDispatches > 0 : result.paletteDispatches == 0, "Palette did not use the requested compute/fallback path");
            Require(Shader.GetGlobalTexture("_LUT") != null && Shader.IsKeywordEnabled("PALETTIZE"), "Palette LUT was not bound to post-processing");
            Capture(post, "palette");
            post.ApplyMapColorPalette(null);
            Shader.DisableKeyword("PALETTIZE");
            Shader.SetGlobalFloat("_ColorPrecision", result.precision);
            for (int i = 0; i < 3; i++) yield return null;
            Capture(post, "restored");
            Destroy(palette);
        }
        void Capture(PostProcessV2_Handler post, string label)
        {
            post.mainCam.Render();
            var raw = typeof(PostProcessV2_Handler).GetField("mainTex", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance).GetValue(post) as RenderTexture;
            if (raw != null) Save(raw, label + "-raw");
            var frame = RenderTexture.GetTemporary(960, 600, 24);
            var oldTarget = post.virtualCam.targetTexture;
            post.virtualCam.targetTexture = frame; post.virtualCam.Render();
            int lit = Save(frame, label);
            post.virtualCam.targetTexture = oldTarget;
            RenderTexture.ReleaseTemporary(frame);
            if (label == "normal") Require(lit > 960 * 600 / 50, "Normal frame is almost blank; visual comparison rejected");
        }
        int Save(RenderTexture frame, string label)
        {
            var oldActive = RenderTexture.active; RenderTexture.active = frame;
            var pixels = new Texture2D(frame.width, frame.height, TextureFormat.RGB24, false);
            pixels.ReadPixels(new Rect(0, 0, frame.width, frame.height), 0, 0); pixels.Apply();
            File.WriteAllBytes(Path.Combine(output, label + ".png"), pixels.EncodeToPNG());
            result.captures.Add(label + ".png");
            int lit = 0;
            var colors = new HashSet<uint>();
            foreach (var color in pixels.GetPixels32())
            {
                if (Math.Max(color.r, Math.Max(color.g, color.b)) > 5) lit++;
                colors.Add((uint)(color.r | color.g << 8 | color.b << 16));
            }
            result.imageChecks.Add(label + ":" + lit + "/" + (frame.width * frame.height) + ";colors=" + colors.Count);
            RenderTexture.active = oldActive; Destroy(pixels);
            if (label == "normal") Require(colors.Count >= 32, "Normal frame has too little detail; solid/blank capture rejected");
            return lit;
        }
        void Finish(bool success, string error)
        {
            if (finished) return; finished = true;
            result.success = success; result.error = error;
            File.WriteAllText(Path.Combine(output, "result.json"), JsonUtility.ToJson(result, true));
            Debug.Log("[GameplayCompute] " + (success ? "PASS" : "FAIL") + " dispatches=" + result.paletteDispatches + " " + error);
            Application.Quit(success ? 0 : 2);
        }
    }
}
