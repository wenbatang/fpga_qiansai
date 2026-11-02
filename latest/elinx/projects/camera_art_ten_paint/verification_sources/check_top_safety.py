"""Run the actual new top/reset/boot with explicitly black-boxed functional IP."""
from pathlib import Path
import sys,re
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from simutil import *
IV=Path('E:/softare_FPGA/iverilog/iverilog/bin')
def main():
    folder=ROOT/'sim/top_safety';folder.mkdir(exist_ok=True)
    original=OLD/'sim/p720/check_top_safety.py'
    old=original.read_text(encoding='utf-8');tb=old.split("tb=r'''")[1].split("'''",1)[0]
    tb=tb.replace('keys=6;repeat(15)', 'for(i=0;i<3;i=i+1)begin keys=15^(1<<i);repeat(15)@(negedge ref_clk);if(!dut.sys_rst_n)$fatal(1,"non-reset key reset boot");keys=15;repeat(4)@(negedge ref_clk);end\n keys=7;repeat(15)')
    tb=tb.replace('keys=7;repeat(15)@(negedge ref_clk);safe();', 'keys=7;repeat(15)@(negedge ref_clk);healthy();')
    tb=tb.replace('if({ddr_pll_n,user_pll_n,core_pll_n}!==0)$fatal(1,"reset keys did not reset PLLs");','if({ddr_pll_n,user_pll_n,core_pll_n}!==7)$fatal(1,"UI key reset PLLs");')
    assert 'reset keys did not reset PLLs' not in tb
    (folder/'tb.sv').write_text(tb,encoding='utf-8')
    files=[folder/'tb.sv',ROOT/'build/720p/rtl/ti60_camera_ppi_top.sv',ROOT/'rtl/board_boot.sv',ROOT/'rtl/reset_sync.sv',ROOT/'rtl/view/camera_view_uart.sv']
    assert run([str(IV/'iverilog.exe'),'-g2012','-i','-s','tb','-o','test.vvp',*map(str,files)],folder,folder/'compile.log')==0
    assert run([str(IV/'vvp.exe'),'test.vvp'],folder,folder/'vsim.log')==0
    assert 'PASS actual top' in (folder/'vsim.log').read_text(encoding='utf-8');receipt(folder,[*files,Path(__file__),original],'Actual new top/reset/boot with functional IP explicitly black boxes; open-drain, ACK, PLL/calibration/stopped-clock/all four keys including held KEY3 do not reset; not analog/complete SoC')
if __name__=='__main__':main()
