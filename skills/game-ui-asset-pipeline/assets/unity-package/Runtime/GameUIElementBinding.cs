using UnityEngine;

namespace CuttingTool.GameUI
{
    [DisallowMultipleComponent]
    public sealed class GameUIElementBinding : MonoBehaviour
    {
        [SerializeField] private string bindingId = string.Empty;

        public string BindingId => bindingId;

        public void Configure(string value)
        {
            bindingId = value ?? string.Empty;
        }
    }
}
