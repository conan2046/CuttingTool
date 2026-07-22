using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using CuttingTool.GameUI;
using TMPro;
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
        private const string FallbackTextFontSourcePath = "Assets/_Project/UI/Fonts/SourceHanSansOLD-Heavy-2.otf";
        private const string FallbackTextFontAssetPath = "Assets/_Project/UI/Fonts/TMP_SourceHanSansOLD Heavy SDF.asset";
        [Serializable]
        private sealed class ImportPlan
        {
            public int schema_version;
            public string project_id = string.Empty;
            public string sprite_root = string.Empty;
            public string screen_prefab_root = string.Empty;
            public string scene_root = string.Empty;
            public string legacy_asset_prefab_root = string.Empty;
            public string report_path = string.Empty;
            public string preview_output_dir = string.Empty;
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
            public string text = string.Empty;
            public float font_size = 32f;
            public string text_alignment = "Center";
            public string font_style = "Normal";
            public string text_overflow = "Ellipsis";
            public bool enable_auto_sizing;
            public float font_size_min = 18f;
            public float font_size_max = 32f;
            public string font_source_path = string.Empty;
            public string font_asset_path = string.Empty;
            public bool preserve_aspect;
            public bool raycast_target;
            public string highlighted_asset_id = string.Empty;
            public string pressed_asset_id = string.Empty;
            public string disabled_asset_id = string.Empty;
            public float[] spacing = Array.Empty<float>();
            public float[] cell_size = Array.Empty<float>();
            public int[] padding = Array.Empty<int>();
            public string constraint = "Flexible";
            public int constraint_count = 1;
            public string start_axis = "Horizontal";
            public string start_corner = "UpperLeft";
            public string child_alignment = "MiddleCenter";
            public bool[] child_control_size = Array.Empty<bool>();
            public bool[] child_force_expand = Array.Empty<bool>();
            public string viewport_id = string.Empty;
            public string content_id = string.Empty;
            public bool horizontal_scroll;
            public bool vertical_scroll = true;
            public string movement_type = "Clamped";
            public float elasticity = 0.1f;
            public bool inertia = true;
            public float deceleration_rate = 0.135f;
            public float scroll_sensitivity = 20f;
            public bool content_size_fitter;
            public string horizontal_fit = "Unconstrained";
            public string vertical_fit = "Unconstrained";
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
            RemoveLegacyAssetPrefabs(plan, issues);
            var importedSprites = ConfigureSprites(plan, issues);
            var screenPrefabCount = CreateScreenPrefabs(plan, importedSprites, issues);
            var previewSceneCount = CreatePreviewScenes(plan, issues, out var previewImageCount);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);

            var report = new ImportReport
            {
                ok = issues.All(issue => issue.severity != "fail"),
                project_id = plan.project_id,
                imported_sprite_count = importedSprites.Count,
                asset_prefab_count = 0,
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

        private static void RemoveLegacyAssetPrefabs(ImportPlan plan, ICollection<ImportIssue> issues)
        {
            if (string.IsNullOrWhiteSpace(plan.legacy_asset_prefab_root) || !AssetDatabase.IsValidFolder(plan.legacy_asset_prefab_root))
            {
                return;
            }
            if (!AssetDatabase.DeleteAsset(plan.legacy_asset_prefab_root))
            {
                AddIssue(issues, "legacy-asset-prefab-delete-failed", plan.legacy_asset_prefab_root, "Unity could not remove the obsolete per-asset prefab directory.");
            }
        }

        private static int CreateScreenPrefabs(ImportPlan plan, IReadOnlyDictionary<string, Sprite> sprites, ICollection<ImportIssue> issues)
        {
            var directory = plan.screen_prefab_root;
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
                    var item = CreateElementObject(element, sprite, issues);
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
                    }
                    var text = item.GetComponent<TextMeshProUGUI>();
                    if (text != null)
                    {
                        text.color = ReadColor(element.color, Color.white);
                    }
                    ConfigureLayoutGroup(item, element, issues);
                    ConfigureContentSizeFitter(item, element, issues);
                    ConfigureButtonSprites(item, element, sprites, issues);
                    objects[element.id] = item;
                }
                ConfigureScrollViews(screen.elements, objects, issues);

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
            var directory = plan.scene_root;
            EnsureAssetDirectory(directory);
            Directory.CreateDirectory(plan.preview_output_dir);
            var count = 0;
            previewImageCount = 0;
            foreach (var screen in plan.screens ?? Array.Empty<ScreenPlan>())
            {
                var prefabPath = $"{plan.screen_prefab_root}/{SanitizeFileName(screen.id)}.prefab";
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

        private static GameObject CreateElementObject(ElementPlan element, Sprite sprite, ICollection<ImportIssue> issues)
        {
            if (string.Equals(element.kind, "Text", StringComparison.Ordinal))
            {
                return CreateTextObject(element, issues);
            }
            if (string.Equals(element.kind, "ScrollView", StringComparison.Ordinal))
            {
                var scrollView = new GameObject(
                    string.IsNullOrWhiteSpace(element.id) ? "ScrollView" : element.id,
                    typeof(RectTransform),
                    typeof(CanvasRenderer),
                    typeof(Image),
                    typeof(ScrollRect),
                    typeof(GameUIElementBinding));
                var image = scrollView.GetComponent<Image>();
                image.color = Color.clear;
                image.raycastTarget = true;
                scrollView.GetComponent<GameUIElementBinding>().Configure(element.id);
                return scrollView;
            }
            if (string.Equals(element.kind, "ScrollViewport", StringComparison.Ordinal))
            {
                var viewport = new GameObject(
                    string.IsNullOrWhiteSpace(element.id) ? "Viewport" : element.id,
                    typeof(RectTransform),
                    typeof(RectMask2D),
                    typeof(GameUIElementBinding));
                viewport.GetComponent<GameUIElementBinding>().Configure(element.id);
                return viewport;
            }
            if (element.kind.EndsWith("LayoutGroup", StringComparison.Ordinal))
            {
                var container = new GameObject(
                    string.IsNullOrWhiteSpace(element.id) ? "LayoutGroup" : element.id,
                    typeof(RectTransform),
                    typeof(GameUIElementBinding));
                container.GetComponent<GameUIElementBinding>().Configure(element.id);
                if (string.Equals(element.kind, "GridLayoutGroup", StringComparison.Ordinal))
                {
                    container.AddComponent<GridLayoutGroup>();
                }
                else if (string.Equals(element.kind, "HorizontalLayoutGroup", StringComparison.Ordinal))
                {
                    container.AddComponent<HorizontalLayoutGroup>();
                }
                else
                {
                    container.AddComponent<VerticalLayoutGroup>();
                }
                return container;
            }
            return CreateVisualObject(element.id, element.id, element.kind, sprite, element.preserve_aspect, element.raycast_target);
        }

        private static GameObject CreateTextObject(ElementPlan element, ICollection<ImportIssue> issues)
        {
            var item = new GameObject(
                string.IsNullOrWhiteSpace(element.id) ? "Text" : element.id,
                typeof(RectTransform),
                typeof(CanvasRenderer),
                typeof(TextMeshProUGUI),
                typeof(GameUIElementBinding));
            var label = item.GetComponent<TextMeshProUGUI>();
            label.font = ResolveTextFont(element, issues);
            label.text = element.text ?? string.Empty;
            label.fontSize = Mathf.Max(1f, element.font_size);
            label.enableAutoSizing = element.enable_auto_sizing;
            label.fontSizeMin = Mathf.Max(1f, element.font_size_min);
            label.fontSizeMax = Mathf.Max(label.fontSizeMin, element.font_size_max);
            label.alignment = ReadEnum(element.text_alignment, TextAlignmentOptions.Center, issues, element.id, "text-alignment-invalid");
            label.fontStyle = ReadEnum(element.font_style, FontStyles.Normal, issues, element.id, "text-font-style-invalid");
            label.overflowMode = ReadEnum(element.text_overflow, TextOverflowModes.Ellipsis, issues, element.id, "text-overflow-invalid");
            label.raycastTarget = element.raycast_target;
            item.GetComponent<GameUIElementBinding>().Configure(element.id);
            return item;
        }

        private static TMP_FontAsset ResolveTextFont(ElementPlan element, ICollection<ImportIssue> issues)
        {
            if (string.IsNullOrWhiteSpace(element.font_source_path) && string.IsNullOrWhiteSpace(element.font_asset_path))
            {
                if (!EnsureTmpEssentialResources(issues, element.id))
                {
                    return null;
                }
                var projectDefaultFont = TMP_Settings.defaultFontAsset;
                if (projectDefaultFont != null && HasUsableAtlas(projectDefaultFont))
                {
                    var defaultFontIssues = new List<ImportIssue>();
                    if (EnsureTextCharacters(projectDefaultFont, element, defaultFontIssues))
                    {
                        return projectDefaultFont;
                    }
                }
                element.font_source_path = FallbackTextFontSourcePath;
                element.font_asset_path = FallbackTextFontAssetPath;
                Debug.Log($"TMP project default font is unavailable; using fallback: {FallbackTextFontAssetPath}");
            }
            if (string.IsNullOrWhiteSpace(element.font_source_path) || string.IsNullOrWhiteSpace(element.font_asset_path))
            {
                AddIssue(issues, "text-font-path-incomplete", element.id, "TMP source font and font asset paths must be provided together.");
                return null;
            }
            var sourceFont = AssetDatabase.LoadAssetAtPath<Font>(element.font_source_path);
            if (sourceFont == null)
            {
                AddIssue(issues, "text-font-source-missing", element.id, $"TMP source font is unavailable: {element.font_source_path}");
                return null;
            }
            var fontAsset = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(element.font_asset_path);
            if (fontAsset != null && (!HasUsableAtlas(fontAsset) || fontAsset.sourceFontFile != sourceFont))
            {
                Debug.Log($"Recreating stale or incomplete TMP font asset: {element.font_asset_path}");
                AssetDatabase.DeleteAsset(element.font_asset_path);
                fontAsset = null;
            }
            if (fontAsset != null)
            {
                return EnsureTextCharacters(fontAsset, element, issues) ? fontAsset : null;
            }
            if (!EnsureTmpEssentialResources(issues, element.id))
            {
                return null;
            }
            EnsureAssetDirectory(Path.GetDirectoryName(element.font_asset_path) ?? "Assets");
            fontAsset = TMP_FontAsset.CreateFontAsset(sourceFont);
            if (fontAsset == null)
            {
                AddIssue(issues, "text-font-asset-create-failed", element.id, $"TMP font asset could not be created from: {element.font_source_path}");
                return null;
            }
            fontAsset.atlasPopulationMode = AtlasPopulationMode.Dynamic;
            AssetDatabase.CreateAsset(fontAsset, element.font_asset_path);
            AssetDatabase.AddObjectToAsset(fontAsset.atlasTextures[0], fontAsset);
            AssetDatabase.AddObjectToAsset(fontAsset.material, fontAsset);
            AssetDatabase.SaveAssets();
            return EnsureTextCharacters(fontAsset, element, issues) ? fontAsset : null;
        }

        private static bool HasUsableAtlas(TMP_FontAsset fontAsset)
        {
            return fontAsset.atlasTextures != null
                && fontAsset.atlasTextures.Length > 0
                && fontAsset.atlasTextures[0] != null
                && fontAsset.material != null;
        }

        private static bool EnsureTextCharacters(TMP_FontAsset fontAsset, ElementPlan element, ICollection<ImportIssue> issues)
        {
            if (fontAsset == null || string.IsNullOrWhiteSpace(element.text))
            {
                return fontAsset != null;
            }
            if (fontAsset.HasCharacters(element.text))
            {
                return true;
            }
            if (!fontAsset.TryAddCharacters(element.text, out var missingCharacters))
            {
                AddIssue(issues, "text-font-glyphs-missing", element.id, $"TMP font is missing glyphs: {missingCharacters}");
                return false;
            }
            EditorUtility.SetDirty(fontAsset);
            return true;
        }

        private static bool EnsureTmpEssentialResources(ICollection<ImportIssue> issues, string target)
        {
            if (Resources.Load<TMP_Settings>("TMP Settings") != null && Shader.Find("TextMeshPro/Mobile/Distance Field") != null)
            {
                return true;
            }
            var package = UnityEditor.PackageManager.PackageInfo.FindForPackageName("com.unity.textmeshpro");
            var resourcePackage = package == null
                ? string.Empty
                : Path.Combine(package.resolvedPath, "Package Resources", "TMP Essential Resources.unitypackage");
            if (string.IsNullOrWhiteSpace(resourcePackage) || !File.Exists(resourcePackage))
            {
                AddIssue(issues, "tmp-essential-resources-missing", target, "TextMeshPro Essential Resources package is unavailable.");
                return false;
            }
            AssetDatabase.ImportPackage(resourcePackage, false);
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            if (Resources.Load<TMP_Settings>("TMP Settings") == null || Shader.Find("TextMeshPro/Mobile/Distance Field") == null)
            {
                AddIssue(issues, "tmp-essential-resources-import-failed", target, "TextMeshPro Essential Resources could not be imported.");
                return false;
            }
            return true;
        }

        private static void ConfigureLayoutGroup(GameObject item, ElementPlan element, ICollection<ImportIssue> issues)
        {
            var layoutGroup = item.GetComponent<LayoutGroup>();
            if (layoutGroup == null)
            {
                return;
            }
            layoutGroup.padding = ReadPadding(element.padding);
            layoutGroup.childAlignment = ReadEnum(element.child_alignment, TextAnchor.MiddleCenter, issues, element.id, "child-alignment-invalid");
            if (layoutGroup is GridLayoutGroup grid)
            {
                grid.cellSize = ReadVector2(element.cell_size, new Vector2(100f, 100f));
                grid.spacing = ReadVector2(element.spacing, Vector2.zero);
                grid.constraint = ReadEnum(element.constraint, GridLayoutGroup.Constraint.Flexible, issues, element.id, "grid-constraint-invalid");
                grid.constraintCount = Mathf.Max(1, element.constraint_count);
                grid.startAxis = ReadEnum(element.start_axis, GridLayoutGroup.Axis.Horizontal, issues, element.id, "grid-start-axis-invalid");
                grid.startCorner = ReadEnum(element.start_corner, GridLayoutGroup.Corner.UpperLeft, issues, element.id, "grid-start-corner-invalid");
                return;
            }
            if (layoutGroup is HorizontalOrVerticalLayoutGroup linear)
            {
                linear.spacing = element.spacing != null && element.spacing.Length > 0 ? element.spacing[0] : 0f;
                linear.childControlWidth = ReadBool(element.child_control_size, 0, false);
                linear.childControlHeight = ReadBool(element.child_control_size, 1, false);
                linear.childForceExpandWidth = ReadBool(element.child_force_expand, 0, false);
                linear.childForceExpandHeight = ReadBool(element.child_force_expand, 1, false);
            }
        }

        private static void ConfigureContentSizeFitter(GameObject item, ElementPlan element, ICollection<ImportIssue> issues)
        {
            if (!element.content_size_fitter)
            {
                return;
            }
            var fitter = item.GetComponent<ContentSizeFitter>() ?? item.AddComponent<ContentSizeFitter>();
            fitter.horizontalFit = ReadEnum(element.horizontal_fit, ContentSizeFitter.FitMode.Unconstrained, issues, element.id, "content-horizontal-fit-invalid");
            fitter.verticalFit = ReadEnum(element.vertical_fit, ContentSizeFitter.FitMode.Unconstrained, issues, element.id, "content-vertical-fit-invalid");
        }

        private static void ConfigureScrollViews(
            IEnumerable<ElementPlan> elements,
            IReadOnlyDictionary<string, GameObject> objects,
            ICollection<ImportIssue> issues)
        {
            foreach (var element in elements ?? Array.Empty<ElementPlan>())
            {
                if (!string.Equals(element.kind, "ScrollView", StringComparison.Ordinal) ||
                    !objects.TryGetValue(element.id, out var item))
                {
                    continue;
                }
                var scrollRect = item.GetComponent<ScrollRect>();
                if (scrollRect == null ||
                    !objects.TryGetValue(element.viewport_id, out var viewportObject) ||
                    !objects.TryGetValue(element.content_id, out var contentObject))
                {
                    AddIssue(issues, "scroll-view-reference-missing", element.id, "ScrollView viewport or content is missing.");
                    continue;
                }
                scrollRect.viewport = viewportObject.GetComponent<RectTransform>();
                scrollRect.content = contentObject.GetComponent<RectTransform>();
                scrollRect.horizontal = element.horizontal_scroll;
                scrollRect.vertical = element.vertical_scroll;
                scrollRect.movementType = ReadEnum(element.movement_type, ScrollRect.MovementType.Clamped, issues, element.id, "scroll-movement-type-invalid");
                scrollRect.elasticity = Mathf.Max(0f, element.elasticity);
                scrollRect.inertia = element.inertia;
                scrollRect.decelerationRate = Mathf.Max(0f, element.deceleration_rate);
                scrollRect.scrollSensitivity = Mathf.Max(0f, element.scroll_sensitivity);
                scrollRect.horizontalNormalizedPosition = 0f;
                scrollRect.verticalNormalizedPosition = 1f;
            }
        }

        private static RectOffset ReadPadding(IReadOnlyList<int> values)
        {
            return values != null && values.Count == 4
                ? new RectOffset(values[0], values[1], values[2], values[3])
                : new RectOffset();
        }

        private static bool ReadBool(IReadOnlyList<bool> values, int index, bool fallback)
        {
            return values != null && values.Count > index ? values[index] : fallback;
        }

        private static T ReadEnum<T>(string value, T fallback, ICollection<ImportIssue> issues, string target, string code) where T : struct
        {
            if (!string.IsNullOrWhiteSpace(value) && Enum.TryParse(value, true, out T parsed))
            {
                return parsed;
            }
            AddIssue(issues, code, target, $"Unsupported {typeof(T).Name} value: {value}");
            return fallback;
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
