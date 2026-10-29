"""Inventory reproducible caches; protect every referenced file and old releases."""
from pathlib import Path
import json,os,re
WS=Path(__file__).resolve().parents[4];ROOT=Path(__file__).resolve().parents[1]


def strings(value):
    if isinstance(value,str):yield value
    elif isinstance(value,dict):
        for k,v in value.items():yield str(k);yield from strings(v)
    elif isinstance(value,list):
        for v in value:yield from strings(v)


def main():
    projects=[p for platform in ['elinx','xilinx'] for p in (WS/platform/'projects').iterdir() if p.is_dir()]
    references=set();json_count=0;dirs=[]
    for project in projects:
        for current,children,files in os.walk(project):
            children[:]=[n for n in children if n not in ['vendor','.git','__pycache__']]
            for name in files:
                if not name.endswith('.json'):continue
                path=Path(current)/name
                try:data=json.loads(path.read_text(encoding='utf-8-sig'))
                except (OSError,ValueError):continue
                json_count+=1
                for value in strings(data):
                    if re.match(r'^[A-Za-z]:[\\/]',value):
                        try:references.add(Path(value).resolve())
                        except (OSError,ValueError):pass
    for parent in [*projects,WS/'pycode']:
        for current,children,files in os.walk(parent):
            children[:]=[n for n in children if n not in ['vendor','.git','elinxdemo','xc7k325tffg_base']]
            if 'baseline_720p60_20261013' in Path(current).parts:children[:]=[];continue
            for name in list(children):
                if name not in ['work_syn','work_pnr','__pycache__','work','.Xil']:continue
                path=(Path(current)/name).resolve()
                if name=='work' and 'sim' not in [p.lower() for p in path.parts]:continue
                assert path.is_relative_to(WS) and path!=WS and not path.is_symlink()
                children.remove(name);bound=[str(p) for p in references if p==path or path in p.parents]
                if bound:continue
                members=list(path.rglob('*'))
                if any(p.is_symlink() or p.is_junction() for p in [path,*members]):continue
                dirs.append(dict(path=str(path),bytes=sum(p.stat().st_size for p in members if p.is_file()),files=sum(p.is_file() for p in members)))
    result=dict(workspace=str(WS),json_manifests_checked=json_count,referenced_paths=len(references),directories=dirs,bytes=sum(x['bytes'] for x in dirs),files=sum(x['files'] for x in dirs),scope='Only unreferenced reproducible work/cache directories; no project/IP/bit/model/report/source/demo deletion')
    target=ROOT/'build/cleanup_plan.json';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,indent=2),encoding='utf-8');print('PLAN',len(dirs),'directories',result['bytes'],'bytes',json_count,'manifests')


if __name__=='__main__':main()
