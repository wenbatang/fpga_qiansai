"""Copy reviewed test sources, never compiled work or old receipts."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT.parent/'camera_full720_30'


def main():
    for source in (BASE/'sim').rglob('*'):
        rel=source.relative_to(BASE/'sim')
        if any(x in rel.parts for x in ['work','__pycache__']) or source.suffix not in ['.py','.sv','.v','.tcl']:continue
        if source.name.startswith(('archive_','finalize_','prepare_','run_','check_delivery')):continue
        target=ROOT/'sim'/rel
        if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    helper=ROOT/'scripts/simutil.py';text=helper.read_text(encoding='utf-8').replace("WS/'pycode/full720_style'","WS/'pycode/painterly_style'").replace("'full_shared_params.sv'","'full_parameter_bank.sv'");helper.write_text(text,encoding='utf-8')
    kernel=ROOT/'sim/check_kernel.py';text=kernel.read_text(encoding='utf-8').replace('.cfg_data(cd));',".cfg_data(cd),.split_mode(1'b0));");assert '.split_mode' in text;kernel.write_text(text,encoding='utf-8')
    probe=ROOT/'scripts/probe.py';text=probe.read_text(encoding='utf-8').replace("'full_shared_params.sv'","'full_parameter_bank.sv'").replace('.cfg_data(cfg_data));endmodule',".cfg_data(cfg_data),.split_mode(1'b0));endmodule");assert '.split_mode' in text;probe.write_text(text,encoding='utf-8')
    for directory in [ROOT/'sim/templates',ROOT/'sim/fps_reader',ROOT/'sim/scheduling']:
        for path in directory.glob('*'):
            if path.suffix in ['.sv','.py']:
                text=path.read_text(encoding='utf-8');text=text.replace(BASE.as_posix(),ROOT.as_posix()).replace(str(BASE),str(ROOT));path.write_text(text,encoding='utf-8')
    print('Copied verification sources and full runtime-model source list')


if __name__=='__main__':main()
