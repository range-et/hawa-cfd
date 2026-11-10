using Rhino.Geometry;

namespace Hawa.Shared;
/// <summary>Surface approximation in the same length units as the input geometry.</summary>
public static class SurfaceMeshing
{
    public static Mesh Create(Brep brep, double cell)
    {
        if (!double.IsFinite(cell) || cell <= 0 || !brep.IsValid || !brep.IsSolid)
            throw new ArgumentException("Provide a valid closed solid and positive cell size");
        // Near-tangent link positions amplify surface error. Scale the chord
        // tolerance quadratically with grid spacing relative to body extent.
        double tolerance = Math.Min(cell * .002, .01 * cell * cell / brep.GetBoundingBox(true).Diagonal.Length);
        using var parameters = new MeshingParameters
        {
            Tolerance = tolerance,
            MinimumTolerance = tolerance * .01,
            RelativeTolerance = 0,
            MinimumEdgeLength = tolerance * .01,
            MaximumEdgeLength = cell * .5,
            RefineGrid = true,
            SimplePlanes = true,
            JaggedSeams = false,
            DoublePrecision = true
        };
        var mesh = new Mesh();
        try
        {
            foreach (var part in Mesh.CreateFromBrep(brep, parameters) ?? Array.Empty<Mesh>())
            {
                using (part)
                    mesh.Append(part);
            }

            if (!mesh.IsValid || !mesh.IsClosed)
                throw new ArgumentException("Surface meshing did not produce a closed mesh. Repair the solid before running.");
            if (mesh.Faces.Count > 2_000_000)
                throw new ArgumentException("Surface mesh exceeds 2,000,000 faces. Simplify geometry or increase cell size.");
            return mesh;
        }
        catch
        {
            mesh.Dispose();
            throw;
        }
    }
}
