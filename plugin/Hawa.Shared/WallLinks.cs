using System.Text.Json.Nodes;
using Rhino.Geometry;
using Rhino.Geometry.Intersect;

namespace Hawa.Shared;
/// <summary>Stationary D3Q19 links; coordinates and spacing use the input mesh units.</summary>
public static class WallLinks
{
    // Lettuce D3Q19 order, not an arbitrary neighbour enumeration.
    private static readonly int[][] Directions =
    {
        new[]
        {
            0,
            0,
            0
        },
        new[]
        {
            1,
            0,
            0
        },
        new[]
        {
            -1,
            0,
            0
        },
        new[]
        {
            0,
            1,
            0
        },
        new[]
        {
            0,
            -1,
            0
        },
        new[]
        {
            0,
            0,
            1
        },
        new[]
        {
            0,
            0,
            -1
        },
        new[]
        {
            0,
            1,
            1
        },
        new[]
        {
            0,
            -1,
            -1
        },
        new[]
        {
            0,
            1,
            -1
        },
        new[]
        {
            0,
            -1,
            1
        },
        new[]
        {
            1,
            0,
            1
        },
        new[]
        {
            -1,
            0,
            -1
        },
        new[]
        {
            1,
            0,
            -1
        },
        new[]
        {
            -1,
            0,
            1
        },
        new[]
        {
            1,
            1,
            0
        },
        new[]
        {
            -1,
            -1,
            0
        },
        new[]
        {
            1,
            -1,
            0
        },
        new[]
        {
            -1,
            1,
            0
        }
    };
    public static double Fraction(Mesh mesh, Point3d start, Vector3d segment)
    {
        if (!start.IsValid || !segment.IsValid || segment.SquareLength <= 0)
            throw new ArgumentException("Wall link needs a finite nonzero segment");
        // Rhino's intersection uses the mesh acceleration structure. Do not scan
        // every triangle for every link: refined surface meshes make that quadratic.
        var hits = Intersection.MeshLine(mesh, new Line(start, start + segment));
        double nearest = double.PositiveInfinity;
        foreach (var hit in hits ?? Array.Empty<Point3d>())
        {
            double q = (hit - start) * segment / segment.SquareLength;
            if (q >= -1e-8 && q <= 1 + 1e-8)
                nearest = Math.Min(nearest, Math.Clamp(q, 0, 1));
        }

        // An endpoint exactly on a face can be omitted by segment intersection.
        if (!double.IsFinite(nearest))
        {
            var endpoint = start + segment;
            var point = mesh.ClosestMeshPoint(endpoint, segment.Length * 1e-8);
            if (point != null && point.Point.DistanceTo(endpoint) <= segment.Length * 1e-8)
                nearest = 1;
        }

        if (!double.IsFinite(nearest) && MeshContainment.Contains(mesh, mesh.GetBoundingBox(false), start + segment, segment.Length * 1e-8))
            nearest = TriangleFraction(mesh, start, segment);
        return nearest;
    }

    // MeshLine can omit a crossing on a Brep meshing seam. Fall back only
    // when the segment endpoint is inside this mesh; ordinary misses stay cheap.
    private static double TriangleFraction(Mesh mesh, Point3d origin, Vector3d segment)
    {
        double nearest = double.PositiveInfinity;
        foreach (var face in mesh.Faces)
        {
            Test((Point3d)mesh.Vertices[face.A], (Point3d)mesh.Vertices[face.B], (Point3d)mesh.Vertices[face.C]);
            if (face.IsQuad)
                Test((Point3d)mesh.Vertices[face.A], (Point3d)mesh.Vertices[face.C], (Point3d)mesh.Vertices[face.D]);
        }

        return nearest;
        void Test(Point3d a, Point3d b, Point3d c)
        {
            var e1 = b - a;
            var e2 = c - a;
            var h = Vector3d.CrossProduct(segment, e2);
            double det = e1 * h;
            if (Math.Abs(det) <= 1e-12 * e1.Length * e2.Length * segment.Length)
                return;
            double inv = 1 / det;
            var s = origin - a;
            double u = inv * (s * h);
            if (u < -1e-8 || u > 1 + 1e-8)
                return;
            var q = Vector3d.CrossProduct(s, e1);
            double v = inv * (segment * q);
            if (v < -1e-8 || u + v > 1 + 1e-8)
                return;
            double t = inv * (e2 * q);
            if (t >= -1e-8 && t <= 1 + 1e-8)
                nearest = Math.Min(nearest, Math.Clamp(t, 0, 1));
        }
    }

    public static JsonArray Build(IReadOnlyList<Mesh> meshes, int[] n, IEnumerable<int> solid, Point3d origin, Vector3d ax, Vector3d ay, Vector3d az, CancellationToken token)
    {
        var occupied = solid.ToHashSet();
        var links = new JsonArray();
        foreach (int site in occupied.OrderBy(v =>
            v
        ))
        {
            token.ThrowIfCancellationRequested();
            int[] c =
            {
                site / (n[1] * n[2]),
                site / n[2] % n[1],
                site % n[2]
            };
            if (Enumerable.Range(0, 3).Any(a =>
                c[a] < 2 || c[a] >= n[a] - 2
            ))
                throw new ArgumentException("Curved walls require two-cell domain clearance");
            for (int dir = 1; dir < Directions.Length; dir++)
            {
                var e = Directions[dir];
                int x = c[0] - e[0], y = c[1] - e[1], z = c[2] - e[2];
                int index = (x * n[1] + y) * n[2] + z;
                if (occupied.Contains(index))
                    continue;
                var point = origin + x * ax + y * ay + z * az;
                var segment = e[0] * ax + e[1] * ay + e[2] * az;
                double q = double.PositiveInfinity;
                foreach (var mesh in meshes)
                    q = Math.Min(q, Fraction(mesh, point, segment));
                if (!double.IsFinite(q) || q <= 0)
                    throw new ArgumentException("Cannot resolve a wall intersection. Refine the mesh/grid or shift the domain origin slightly.");
                int behind = ((x - e[0]) * n[1] + y - e[1]) * n[2] + z - e[2];
                if (q < .5 && occupied.Contains(behind))
                    throw new ArgumentException("Unresolved narrow gap at curved wall. Reduce cell size.");
                links.Add(new JsonArray(dir, index, q));
            }
        }

        return links;
    }
}
