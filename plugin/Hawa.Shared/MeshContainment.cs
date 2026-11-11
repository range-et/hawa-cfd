using Rhino.Geometry;

namespace Hawa.Shared;
public static class MeshContainment
{
    public static bool Contains(Mesh mesh, BoundingBox bounds, Point3d point, double tolerance)
    {
        // Pad by the surface tolerance, so a node a few ULP outside a face that
        // lies on a lattice plane still reaches the surface test below.
        var padded = new BoundingBox(new Point3d(bounds.Min.X - tolerance, bounds.Min.Y - tolerance, bounds.Min.Z - tolerance),
            new Point3d(bounds.Max.X + tolerance, bounds.Max.Y + tolerance, bounds.Max.Z + tolerance));
        if (!padded.Contains(point))
            return false;
        var closest = mesh.ClosestMeshPoint(point, tolerance);
        if (closest != null && closest.Point.DistanceTo(point) <= tolerance)
            return true;
        // Axis-aligned parity rays can hit mesh seams. Use three oblique rays
        // and merge duplicate triangle hits before taking the majority vote.
        int votes = 0;
        double reach = 3 * bounds.Diagonal.Length + tolerance;
        foreach (var direction in new[]
        {
            new Vector3d(1, .371, .529),
            new Vector3d(.237, 1, .617),
            new Vector3d(.419, .283, 1)
        }

        )
        {
            var ray = direction;
            ray.Unitize();
            var hits = Rhino.Geometry.Intersect.Intersection.MeshLine(mesh, new Line(point, point + reach * ray));
            var distances = (hits ?? Array.Empty<Point3d>()).Select(p =>
                p.DistanceTo(point)
            ).OrderBy(x =>
                x
            ).ToArray();
            int unique = 0;
            double previous = double.NegativeInfinity;
            foreach (double distance in distances)
            {
                if (distance - previous > tolerance)
                {
                    unique++;
                    previous = distance;
                }
            }

            if (unique % 2 == 1)
                votes++;
        }

        return votes >= 2;
    }
}
