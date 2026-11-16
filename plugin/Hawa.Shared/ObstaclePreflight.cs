using Rhino.Geometry;

namespace Hawa.Shared;

/// <summary>
/// Admission for obstacle meshes, not display meshes or domain faces. Exact
/// coordinate welding is used only for edge counting; the input is never edited.
/// Transverse triangle intersections are checked with a bounded sweep. This is
/// not a certificate against coplanar overlap or near-coincident self-contact.
/// </summary>
public static class ObstaclePreflight
{
    public const string Limits = "Coplanar overlap and near-coincident self-contact are not certified; self-intersecting single meshes are unsupported. Split separate bodies into separate obstacle inputs or union them.";

    public static void Require(Mesh mesh, string obstacle, CancellationToken token = default)
    {
        var error = Error(mesh, obstacle, token);
        if (error != null)
            throw new ArgumentException(error);
    }

    public static string? Error(Mesh mesh, string obstacle, CancellationToken token = default)
    {
        if (mesh == null || mesh.Vertices.Count == 0 || mesh.Faces.Count == 0)
            return $"{obstacle}: invalid or empty mesh. Supply a valid closed volumetric mesh.";
        var vertices = new Point3d[mesh.Vertices.Count];
        var welded = new int[vertices.Length];
        var indices = new Dictionary<(double, double, double), int>();
        for (int i = 0; i < vertices.Length; i++)
        {
            token.ThrowIfCancellationRequested();
            var p = mesh.Vertices.Point3dAt(i);
            if (!p.IsValid)
                return $"{obstacle}: non-finite vertex {i}. Repair mesh coordinates.";
            vertices[i] = p;
            var key = (p.X, p.Y, p.Z);
            if (!indices.TryGetValue(key, out var index))
            {
                index = indices.Count;
                indices.Add(key, index);
            }
            welded[i] = index;
        }
        var edges = new Dictionary<(int, int), int>();
        var triangles = new List<Triangle>();
        int degenerate = 0;
        for (int i = 0; i < mesh.Faces.Count; i++)
        {
            token.ThrowIfCancellationRequested();
            var f = mesh.Faces[i];
            var ids = f.IsQuad ? new[] { f.A, f.B, f.C, f.D } : new[] { f.A, f.B, f.C };
            if (ids.Any(v =>
                v < 0 || v >= vertices.Length
            ))
                return $"{obstacle}: face {i} has an invalid vertex index. Repair mesh faces.";
            var a = new Triangle(vertices[f.A], vertices[f.B], vertices[f.C], i);
            Triangle? b = f.IsQuad ? new Triangle(vertices[f.A], vertices[f.C], vertices[f.D], i) : null;
            if (ids.Select(v =>
                welded[v]
            ).Distinct().Count() != ids.Length || Degenerate(a) || (b.HasValue && Degenerate(b.Value)))
                degenerate++;
            triangles.Add(a);
            if (b.HasValue)
                triangles.Add(b.Value);
            for (int j = 0; j < ids.Length; j++)
            {
                int x = welded[ids[j]], y = welded[ids[(j + 1) % ids.Length]];
                var edge = (Math.Min(x, y), Math.Max(x, y));
                edges.TryGetValue(edge, out int count);
                edges[edge] = count + 1;
            }
        }
        if (degenerate > 0)
            return $"{obstacle}: {degenerate} degenerate/zero-area faces. Remove degenerate faces and close the mesh.";
        int naked = edges.Count(e =>
            e.Value == 1
        );
        int nonManifold = edges.Count(e =>
            e.Value > 2
        );
        if (naked > 0 || nonManifold > 0)
            return $"{obstacle}: {naked} naked edges; {nonManifold} non-manifold edges. Close the mesh; every edge must have exactly two faces. Split separate bodies into separate obstacle inputs or union them.";
        if (!mesh.IsValid)
            return $"{obstacle}: invalid mesh data. Repair the mesh before voxelization.";
        if (!mesh.IsClosed)
            return $"{obstacle}: Rhino reports an open mesh. Close the mesh before voxelization.";
        var intersection = FirstCrossing(triangles, token);
        return intersection == null ? null : $"{obstacle}: {intersection} {Limits}";
    }

    private readonly record struct Triangle(Point3d A, Point3d B, Point3d C, int Face);

    private static bool Degenerate(Triangle t)
    {
        var ab = t.B - t.A;
        var ac = t.C - t.A;
        double scale = Math.Max(ab.Length, ac.Length);
        if (!double.IsFinite(scale) || scale == 0)
            return true;
        // Normalize locally: distant world origins and small but valid bodies
        // must not change the area decision.
        double area = Vector3d.CrossProduct(ab / scale, ac / scale).Length;
        return !double.IsFinite(area) || area == 0;
    }

    private sealed record Node(BoundingBox Bounds, int Start, int Count, Node? Left, Node? Right);

    private static Node Tree(Triangle[] triangles, int start, int count, CancellationToken token)
    {
        token.ThrowIfCancellationRequested();
        var points = new List<Point3d>();
        for (int i = start; i < start + count; i++)
        {
            points.Add(triangles[i].A);
            points.Add(triangles[i].B);
            points.Add(triangles[i].C);
        }
        var box = new BoundingBox(points);
        if (count <= 8)
            return new Node(box, start, count, null, null);
        var size = box.Diagonal;
        int axis = size.X >= size.Y && size.X >= size.Z ? 0 : size.Y >= size.Z ? 1 : 2;
        Array.Sort(triangles, start, count, Comparer<Triangle>.Create((a, b) =>
            Center(a, axis).CompareTo(Center(b, axis))
        ));
        int left = count / 2;
        return new Node(box, start, count, Tree(triangles, start, left, token), Tree(triangles, start + left, count - left, token));
    }

