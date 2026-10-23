"""Create the isolated reviewed MIG/clock IP only, without CNN synthesis."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/'uart_hdmi'
sys.path.insert(0,str(ROOT/'scripts'))
from desktop_process import run

def main():
 template=(BASE/'scripts/create_project_fast.tcl').read_text()
 template=template[:template.index('if {[lsearch -exact $argv --build]>=0} {')]
 template=template.replace('vivado_fast','vivado').replace('uart_hdmi.xpr','uart_style.xpr').replace('create_project uart_hdmi','create_project uart_style')
 template=template.replace('set_property top uart_hdmi_top','set_property top uart_style_top')
 script=ROOT/'scripts/create_ips.tcl';script.write_text(template)
 result=run(['E:/softare_FPGA/vivado2023/Vivado/2023.2/bin/vivado.bat','-mode','batch','-source',str(script)],ROOT/'build',ROOT/'build/prepare_ips.log')
 if result:raise RuntimeError('IP project preparation failed')
if __name__=='__main__':main()
