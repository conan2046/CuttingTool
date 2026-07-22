using System;
using System.IO;
using System.Linq;
using CuttingTool.GameUI;
using UnityEditor;
using UnityEngine;

namespace CuttingTool.GameUI.Editor
{
    public static class GameUIInteractionVerifier
    {
        [Serializable]
        private sealed class Report
        {
            public bool ok;
            public string prefab = string.Empty;
            public int entry_count;
            public bool default_state_ok;
            public bool second_button_state_ok;
            public bool first_button_restore_ok;
            public string[] issues = Array.Empty<string>();
        }

        public static void RunFromCommandLine()
        {
            var args = Environment.GetCommandLineArgs();
            var prefabPath = ReadArgument(args, "-gameUIPrefab");
            var reportPath = ReadArgument(args, "-gameUIInteractionReport");
            var report = new Report { prefab = prefabPath };
            var issues = new System.Collections.Generic.List<string>();
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
            if (prefab == null)
            {
                issues.Add("prefab-missing");
            }
            else
            {
                var instance = UnityEngine.Object.Instantiate(prefab);
                try
                {
                    var switcher = instance.GetComponent<GameUIViewSwitcher>();
                    if (switcher == null)
                    {
                        issues.Add("switcher-missing");
                    }
                    else
                    {
                        switcher.SendMessage("Awake");
                        report.entry_count = switcher.EntryCount;
                        if (switcher.EntryCount != 2 || Enumerable.Range(0, switcher.EntryCount).Any(index => switcher.GetButton(index) == null || switcher.GetTarget(index) == null))
                        {
                            issues.Add("toggle-binding-invalid");
                        }
                        else
                        {
                            report.default_state_ok = switcher.GetTarget(0).activeSelf && !switcher.GetTarget(1).activeSelf;
                            switcher.GetButton(1).onClick.Invoke();
                            report.second_button_state_ok = !switcher.GetTarget(0).activeSelf && switcher.GetTarget(1).activeSelf;
                            switcher.GetButton(0).onClick.Invoke();
                            report.first_button_restore_ok = switcher.GetTarget(0).activeSelf && !switcher.GetTarget(1).activeSelf;
                            if (!report.default_state_ok) issues.Add("default-state-invalid");
                            if (!report.second_button_state_ok) issues.Add("second-button-did-not-switch");
                            if (!report.first_button_restore_ok) issues.Add("first-button-did-not-restore");
                        }
                    }
                }
                finally
                {
                    UnityEngine.Object.DestroyImmediate(instance);
                }
            }
            report.issues = issues.ToArray();
            report.ok = issues.Count == 0;
            Directory.CreateDirectory(Path.GetDirectoryName(reportPath) ?? ".");
            File.WriteAllText(reportPath, JsonUtility.ToJson(report, true));
            Debug.Log($"GameUIInteractionVerificationComplete: ok={report.ok} issues={issues.Count}");
            EditorApplication.Exit(report.ok ? 0 : 2);
        }

        private static string ReadArgument(string[] args, string name)
        {
            for (var index = 0; index < args.Length - 1; index++)
            {
                if (string.Equals(args[index], name, StringComparison.Ordinal)) return args[index + 1];
            }
            return string.Empty;
        }
    }
}