    private static double Center(Triangle t, int axis) => axis == 0 ? t.A.X / 3 + t.B.X / 3 + t.C.X / 3
        : axis == 1 ? t.A.Y / 3 + t.B.Y / 3 + t.C.Y / 3 : t.A.Z / 3 + t.B.Z / 3 + t.C.Z / 3;

    private static bool BoxesOverlap(BoundingBox a, BoundingBox b) => a.Min.X <= b.Max.X && b.Min.X <= a.Max.X
        && a.Min.Y <= b.Max.Y && b.Min.Y <= a.Max.Y && a.Min.Z <= b.Max.Z && b.Min.Z <= a.Max.Z;

    private static string? FirstCrossing(List<Triangle> triangles, CancellationToken token)
    {
        var ordered = triangles.ToArray();
        var root = Tree(ordered, 0, ordered.Length, token);
        var pending = new Stack<(Node, Node)>();
        pending.Push((root, root));
        int comparisons = 0;
        while (pending.Count > 0)
        {
            token.ThrowIfCancellationRequested();
            var (a, b) = pending.Pop();
            if (!BoxesOverlap(a.Bounds, b.Bounds))
                continue;
            if (a.Left == null && b.Left == null)
            {
                for (int i = a.Start; i < a.Start + a.Count; i++)
                    for (int j = b.Start; j < b.Start + b.Count; j++)
                    {
                        if (ReferenceEquals(a, b) && j <= i)
                            continue;
                        var x = ordered[i];
                        var y = ordered[j];
                        if (x.Face == y.Face || !Overlap(x, y))
                            continue;
                        if (++comparisons > 2_000_000)
                            return "self-intersection preflight exceeded 2,000,000 overlapping candidate pairs. Simplify the mesh or split separate bodies into separate obstacle inputs.";
                        if (Crosses(x.A, x.B, y) || Crosses(x.B, x.C, y) || Crosses(x.C, x.A, y)
                            || Crosses(y.A, y.B, x) || Crosses(y.B, y.C, x) || Crosses(y.C, y.A, x))
                            return $"self-intersection between faces {x.Face} and {y.Face}.";
                    }
            }
            else if (ReferenceEquals(a, b))
            {
                pending.Push((a.Left!, a.Left!));
                pending.Push((a.Right!, a.Right!));
                pending.Push((a.Left!, a.Right!));
            }
            else if (a.Left != null && (b.Left == null || a.Count >= b.Count))
            {
                pending.Push((a.Left, b));
                pending.Push((a.Right!, b));
            }
            else
            {
                pending.Push((a, b.Left!));
                pending.Push((a, b.Right!));
            }
        }
        return null;
    }

    private static bool Overlap(Triangle a, Triangle b)
    {
        return Math.Min(a.A.X, Math.Min(a.B.X, a.C.X)) <= Math.Max(b.A.X, Math.Max(b.B.X, b.C.X))
            && Math.Min(b.A.X, Math.Min(b.B.X, b.C.X)) <= Math.Max(a.A.X, Math.Max(a.B.X, a.C.X))
            && Math.Min(a.A.Y, Math.Min(a.B.Y, a.C.Y)) <= Math.Max(b.A.Y, Math.Max(b.B.Y, b.C.Y))
            && Math.Min(b.A.Y, Math.Min(b.B.Y, b.C.Y)) <= Math.Max(a.A.Y, Math.Max(a.B.Y, a.C.Y))
            && Math.Min(a.A.Z, Math.Min(a.B.Z, a.C.Z)) <= Math.Max(b.A.Z, Math.Max(b.B.Z, b.C.Z))
            && Math.Min(b.A.Z, Math.Min(b.B.Z, b.C.Z)) <= Math.Max(a.A.Z, Math.Max(a.B.Z, a.C.Z));
    }

    private static bool Crosses(Point3d p, Point3d q, Triangle t)
    {
        var e1 = t.B - t.A;
        var e2 = t.C - t.A;
        double scale = Math.Max(e1.Length, Math.Max(e2.Length, (q - p).Length));
        e1 /= scale;
        e2 /= scale;
        var direction = (q - p) / scale;
        var offset = (p - t.A) / scale;
        var h = Vector3d.CrossProduct(direction, e2);
        double det = e1 * h;
        // Only proper transverse crossings: adjacent triangles legitimately
        // meet on edges/vertices. Coplanar and near-tangent cases are excluded.
        if (Math.Abs(det) <= 1e-12)
            return false;
        double u = (offset * h) / det;
        var cross = Vector3d.CrossProduct(offset, e1);
        double v = (direction * cross) / det;
        double s = (e2 * cross) / det;
        return u >= -1e-10 && v >= -1e-10 && u + v <= 1 + 1e-10
            && u < 1 - 1e-10 && v < 1 - 1e-10 && u + v > 1e-10
            && s > 1e-10 && s < 1 - 1e-10;
    }
}
