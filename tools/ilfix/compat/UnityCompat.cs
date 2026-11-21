// Stand-ins for Unity 2019 APIs whose signatures changed by 2021.  ilfix redirects unresolved calls on UnityEngine.X to UnityCompat.X
// (same method name and parameter count).  2020+ widened UI uv streams from Vector2 to Vector4; convert at the boundary.
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace UnityCompat
{
    // Debug aid, run via repo_tweaks: REPO_INVOKE="UnityCompat:UnityCompat.Diag:Run" (DIAG_MODE=nofx also disables image effects).
    public static class Diag
    {
        static System.Collections.Generic.List<(object, System.Reflection.PropertyInfo, string)> models; static int step;
        static System.Collections.Generic.Dictionary<string, bool> orig;

        static string Measure(Camera c, Shader replace = null)          // render offscreen, report mean rgb, max and NaN count
        {
            const int W = 192, H = 120;
            var rt = RenderTexture.GetTemporary(W, H, 24, RenderTextureFormat.ARGBHalf);
            var old = c.targetTexture; c.targetTexture = rt;
            if (replace) c.RenderWithShader(replace, ""); else c.Render();
            c.targetTexture = old;
            var s = ReadRT(rt); RenderTexture.ReleaseTemporary(rt); return s;
        }

        static string ReadRT(RenderTexture rt)
        {
            int W = rt.width, H = rt.height;
            var prev = RenderTexture.active; RenderTexture.active = rt;
            var tex = new Texture2D(W, H, TextureFormat.RGBAHalf, false); tex.ReadPixels(new Rect(0, 0, W, H), 0, 0); tex.Apply();
            RenderTexture.active = prev;
            double sr = 0, sg = 0, sb = 0, mx = 0; int nan = 0, n = 0;
            foreach (var px in tex.GetPixels())
            {
                if (float.IsNaN(px.r) || float.IsInfinity(px.r)) { nan++; continue; }
                sr += px.r; sg += px.g; sb += px.b; n++; mx = System.Math.Max(mx, px.r + px.g + px.b);
            }
            Object.Destroy(tex);
            return n == 0 ? $"all {nan} px NaN" : $"mean=({sr / n:F4},{sg / n:F4},{sb / n:F4}) max={mx:F3} nan={nan}";
        }

        static bool loaded, asked, bigDone; static int sweep = -1; static float loadT, lastT; static int lastF;
        public static void Run() { try { Run1(); } catch (System.Exception e) { Debug.Log("[diag] EXC " + e); } }
        static void Run1()
        {
            var mode = System.Environment.GetEnvironmentVariable("DIAG_MODE") ?? "";
            if (mode.Contains("bg")) Application.runInBackground = true;     // keep rendering while unfocused (screenshots)
            if (mode.Contains("fps"))                                         // frames per second since the last tick, plus pacing settings
            {
                float now = Time.realtimeSinceStartup;
                if (lastT > 0) Debug.Log($"[diag] fps {(Time.frameCount - lastF) / (now - lastT):F1} vsync={QualitySettings.vSyncCount} target={Application.targetFrameRate} dt={Time.unscaledDeltaTime * 1000:F1}ms fixed={Time.fixedDeltaTime * 1000:F1}ms maxQueued={QualitySettings.maxQueuedFrames} res={Screen.width}x{Screen.height}@{Screen.currentResolution.refreshRate}");
                lastT = now; lastF = Time.frameCount;
                var vs = System.Environment.GetEnvironmentVariable("DIAG_VSYNC");
                if (vs != null && loaded && now > loadT + 60) { QualitySettings.vSyncCount = int.Parse(vs); var tf = System.Environment.GetEnvironmentVariable("DIAG_TARGET"); if (tf != null) Application.targetFrameRate = int.Parse(tf); }
            }
            if (mode.Contains("sweep") && loaded && Time.realtimeSinceStartup > loadT + 60)   // step through AO/shadow settings, 30 s each, via the game's own settings (in memory)
            {
                var cfg = new[] { (4, 3), (0, 3), (4, 1), (0, 1), (1, 2), (0, 2) };
                int i = (int)((Time.realtimeSinceStartup - loadT - 60) / 30);
                if (i != sweep && i < cfg.Length)
                {
                    sweep = i; var asm = System.AppDomain.CurrentDomain.GetAssemblies().First(a => a.GetName().Name == "Assembly-CSharp");
                    var gs = asm.GetType("PlayerData").GetMethod("GetGraphicSettings").Invoke(null, null);
                    var ao = gs.GetType().GetField("ambientOcclusionQuality"); var sh = gs.GetType().GetField("shadowQuality");
                    ao.SetValue(gs, System.Enum.ToObject(ao.FieldType, cfg[i].Item1)); sh.SetValue(gs, System.Enum.ToObject(sh.FieldType, cfg[i].Item2));
                    gs.GetType().GetMethod("ApplyAllGraphicSettings").Invoke(gs, null);
                    Debug.Log($"[diag] sweep {i}: ao={ao.GetValue(gs)} shadow={sh.GetValue(gs)} (ao names: {string.Join(",", System.Enum.GetNames(ao.FieldType))}; shadow names: {string.Join(",", System.Enum.GetNames(sh.FieldType))})");
                }
            }
            var cf = System.Environment.GetEnvironmentVariable("DIAG_CMD_FILE");    // live toggles: lines "shadows 0|1", "comp <TypeName> 0|1" (enable/disable every MonoBehaviour of that type)
            if (cf != null && System.IO.File.Exists(cf))
            {
                foreach (var line in System.IO.File.ReadAllLines(cf))
                {
                    var w = line.Split(' '); if (w.Length < 2) continue;
                    if (w[0] == "cam") foreach (var c in Resources.FindObjectsOfTypeAll<Camera>()) if (c.name == w[1].Replace("_", " ") || (c.targetTexture && c.targetTexture.name.Contains(w[1].Replace("_", " ")))) { c.enabled = w[2] == "1"; Debug.Log($"[diag] cam {c.name} -> {c.enabled}"); }
                    if (w[0] == "ui") foreach (var g in Object.FindObjectsOfType<RectTransform>())
                    {
                        var comp = g.GetComponents<Component>().FirstOrDefault(k => k.GetType().Name is "RawImage" or "Image"); if (comp == null) continue;
                        var cs = new Vector3[4]; g.GetWorldCorners(cs); var cv = g.GetComponentInParent<Canvas>(); var ucam = cv && cv.renderMode != RenderMode.ScreenSpaceOverlay ? cv.worldCamera : null;
                        Vector2 a0 = RectTransformUtility.WorldToScreenPoint(ucam, cs[0]), a2 = RectTransformUtility.WorldToScreenPoint(ucam, cs[2]);
                        if (a0.x > 400 || a0.y > 400 || a2.x - a0.x > 600) continue;
                        var tex = comp.GetType().GetProperty("mainTexture")?.GetValue(comp) as Texture;
                        Debug.Log($"[diag] ui {comp.GetType().Name} {g.name} parent={(g.parent ? g.parent.name : "-")} screen=({a0.x:F0},{a0.y:F0})-({a2.x:F0},{a2.y:F0}) canvas={(cv ? cv.name + " " + cv.renderMode : "-")} tex={(tex ? tex.name + " " + tex.width + "x" + tex.height : "-")}");
                    }
                    if (w[0] == "dump")                                             // save every camera target and the final screen as PNGs into w[1]
                    {
                        System.IO.Directory.CreateDirectory(w[1]);
                        foreach (var c in Camera.allCameras)
                        {
                            var rt = c.targetTexture; if (!rt || !rt.IsCreated()) continue;
                            var prev = RenderTexture.active; RenderTexture.active = rt;
                            var t = new Texture2D(rt.width, rt.height, TextureFormat.RGBA32, false); t.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0); t.Apply();
                            RenderTexture.active = prev;
                            System.IO.File.WriteAllBytes($"{w[1]}/{c.name.Replace(' ', '_')}_{rt.name.Replace(' ', '_')}.png", ImageConversion.EncodeToPNG(t)); Object.Destroy(t);
                        }
                        foreach (var rt in Resources.FindObjectsOfTypeAll<RenderTexture>())        // and every LUT render texture (post-processing color grading)
                        {
                            if (!rt || !rt.IsCreated() || !rt.name.ToLower().Contains("lut") || rt.dimension != UnityEngine.Rendering.TextureDimension.Tex2D) continue;
                            var prev = RenderTexture.active; RenderTexture.active = rt;
                            var t = new Texture2D(rt.width, rt.height, TextureFormat.RGBAFloat, false); t.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0); t.Apply(); RenderTexture.active = prev;
                            var px = t.GetPixels(); float mx = 0, mean = 0; foreach (var c in px) { mx = Mathf.Max(mx, c.r); mean += c.r; }
                            Debug.Log($"[diag] lut {rt.name} {rt.width}x{rt.height} {rt.graphicsFormat} red mean={mean / px.Length:F4} max={mx:F4} first={px[0]} last={px[px.Length - 1]}");
                            Object.Destroy(t);
                        }
                        ScreenCapture.CaptureScreenshot($"{w[1]}/screen.png"); Debug.Log("[diag] dumped to " + w[1]);
                    }
                    if (w[0] == "ppfx")                                             // ppfx <SettingsType> 0|1: post-processing effect on/off in every volume profile (PPv2, by reflection)
                        foreach (var v in Object.FindObjectsOfType<MonoBehaviour>())
                        {
                            if (v.GetType().Name != "PostProcessVolume") continue;
                            const System.Reflection.BindingFlags F = System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
                            var prof = v.GetType().GetField("sharedProfile", F)?.GetValue(v); if (prof == null) continue;
                            var list = prof.GetType().GetField("settings", F)?.GetValue(prof) as System.Collections.IList; if (list == null) continue;
                            foreach (var st in list)
                            {
                                if (st == null || st.GetType().Name != w[1]) continue;
                                var en = st.GetType().GetField("enabled", F)?.GetValue(st); if (en == null) continue;
                                en.GetType().GetField("value", F)?.SetValue(en, w[2] == "1"); en.GetType().GetField("overrideState", F)?.SetValue(en, true);
                                Debug.Log($"[diag] ppfx {v.name}/{w[1]} -> {w[2]}");
                            }
                        }
                    if (w[0] == "pplist")                                           // post-processing components and the effects in their profiles
                        foreach (var v in Object.FindObjectsOfType<MonoBehaviour>())
                        {
                            var tn = v.GetType().Name; if (!tn.Contains("PostProcess")) continue;
                            const System.Reflection.BindingFlags F = System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
                            var info = $"[diag] pp {tn} on {v.name} enabled={v.enabled}";
                            if (tn == "PostProcessLayer") foreach (var fn in new[] { "antialiasingMode", "volumeLayer", "stopNaNPropagation", "finalBlitToCameraTarget", "breakBeforeColorGrading", "fog", "m_ShowToolkit" })
                                { object fv = null; try { fv = v.GetType().GetField(fn, F)?.GetValue(v); } catch { } if (fv is LayerMask lm) fv = lm.value.ToString("x"); else if (fv != null && fv.GetType().GetField("enabled") != null) fv = "fog.enabled=" + fv.GetType().GetField("enabled").GetValue(fv); info += $" {fn}={fv}"; }
                            foreach (var fn in new[] { "sharedProfile", "m_Profile", "profile" })
                            {
                                object prof = null; try { prof = v.GetType().GetField(fn, F)?.GetValue(v) ?? v.GetType().GetProperty(fn, F)?.GetValue(v); } catch { }
                                if (!(prof is Object po) || !po) continue;
                                var list = prof.GetType().GetField("settings", F)?.GetValue(prof) as System.Collections.IList;
                                if (list != null) foreach (var st in list) if (st != null) { var en = st.GetType().GetField("enabled", F)?.GetValue(st); info += $" | {fn}:{st.GetType().Name}={en?.GetType().GetField("value", F)?.GetValue(en)}"; }
                            }
                            Debug.Log(info);
                        }
                    if (w[0] == "camcomp")                                          // camcomp <camera name with _> <Type> 0|1: one component on one camera
                        foreach (var c in Resources.FindObjectsOfTypeAll<Camera>())
                            if (c.name == w[1].Replace("_", " ")) foreach (var b in c.GetComponents<Behaviour>()) if (b.GetType().Name == w[2]) { b.enabled = w[3] == "1"; Debug.Log($"[diag] camcomp {c.name}/{w[2]} -> {b.enabled}"); }
                    if (w[0] == "volmask")                                          // volmask <camera name with _> <int>: PostProcessLayer.volumeLayer of that camera
                        foreach (var c in Resources.FindObjectsOfTypeAll<Camera>())
                            if (c.name == w[1].Replace("_", " ")) foreach (var b in c.GetComponents<Behaviour>()) if (b.GetType().Name == "PostProcessLayer")
                            { var fi = b.GetType().GetField("volumeLayer"); fi.SetValue(b, (LayerMask)int.Parse(w[2])); Debug.Log($"[diag] volmask {c.name} -> {w[2]}"); }
                    if (w[0] == "call")                                             // call <Type> <method> [float]: invoke on every live object of that type
                        foreach (var o in Object.FindObjectsOfType<MonoBehaviour>())
                        {
                            if (o.GetType().Name != w[1]) continue;
                            var mi = o.GetType().GetMethods(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                                .FirstOrDefault(x => x.Name == w[2] && x.GetParameters().Length == (w.Length > 3 ? 1 : 0));
                            try { mi?.Invoke(o, w.Length > 3 ? new object[] { float.Parse(w[3], System.Globalization.CultureInfo.InvariantCulture) } : null); Debug.Log($"[diag] call {w[1]}.{w[2]} -> {(mi != null ? "ok" : "no such method")}"); }
                            catch (System.Exception e) { Debug.Log($"[diag] call {w[1]}.{w[2]} threw {e.InnerException?.Message ?? e.Message}"); }
                        }
                    if (w[0] == "ppv1")                                             // ppv1 <model field, e.g. eyeAdaptation> 0|1: PostProcessing v1 profile model on/off
                        foreach (var b in Object.FindObjectsOfType<MonoBehaviour>())
                        {
                            if (b.GetType().Name != "PostProcessingBehaviour") continue;
                            const System.Reflection.BindingFlags F = System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
                            var prof = b.GetType().GetField("profile", F)?.GetValue(b); if (prof == null) continue;
                            var model = prof.GetType().GetField(w[1], F)?.GetValue(prof); if (model == null) { Debug.Log($"[diag] ppv1 no {w[1]}"); continue; }
                            var pe = model.GetType().GetProperty("enabled", F); var was = pe?.GetValue(model); pe?.SetValue(model, w[2] == "1");
                            Debug.Log($"[diag] ppv1 {b.name}/{w[1]} {was} -> {w[2]}");
                        }
                    if (w[0] == "find")                                             // find <root name part>: renderers under matching roots that are on screen now
                    {
                        var fcam = Camera.main; int n = 0; var seenFind = new System.Collections.Generic.HashSet<string>();
                        foreach (var r in Object.FindObjectsOfType<Renderer>())
                        {
                            if (!r.enabled || !r.isVisible || !(r.transform.root.name.Contains(w[1]) || r.name.Contains(w[1]))) continue;
                            var m = r.sharedMaterial; var key = (m && m.shader ? m.shader.name : "-") + (m ? m.name : "");
                            if (!seenFind.Add(key)) continue; n++;
                            Debug.Log($"[diag] find {r.transform.root.name}/{r.transform.parent?.name}/{r.name} mat={(m ? m.name : "-")} dist={(r.bounds.center - fcam.transform.position).magnitude:F0} shader={(m && m.shader ? m.shader.name : "-")} kw={(m ? string.Join(" ", m.shaderKeywords) : "")} q={(m ? m.renderQueue : 0)}");
                        }
                        Debug.Log($"[diag] find {w[1]}: {n} visible");
                    }
                    if (w[0] == "where")                                            // where <root name>: screen position (viewport 0..1) of that body from the main camera
                    {
                        var wc = Camera.main; var go = GameObject.Find(w[1]);
                        if (!go || !wc) Debug.Log($"[diag] where {w[1]}: not found");
                        else { var vp = wc.WorldToViewportPoint(go.transform.position); var sun = GameObject.Find("Sun_Body");
                               var lit = sun ? Vector3.Dot((sun.transform.position - go.transform.position).normalized, (wc.transform.position - go.transform.position).normalized) : 0f;
                               Debug.Log($"[diag] where {w[1]} viewport=({vp.x:F2},{vp.y:F2}) dist={vp.z:F0} onscreen={(vp.z > 0 && vp.x > 0 && vp.x < 1 && vp.y > 0 && vp.y < 1)} sunFacingUs={lit:F2} cam={wc.name}"); }
                    }
                    if (w[0] == "res") Screen.SetResolution(int.Parse(w[1]), int.Parse(w[2]), Screen.fullScreenMode);
                    if (w[0] == "shadows") QualitySettings.shadows = w[1] == "0" ? ShadowQuality.Disable : ShadowQuality.All;
                    if (w[0] == "comp") foreach (var b in Object.FindObjectsOfType<MonoBehaviour>()) if (b.GetType().Name == w[1]) b.enabled = w[2] == "1";
                    Debug.Log("[diag] cmd " + line);
                }
                System.IO.File.Delete(cf);
            }
            var pf = System.Environment.GetEnvironmentVariable("DIAG_PICK_FILE");   // file "x y" (viewport 0..1, y up): list renderers covering that point, nearest first
            if (pf != null && System.IO.File.Exists(pf))
            {
                var xy = System.IO.File.ReadAllText(pf).Split(' '); System.IO.File.Delete(pf);
                var c = Camera.main; var v = new Vector2(float.Parse(xy[0], System.Globalization.CultureInfo.InvariantCulture), float.Parse(xy[1], System.Globalization.CultureInfo.InvariantCulture));
                Debug.Log($"[diag] pick cam={c.name} pos={c.transform.position} at {v}");
                foreach (var cc in Camera.allCameras) Debug.Log($"[diag] pick camera {cc.name} depth={cc.depth} mask={cc.cullingMask:x} clip={cc.nearClipPlane}-{cc.farClipPlane} rt={(cc.targetTexture ? cc.targetTexture.name : "-")}");
                foreach (var r in Object.FindObjectsOfType<Renderer>().Where(r => r.enabled && (r.bounds.center - c.transform.position).magnitude > 300).OrderBy(r => (r.bounds.center - c.transform.position).magnitude))
                {
                    var p0 = c.WorldToViewportPoint(r.bounds.center); if (p0.z <= 0) continue;
                    var p1 = c.WorldToViewportPoint(r.bounds.center + c.transform.right * r.bounds.extents.magnitude);
                    if ((new Vector2(p0.x, p0.y) - v).magnitude > (p1 - p0).magnitude) continue;
                    var m = r.sharedMaterial;
                    Debug.Log($"[diag] pick vis={r.isVisible} {r.name} parent={(r.transform.parent ? r.transform.parent.name : "-")} dist={p0.z:F0} ext={r.bounds.extents.magnitude:F0} layer={r.gameObject.layer} shader={(m && m.shader ? m.shader.name : "-")} kw={(m ? string.Join(" ", m.shaderKeywords) : "")} q={(m ? m.renderQueue : 0)} tex={(m && m.mainTexture ? m.mainTexture.name + " " + m.mainTexture.width : "-")}");
                }
            }
            if (mode.Contains("cams"))                                       // every camera and the screen area it draws to (a small one drawing to the screen = a corner square)
            {
                foreach (var c in Camera.allCameras)
                    Debug.Log($"[diag] cam {c.name} parent={(c.transform.parent ? c.transform.parent.name : "-")} enabled={c.enabled} depth={c.depth} pixelRect={c.pixelRect} rect={c.rect} target={(c.targetTexture ? $"{c.targetTexture.name} {c.targetTexture.width}x{c.targetTexture.height} {c.targetTexture.graphicsFormat} created={c.targetTexture.IsCreated()}" : "SCREEN")} mask={c.cullingMask:x}");
                Debug.Log($"[diag] screen {Screen.width}x{Screen.height}");
            }
            if (mode.Replace("bg", "").Trim(',').Length == 0) return;         // nothing else asked: stay cheap
            if (mode.Contains("game") && Time.realtimeSinceStartup > 45)   // skip the menu like its Resume button: async load, then allow the transition
            {
                var asm = System.AppDomain.CurrentDomain.GetAssemblies().First(a => a.GetName().Name == "Assembly-CSharp");
                var lm = asm.GetType("LoadManager"); var sc = asm.GetType("OWScene"); var ft = lm.GetNestedType("FadeType");
                var cur = lm.GetMethod("GetCurrentScene").Invoke(null, null).ToString();
                if (cur == "TitleScreen" && !asked) { asked = true; Debug.Log("[diag] game: async load SolarSystem");
                    lm.GetMethod("LoadSceneAsync").Invoke(null, new object[] { System.Enum.Parse(sc, "SolarSystem"), false, System.Enum.ToObject(ft, 1), 1f, false }); }
                else if (cur == "TitleScreen" && asked && (bool)lm.GetMethod("IsAsyncLoadComplete").Invoke(null, null)) { Debug.Log("[diag] game: transition"); lm.GetMethod("EnableAsyncLoadTransition").Invoke(null, null); }
                else if (cur == "SolarSystem" && !loaded) { loaded = true; loadT = Time.realtimeSinceStartup; Debug.Log("[diag] game: in SolarSystem"); }
            }
            if (mode.Contains("big") && loaded && Time.realtimeSinceStartup > loadT + 40 && !bigDone)   // big (planet-sized) renderers and their shaders
            {
                bigDone = true;
                foreach (var r in Object.FindObjectsOfType<Renderer>())
                {
                    if (!r.isVisible || r.bounds.extents.magnitude < 150) continue;
                    var m = r.sharedMaterial; var sh = m ? m.shader : null;
                    Debug.Log($"[diag] big {r.name} ext={r.bounds.extents.magnitude:F0} shader={(sh ? sh.name : "-")} ok={(sh ? sh.isSupported : false)} kw={(m ? string.Join(" ", m.shaderKeywords) : "")} q={(m ? m.renderQueue : 0)}");
                }
            }
            if (mode.Contains("cbtest"))                                      // do material constants reach converted shaders?
                foreach (var sn in new[] { "UI/Default", "Hidden/Post FX/Uber Shader" })
                {
                    var sh = Shader.Find(sn); if (!sh) continue;
                    var mat = new Material(sh); mat.SetColor("_Color", Color.red); mat.SetFloat("_ExposureEV", 0.25f);
                    mat.SetVector("_LogLut_Params", new Vector4(1f / 1024, 1f / 32, 31, 0));
                    if (sn.Contains("Uber")) { mat.shaderKeywords = new[] { "COLOR_GRADING" }; var w = RenderTexture.GetTemporary(1024, 32, 0, RenderTextureFormat.ARGBHalf); Graphics.Blit(Texture2D.whiteTexture, w); mat.SetTexture("_LogLut", w); mat.SetTexture("_AutoExposure", Texture2D.whiteTexture); }
                    var rt = RenderTexture.GetTemporary(64, 64, 0, RenderTextureFormat.ARGBHalf);
                    Graphics.Blit(Texture2D.whiteTexture, rt, mat, 0);
                    Debug.Log($"[diag] cbtest {sn}: {ReadRT(rt)}");
                    RenderTexture.ReleaseTemporary(rt); Object.Destroy(mat);
                }
            if (mode.Contains("blittest"))                                    // push a white texture through post-FX shaders on their own
                foreach (var sn in new[] { "Hidden/Post FX/Blit", "Hidden/Post FX/Uber Shader", "Hidden/Post FX/FXAA" })
                {
                    var sh = Shader.Find(sn); if (!sh) { Debug.Log($"[diag] blit {sn}: not found"); continue; }
                    var mat = new Material(sh); mat.SetTexture("_AutoExposure", Texture2D.whiteTexture);
                    var rt = RenderTexture.GetTemporary(64, 64, 0, RenderTextureFormat.ARGBHalf);
                    Graphics.Blit(Texture2D.whiteTexture, rt, mat, 0);
                    Debug.Log($"[diag] blit {sn}: supported={sh.isSupported} passes={mat.passCount} -> {ReadRT(rt)}");
                    RenderTexture.ReleaseTemporary(rt); Object.Destroy(mat);
                }
            if (mode.Split(',').All(t => t is "bg" or "game" or "big" or "fps" or "sweep" or "cams")) return;   // the scans below run every tick: only when asked
            var cam = Camera.main ?? (Camera.allCamerasCount > 0 ? Camera.allCameras[0] : null);
            if (cam != null && mode.Contains("probe"))                         // heavy: offscreen renders, scene scans
            {
                foreach (var c in Camera.allCameras)
                    Debug.Log($"[diag] cam {c.name} depth={c.depth} clear={c.clearFlags} bg={c.backgroundColor} hdr={c.allowHDR} path={c.actualRenderingPath} rt={(c.targetTexture ? c.targetTexture.name : "-")} mask={c.cullingMask:x} clip={c.nearClipPlane}-{c.farClipPlane} pos={c.transform.position}");
                var path0 = cam.renderingPath;
                foreach (var p in new[] { RenderingPath.DeferredShading, RenderingPath.Forward })
                { cam.renderingPath = p; Debug.Log($"[diag] render {p}: {Measure(cam)}"); }
                cam.renderingPath = path0;
                var ui = Shader.Find("UI/Default");
                if (ui != null) Debug.Log($"[diag] render all-UI/Default: {Measure(cam, ui)}");
                var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);          // stock mesh in front of the camera
                cube.transform.position = cam.transform.position + cam.transform.forward * 3f;
                if (ui != null) cube.GetComponent<Renderer>().sharedMaterial = new Material(ui);
                Debug.Log($"[diag] render with stock cube: {Measure(cam)}");
                Object.Destroy(cube);
                int shown = 0;
                foreach (var mf in Object.FindObjectsOfType<MeshFilter>())
                {
                    var r = mf.GetComponent<Renderer>(); var m = mf.sharedMesh;
                    if (!r || !r.isVisible || shown++ >= 6) continue;
                    var v0 = m && m.isReadable && m.vertexCount > 0 ? m.vertices[0].ToString() : "-";
                    Debug.Log($"[diag] mesh {mf.name}: {(m ? m.name : "null")} verts={(m ? m.vertexCount : 0)} sub={(m ? m.subMeshCount : 0)} readable={(m ? m.isReadable : false)} bounds={(m ? m.bounds.ToString() : "-")} rbounds={r.bounds} static={r.isPartOfStaticBatch} v0={v0} fmt={(m && m.vertexBufferCount > 0 ? m.GetVertexAttribute(0).ToString() : "-")}");
                }
                var seen = new System.Collections.Generic.Dictionary<string, int>();
                foreach (var r in Object.FindObjectsOfType<Renderer>())
                    if (r.isVisible) foreach (var m in r.sharedMaterials) if (m && m.shader) { seen.TryGetValue(m.shader.name, out var k); seen[m.shader.name] = k + 1; }
                foreach (var kv in seen) Debug.Log($"[diag] visible shader {kv.Key} x{kv.Value} supported={Shader.Find(kv.Key)?.isSupported}");
            }
            foreach (var b in Object.FindObjectsOfType<MonoBehaviour>())
            {
                var n = b.GetType().Name;
                if (!n.Contains("PostProcess") && !n.Contains("ImageEffect") && !n.Contains("Bloom") && !n.Contains("Tonemap")) continue;
                if (mode.Contains("nofx") || (mode.Contains("nopp") && n == "PostProcessingBehaviour") || (mode.Contains("nofog") && n.Contains("Fog"))) b.enabled = false;
                if (mode.Contains("noeye") && n == "PostProcessingBehaviour")            // profile.eyeAdaptation.enabled = false (reflection: type lives in the game assembly)
                {
                    const System.Reflection.BindingFlags F = System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
                    var prof = b.GetType().GetField("profile", F)?.GetValue(b);
                    var eye = prof?.GetType().GetField("eyeAdaptation", F)?.GetValue(prof);
                    var en = eye?.GetType().GetProperty("enabled", F);
                    if (en != null) { Debug.Log($"[diag] eyeAdaptation was {en.GetValue(eye)}"); en.SetValue(eye, false); }
                    else Debug.Log("[diag] eyeAdaptation not found");
                    if (prof != null && mode.Contains("shots") && Object.FindObjectsOfType<Renderer>().Length > 100)
                    {                                                     // one real frame per call: all on, then each enabled effect off, then no post FX
                        if (models == null)
                        {
                            models = new System.Collections.Generic.List<(object, System.Reflection.PropertyInfo, string)>();
                            foreach (var f in prof.GetType().GetFields(F))
                            {
                                var mdl = f.GetValue(prof); var p = mdl?.GetType().GetProperty("enabled", F);
                                if (p != null && (bool)p.GetValue(mdl)) models.Add((mdl, p, f.Name));
                            }
                        }
                        foreach (var (mdl, p, _) in models) p.SetValue(mdl, true);
                        b.enabled = true;
                        string tag = step == 0 ? "all" : step <= models.Count ? "no_" + models[step - 1].Item3 : step == models.Count + 1 ? "no_postfx" : null;
                        if (tag != null)
                        {
                            if (step >= 1 && step <= models.Count) models[step - 1].Item2.SetValue(models[step - 1].Item1, false);
                            if (step == models.Count + 1) b.enabled = false;
                            var dir = System.Environment.GetEnvironmentVariable("DIAG_DIR") ?? "/tmp";
                            ScreenCapture.CaptureScreenshot($"{dir}/shot{step:00}_{tag}.png");
                            Debug.Log($"[diag] shot {step} {tag}");
                            step++;
                        }
                    }
                    var offFile = System.Environment.GetEnvironmentVariable("DIAG_PPOFF_FILE");   // live control: file lists models to keep off, e.g. "antialiasing,bloom" or "ALL"
                    if (prof != null && offFile != null)
                    {
                        var off = System.IO.File.Exists(offFile) ? System.IO.File.ReadAllText(offFile).Trim() : "";
                        if (orig == null)
                        {
                            orig = new System.Collections.Generic.Dictionary<string, bool>();
                            foreach (var f in prof.GetType().GetFields(F))
                            { var mdl = f.GetValue(prof); var p = mdl?.GetType().GetProperty("enabled", F); if (p != null) orig[f.Name] = (bool)p.GetValue(mdl); }
                        }
                        var list = new System.Collections.Generic.HashSet<string>(off.Split(new[] { ',', ' ', '\n' }, System.StringSplitOptions.RemoveEmptyEntries));
                        foreach (var kv in orig)
                        {
                            var mdl = prof.GetType().GetField(kv.Key, F).GetValue(prof);
                            mdl.GetType().GetProperty("enabled", F).SetValue(mdl, kv.Value && !list.Contains(kv.Key) && !list.Contains("ALL"));
                        }
                        b.enabled = !list.Contains("NOPP");
                        Debug.Log($"[diag] ppoff now: {off}");
                    }
                    if (mode.Contains("uberinfo"))                     // what the live Uber material reads
                    {
                        var fac = b.GetType().GetField("m_MaterialFactory", F)?.GetValue(b);
                        var uber = fac?.GetType().GetMethod("Get")?.Invoke(fac, new object[] { "Hidden/Post FX/Uber Shader" }) as Material;
                        if (uber != null)
                        {
                            Debug.Log($"[diag] uber keywords: {string.Join(" ", uber.shaderKeywords)}");
                            foreach (var tn in uber.GetTexturePropertyNames())
                            {
                                var t = uber.GetTexture(tn);
                                string val = "-";
                                if (t is RenderTexture rtx && rtx.IsCreated() && rtx.dimension == UnityEngine.Rendering.TextureDimension.Tex2D) val = ReadRT(rtx);
                                else if (t is Texture2D t2 && t2.isReadable) { var px = t2.GetPixel(0, 0); val = px.ToString(); }
                                Debug.Log($"[diag] uber tex {tn} = {(t ? t.name + " " + t.GetType().Name + " " + t.width + "x" + t.height : "null")} {val}");
                            }
                        }
                        else Debug.Log("[diag] uber material not found");
                        if (uber != null)
                        {
                            Debug.Log($"[diag] uber _LogLut_Params={uber.GetVector("_LogLut_Params")} _ExposureEV={uber.GetFloat("_ExposureEV")} _CustomGamma={uber.GetFloat("_CustomGamma")}");
                            Debug.Log($"[diag] global keywords on: {string.Join(" ", Shader.enabledGlobalKeywords.Select(k => k.name))}");
                            Debug.Log($"[diag] uber enabledKeywords: {string.Join(" ", uber.enabledKeywords.Select(k => k.name + (k.isOverridable ? "(g)" : "(l)")))}");
                            Debug.Log($"[diag] uber keyword space: {string.Join(" ", uber.shader.keywordSpace.keywords.Select(k => k.name + "/" + k.type + (k.isOverridable ? "(g)" : "(l)")))}");
                            var lut = uber.GetTexture("_LogLut") as RenderTexture;
                            if (lut != null)
                            {
                                Debug.Log($"[diag] lut fmt={lut.format} gfx={lut.graphicsFormat} srgb={lut.sRGB} filter={lut.filterMode} wrap={lut.wrapMode} aniso={lut.anisoLevel} mips={lut.useMipMap}");
                                var dir = System.Environment.GetEnvironmentVariable("DIAG_DIR");
                                if (dir != null)
                                {
                                    var prevA = RenderTexture.active; RenderTexture.active = lut;
                                    var png = new Texture2D(lut.width, lut.height, TextureFormat.RGBA32, false); png.ReadPixels(new Rect(0, 0, lut.width, lut.height), 0, 0); png.Apply();
                                    RenderTexture.active = prevA; System.IO.File.WriteAllBytes(dir + "/lut.png", png.EncodeToPNG()); Object.Destroy(png);
                                }
                                var cp = RenderTexture.GetTemporary(lut.width, lut.height, 0, RenderTextureFormat.ARGBHalf);
                                Graphics.Blit(lut, cp); Debug.Log($"[diag] lut sampled-copy: {ReadRT(cp)}");
                                var wrt = RenderTexture.GetTemporary(lut.width, lut.height, 0, lut.format); Graphics.Blit(Texture2D.whiteTexture, wrt);
                                var m4 = new Material(uber); m4.shaderKeywords = new[] { "COLOR_GRADING" }; m4.SetTexture("_LogLut", wrt);
                                Graphics.Blit(Texture2D.whiteTexture, cp, m4, 0); Debug.Log($"[diag] uber cg white-RT-lut: {ReadRT(cp)}");
                                RenderTexture.ReleaseTemporary(cp); RenderTexture.ReleaseTemporary(wrt); Object.Destroy(m4);
                            }
                            foreach (var (pv, ev) in new[] { (new Vector4(1f / 1024, 1f / 32, 31, 0), 1f), (new Vector4(1f / 1024, 1f / 32, 31, 1), 1f), (new Vector4(1f / 1024, 1f / 32, 31, 100), 1f) })
                            {
                                var m5 = new Material(uber); m5.shaderKeywords = new[] { "COLOR_GRADING" }; m5.SetVector("_LogLut_Params", pv); m5.SetFloat("_ExposureEV", ev);
                                var rt5 = RenderTexture.GetTemporary(64, 64, 0, RenderTextureFormat.ARGBHalf);
                                Graphics.Blit(Texture2D.whiteTexture, rt5, m5, 0);
                                Debug.Log($"[diag] uber cg params {pv.x:F4},{pv.y:F4},{pv.z},w={pv.w} ev={ev}: {ReadRT(rt5)}");
                                RenderTexture.ReleaseTemporary(rt5); Object.Destroy(m5);
                            }
                            foreach (var variant in new[] { "cg live", "cg whitelut", "cg manual" })
                            {
                                var m3 = new Material(uber); m3.shaderKeywords = new[] { "COLOR_GRADING" };
                                if (variant == "cg whitelut") m3.SetTexture("_LogLut", Texture2D.whiteTexture);
                                if (variant == "cg manual") { m3.SetVector("_LogLut_Params", new Vector4(1f / 1024, 1f / 32, 31, 0)); m3.SetFloat("_ExposureEV", 1f); }
                                var rt3 = RenderTexture.GetTemporary(64, 64, 0, RenderTextureFormat.ARGBHalf);
                                Graphics.Blit(Texture2D.whiteTexture, rt3, m3, 0);
                                Debug.Log($"[diag] uber {variant}: {ReadRT(rt3)}");
                                RenderTexture.ReleaseTemporary(rt3); Object.Destroy(m3);
                            }
                            var kws = uber.shaderKeywords;
                            foreach (var drop in new[] { "" }.Concat(kws))
                            {
                                var m2 = new Material(uber); m2.shaderKeywords = kws.Where(k => k != drop).ToArray();
                                var rt = RenderTexture.GetTemporary(64, 64, 0, RenderTextureFormat.ARGBHalf);
                                Graphics.Blit(Texture2D.whiteTexture, rt, m2, 0);
                                Debug.Log($"[diag] uber white-in {(drop == "" ? "all keywords" : "without " + drop)}: {ReadRT(rt)}");
                                RenderTexture.ReleaseTemporary(rt); Object.Destroy(m2);
                            }
                        }
                        foreach (var f in prof.GetType().GetFields(F))
                        { var mdl = f.GetValue(prof); var p = mdl?.GetType().GetProperty("enabled", F); if (p != null) Debug.Log($"[diag] now {f.Name}={p.GetValue(mdl)}"); }
                    }
                    var cam1 = b.GetComponent<Camera>();
                    if (prof != null && cam1 != null && mode.Contains("bisect"))
                    {
                        Debug.Log($"[diag] bisect baseline: {Measure(cam1)}");
                        foreach (var f in prof.GetType().GetFields(F))
                        {
                            var mdl = f.GetValue(prof); var p = mdl?.GetType().GetProperty("enabled", F);
                            if (p == null || !(bool)p.GetValue(mdl)) continue;
                            p.SetValue(mdl, false); Debug.Log($"[diag] bisect without {f.Name}: {Measure(cam1)}"); p.SetValue(mdl, true);
                        }
                        b.enabled = false; Debug.Log($"[diag] bisect without PostProcessingBehaviour: {Measure(cam1)}"); b.enabled = true;
                    }
                }
                Debug.Log($"[diag] fx {n} on {b.name} enabled={b.enabled}");
            }
        }
    }

    public static class CanvasRenderer
    {
        static readonly List<Vector4>[] T = { new List<Vector4>(), new List<Vector4>(), new List<Vector4>(), new List<Vector4>() };   // ponytail: main-thread only, like uGUI itself

        static List<Vector4> In(int k, List<Vector2> src)
        {
            var d = T[k]; d.Clear();
            if (src != null) foreach (var v in src) d.Add(v);
            return d;
        }
        static void Out(List<Vector4> src, List<Vector2> dst)
        {
            if (dst == null) return;
            dst.Clear(); foreach (var v in src) dst.Add(v);
        }

        public static void CreateUIVertexStream(List<UIVertex> verts, List<Vector3> positions, List<Color32> colors, List<Vector2> uv0S, List<Vector2> uv1S,
            List<Vector2> uv2S, List<Vector2> uv3S, List<Vector3> normals, List<Vector4> tangents, List<int> indices)
            => UnityEngine.CanvasRenderer.CreateUIVertexStream(verts, positions, colors, In(0, uv0S), In(1, uv1S), In(2, uv2S), In(3, uv3S), normals, tangents, indices);

        public static void AddUIVertexStream(List<UIVertex> verts, List<Vector3> positions, List<Color32> colors, List<Vector2> uv0S, List<Vector2> uv1S,
            List<Vector2> uv2S, List<Vector2> uv3S, List<Vector3> normals, List<Vector4> tangents)
            => UnityEngine.CanvasRenderer.AddUIVertexStream(verts, positions, colors, In(0, uv0S), In(1, uv1S), In(2, uv2S), In(3, uv3S), normals, tangents);

        public static void SplitUIVertexStreams(List<UIVertex> verts, List<Vector3> positions, List<Color32> colors, List<Vector2> uv0S, List<Vector2> uv1S,
            List<Vector2> uv2S, List<Vector2> uv3S, List<Vector3> normals, List<Vector4> tangents, List<int> indices)
        {
            UnityEngine.CanvasRenderer.SplitUIVertexStreams(verts, positions, colors, T[0], T[1], T[2], T[3], normals, tangents, indices);
            Out(T[0], uv0S); Out(T[1], uv1S); Out(T[2], uv2S); Out(T[3], uv3S);
        }
    }
}
