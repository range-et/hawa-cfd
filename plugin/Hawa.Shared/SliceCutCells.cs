using System.Text.Json.Nodes;

namespace Hawa.Shared;
// Display reconstruction only. Never changes the sampled values, validity or solver.
// Every dual cell of the slice is tiled: fluid pieces carry sampled colours and
// solid pieces are drawn black, so solids and no-data follow the lattice
// representation instead of leaving undrawn gaps.
public static class SliceCutCells
{
    public sealed record Vertex(double[] Grid, double Value);
    public sealed record Piece(Vertex[] Polygon, bool Solid);
    public static IEnumerable<Piece> Polygons(double[][] points, double[] values, bool[] valid, int rows, int cols, int[] shape, JsonArray? wallLinks, string field)
    {
        var links = new Dictionary<(int, int), double>();
        if (wallLinks != null)
            foreach (var row in wallLinks)
                links[(row![0]!.GetValue<int>(), row[1]!.GetValue<int>())] = row[2]!.GetValue<double>();

        Vertex Site(int i) =>
            new(points[i], values[i])
        ;
        // Halfway point of the given sites, coloured by their fluid samples only.
        Vertex Mid(params int[] sites)
        {
            var fluid = sites.Where(i =>
                valid[i]
            ).ToArray();
            return new(Enumerable.Range(0, points[sites[0]].Length).Select(a =>
                sites.Average(i =>
                    points[i][a]
                )
            ).ToArray(), fluid.Length > 0 ? fluid.Average(i =>
                values[i]
            ) : 0);
        }

        // Stationary curved-wall crossing on a D3Q19 link from a fluid to a solid site.
        Vertex? Crossing(int fluid, int solid)
        {
            if (shape.Length != 3 || links.Count == 0)
                return null;
            var p = points[fluid];
            var end = points[solid];
            if (p.Length != 3 || end.Length != 3 || p.Concat(end).Any(v =>
                Math.Abs(v - Math.Round(v)) > 1e-8
            ))
                return null;
            var delta = Enumerable.Range(0, 3).Select(a =>
                (int)Math.Round(end[a] - p[a])
            ).ToArray();
            int dir = Array.FindIndex(WallLinks.Directions, e =>
                e.SequenceEqual(delta)
            );
            int index = ((int)Math.Round(p[0]) * shape[1] + (int)Math.Round(p[1])) * shape[2] + (int)Math.Round(p[2]);
            if (dir < 1 || !links.TryGetValue((dir, index), out double q) || !double.IsFinite(q) || q <= 0 || q > 1)
                return null;
            return new(Enumerable.Range(0, 3).Select(a =>
                p[a] + q * (end[a] - p[a])
            ).ToArray(), field == "speed" ? 0 : values[fluid]);
        }

        Piece? Clean(List<Vertex> polygon, bool solid)
        {
            for (int j = polygon.Count - 1; j > 0; j--)
                if (polygon[j].Grid.SequenceEqual(polygon[j - 1].Grid))
                    polygon.RemoveAt(j);
            if (polygon.Count > 1 && polygon[0].Grid.SequenceEqual(polygon[^1].Grid))
                polygon.RemoveAt(polygon.Count - 1);
            return polygon.Count >= 3 ? new(polygon.ToArray(), solid) : null;
        }

        // Curved-wall cut: fluid and solid sides of the link crossings, or null
        // when any needed crossing is missing.
        List<Piece>? Cut(int[] cell)
        {
            int count = cell.Count(i =>
                valid[i]
            );
            var pieces = new List<Piece>();
            if (count == 2 && valid[cell[0]] == valid[cell[2]])
            {
                // Ambiguous diagonal mask: two separate fluid corners; the solid
                // remainder joins the solid corners instead.
                var solid = new List<Vertex>();
                for (int j = 0; j < 4; j++)
                {
                    int first = cell[j], second = cell[(j + 1) % 4];
                    var hit = valid[first] ? Crossing(first, second) : Crossing(second, first);
                    if (hit == null)
                        return null;
                    if (!valid[first])
                        solid.Add(Site(first));
                    solid.Add(hit);
                    if (valid[first])
                    {
                        var previous = Crossing(first, cell[(j + 3) % 4]);
                        if (previous == null)
                            return null;
                        if (Clean(new List<Vertex> { Site(first), hit, previous }, false) is Piece corner)
                            pieces.Add(corner);
                    }
                }

                if (Clean(solid, true) is Piece rest)
                    pieces.Add(rest);
                return pieces;
            }

            // One solid or one fluid corner: the wall also crosses the in-plane
            // diagonal; that crossing keeps the chord from cutting the corner.
            Vertex? diagonal = null;
            for (int j = 0; j < 4; j++)
                if (count == 3 && !valid[cell[j]])
                    diagonal = Crossing(cell[(j + 2) % 4], cell[j]);
                else if (count == 1 && valid[cell[j]])
                    diagonal = Crossing(cell[j], cell[(j + 2) % 4]);
            var fluidSide = new List<Vertex>();
            var solidSide = new List<Vertex>();
            for (int j = 0; j < 4; j++)
            {
                int first = cell[j], second = cell[(j + 1) % 4];
                (valid[first] ? fluidSide : solidSide).Add(Site(first));
                if (valid[first] == valid[second])
                    continue;
                var hit = valid[first] ? Crossing(first, second) : Crossing(second, first);
                if (hit == null)
                    return null;
                fluidSide.Add(hit);
                solidSide.Add(hit);
                if (diagonal != null)
                    (valid[first] ? fluidSide : solidSide).Add(diagonal);
            }

            // The diagonal crossing is the only interior, possibly reflex, vertex;
            // every other vertex lies on the cell boundary and is visible from it.
            // Start both pieces there so a fan triangulation stays inside them.
            List<Vertex> FromDiagonal(List<Vertex> polygon)
            {
                int start = diagonal == null ? 0 : Math.Max(0, polygon.IndexOf(diagonal));
                return polygon.Skip(start).Concat(polygon.Take(start)).ToList();
            }

            foreach (var piece in new[] { Clean(FromDiagonal(fluidSide), false), Clean(FromDiagonal(solidSide), true) })
                if (piece != null)
                    pieces.Add(piece);
            return pieces;
        }

        for (int x = 0; x < rows - 1; x++)
            for (int y = 0; y < cols - 1; y++)
            {
                int a = x * cols + y;
                int[] cell =
                {
                    a,
                    a + cols,
                    a + cols + 1,
                    a + 1
                };
                int count = cell.Count(i =>
                    valid[i]
                );
                if (count == 4 || count == 0)
                {
                    yield return new(cell.Select(Site).ToArray(), count == 0);
                    continue;
                }

                var cut = Cut(cell);
                if (cut != null)
                {
                    foreach (var piece in cut)
                        yield return piece;
                    continue;
                }

                // Voxel representation, and the fallback for a missing crossing:
                // each corner owns its quadrant up to the halfway lines.
                for (int j = 0; j < 4; j++)
                {
                    int corner = cell[j], next = cell[(j + 1) % 4], previous = cell[(j + 3) % 4];
                    yield return new(new[] { Site(corner), Mid(corner, next), Mid(cell), Mid(corner, previous) }, !valid[corner]);
                }
            }
    }
}
