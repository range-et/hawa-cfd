using System.Text.Json.Nodes;

namespace Hawa.Shared;
// Plain-language lifecycle states shared by the GH components and the native
// panel (#74). Status text only: it never changes what runs or is cancelled.
public static class LifecycleText
{
    public const string DocumentInactive = "cancelled: document inactive";
    public const string DocumentInactiveReason = "Cancelled because another Grasshopper document became active. Only the active document runs Hawa jobs; recompute this document to restart.";
    public const string WaitingForInput = "waiting for input";
    public const string Failed = "failed";

    // A background job before its session exists: waiting for the single
    // device slot is not preparation.
    public static string Pending(string jobState) =>
        jobState == "queued" ? "queued: waiting for the device" : "preparing"
    ;

    // Why a new job replaced the previous one, naming the inputs that changed.
    public static string? Restart(JsonObject? previous, JsonObject next)
    {
        if (previous == null)
            return null;
        var changed = next.Select(p =>
            p.Key
        ).Union(previous.Select(p =>
            p.Key
        )).Where(k =>
            previous[k]?.ToJsonString() != next[k]?.ToJsonString()
        ).ToArray();
        return changed.Length == 0 ? null : "restarted: " + string.Join(", ", changed) + " changed";
    }

    // Wired sources that delivered nothing, by name, so a cancelled or failed
    // child is reported instead of silently leaving a composed view.
    public static string? Missing(IReadOnlyList<(string Name, bool Empty)> sources)
    {
        var empty = sources.Where(s =>
            s.Empty
        ).Select(s =>
            s.Name
        ).ToArray();
        return empty.Length == 0 ? null : $"{empty.Length} of {sources.Count} wired inputs delivered no frame (cancelled, failed or still running upstream): {string.Join(", ", empty)}";
    }

    public static string? Duplicates(IReadOnlyList<string> frames)
    {
        int extra = frames.Count - frames.Distinct().Count();
        return extra == 0 ? null : $"{extra} duplicate frame{(extra == 1 ? " is" : "s are")} used once";
    }
}
