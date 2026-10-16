"""Public steady boundary acceptance; analytic and element oracles are independent."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np

from simcase import Document, run
from steady_boundary_independent_oracle import Elements, UNITS, close, slab

FIELDS = {
    "nodes_m": "m", "triangles": "1", "temperature_k": "K",
    "heat_flux_w_m2": "W/m^2", "load_w_per_m": "W/m",
    "reaction_w_per_m": "W/m", "residual_w_per_m": "W/m",
    "dirichlet_node_ids": "1", "dirichlet_temperature_k": "K",
    "prescribed_outward_load_w_per_m": "W/m", "ambient_load_w_per_m": "W/m",
    "convective_outward_w_per_m": "W/m", "system_rhs_w_per_m": "W/m",
}


def model(case="linear", n=8, unit="m"):
    L,H,k,Q,a,b,g,h,ta,D = slab(case)
    scale = UNITS[unit]
    return {"openphysics":"0.2", "name":"Independent steady boundary",
        "units":{"length":unit,"temperature":"K"},
        "geometry":{"domain":{"xmin":.1/scale,"xmax":(.1+L)/scale,
                               "ymin":.2/scale,"ymax":(.2+H)/scale}},
        "materials":{}, "physics":{"heat1":{"type":"thermal.steady2d",
            "conductivity_w_mk":k,"heat_source_w_m3":Q,
            "dirichlet_temperature_k":D,"outward_flux_w_m2":g,
            "convection":{s:{"h_w_m2k":v,"ambient_temperature_k":ta[s]} for s,v in h.items()}}},
        "mesh":{"subdivisions":[n,n]}, "study":{"type":"single"},
        "results":{"save_fields":True,"plots":False}}


def read_saved(out, version=2):
    out=Path(out)
    s=json.loads((out/"summary.json").read_text(encoding="utf-8"))
    with np.load(out/"fields.npz",allow_pickle=False) as archive:
        arrays={key:np.array(archive[key],copy=True) for key in archive.files}
    fmt="thermal.steady2d-result-v"+str(version)
    layout="thermal2d-p1-node-cell"+("-boundary" if version==2 else "")+"-v"+str(version)
    if s["physics_type"]!="thermal.steady2d" or s["result_format"]!=fmt or s["field_layout"]!=layout:
        raise AssertionError("summary identifiers")
    if arrays["result_format"].item()!=fmt or arrays["field_layout"].item()!=layout:
        raise AssertionError("NPZ identifiers")
    if json.loads(arrays["metadata_json"].item()) != s:
        raise AssertionError("metadata")
    fields=FIELDS if version==2 else dict(list(FIELDS.items())[:9])
    for key,unit in fields.items():
        value=arrays[key]
        if value.dtype.kind not in "iuf" or not np.isfinite(value).all():
            raise AssertionError("real finite "+key)
        if s["field_units"][key]!=unit or s["field_shapes"][key]!=list(value.shape):
            raise AssertionError("units/shape "+key)
        location=("nodes" if key not in ("triangles","heat_flux_w_m2","dirichlet_node_ids","dirichlet_temperature_k")
                  else {"triangles":"triangle_connectivity","heat_flux_w_m2":"triangle_centroids",
                        "dirichlet_node_ids":"dirichlet_nodes","dirichlet_temperature_k":"dirichlet_nodes"}[key])
        if s["field_locations"][key]!=location:
            raise AssertionError("location "+key)
    if (out/".incomplete").exists():
        raise AssertionError("incomplete")
    return s,arrays


def audit(arrays,data,case,patch=False):
    L,H,k,Q,a,b,g,h,ta,D=slab(case)
    x,t,T=arrays["nodes_m"],arrays["triangles"],arrays["temperature_k"]
    e=Elements(x,t,k,Q)
    close(x.min(axis=0),np.array([.1,.2]),1.,"origin")
    close(x.max(axis=0),np.array([.1+L,.2+H]),1.,"extent")
    close(np.array(e.area.sum()),np.array(L*H),L*H,"area")
    G,B,HT=e.boundary(T,g,h,ta)
    rhs=e.f+B-G
    r=e.stiffness(T)+HT-rhs
    selected=set()
    for side in D:
        selected.update(e.sides[side].ravel().tolist())
    fixed=np.array(sorted(selected),dtype=int)
    if not np.array_equal(arrays["dirichlet_node_ids"],fixed):
        raise AssertionError("independent fixed identity")
    reaction=np.zeros(len(x));reaction[fixed]=r[fixed]
    rate=max(np.sum(abs(e.f))+np.sum(abs(G))+np.sum(abs(B))+np.sum(abs(HT))+
             np.sum(abs(reaction)),np.finfo(float).tiny)
    for key,value in (("load_w_per_m",e.f),("prescribed_outward_load_w_per_m",G),
                      ("ambient_load_w_per_m",B),("convective_outward_w_per_m",HT-B),
                      ("system_rhs_w_per_m",rhs),("residual_w_per_m",r),
                      ("reaction_w_per_m",reaction)):
        close(arrays[key],value,rate,key)
    close(arrays["heat_flux_w_m2"],e.flux(T),max(1.,abs(k*b),abs(Q*L)), "element flux")
    free=np.setdiff1d(np.arange(len(x)),fixed)
    close(r[free],np.zeros(len(free)),rate,"free equilibrium")
    close(np.array((G+HT-B-reaction).sum()),np.array(e.f.sum()),rate,"signed heat balance")
    close(arrays["dirichlet_temperature_k"],np.full(len(fixed),a),max(1.,abs(a)),"fixed values")
    if patch:
        close(T,a+b*(x[:,0]-.1),300.,"linear patch")
        close(arrays["heat_flux_w_m2"],np.tile([-k*b,0.],(len(t),1)),max(1.,abs(k*b)),"analytic flux")
        close(np.array((G+HT-B).sum()),np.array(14.),14.,"14 W/m removal")
        close(np.array(-reaction.sum()),np.array(-14.),14.,"thermostat sign")
    return e


def saved(data,out,version=2):
    result=run(Document.from_dict(copy.deepcopy(data)),False)
    result.save(out)
    s,a=read_saved(out,version)
    return result,s,a


class TestSteadyBoundaryIndependent(unittest.TestCase):
    def test_linear_additive_units_and_raw13(self):
        baseline=None
        for unit in UNITS:
            with self.subTest(unit=unit),tempfile.TemporaryDirectory() as tmp:
                data=model(unit=unit)
                _,s,a=saved(data,Path(tmp)/"out")
                audit(a,data,"linear",True)
                if baseline is not None:
                    for key in FIELDS:
                        close(a[key],baseline[key],max(1.,np.max(abs(baseline[key]),initial=0.)),key,1e-9)
                baseline=a
                close(np.array(s["source_heat_w_per_m"]),np.array(0.),14.,"summary source")
                close(np.array(s["outward_heat_w_per_m"]),np.array(0.),14.,"summary total outward")

    def test_robin_only_and_zero_h_anchor(self):
        for case in ("robin","zero_h"):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as tmp:
                data=model(case)
                _,_,a=saved(data,Path(tmp)/"out")
                audit(a,data,case)
                self.assertEqual(a["dirichlet_node_ids"].shape,(0,))

    def test_quadratic_four_mesh_fixed_gates(self):
        primary=[];quad=[]
        for n in (8,16,32,64):
            with tempfile.TemporaryDirectory() as tmp:
                data=model("quadratic",n)
                _,_,a=saved(data,Path(tmp)/"out")
                e=audit(a,data,"quadratic")
                L,H,k,Q,aa,b,*_=slab("quadratic")
                primary.append(e.errors(a["temperature_k"],L,aa,b,Q,.1,8))
                quad.append(e.errors(a["temperature_k"],L,aa,b,Q,.1,10))
                close(np.array(e.f.sum()),np.array(60.),60.,"60 W/m source")
        primary,quad=np.asarray(primary),np.asarray(quad)
        orders=np.log2(primary[:-1]/primary[1:])
        self.assertTrue(np.all(orders[-2:,0]>=1.8),orders)
        self.assertTrue(np.all(orders[-2:,1]>=.9),orders)
        self.assertLess(float(np.max(abs(primary-quad)/primary)),.01)
        # Exact integral H * integral_0^L (Q*x-k*b)^2 dx.
        norm=np.sqrt(H*(Q*Q*L**3/3-Q*k*b*L*L+(k*b)**2*L))
        self.assertLessEqual(primary[-1,1]/norm,.02)
        print(json.dumps({"gate":"steady_boundary_independent_PDE","errors":primary.tolist(),
                          "quadrature10":quad.tolist(),"orders":orders.tolist(),
                          "finest_relative_flux":float(primary[-1,1]/norm)}))

    def test_v1_absence_v2_empty_presence(self):
        base=model()
        p=base["physics"]["heat1"]
        p.pop("outward_flux_w_m2");p.pop("convection")
        with tempfile.TemporaryDirectory() as tmp:
            _,_,old=saved(base,Path(tmp)/"v1",1)
            for key in ("outward_flux_w_m2","convection"):
                newer=copy.deepcopy(base);newer["physics"]["heat1"][key]={}
                _,_,new=saved(newer,Path(tmp)/key)
                for field in list(FIELDS)[:9]:
                    close(new[field],old[field],max(1.,np.max(abs(old[field]),initial=0.)),field)

    def test_snapshot_relabelling_and_fields_disabled(self):
        data=model()
        doc=Document.from_dict(copy.deepcopy(data));result=run(doc,False)
        doc["name"]="caller edited"
        with tempfile.TemporaryDirectory() as tmp:
            result.save(Path(tmp)/"snapshot")
            stored=json.loads((Path(tmp)/"snapshot"/"model.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["name"],data["name"])
            result.doc["name"]="invalid relabelling"
            with self.assertRaises(ValueError):
                result.save(Path(tmp)/"edited")
            data["results"]["save_fields"]=False
            result=run(Document.from_dict(data),False)
            result.save(Path(tmp)/"disabled")
            self.assertFalse((Path(tmp)/"disabled"/"fields.npz").exists())

    def test_strict_inputs_anchor_and_actual_corner(self):
        bad=[]
        for key,value in (("outward_flux_w_m2",None),("convection",[]),
                          ("convection",{"right":{"h_w_m2k":-1,"ambient_temperature_k":290}}),
                          ("convection",{"right":{"h_w_m2k":0,"ambient_temperature_k":-1}}),
                          ("outward_flux_w_m2",{"right":True}),
                          ("outward_flux_w_m2",{"right":float("inf")}),
                          ("convection",{"right":{"h_w_m2k":4}})):
            d=model();d["physics"]["heat1"][key]=value;bad.append(d)
        for g in (0.,1.):
            d=model();p=d["physics"]["heat1"];p["dirichlet_temperature_k"]={}
            p["convection"]={};p["outward_flux_w_m2"]={"right":g};bad.append(d)
        d=model();p=d["physics"]["heat1"];p["dirichlet_temperature_k"]={}
        p["convection"]={"right":{"h_w_m2k":0,"ambient_temperature_k":290}};bad.append(d)
        d=model(n=1);p=d["physics"]["heat1"];p["dirichlet_temperature_k"]={"top":300,"bottom":300}
        p["outward_flux_w_m2"]={"left":0};p["convection"]={};bad.append(d)
        for i,d in enumerate(bad):
            with self.subTest(case=i),self.assertRaises(ValueError):
                run(Document.from_dict(d),False)

    def test_one_fixed_corner_load_is_retained(self):
        d=model(n=2);p=d["physics"]["heat1"]
        p["dirichlet_temperature_k"]={"bottom":300};p["convection"]={}
        result=run(Document.from_dict(d),False)
        with tempfile.TemporaryDirectory() as tmp:
            result.save(Path(tmp)/"out");_,a=read_saved(Path(tmp)/"out")
            e=Elements(a["nodes_m"],a["triangles"],2.,0.)
            G,_,_=e.boundary(a["temperature_k"],{"right":2.},{},{})
            close(a["prescribed_outward_load_w_per_m"],G,2.,"full fixed-corner edge integral")
            fixed=a["dirichlet_node_ids"]
            self.assertGreater(float(G[fixed].sum()),0.)

    def test_cli_and_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/"model.json";out=root/"out"
            path.write_text(json.dumps(model()),encoding="utf-8")
            command=[sys.executable,"-I","-c",
                     "import sys;from simcase.cli import main;sys.exit(main(sys.argv[1:]))",
                     "run",str(path),"-q","-o",str(out)]
            done=subprocess.run(command,cwd=root,capture_output=True,text=True,encoding="utf-8")
            self.assertEqual(done.returncode,0,done.stdout+done.stderr)
            _,a=read_saved(out);audit(a,model(),"linear",True)
            before={p.name:p.read_bytes() for p in out.iterdir() if p.is_file()}
            done=subprocess.run(command,cwd=root,capture_output=True,text=True,encoding="utf-8")
            self.assertNotEqual(done.returncode,0)
            self.assertEqual(before,{p.name:p.read_bytes() for p in out.iterdir() if p.is_file()})

    def test_wrong_boundary_physics_and_saved_actors(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,_,a=saved(model(),Path(tmp)/"out")
            e=Elements(a["nodes_m"],a["triangles"],2.,0.)
            # Vary along the edge so consistent versus lumped H is observable.
            temperature=300+7*e.x[:,0]+3*e.x[:,1]**2
            G,B,HT=e.boundary(temperature,{"right":2.},{"right":4.},{"right":290.})
            truth=HT-B+G
            for variant in ("wrong_sign_G","missing_H","negative_H","missing_B","lumped_H","wrong_offset"):
                gg,bb,hh=e.boundary(temperature,{"right":2.},{"right":4.},{"right":290.},variant)
                with self.subTest(variant=variant),self.assertRaises(AssertionError):
                    close(hh-bb+gg,truth,max(1.,np.sum(abs(truth))),variant)
            for field,value in (
                ("load_w_per_m",a["system_rhs_w_per_m"]),
                ("ambient_load_w_per_m",np.zeros_like(a["ambient_load_w_per_m"])),
                ("prescribed_outward_load_w_per_m",-a["prescribed_outward_load_w_per_m"]),
                ("nodes_m",a["nodes_m"]*1000)):
                with self.subTest(field=field),self.assertRaises(AssertionError):
                    audit(dict(a,**{field:value}),model(),"linear",True)
            reaction=a["reaction_w_per_m"]
            # The thermostat alone is -14, total outward is zero in this source-free case.
            self.assertGreater(abs(-reaction.sum()),1.)

    def test_fixed_corner_and_total_outward_negative_actors(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=model(n=2);p=data["physics"]["heat1"]
            p["dirichlet_temperature_k"]={"bottom":300};p["convection"]={}
            _,_,a=saved(data,Path(tmp)/"corner")
            e=Elements(a["nodes_m"],a["triangles"],2.,0.)
            G,_,_=e.boundary(a["temperature_k"],{"right":2.},{},{})
            dropped=G.copy();dropped[a["dirichlet_node_ids"]]=0
            with self.assertRaises(AssertionError):
                close(dropped,G,2.,"dropped fixed-corner load")
            _,s,a=saved(model(),Path(tmp)/"linear")
            physical=(a["prescribed_outward_load_w_per_m"]+
                      a["convective_outward_w_per_m"]-a["reaction_w_per_m"]).sum()
            wrong=-a["reaction_w_per_m"].sum()
            with self.assertRaises(AssertionError):
                close(np.array(wrong),np.array(physical),14.,"thermostat-only total")
            close(np.array(s["outward_heat_w_per_m"]),np.array(physical),14.,"summary outward")

    def test_saved_labels_units_object_and_nonfinite_actors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,summary,arrays=saved(model(),root/"original")
            for variant in ("format","layout","units","object","nonfinite"):
                out=root/variant;out.mkdir()
                a={k:np.array(v,copy=True) for k,v in arrays.items()}
                metadata=copy.deepcopy(summary)
                if variant=="format":
                    a["result_format"]=np.asarray("thermal.steady2d-result-v1")
                elif variant=="layout":
                    a["field_layout"]=np.asarray("thermal2d-p1-node-cell-v1")
                elif variant=="units":
                    metadata["field_units"]["ambient_load_w_per_m"]="W"
                    a["metadata_json"]=np.asarray(json.dumps(metadata))
                elif variant=="object":
                    a["temperature_k"]=np.asarray([object()],dtype=object)
                else:
                    a["temperature_k"][0]=np.nan
                (out/"summary.json").write_text(json.dumps(metadata),encoding="utf-8")
                with (out/"fields.npz").open("wb") as stream:
                    np.savez(stream,**a)
                with self.subTest(variant=variant),self.assertRaises((ValueError,AssertionError)):
                    read_saved(out)
