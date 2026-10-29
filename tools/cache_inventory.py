"""Read-only inventory of unreferenced Questa work libraries in own projects.

No deletion API. Preserve all project sources, IP, models, delivery artifacts,
reports, logs and reference/demo trees. Review the exact directory list before
removing any compiled library with native filesystem tools.
"""
from pathlib import Path
import argparse,json,os,re
WS=Path(__file__).resolve().parents[1]


def strings(value):
    if isinstance(value,str):yield value
    elif isinstance(value,dict):
        for key,item in value.items():yield str(key);yield from strings(item)
    elif isinstance(value,list):
        for item in value:yield from strings(item)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve();assert output.is_relative_to(WS) and 'build' in output.parts
    projects=[p for family in ['elinx','xilinx'] for p in (WS/family/'projects').iterdir() if p.is_dir()]
    references=set();manifests=0
    for project in projects:
        for current,children,files in os.walk(project):
            children[:]=[name for name in children if name not in ['vendor','work','work_syn','work_pnr','__pycache__','.git']]
            for name in files:
                if not name.endswith('.json'):continue
                try:value=json.loads((Path(current)/name).read_text(encoding='utf-8-sig'))
                except (OSError,ValueError):continue
                manifests+=1
                for item in strings(value):
                    if re.match(r'^[A-Za-z]:[\\/]',item):references.add(Path(item).resolve())
    entries=[];protected=[]
    for project in projects:
        for current,children,files in os.walk(project):
            children[:]=[name for name in children if name not in ['vendor','__pycache__','.git','baseline_720p60_20261013']]
            for name in list(children):
                if name!='work':continue
                path=(Path(current)/name).resolve();children.remove(name)
                if 'sim' not in [p.lower() for p in path.parts]:continue
                if not path.is_relative_to(WS) or path==WS:continue
                if any(p==path or path in p.parents for p in references):protected.append(str(path));continue
                members=list(path.rglob('*'))
                if any(p.is_symlink() or p.is_junction() for p in [path,*members]):continue
                # Plain source/parameters/results inside a library are unusual:
                # retain them rather than interpreting their importance.
                keep={'.v','.sv','.vh','.svh','.vhd','.vhdl','.py','.pdf','.md','.bit','.hex','.bin','.mem','.coe','.rpt','.log'}
                if any(p.is_file() and p.suffix.lower() in keep for p in members):continue
                entries.append(dict(path=str(path),bytes=sum(p.stat().st_size for p in members if p.is_file()),files=sum(p.is_file() for p in members)))
    entries.sort(key=lambda row:row['bytes'],reverse=True)
    result=dict(scope='Read-only inventory; only unreferenced compiled sim/work libraries',manifests_checked=manifests,reference_paths=len(references),directories=entries,protected=protected,bytes=sum(row['bytes'] for row in entries))
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('MANIFESTS',manifests,'REFERENCES',len(references),'CANDIDATES',len(entries),'GiB',round(result['bytes']/2**30,3))
    for row in entries[:16]:print(f"{row['bytes']/2**20:9.1f} MiB  {row['path']}")


if __name__=='__main__':main()
