using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using CuttingTool.GameUI;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace CuttingTool.GameUI.Editor
{
    public static class GameUIBatchImporter
    {
        [Serializable]
        private sealed class ImportPlan
        {
            public int schema_version;
            public string project_id = string.Empty;
            public string generated_root = string.Empty;
            public string prefab_root = string.Empty;
            public string report_path = string.Empty;
            public string preview_output_dir = string.Empty;
            public bool create_asset_prefabs;
            public SpritePlan[] sprites = Array.Empty<SpritePlan>();
            public ScreenPlan[] screens = Array.Empty<ScreenPlan>();
        }

        [Serializable]
        private sealed class SpritePlan
        {
            public string id = string.Empty;
            public string category = string.Empty;
            public string asset_path = string.Empty;
            public float pixels_per_unit = 100f;
            public int[] border = Array.Empty<int>();
            public float[] pivot = Array.Empty<float>();
        }

        [Serializable]
        private sealed class ScreenPlan
        {
            public string id = string.Empty;
            public string name = string.Empty;
            public float[] reference_size = Array.Empty<float>();
            public ElementPlan[] elements = Array.Empty<ElementPlan>();
        }

        [Serializable]
        private sealed class ElementPlan
        {
            public string id = string.Empty;
            public string parent_id = string.Empty;
            public string asset_id = string.Empty;
            public string kind = "Image";
            public float[] anchor_min = Array.Empty<float>();
            public float[] anchor_max = Array.Empty<float>();
            public float[] pivot = Array.Empty<float>();
            public float[] anchored_position = Array.Empty<float>();
            public float[] size = Array.Empty<float>();
            public float[] color = Array.Empty<float>();
            public bool preserve_aspect;
            public bool raycast_target;
            public string highlighted_asset_id = string.Empty;
            public string pressed_asset_id = string.Empty;
            public string disabled_asset_id = string.Empty;
            public float spacing;
            public int[] padding = Array.Empty<int>();
            public string child_alignment = "MiddleCenter";
            public bool control_child_size;
            public bool child_force_expand;
        }

        [Serializable]
        private sealed class ImportIssue
        {
            public string severity = "fail";
            public string code = string.Empty;
            public string target = string.Empty;
            public string message = string.Empty;
        }

        [Serializable]
        private sealed class ImportReport
        {
            public int schema_version = 1;
            public bool ok;
            public string project_id = string.Empty;
            public int imported_sprite_count;
            public int asset_prefab_count;
            public int screen_prefab_count;
            public int preview_scene_count;
            public int preview_image_count;
            public ImportIssue[] issues = Array.Empty<ImportIssue>();
        }

        public static void RunFromCommandLine()
        {
            var args = Environment.GetCommandLineArgs();
            var planPath = ReadArgument(args, "-gameUIPlan");
            if (string.IsNullOrWhiteSpace(planPath) || !File.Exists(planPath))
            {
                Debug.LogError("GameUI import plan is missing. Pass -gameUIPlan <absolute-path>.");
                EditorApplication.Exit(2);
                return;
            }

            ImportPlan plan;
            try
            {
                plan = JsonUtility.FromJson<ImportPlan>(File.ReadAllText(planPath));
            }
            catch (Exception exception)
            {
                Debug.LogException(exception);
                EditorApplication.Exit(2);
                return;
            }

            var issues = new List<ImportIssue>();
            var importedSprites = ConfigureSprites(plan, issues);
            var assetPrefabCount = plan.create_asset_prefabs
                ? CreateAssetPrefabs(plan, importedSprites, issues)
                : 0;
            var screenPrefabCount = CreateScreenPrefabs(plan, importedSprites, issues);
            var previewSceneCount = CreatePreviewScenes(plan, issues, out var previewImageCount);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);

            var report = new ImportReport
            {
                ok = issues.All(issue => issue.severity != "fail"),
                project_id = plan.project_id,
                imported_sprite_count = importedSprites.Count,
                asset_prefab_count = assetPrefabCount,
                screen_prefab_count = screenPrefabCount,
                preview_scene_count = previewSceneCount,
                preview_image_count = previewImageCount,
                issues = issues.ToArray(),
            };
            Directory.CreateDirectory(Path.GetDirectoryName(plan.report_path) ?? ".");
            File.WriteAllText(plan.report_path, JsonUtility.ToJson(report, true));
            Debug.Log($"GameUIImportComplete: sprites={report.imported_sprite_count} assetPrefabs={report.asset_prefab_count} screenPrefabs={report.screen_prefab_count} previewScenes={report.preview_scene_count} previewImages={report.preview_image_count} ok={report.ok}");
            EditorApplication.Exit(report.ok ? 0 : 2);
        }

        private static Dictionary<string, Sprite> ConfigureSprites(ImportPlan plan, ICollection<ImportIssue> issues)
        {
            var result = new Dictionary<string, Sprite>(StringComparer.Ordinal);
            foreach (var spritePlan in plan.sprites ?? Array.Empty<SpritePlan>())
            {
                if (string.IsNullOrWhiteSpace(spritePlan.id) || result.ContainsKey(spritePlan.id))
                {
                    AddIssue(issues, "duplicate-or-empty-sprite-id", spritePlan.id, "Sprite IDs must be unique and non-empty.");
                    continue;
                }

                AssetDatabase.ImportAsset(spritePlan.asset_path, ImportAssetOptions.ForceSynchronousImport);
                var importer = AssetImporter.GetAtPath(spritePlan.asset_path) as TextureImporter;
                if (importer == null)
                {
                    AddIssue(issues, "texture-importer-missing", spritePlan.asset_path, "Asset is not a Unity TextureImporter target.");
                    continue;
                }

                importer.textureType = TextureImporterType.Sprite;
                importer.spriteImportMode = SpriteImportMode.Single;
                importer.alphaIsTransparency = true;
                importer.mipmapEnabled = false;
                importer.wrapMode = TextureWrapMode.Clamp;
                importer.filterMode = FilterMode.Bilinear;
                importer.textureCompression = TextureImporterCompression.Uncompressed;
                importer.spritePixelsPerUnit = Mathf.Max(1f, spritePlan.pixels_per_unit);
                importer.spritePivot = ReadVector2(spritePlan.pivot, new Vector2(0.5f, 0.5f));
                importer.spriteBorder = ReadBorder(spritePlan.border);
                importer.SaveAndReimport();

                var sprite = AssetDatabase.LoadAssetAtPath<Sprite>(spritePlan.asset_path);
                if (sprite == null)
                {
                    AddIssue(issues, "sprite-load-failed", spritePlan.asset_path, "Sprite was not created after import.");
                    continue;
                }
                result.Add(spritePlan.id, sprite);
            }
            return result;
        }

        private static int CreateAssetPrefabs(ImportPlan plan, IReadOnlyDictionary<string, Sprite> sprites, ICollection<ImportIssue> issues)
        {
            var directory = $"{plan.prefab_root}/Assets";
            EnsureAssetDirectory(directory);
            var count = 0;
            foreach (var spritePlan in plan.sprites ?? Array.Empty<SpritePlan>())
            {
                if (!sprites.TryGetValue(spritePlan.id, out var sprite))
                {
                    continue;
                }
                var kind = string.Equals(spritePlan.category, "Button", StringComparison.Ordinal) ? "Button" : "Image";
                var root = CreateVisualObject(spritePlan.id, spritePlan.id, kind, sprite, false, kind == "Button");
                var path = $"{directory}/{SanitizeFileName(spritePlan.id)}.prefab";
                PrefabUtility.SaveAsPrefabAsset(root, path, out var success);
                UnityEngine.Object.DestroyImmediate(root);
                if (!success)
                {
                    AddIssue(issues, "asset-prefab-save-failed", path, "Unity could not save the asset prefab.");
                    continue;
                }
                count++;
            }
            return count;
        }

        private static int CreateScreenPrefabs(ImportPlan plan, IReadOnlyDictionary<string, Sprite> sprites, ICollection<ImportIssue> issues)
        {
            var directory = $"{plan.prefab_root}/Screens";
            EnsureAssetDirectory(directory);
            var count = 0;
            foreach (var screen in plan.screens ?? Array.Empty<ScreenPlan>())
            {
                var root = new GameObject(string.IsNullOrWhiteSpace(screen.name) ? screen.id : screen.name, typeof(RectTransform), typeof(CanvasGroup));
                var rootRect = root.GetComponent<RectTransform>();
                rootRect.anchorMin = rootRect.anchorMax = new Vector2(0.5f, 0.5f);
                rootRect.pivot = new Vector2(0.5f, 0.5f);
                rootRect.sizeDelta = ReadVector2(screen.reference_size, new Vector2(1920f, 1080f));
                var objects = new Dictionary<string, GameObject>(StringComparer.Ordinal);
                foreach (var element in screen.elements ?? Array.Empty<ElementPlan>())
                {
                    sprites.TryGetValue(element.asset_id ?? string.Empty, out var sprite);
                    if (!string.IsNullOrWhiteSpace(element.asset_id) && sprite == null)
                    {
                        AddIssue(issues, "layout-sprite-missing", element.id, $"Unknown sprite ID: {element.asset_id}");
                        continue;
                    }
                    var item = IsLayoutGroup(element.kind)
                        ? CreateLayoutGroupObject(element)
                        : CreateVisualObject(element.id, element.id, element.kind, sprite, element.preserve_aspect, element.raycast_target);
                    var parent = root.transform;
                    if (!string.IsNullOrWhiteSpace(element.parent_id) && objects.TryGetValue(element.parent_id, out var parentObject))
                    {
                        parent = parentObject.transform;
                    }
                    item.transform.SetParent(parent, false);
                    var rect = item.GetComponent<RectTransform>();
                    rect.anchorMin = ReadVector2(element.anchor_min, new Vector2(0.5f, 0.5f));
                    rect.anchorMax = ReadVector2(element.anchor_max, new Vector2(0.5f, 0.5f));
                    rect.pivot = ReadVector2(element.pivot, new Vector2(0.5f, 0.5f));
                    rect.anchoredPosition = ReadVector2(element.anchored_position, Vector2.zero);
                    rect.sizeDelta = ReadVector2(element.size, new Vector2(100f, 100f));
                    var image = item.GetComponent<Image>();
                    if (image != null)
                    {
                        image.color = ReadColor(element.color, Color.white);
                        ConfigureButtonSprites(item, element, sprites, issues);
                    }
                    objects[element.id] = item;
                }
                foreach (var layoutGroup in root.GetComponentsInChildren<LayoutGroup>(true))
                {
                    LayoutRebuilder.ForceRebuildLayoutImmediate(layoutGroup.GetComponent<RectTransform>());
                }

                var path = $"{directory}/{SanitizeFileName(screen.id)}.prefab";
                PrefabUtility.SaveAsPrefabAsset(root, path, out var success);
                UnityEngine.Object.DestroyImmediate(root);
                if (!success)
                {
                    AddIssue(issues, "screen-prefab-save-failed", path, "Unity could not save the screen prefab.");
                    continue;
                }
                count++;
            }
            return count;
        }

        private static int CreatePreviewScenes(ImportPlan plan, ICollection<ImportIssue> issues, out int previewImageCount)
        {
            var directory = $"{plan.generated_root}/Scenes";
            EnsureAssetDirectory(directory);
            Directory.CreateDirectory(plan.preview_output_dir);
            var count = 0;
            previewImageCount = 0;
            foreach (var screen in plan.screens ?? Array.Empty<ScreenPlan>())
            {
                var prefabPath = $"{plan.prefab_root}/Screens/{SanitizeFileName(screen.id)}.prefab";
                var screenPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
                if (screenPrefab == null)
                {
                    AddIssue(issues, "preview-screen-prefab-missing", prefabPath, "Screen prefab is unavailable for preview scene generation.");
                    continue;
                }

                var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                var cameraObject = new GameObject("PreviewCamera", typeof(Camera));
                var camera = cameraObject.GetComponent<Camera>();
                camera.clearFlags = CameraClearFlags.SolidColor;
                camera.backgroundColor = new Color(0.015f, 0.035f, 0.075f, 1f);
                camera.orthographic = true;
                cameraObject.tag = "MainCamera";

                var canvasObject = new GameObject("PreviewCanvas", typeof(RectTransform), typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
                var canvas = canvasObject.GetComponent<Canvas>();
                canvas.renderMode = RenderMode.ScreenSpaceCamera;
                canvas.worldCamera = camera;
                canvas.planeDistance = 1f;
                var scaler = canvasObject.GetComponent<CanvasScaler>();
                scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
                scaler.referenceResolution = ReadVector2(screen.reference_size, new Vector2(1920f, 1080f));
                scaler.screenMatchMode = CanvasScaler.ScreenMatchMode.MatchWidthOrHeight;
                scaler.matchWidthOrHeight = 0.5f;

                var eventSystemObject = new GameObject("EventSystem", typeof(EventSystem), typeof(StandaloneInputModule));
                SceneManager.MoveGameObjectToScene(cameraObject, scene);
                SceneManager.MoveGameObjectToScene(canvasObject, scene);
                SceneManager.MoveGameObjectToScene(eventSystemObject, scene);
                var instance = PrefabUtility.InstantiatePrefab(screenPrefab, scene) as GameObject;
                if (instance == null)
                {
                    AddIssue(issues, "preview-prefab-instantiation-failed", prefabPath, "Screen prefab could not be instantiated in preview scene.");
                    continue;
                }
                instance.transform.SetParent(canvasObject.transform, false);
                var rect = instance.GetComponent<RectTransform>();
                rect.anchorMin = rect.anchorMax = new Vector2(0.5f, 0.5f);
                rect.pivot = new Vector2(0.5f, 0.5f);
                rect.anchoredPosition = Vector2.zero;
                rect.sizeDelta = ReadVector2(screen.reference_size, new Vector2(1920f, 1080f));

                var previewSize = ReadVector2(screen.reference_size, new Vector2(1920f, 1080f));
                var previewPath = Path.Combine(plan.preview_output_dir, $"{SanitizeFileName(screen.id)}.png");
                if (RenderPreview(camera, Mathf.RoundToInt(previewSize.x), Mathf.RoundToInt(previewSize.y), previewPath, issues))
                {
                    previewImageCount++;
                }

                var scenePath = $"{directory}/{SanitizeFileName(screen.id)}-Preview.unity";
                if (!EditorSceneManager.SaveScene(scene, scenePath))
                {
                    AddIssue(issues, "preview-scene-save-failed", scenePath, "Unity could not save the preview scene.");
                    continue;
                }
                count++;
            }
            return count;
        }

        private static bool RenderPreview(Camera camera, int width, int height, string outputPath, ICollection<ImportIssue> issues)
        {
            if (width <= 0 || height <= 0 || width > 4096 || height > 4096)
            {
                AddIssue(issues, "preview-size-invalid", outputPath, $"Preview size {width}x{height} is outside 1..4096.");
                return false;
            }
            RenderTexture renderTexture = null;
            Texture2D texture = null;
            var previous = RenderTexture.active;
            try
            {
                renderTexture = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32);
                camera.targetTexture = renderTexture;
                RenderTexture.active = renderTexture;
                Canvas.ForceUpdateCanvases();
                camera.Render();
                texture = new Texture2D(width, height, TextureFormat.RGBA32, false);
                texture.ReadPixels(new Rect(0, 0, width, height), 0, 0);
                texture.Apply(false, false);
                File.WriteAllBytes(outputPath, texture.EncodeToPNG());
                return true;
            }
            catch (Exception exception)
            {
                AddIssue(issues, "preview-render-failed", outputPath, exception.Message);
                return false;
            }
            finally
            {
                camera.targetTexture = null;
                RenderTexture.active = previous;
                if (renderTexture != null)
                {
                    UnityEngine.Object.DestroyImmediate(renderTexture);
                }
                if (texture != null)
                {
                    UnityEngine.Object.DestroyImmediate(texture);
                }
            }
        }

        private static void ConfigureButtonSprites(
            GameObject item,
            ElementPlan element,
            IReadOnlyDictionary<string, Sprite> sprites,
            ICollection<ImportIssue> issues)
        {
            var button = item.GetComponent<Button>();
            if (button == null)
            {
                return;
            }
            var state = button.spriteState;
            var hasSpriteSwap = false;
            hasSpriteSwap |= AssignStateSprite(element.highlighted_asset_id, "highlighted", sprites, issues, sprite =>
            {
                state.highlightedSprite = sprite;
                state.selectedSprite = sprite;
            });
            hasSpriteSwap |= AssignStateSprite(element.pressed_asset_id, "pressed", sprites, issues, sprite => state.pressedSprite = sprite);
            hasSpriteSwap |= AssignStateSprite(element.disabled_asset_id, "disabled", sprites, issues, sprite => state.disabledSprite = sprite);
            button.spriteState = state;
            button.transition = hasSpriteSwap ? Selectable.Transition.SpriteSwap : Selectable.Transition.ColorTint;
        }

        private static bool AssignStateSprite(
            string assetId,
            string stateName,
            IReadOnlyDictionary<string, Sprite> sprites,
            ICollection<ImportIssue> issues,
            Action<Sprite> assign)
        {
            if (string.IsNullOrWhiteSpace(assetId))
            {
                return false;
            }
            if (!sprites.TryGetValue(assetId, out var sprite))
            {
                AddIssue(issues, "button-state-sprite-missing", assetId, $"Button {stateName} sprite is missing.");
                return false;
            }
            assign(sprite);
            return true;
        }

        private static GameObject CreateVisualObject(string name, string bindingId, string kind, Sprite sprite, bool preserveAspect, bool raycastTarget)
        {
            var item = new GameObject(string.IsNullOrWhiteSpace(name) ? "UIElement" : name, typeof(RectTransform), typeof(CanvasRenderer), typeof(Image), typeof(GameUIElementBinding));
            var image = item.GetComponent<Image>();
            image.sprite = sprite;
            image.preserveAspect = preserveAspect;
            image.raycastTarget = raycastTarget;
            image.type = sprite != null && sprite.border.sqrMagnitude > 0f ? Image.Type.Sliced : Image.Type.Simple;
            item.GetComponent<GameUIElementBinding>().Configure(bindingId);
            if (string.Equals(kind, "Button", StringComparison.Ordinal))
            {
                var button = item.AddComponent<Button>();
                button.targetGraphic = image;
                button.transition = Selectable.Transition.ColorTint;
            }
            return item;
        }

        private static bool IsLayoutGroup(string kind)
        {
            return string.Equals(kind, "HorizontalLayoutGroup", StringComparison.Ordinal)
                || string.Equals(kind, "VerticalLayoutGroup", StringComparison.Ordinal);
        }

        private static GameObject CreateLayoutGroupObject(ElementPlan element)
        {
            var item = new GameObject(
                string.IsNullOrWhiteSpace(element.id) ? "LayoutGroup" : element.id,
                typeof(RectTransform),
                typeof(GameUIElementBinding));
            item.GetComponent<GameUIElementBinding>().Configure(element.id);
            HorizontalOrVerticalLayoutGroup group;
            if (string.Equals(element.kind, "VerticalLayoutGroup", StringComparison.Ordinal))
            {
                group = item.AddComponent<VerticalLayoutGroup>();
            }
            else
            {
                group = item.AddComponent<HorizontalLayoutGroup>();
            }
            group.spacing = element.spacing;
            group.padding = ReadPadding(element.padding);
            group.childAlignment = ReadTextAnchor(element.child_alignment, TextAnchor.MiddleCenter);
            group.childControlWidth = element.control_child_size;
            group.childControlHeight = element.control_child_size;
            group.childForceExpandWidth = element.child_force_expand;
            group.childForceExpandHeight = element.child_force_expand;
            return item;
        }

        private static string ReadArgument(IReadOnlyList<string> args, string name)
        {
            for (var index = 0; index < args.Count - 1; index++)
            {
                if (string.Equals(args[index], name, StringComparison.OrdinalIgnoreCase))
                {
                    return args[index + 1];
                }
            }
            return string.Empty;
        }

        private static Vector2 ReadVector2(IReadOnlyList<float> values, Vector2 fallback)
        {
            return values != null && values.Count == 2 ? new Vector2(values[0], values[1]) : fallback;
        }

        private static Vector4 ReadBorder(IReadOnlyList<int> values)
        {
            return values != null && values.Count == 4
                ? new Vector4(values[0], values[1], values[2], values[3])
                : Vector4.zero;
        }

        private static Color ReadColor(IReadOnlyList<float> values, Color fallback)
        {
            return values != null && values.Count == 4
                ? new Color(values[0], values[1], values[2], values[3])
                : fallback;
        }

        private static RectOffset ReadPadding(IReadOnlyList<int> values)
        {
            return values != null && values.Count == 4
                ? new RectOffset(values[0], values[1], values[2], values[3])
                : new RectOffset();
        }

        private static TextAnchor ReadTextAnchor(string value, TextAnchor fallback)
        {
            return Enum.TryParse(value, false, out TextAnchor parsed) ? parsed : fallback;
        }

        private static void EnsureAssetDirectory(string assetPath)
        {
            var projectRoot = Path.GetDirectoryName(Application.dataPath) ?? Directory.GetCurrentDirectory();
            var physical = Path.Combine(projectRoot, assetPath.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(physical);
        }

        private static string SanitizeFileName(string value)
        {
            var invalid = Path.GetInvalidFileNameChars();
            return new string((value ?? "UI").Select(character => invalid.Contains(character) ? '_' : character).ToArray());
        }

        private static void AddIssue(ICollection<ImportIssue> issues, string code, string target, string message)
        {
            issues.Add(new ImportIssue { code = code, target = target ?? string.Empty, message = message });
            Debug.LogError($"GameUIImportError [{code}] {target}: {message}");
        }
    }
}
