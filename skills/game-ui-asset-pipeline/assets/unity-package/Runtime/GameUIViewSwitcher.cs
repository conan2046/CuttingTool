using System;
using UnityEngine;
using UnityEngine.UI;

namespace CuttingTool.GameUI
{
    [DisallowMultipleComponent]
    public sealed class GameUIViewSwitcher : MonoBehaviour
    {
        [Serializable]
        public sealed class Entry
        {
            public Button button;
            public GameObject target;
        }

        [SerializeField] private string bindingId = string.Empty;
        [SerializeField] private Entry[] entries = Array.Empty<Entry>();
        [SerializeField] private int defaultIndex;
        private bool initialized;

        public string BindingId => bindingId;
        public int ActiveIndex { get; private set; } = -1;
        public int EntryCount => entries?.Length ?? 0;

        public Button GetButton(int index) => index >= 0 && index < EntryCount ? entries[index]?.button : null;
        public GameObject GetTarget(int index) => index >= 0 && index < EntryCount ? entries[index]?.target : null;

        public void Configure(string id, Button[] buttons, GameObject[] targets, int initialIndex)
        {
            bindingId = id ?? string.Empty;
            var count = Math.Min(buttons?.Length ?? 0, targets?.Length ?? 0);
            entries = new Entry[count];
            for (var index = 0; index < count; index++)
            {
                entries[index] = new Entry { button = buttons[index], target = targets[index] };
            }
            defaultIndex = Mathf.Clamp(initialIndex, 0, Math.Max(0, count - 1));
            initialized = false;
            Bind();
        }

        private void Awake()
        {
            Bind();
        }

        private void Bind()
        {
            if (initialized)
            {
                return;
            }
            initialized = true;
            for (var index = 0; index < entries.Length; index++)
            {
                var capturedIndex = index;
                if (entries[index]?.button != null)
                {
                    entries[index].button.onClick.AddListener(() => Show(capturedIndex));
                }
            }
            Show(defaultIndex);
        }

        public void Show(int index)
        {
            if (entries.Length == 0)
            {
                ActiveIndex = -1;
                return;
            }
            index = Mathf.Clamp(index, 0, entries.Length - 1);
            for (var entryIndex = 0; entryIndex < entries.Length; entryIndex++)
            {
                if (entries[entryIndex]?.target != null)
                {
                    entries[entryIndex].target.SetActive(entryIndex == index);
                }
            }
            ActiveIndex = index;
        }
    }
}
