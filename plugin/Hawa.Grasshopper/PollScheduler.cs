using Grasshopper.Kernel;
using Eto.Forms;

namespace Hawa.Grasshopper;
/// <summary>Retained UI polling; independent GH solutions cannot erase requests.</summary>
public static class HawaPollScheduler
{
    private sealed record Entry(GH_Document Document, Func<bool> Current, long Due, int Delay);
    private static readonly Dictionary<GH_Component, Entry> pending = new(ReferenceEqualityComparer.Instance);
    private static readonly HashSet<GH_Component> solved = new(ReferenceEqualityComparer.Instance);
    private static UITimer? timer;
    private static bool draining;
    public static int PendingCount => pending.Count;

    // Called only from the host UI thread. The predicate captures a generation
    // or job identity, never waits on a worker, and becomes false after cleanup.
    public static void Request(GH_Component component, Func<bool> current, int delay = 100)
    {
        var document = component.OnPingDocument();
        if (document == null)
            return;
        if (draining)
            solved.Add(component);
        long due = Environment.TickCount64 + delay;
        if (pending.TryGetValue(component, out var old) && old.Document == document)
            due = Math.Min(due, old.Due);
        pending[component] = new(document, current, due, delay);
        // Idle alone need not wake again after the due time. Own the UI timer
        // so this works even when the native Hawa panel has never been loaded.
        if (timer == null)
        {
            timer = new UITimer
            {
                Interval = .1
            };
            timer.Elapsed += Drain;
            timer.Start();
        }
    }

    public static void Cancel(GH_Component component)
    {
        if (draining)
            solved.Add(component);
        pending.Remove(component);
        UnsubscribeIfEmpty();
    }

    internal static void NoteSolved(GH_Component component)
    {
        if (draining)
            solved.Add(component);
    }

    private static void UnsubscribeIfEmpty()
    {
        if (timer != null && pending.Count == 0)
        {
            timer.Stop();
            timer.Elapsed -= Drain;
            timer.Dispose();
            timer = null;
        }
    }

    private static void Drain(object? sender, EventArgs args)
    {
        if (draining)
            return;
        draining = true;
        try
        {
            var ready = new List<(GH_Component Component, Entry Entry)>();
            foreach (var item in pending.ToArray())
            {
                var c = item.Key;
                var e = item.Value;
                bool current;
                try
                {
                    current = c.OnPingDocument() == e.Document && global::Grasshopper.Instances.DocumentServer.Any(d =>
                        ReferenceEquals(d, e.Document)
                    ) && !c.Locked && e.Current();
                }
                catch (Exception ex)
                {
                    pending.Remove(c);
                    c.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Refresh identity: " + ex.GetBaseException().Message);
                    continue;
                }

                if (!current)
                {
                    pending.Remove(c);
                    continue;
                }

                if (!GH_Document.EnableSolutions || !e.Document.Enabled || e.Document.SolutionDepth != 0 || Environment.TickCount64 < e.Due)
                    continue;
                pending.Remove(c);
                ready.Add((c, e));
            }

            foreach (var group in ready.GroupBy(x =>
                x.Entry.Document
            ))
            {
                // Expire outside a solution, then solve once for the whole group.
                // New requests registered by that solution stay in the registry.
                solved.Clear();
                try
                {
                    foreach (var item in group)
                        item.Component.ExpireSolution(false);
                    group.Key.NewSolution(false);
                }
                catch (Exception ex)
                {
                    foreach (var item in group)
                    {
                        item.Component.Message = "refresh failed";
                        item.Component.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, ex.GetBaseException().Message);
                    }
                    continue;
                }

                // If Grasshopper aborted or skipped solving a scheduled component
                // without throwing (#122), retain its poll so the next tick retries
                // rather than stalling with empty outputs and PendingCount == 0.
                foreach (var item in group)
                {
                    var c = item.Component;
                    var e = item.Entry;
                    if (c is not HawaComponent || solved.Contains(c) || pending.ContainsKey(c))
                        continue;
                    bool stillCurrent;
                    try
                    {
                        stillCurrent = c.OnPingDocument() == e.Document && global::Grasshopper.Instances.DocumentServer.Any(d =>
                            ReferenceEquals(d, e.Document)
                        ) && !c.Locked && e.Current();
                    }
                    catch (Exception ex)
                    {
                        c.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, "Refresh identity: " + ex.GetBaseException().Message);
                        continue;
                    }
                    if (stillCurrent)
                        pending[c] = new(e.Document, e.Current, Environment.TickCount64 + Math.Max(e.Delay, 0), e.Delay);
                }
            }
        }
        finally
        {
            solved.Clear();
            draining = false;
            UnsubscribeIfEmpty();
        }
    }
}
