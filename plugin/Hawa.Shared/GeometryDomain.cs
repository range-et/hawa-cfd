using System.Text.Json.Nodes;

namespace Hawa.Shared;
/// <summary>Structural checks available before standalone GH obstacle voxelization.
/// Physics/device/capture budgets remain case-level checks, since a Domain has no
/// physics, memory budget or capture settings. Native cases preflight their spec.</summary>
public static class GeometryDomain
{
    public static void Require(JsonObject domain)
    {
        var n = domain["shape"] as JsonArray;
        if (n == null || n.Count != 3)
            throw new ArgumentException("Domain needs three lattice dimensions. Connect Hawa Domain.");
        double count = 1;
        foreach (var value in n)
        {
            if (value is not JsonValue v || !v.TryGetValue<int>(out int size) || size < 4 || size > 2_000_000)
                throw new ArgumentException("Domain needs at least four sites per axis and at most 2,000,000 cells. Increase cell size or reduce the domain.");
            count *= size;
        }
        if (count > 2_000_000)
            throw new ArgumentException("Domain exceeds 2,000,000 cells. Increase cell size or reduce the domain.");
        foreach (var key in new[] { "spacing", "dx" })
        {
            if (domain[key] is not JsonValue value || !value.TryGetValue<double>(out double size) || !double.IsFinite(size) || size <= 0)
                throw new ArgumentException($"Domain {key} must be finite and positive. Connect Hawa Domain with positive cell size.");
        }
        var origin = domain["origin"] as JsonArray;
        if (origin == null || origin.Count != 3 || origin.Any(v =>
            v is not JsonValue value || !value.TryGetValue<double>(out double number) || !double.IsFinite(number)
        ))
            throw new ArgumentException("Domain origin needs three finite coordinates.");
        if (domain["basis"] == null)
            return;
        var axes = domain["basis"] as JsonArray;
        if (axes == null || axes.Count != 3)
            throw new ArgumentException("Domain basis needs three orthonormal axes.");
        var vectors = new double[3][];
        for (int i = 0; i < 3; i++)
        {
            var axis = axes[i] as JsonArray;
            if (axis == null || axis.Count != 3 || axis.Any(v =>
                v is not JsonValue value || !value.TryGetValue<double>(out double number) || !double.IsFinite(number)
            ))
                throw new ArgumentException("Domain basis needs three finite orthonormal axes.");
            vectors[i] = axis.Select(v =>
                v!.GetValue<double>()
            ).ToArray();
            for (int j = 0; j <= i; j++)
            {
                double dot = 0;
                for (int k = 0; k < 3; k++)
                    dot += vectors[i][k] * vectors[j][k];
                if (Math.Abs(dot - (i == j ? 1 : 0)) > 1e-8)
                    throw new ArgumentException("Domain basis must be orthonormal. Connect an oriented Hawa Domain box.");
            }
        }
    }
}
