using System.Text.Json.Nodes;
namespace Hawa.Shared;

// Display reconstruction only. Never changes the sampled values, validity or solver.
public static class SliceCutCells
{
    public sealed record Vertex(double[] Grid, double Value);
    public static IEnumerable<Vertex[]> Polygons(double[][] points, double[] values, bool[] valid,
        int rows, int cols, int[] shape, JsonArray? wallLinks, string field)
    {
        var links=new Dictionary<(int,int),double>();
        if(wallLinks!=null)foreach(var row in wallLinks){int dir=row![0]!.GetValue<int>();if(dir<=6)links[(dir,row[1]!.GetValue<int>())]=row[2]!.GetValue<double>();}
        Vertex Site(int i)=>new(points[i],values[i]);
        Vertex? Crossing(int fluid,int solid){
            if(shape.Length!=3||links.Count==0)return null;
            var p=points[fluid];var end=points[solid];
            if(p.Length!=3||end.Length!=3||p.Concat(end).Any(v=>Math.Abs(v-Math.Round(v))>1e-8))return null;
            var delta=Enumerable.Range(0,3).Select(a=>(int)Math.Round(end[a]-p[a])).ToArray();
            if(delta.Sum(v=>Math.Abs(v))!=1)return null;
            int axis=Array.FindIndex(delta,v=>v!=0),dir=1+2*axis+(delta[axis]<0?1:0);
            int index=((int)Math.Round(p[0])*shape[1]+(int)Math.Round(p[1]))*shape[2]+(int)Math.Round(p[2]);
            if(!links.TryGetValue((dir,index),out double q)||!double.IsFinite(q)||q<=0||q>1)return null;
            return new(Enumerable.Range(0,3).Select(a=>p[a]+q*(end[a]-p[a])).ToArray(),field=="speed"?0:values[fluid]);
        }
        for(int x=0;x<rows-1;x++)for(int y=0;y<cols-1;y++){
            int a=x*cols+y;int[] cell={a,a+cols,a+cols+1,a+1};int count=cell.Count(i=>valid[i]);
            if(count==4){yield return cell.Select(Site).ToArray();continue;}
            if(count==0||links.Count==0)continue;
            // Resolve ambiguous diagonal masks conservatively as two disjoint
            // fluid corners, rather than joining through an unresolved solid.
            if(count==2&&valid[cell[0]]==valid[cell[2]]){
                for(int j=0;j<4;j++)if(valid[cell[j]]){
                    var next=Crossing(cell[j],cell[(j+1)%4]);var previous=Crossing(cell[j],cell[(j+3)%4]);
                    if(next!=null&&previous!=null)yield return new[]{Site(cell[j]),next,previous};
                }
                continue;
            }
            var polygon=new List<Vertex>();bool resolved=true;
            for(int j=0;j<4;j++){
                int first=cell[j],second=cell[(j+1)%4];
                if(valid[first])polygon.Add(Site(first));
                if(valid[first]!=valid[second]){
                    var hit=valid[first]?Crossing(first,second):Crossing(second,first);
                    if(hit==null){resolved=false;break;}polygon.Add(hit);
                }
            }
            if(resolved){
                for(int j=polygon.Count-1;j>0;j--)if(polygon[j].Grid.SequenceEqual(polygon[j-1].Grid))polygon.RemoveAt(j);
                if(polygon.Count>1&&polygon[0].Grid.SequenceEqual(polygon[^1].Grid))polygon.RemoveAt(polygon.Count-1);
                if(polygon.Count>=3)yield return polygon.ToArray();
            }
        }
    }
}
