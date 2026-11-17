using Eto.Forms;
using Hawa.Shared;
using System.Text.Json.Nodes;

namespace Hawa.Native;
public sealed partial class HawaPanel
{
    private string viewDraftError = "";

    private void WireDynamicControls()
    {
        foreach (var input in origin.Concat(size).Concat(new[] { viscosity, density, mach }))
            input.ValueChanged += SetupChanged;
        curvedWalls.CheckedChanged += SetupChanged;
        collision.SelectedIndexChanged += SetupChanged;
        for (int index = 2; index < boundaries.Length; index++)
        {
            int face = index;
            boundaries[index].SelectedIndexChanged += (_, _) =>
            {
                BoundaryChanged(face);
            };
        }
        axis.SelectedIndexChanged += ViewChanged;
        palette.SelectedIndexChanged += ViewChanged;
        foreach (var input in new[] { position, low, high })
            input.ValueChanged += ViewChanged;
        foreach (var input in new[] { autoRange, showDomain, showBody, showField, showAnnotations })
            input.CheckedChanged += ViewChanged;
    }

    private void SetupChanged(object? sender, EventArgs e)
    {
        if (!refreshing && CaseHub.Find(document) != null && collision.SelectedIndex >= 0)
            Safe(ApplySetup);
    }

    private void BoundaryChanged(int face)
    {
        if (refreshing || CaseHub.Find(document) == null || boundaries[face].SelectedIndex < 0)
            return;
        Safe(() =>
        {
            var c = CaseHub.Find(document)!;
            var setup = c.Setup;
            var values = setup["boundaries"]!.AsArray();
            string choice = boundaries[face].SelectedValue.ToString()!;
            int opposite = face ^ 1;
            // A periodic boundary is a pair: enter and leave it in one accepted edit.
            if (choice == "periodic" || values[opposite]!.GetValue<string>() == "periodic")
                values[opposite] = choice;
            values[face] = choice;
            CaseHub.Edit(document, new() { ["setup"] = setup }, displayedVersion);
        });
    }

    private void ViewChanged(object? sender, EventArgs e)
    {
        if (refreshing || CaseHub.Find(document) == null || axis.SelectedIndex < 0 || palette.SelectedIndex < 0)
            return;
        if (high.Value <= low.Value)
        {
            // Keep the last accepted view while the user edits the second limit.
            // An external settings/version change refreshes both controls from accepted state.
            viewDraftError = "Set the upper colour limit above the lower limit. The accepted view is unchanged.";
            error.Text = viewDraftError;
            return;
        }
        viewDraftError = "";
        Safe(ApplyView);
    }
}
