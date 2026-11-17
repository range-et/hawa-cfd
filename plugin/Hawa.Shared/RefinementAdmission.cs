using System.Text.Json.Nodes;

namespace Hawa.Shared;
/// <summary>Cheap immutable relationship admission; no runtime, geometry sampling or solver allocation.</summary>
public static class RefinementAdmission
{
    public static void Require(JsonObject coarse, JsonObject fine)
    {
        GeometryDomain.Require(coarse);
        GeometryDomain.Require(fine);
        var lower = fine["refinement_lower"] as JsonArray;
        var upper = fine["refinement_upper"] as JsonArray;
        if (lower == null || upper == null || lower.Count != 3 || upper.Count != 3)
            throw new ArgumentException("Fine case needs three parent patch indices for lower and upper corners.");
        for (int a = 0; a < 3; a++)
        {
            if (lower[a] is not JsonValue loValue || !loValue.TryGetValue<int>(out int lo) ||
                upper[a] is not JsonValue hiValue || !hiValue.TryGetValue<int>(out int hi))
                throw new ArgumentException("Fine case patch corners must be integer parent indices.");
            if (lo < 2 || hi > coarse["shape"]![a]!.GetValue<int>() - 3 || hi - lo < 4)
                throw new ArgumentException("Fine case needs cubic-stencil clearance inside the coarse case and at least four coarse intervals per axis.");
            if (fine["shape"]![a]!.GetValue<int>() != 2 * (hi - lo) + 1)
                throw new ArgumentException("Fine case resolution must equal 2*(upper-lower)+1.");
        }
        double dx = coarse["dx"]!.GetValue<double>();
        if (Math.Abs(2 * fine["dx"]!.GetValue<double>() - dx) > 1e-8 + 1e-5 * Math.Abs(dx))
            throw new ArgumentException("Fine cell size must be half the coarse size.");
        if ((coarse["basis"] == null) != (fine["basis"] == null))
            throw new ArgumentException("Coarse and fine grid axes must match.");
        if (coarse["basis"] != null)
            for (int a = 0; a < 3; a++)
                for (int b = 0; b < 3; b++)
                    if (coarse["basis"]![a]![b]!.GetValue<double>() != fine["basis"]![a]![b]!.GetValue<double>())
                        throw new ArgumentException("Coarse and fine grid axes must match.");
        for (int a = 0; a < 3; a++)
        {
            double expected = coarse["origin"]![a]!.GetValue<double>();
            for (int b = 0; b < 3; b++)
                expected += lower[b]!.GetValue<int>() * (coarse["basis"]?[b]?[a]?.GetValue<double>() ?? (a == b ? 1d : 0d)) * coarse["spacing"]!.GetValue<double>();
            if (Math.Abs(expected - fine["origin"]![a]!.GetValue<double>()) > 1e-7)
                throw new ArgumentException($"Fine grid origin does not match its parent patch on axis {a}: expected {expected:R}, got {fine["origin"]![a]}.");
        }
    }
}
