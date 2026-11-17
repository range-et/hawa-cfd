// Run through Rhino MCP with Hawa loaded; adjust root. Creates only example 35.
// Refuses to overwrite an existing definition. Never regenerates example 09.
// Geometry is ordinary GH, not a new public Hawa geometry primitive.
using System.Drawing;
using System.IO;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Special;
using Grasshopper.Kernel.Parameters;
using Grasshopper.Kernel.Types;
using Rhino.Geometry;
var root="/Users/r2d2/Desktop/hawa-parametric-wing-example";
bool geometryOnly=false; // Set true for transient geometry validation before Study is installed.
var path=Path.Combine(root,"examples/grasshopper/35-parametric-wing-study.gh");
if(!geometryOnly&&File.Exists(path))throw new Exception("Example 35 exists; preserve it and generate into an isolated new output checkout.");
var document=new GH_Document();
var assembly=AppDomain.CurrentDomain.GetAssemblies().Single(a=>a.GetName().Name=="Hawa.Grasshopper");
T Add<T>(T item,float x,float y) where T:IGH_DocumentObject {
 item.CreateAttributes();item.Attributes.Pivot=new PointF(x,y);document.AddObject(item,false);return item;
}
GH_Component Stock(string guid,string label,float x,float y){
 var proxy=Grasshopper.Instances.ComponentServer.EmitObjectProxy(new Guid(guid));
 if(proxy==null)throw new Exception("Missing stock GH component: "+label);
 var component=Add((GH_Component)proxy.CreateInstance(),x,y);component.NickName=label;component.Hidden=true;return component;
}
GH_Component Hawa(string type,float x,float y){
 var component=Add((GH_Component)Activator.CreateInstance(assembly.GetType("Hawa.Grasshopper."+type+"Component",true)),x,y);
 component.Hidden=true;return component;
}
void Wire(IGH_Param source,GH_Component target,int input)=>target.Params.Input[input].AddSource(source);
void Connect(GH_Component source,int output,GH_Component target,int input)=>Wire(source.Params.Output[output],target,input);
IGH_Param Output(GH_Component component,string name)=>component.Params.Output.Single(p=>p.Name==name);
void Named(IGH_Param source,GH_Component target,string name)=>target.Params.Input.Single(p=>p.Name==name).AddSource(source);
void Number(GH_Component component,int input,double value){var parameter=(Param_Number)component.Params.Input[input];parameter.PersistentData.Clear();parameter.SetPersistentData(value);}
void Text(GH_Component component,int input,string value){var parameter=(Param_String)component.Params.Input[input];parameter.PersistentData.Clear();parameter.SetPersistentData(value);}
GH_BooleanToggle Toggle(string label,float x,float y){var toggle=Add(new GH_BooleanToggle(),x,y);toggle.NickName=label;toggle.Value=false;return toggle;}
GH_NumberSlider Slider(string label,decimal value,decimal minimum,decimal maximum,int decimals,float x,float y){
 var slider=Add(new GH_NumberSlider(),x,y);slider.NickName=label;
 slider.Slider.Minimum=minimum;slider.Slider.Maximum=maximum;slider.Slider.DecimalPlaces=decimals;slider.SetSliderValue(value);return slider;
}
GH_Panel Panel(string label,string text,float x,float y,float width=300,float height=100){
 var panel=Add(new GH_Panel(),x,y);panel.NickName=label;panel.UserText=text;
 panel.Properties.Font=new Font("Helvetica",11);panel.Properties.Wrap=true;panel.Properties.Multiline=true;
 panel.Properties.DrawIndices=false;panel.Properties.DrawPaths=false;
 var align=panel.Properties.GetType().GetProperty("Alignment");align.SetValue(panel.Properties,Enum.Parse(align.PropertyType,"Left"));
 panel.Attributes.Bounds=new RectangleF(x,y,width,height);return panel;
}
GH_Component Expression(string formula,string label,float x,float y,params IGH_Param[] inputs){
 var component=Stock("9df5e896-552d-4c8c-b9ca-4fc147ffa022",label,x,y);
 var variable=(IGH_VariableParameterComponent)component;
 while(component.Params.Input.Count<inputs.Length)component.Params.RegisterInputParam(variable.CreateParameter(GH_ParameterSide.Input,component.Params.Input.Count));
 while(component.Params.Input.Count>inputs.Length)component.Params.UnregisterInputParameter(component.Params.Input.Last(),true);
 for(int i=0;i<inputs.Length;i++){component.Params.Input[i].Name=component.Params.Input[i].NickName=new[]{"x","y","z"}[i];Wire(inputs[i],component,i);}
 component.Params.OnParametersChanged();component.GetType().GetProperty("Expression").SetValue(component,formula);return component;
}
void Group(string title,params IGH_DocumentObject[] items){
 var group=Add(new GH_Group(),0,0);group.NickName=title;group.Colour=Color.FromArgb(50,35,150,155);
 foreach(var item in items)group.AddObject(item.InstanceGuid);
}
void Scatter(IGH_Param xs,IGH_Param ys,string title,string xLabel,string yLabel,double xScale,double yScale,double originX,float x,float y){
 // Cull the SAME paired-row mask before arithmetic: null output slots are not numeric zero.
 var nullX=Stock("c74efd0e-7fe3-4c2d-8c9d-295c5672fb13",title+" / missing X",x,y);Wire(xs,nullX,0);
 var nullY=Stock("c74efd0e-7fe3-4c2d-8c9d-295c5672fb13",title+" / missing Y",x,y+110);Wire(ys,nullY,0);
 var missing=Stock("548177c2-d1db-4172-b667-bec979e2d38b",title+" / both coordinates present",x+230,y+220);Connect(nullX,0,missing,0);Connect(nullY,0,missing,1);
 var cleanX=Stock("008e9a6f-478a-4813-8c8a-546273bc3a6b",title+" / paired X",x+260,y);Wire(xs,cleanX,0);Connect(missing,0,cleanX,1);
 var cleanY=Stock("008e9a6f-478a-4813-8c8a-546273bc3a6b",title+" / paired Y",x+260,y+110);Wire(ys,cleanY,0);Connect(missing,0,cleanY,1);
 // Display coordinates only. The returned numerical coefficients are unchanged.
 var px=Expression(xScale.ToString(System.Globalization.CultureInfo.InvariantCulture),title+" / display X scale",x+520,y);
 var py=Expression(yScale.ToString(System.Globalization.CultureInfo.InvariantCulture),title+" / display Y scale",x+520,y+110);
 var mx=Stock("ce46b74e-00c9-43c4-805a-193b69ea4a11",title+" / scale X",x+750,y);Connect(cleanX,0,mx,0);Connect(px,0,mx,1);
 var my=Stock("ce46b74e-00c9-43c4-805a-193b69ea4a11",title+" / scale Y",x+750,y+110);Connect(cleanY,0,my,0);Connect(py,0,my,1);
 var ax=Stock("a0d62394-a118-422d-abb3-6af115c75b25",title+" / offset X",x+950,y);Connect(mx,0,ax,0);((Param_GenericObject)ax.Params.Input[1]).SetPersistentData(new GH_Number(originX));
 var ay=Stock("a0d62394-a118-422d-abb3-6af115c75b25",title+" / offset Y",x+950,y+110);Connect(my,0,ay,0);((Param_GenericObject)ay.Params.Input[1]).SetPersistentData(new GH_Number(-1.5));
 var points=Stock("3581f42a-9592-4549-bd6b-1c0fc39d067b",title+" / scatter only",x+1180,y);Connect(ax,0,points,0);Connect(ay,0,points,1);points.Hidden=false;
 var axes=Add(new Param_Curve(),x+800,y+150);axes.NickName=title+" / axes";
 double lowX=xLabel=="Angle (deg)"?-.3:0,highX=.6;
 axes.SetPersistentData(new LineCurve(new Point3d(originX+lowX,-1.5,0),new Point3d(originX+highX,-1.5,0)),new LineCurve(new Point3d(originX,-1.75,0),new Point3d(originX,-.9,0)));
 var locations=Add(new Param_Point(),x+800,y+270);locations.NickName=title+" / label positions";locations.Hidden=true;
 locations.SetPersistentData(new Point3d(originX+lowX,-.82,0),new Point3d(originX+highX,-1.59,0),new Point3d(originX-.05,-.94,0),new Point3d(originX,-1.56,0),new Point3d(originX+.3,-1.56,0),new Point3d(originX-.08,-1.2,0));
 var labels=Add(new Param_String(),x+520,y+300);labels.NickName=title+" / numeric axes";
 labels.SetPersistentData(title,xLabel,yLabel,"0",(.3/xScale).ToString("G3",System.Globalization.CultureInfo.InvariantCulture),(.3/yScale).ToString("G3",System.Globalization.CultureInfo.InvariantCulture));
 var tags=Stock("ebf4d987-09b9-4825-a735-cac3d4770c19",title+" / labels",x+1070,y+270);Wire(locations,tags,0);Wire(labels,tags,1);Number(tags,2,.035);tags.Hidden=false;
 Group(title+" / display scaling only; points never joined",nullX,nullY,missing,cleanX,cleanY,px,py,mx,my,ax,ay,points,axes,locations,labels,tags);
}
try{
 var rootCode=Panel("Root NACA","2418",0,0,220,60);
 var tipCode=Panel("Tip NACA","0018",0,110,220,60);
 var rootChord=Slider("Root chord (m)",.3m,.1m,.5m,3,0,240);
 var tipChord=Slider("Tip chord (m)",.2m,.05m,.4m,3,0,310);
 var span=Slider("Full span (m)",.6m,.2m,.8m,3,0,380);
 var cell=Slider("Cell size (m)",.01m,.01m,.025m,4,0,520);
 var sectionPlane=Add(new Param_Plane(),300,380);sectionPlane.NickName="Sections / XZ plane";
 sectionPlane.SetPersistentData(new Plane(Point3d.Origin,Vector3d.XAxis,Vector3d.ZAxis));sectionPlane.Hidden=true;
 var rootFoil=Hawa("Airfoil",330,0);rootFoil.NickName="Root / separate airfoil";
 var tipFoil=Hawa("Airfoil",330,180);tipFoil.NickName="Tip / separate airfoil";
 Wire(rootCode,rootFoil,0);Wire(rootChord,rootFoil,1);Wire(sectionPlane,rootFoil,2);
 Wire(tipCode,tipFoil,0);Wire(tipChord,tipFoil,1);Wire(sectionPlane,tipFoil,2);
 var offset=Expression("(x-y)/4","Quarter-chord alignment",650,260,rootChord,tipChord);
 var positiveSpan=Expression("x/2","Positive half span",650,360,span);
 var negativeSpan=Expression("-x/2","Negative half span",650,460,span);
 var plusVector=Stock("56b92eab-d121-43f7-94d3-6cd8f0ddead8","Tip + placement",950,310);
 var minusVector=Stock("56b92eab-d121-43f7-94d3-6cd8f0ddead8","Tip − placement",950,460);
 Connect(offset,0,plusVector,0);Connect(positiveSpan,0,plusVector,1);
 Connect(offset,0,minusVector,0);Connect(negativeSpan,0,minusVector,1);
 var tipPlus=Stock("e9eb1dcf-92f6-4d4d-84ae-96222d60f56b","Place positive tip",1220,110);
 var tipMinus=Stock("e9eb1dcf-92f6-4d4d-84ae-96222d60f56b","Place negative tip",1220,290);
 Connect(tipFoil,0,tipPlus,0);Connect(plusVector,0,tipPlus,1);
 Connect(tipFoil,0,tipMinus,0);Connect(minusVector,0,tipMinus,1);
 var sections=Add(new Param_Curve(),1480,110);sections.NickName="Ordered tip− / root / tip+ profiles";sections.Hidden=true;
 sections.AddSource(tipMinus.Params.Output[0]);sections.AddSource(rootFoil.Params.Output[0]);sections.AddSource(tipPlus.Params.Output[0]);
 var loft=Stock("a7a41d0a-2188-4f7a-82cc-1a2c4e4ec850","Loft distinct sections",1740,110);Wire(sections,loft,0);
 var cap=Stock("f6409a9c-3d2a-4b14-9f2c-e3c3f2cb72f8","Cap / closed solid",1980,110);Connect(loft,0,cap,0);
 var solid=Add(new Param_Brep(),2220,320);solid.NickName="Closed loft solid / preview before Run";solid.AddSource(cap.Params.Output[0]);solid.Hidden=true;
 var closed=Panel("Loft solid?","",2220,450,230,90);closed.AddSource(cap.Params.Output[2]);
 var meshBrep=Stock("60e7defa-8b21-4ee1-99aa-a9223d6134ff","Mesh the actual loft",2220,110);Connect(cap,0,meshBrep,0);
 var join=Stock("4bc9dbbf-fec8-4348-a3af-e33e7edc8e7b","Join loft and cap meshes",2460,110);Connect(meshBrep,0,join,0);
 var weld=Stock("9f6d85c9-1143-4538-bca7-69dcb11a74ef","Weld mesh seams",2700,110);Connect(join,0,weld,0);
 var angle=(Param_Number)weld.Params.Input[1];angle.PersistentData.Clear();angle.SetPersistentData(Math.PI);
 var normals=Stock("98c2a1f2-5ba6-4be0-8999-c540097406c5","Unify mesh normals",2940,110);Connect(weld,0,normals,0);
 var wing=Add(new Param_Mesh(),3180,110);wing.NickName="Actual closed wing mesh / study input";wing.AddSource(normals.Params.Output[0]);wing.Hidden=false;
 if(geometryOnly){
  var previous=Grasshopper.Instances.ActiveCanvas.Document;
  var checks=new System.Text.Json.Nodes.JsonArray();
  try{
   Grasshopper.Instances.DocumentServer.AddDocument(document);Grasshopper.Instances.ActiveCanvas.Document=document;
   var variants=new[]{("2418","0018",.3m,.2m,.6m),("0012","2412",.35m,.18m,.7m),("2418","0018",.25m,.15m,.5m)};
   foreach(var value in variants){
    rootCode.UserText=value.Item1;tipCode.UserText=value.Item2;rootChord.SetSliderValue(value.Item3);tipChord.SetSliderValue(value.Item4);span.SetSliderValue(value.Item5);
    rootCode.ExpireSolution(false);tipCode.ExpireSolution(false);rootChord.ExpireSolution(false);tipChord.ExpireSolution(false);span.ExpireSolution(false);
    document.NewSolution(false);
    var errors=document.Objects.OfType<GH_Component>().SelectMany(c=>c.RuntimeMessages(GH_RuntimeMessageLevel.Error).Select(e=>c.NickName+": "+e)).ToArray();
    if(errors.Length!=0)throw new Exception(string.Join(" | ",errors));
    var brep=cap.Params.Output[0].VolatileData.AllData(true).OfType<GH_Brep>().Single().Value;
    var mesh=wing.VolatileData.AllData(true).OfType<GH_Mesh>().Single().Value;
    if(!brep.IsValid||!brep.IsSolid||!mesh.IsValid||!mesh.IsClosed||mesh.SolidOrientation()!=1)throw new Exception("Expected an outward closed loft solid and closed mesh");
    var bbox=mesh.GetBoundingBox(true);double width=(double)value.Item5;
    if(Math.Abs(bbox.Min.Y+width/2)>1e-6||Math.Abs(bbox.Max.Y-width/2)>1e-6)throw new Exception("Wing span does not match slider");
    double volume=VolumeMassProperties.Compute(mesh).Volume;
    if(!(volume>0))throw new Exception("Mesh must have positive volume");
    checks.Add(new System.Text.Json.Nodes.JsonObject{["root"]=value.Item1,["tip"]=value.Item2,["root_chord_m"]=(double)value.Item3,["tip_chord_m"]=(double)value.Item4,["span_m"]=width,["brep_solid"]=brep.IsSolid,["mesh_closed"]=mesh.IsClosed,["mesh_vertices"]=mesh.Vertices.Count,["mesh_faces"]=mesh.Faces.Count,["mesh_volume_m3"]=volume,["mesh_crc"]=mesh.DataCRC(0)});
   }
   var output=Path.Combine(root,"results/parametric-wing-geometry");Directory.CreateDirectory(output);
   File.WriteAllText(Path.Combine(output,"preflight.json"),checks.ToJsonString(new System.Text.Json.JsonSerializerOptions{WriteIndented=true}));
   Console.WriteLine("Three transient ordinary GH loft/closed-mesh variants passed: "+checks.ToJsonString());
  }finally{
   if(Grasshopper.Instances.ActiveCanvas.Document==document)Grasshopper.Instances.ActiveCanvas.Document=previous;
   Grasshopper.Instances.DocumentServer.RemoveDocument(document);
  }
  return;
 }
 var geometryCheck=Hawa("GeometryCheck",3420,400);Wire(wing,geometryCheck,0);Wire(cell,geometryCheck,1);
 var geometryReport=Panel("Mesh admission and resolution","",3680,400,410,210);geometryReport.AddSource(geometryCheck.Params.Output[2]);
 var area=Expression("x*(y+z)/2","Fixed planform area (m²)",650,620,span,rootChord,tipChord);
 var mac=Expression("2*(x*x+x*y+y*y)/(3*(x+y))","Mean aerodynamic chord (m)",650,730,rootChord,tipChord);
 var quarter=Expression("x/4","Root quarter-chord pivot X",650,840,rootChord);
 var pivot=Stock("3581f42a-9592-4549-bd6b-1c0fc39d067b","Study pivot (m)",950,840);Connect(quarter,0,pivot,0);
 var runtime=Hawa("Runtime",330,1020);var initialize=Toggle("Initialize runtime",0,1020);Wire(initialize,runtime,0);
 var runtimeReport=Panel("Embedded runtime","",650,1040,400,120);runtimeReport.AddSource(Output(runtime,"Runtime"));
 var domainBox=Add(new Param_Box(),1220,620);domainBox.NickName="Fixed tunnel / edit bounds (m)";domainBox.Hidden=true;
 // Translate the plane instead of subtracting floating interval endpoints:
 // a 0.6 m Z extent must remain 61 nodes at dx=.01, not round up to62.
 domainBox.SetPersistentData(new Box(new Plane(new Point3d(-.2,-.5,-.2),Vector3d.XAxis,Vector3d.YAxis),new Interval(0,.8),new Interval(0,1),new Interval(0,.6)));
 var domain=Hawa("Domain",1480,620);Wire(domainBox,domain,0);Wire(cell,domain,1);Text(domain,2,"meters");
 var gridReport=Panel("Requested grid / CPU limit 500000 cells","",1740,650,300,120);gridReport.AddSource(Output(domain,"Grid"));
 var physics=Hawa("Physics",1480,920);Number(physics,0,1);Number(physics,1,.01);Number(physics,2,1);Text(physics,3,"bgk");Number(physics,4,.03);
 var viscosity=Slider("Synthetic viscosity (m²/s)",.01m,.001m,.1m,4,1220,1000);Wire(viscosity,physics,1);
 var boundaries=Hawa("Boundaries",1740,920);foreach(int side in new[]{2,3,4,5})Text(boundaries,side,"slip");
 var emptyCase=Hawa("Case",2220,850);Connect(domain,0,emptyCase,0);Connect(physics,0,emptyCase,2);Connect(boundaries,0,emptyCase,3);
 var bounds=Hawa("DomainPreview",1980,650);Connect(domain,0,bounds,0);bounds.Hidden=false;
 var alphaFirst=Slider("First angle (deg)",-3,-10,10,2,2220,1080);
 var alphaSecond=Slider("Second angle (deg)",3,-10,10,2,2220,1170);
 var speed=Slider("Study speed (m/s)",1,.1m,3,2,2220,1260);
 var angles=Add(new Param_Number(),2460,650);angles.NickName="Angle cases (deg) / ordered sources";angles.AddSource(alphaFirst);angles.AddSource(alphaSecond);
 var speeds=Add(new Param_Number(),2460,750);speeds.NickName="Speed cases (m/s) / cross product";speeds.AddSource(speed);
 var probes=Add(new Param_Point(),2460,850);probes.NickName="Fluid pressure probes (m)";probes.SetPersistentData(new Point3d(-.1,0,.1));probes.Hidden=true;
 var settling=Slider("Settling steps",3000,0,20000,0,2700,650);
 var samples=Slider("Sample steps",201,4,2000,0,2700,750);
 var tolerance=Slider("Stationarity tolerance (absolute coefficient)",.05m,.001m,.1m,3,2700,850);
 var selected=Slider("Selected case index",0,0,1,0,2940,650);
 var run=Toggle("Run / explicit re-arm",2940,750);var pause=Toggle("Pause study",2940,850);var cancel=Toggle("Cancel study",2940,950);
 var study=Hawa("StationaryStudy",3420,760);
 if(study.ComponentGuid!=new Guid("4823e5ad-f4fb-4b62-96e3-127989a184b5"))throw new Exception("Unexpected Stationary Study identity");
 Named(Output(emptyCase,"Case"),study,"Case");Named(wing,study,"Mesh");Named(angles,study,"Angles");Named(speeds,study,"Speeds");
 Named(area.Params.Output[0],study,"Reference area");Named(mac.Params.Output[0],study,"Reference chord");Named(pivot.Params.Output[0],study,"Pivot");Named(probes,study,"Probes");
 Named(settling,study,"Settling steps");Named(samples,study,"Sample steps");Named(tolerance,study,"Stationarity tolerance");Named(selected,study,"Selected case");Named(run,study,"Run");Named(pause,study,"Pause");Named(cancel,study,"Cancel");
 var progress=Panel("Study progress / failures","",3680,720,440,220);progress.AddSource(Output(study,"Report"));
 var identity=Panel("Selected capture identity","",3680,990,440,220);identity.AddSource(Output(study,"Identity"));
 var cases=Panel("Ordered case results / rejected slots stay empty","",4180,720,460,290);cases.AddSource(Output(study,"Cases"));
 var force=Stock("a50fcd4a-cf42-4c3f-8616-022761e6cc93","Total selected-body fluid force",4180,1100);Wire(Output(study,"Force"),force,0);
 var drag=Panel("Total drag +X (N) / selected window mean","",4450,1100,350,100);drag.AddSource(Output(study,"Drag"));
 var lift=Panel("Total lift +Z (N) / selected window mean","",4450,1240,350,100);lift.AddSource(Output(study,"Lift"));
 var sideForce=Panel("Total side force +Y (N)","",4180,1270,230,90);sideForce.AddSource(Output(force,"Y component"));
 var moment=Panel("Moment about pivot (N m) / world axes","",4450,1380,350,100);moment.AddSource(Output(study,"Moment"));
 var colors=Hawa("ColorMap",3680,1400);Text(colors,0,"diverging");Number(colors,1,-2);Number(colors,2,2);Text(colors,3,"Pa");
 var pressureLow=Slider("Pressure colour lower (Pa)",-2,-20,0,2,3420,1400);var pressureHigh=Slider("Pressure colour upper (Pa)",2,0,20,2,3420,1490);Wire(pressureLow,colors,1);Wire(pressureHigh,colors,2);
 var offsetDistance=Expression("1.5*x","Pressure sample offset (m)",3420,1600,cell);
 var surface=Hawa("SurfaceField",4180,1570);Wire(Output(study,"Field"),surface,0);Wire(Output(study,"Selected mesh"),surface,1);Connect(offsetDistance,0,surface,3);Connect(colors,0,surface,4);surface.Hidden=false;
 var valid=Panel("Local sampled pressure validity / not local force","",4450,1590,400,150);valid.AddSource(Output(surface,"Valid"));
 var pressure=Panel("Sampled surface pressure (Pa)","",4450,1780,400,180);pressure.AddSource(Output(surface,"Values"));
 var legend=Hawa("Legend",4180,1870);Connect(colors,0,legend,0);var legendPlane=(Param_Plane)legend.Params.Input[1];legendPlane.PersistentData.Clear();legendPlane.SetPersistentData(new Plane(new Point3d(.7,-.4,0),Vector3d.XAxis,Vector3d.ZAxis));Number(legend,2,.3);legend.Hidden=false;
 Scatter(Output(study,"Angles"),Output(study,"CL"),"CL versus angle","Angle (deg)","CL",.05,.5,0,4900,0);
 Scatter(Output(study,"Angles"),Output(study,"CD"),"CD versus angle","Angle (deg)","CD",.05,.2,1.2,4900,600);
 Scatter(Output(study,"CD"),Output(study,"CL"),"CL versus CD","CD","CL",.2,.5,2.2,4900,1200);
 Group("01 / Dimensions and distinct section shapes",rootCode,tipCode,rootChord,tipChord,span,cell,sectionPlane,rootFoil,tipFoil);
 Group("02 / Quarter-chord placement and fixed references",offset,positiveSpan,negativeSpan,area,mac,quarter,pivot);
 Group("03 / Ordinary GH loft, caps and closed mesh",plusVector,minusVector,tipPlus,tipMinus,sections,loft,cap,solid,closed,meshBrep,join,weld,normals,wing,geometryCheck,geometryReport);
 Group("04 / Fixed tunnel and synthetic fluid",runtime,initialize,runtimeReport,domainBox,domain,gridReport,physics,viscosity,boundaries,emptyCase,bounds);
 Group("05 / Explicit stationary study",alphaFirst,alphaSecond,speed,angles,speeds,probes,settling,samples,tolerance,selected,run,pause,cancel,study,progress,identity,cases);
 Group("06 / Total loads and selected pressure",force,drag,lift,sideForce,moment,colors,pressureLow,pressureHigh,offsetDistance,surface,valid,pressure,legend);
 Panel("Hawa guide / purpose","HAWA / 35\nEDITABLE WING STUDY\n\nTwo distinct offline airfoil sections. Edit chord/span/NACA controls; ordinary GH components loft and cap the wing. The resulting closed mesh is the actual study input. Read 35-parametric-wing-study.md.",0,-410,410,340);
 Panel("Hawa guide / operation","START EXPLICITLY\n\nOpen in a metre document. Initialize runtime if needed. Wait for accepted geometry, then enable the study. Pause/cancel cooperatively. Changes invalidate the previous study; re-arm explicitly. Reopen remains idle. Choose a returned candidate to inspect its matching field and identity.",440,-410,410,340);
 Panel("Hawa guide / limits","EXPERIMENTAL CPU WORKFLOW\n\nSynthetic viscosity and coarse full-way walls. Grid/domain sensitivity and physical reference qualification remain open. A finer visible wing or smooth plot is not engineering accuracy. Keep failed candidates visible. No lifting-line or external polar values are substituted for CFD.",880,-410,410,340);
 // Serialize idle without canvas activation or a solver solution. Root verifies an owned copy.
 if(document.Objects.OfType<GH_BooleanToggle>().Any(t=>t.Value))throw new Exception("All run controls must open off");
 document.FilePath=path;document.Enabled=true;
 if(!new GH_DocumentIO{Document=document}.SaveQuiet(path))throw new Exception("Cannot save new wing definition");
 Console.WriteLine("Created "+path+"; verify closed solid/mesh, live study, annotations and reopen before acceptance.");
}finally{document.Dispose();}
