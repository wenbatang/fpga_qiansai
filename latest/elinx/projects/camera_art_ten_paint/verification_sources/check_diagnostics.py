"""Actual CAM7 UART serial bits plus ten-style/ten-digit parser checks."""
from pathlib import Path
import importlib.util,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from simutil import questa,sha


def main():
    folder=ROOT/'sim/diagnostics';folder.mkdir(parents=True,exist_ok=True)
    tb=r'''module tb;
reg clk=0;always #5 clk=~clk;
reg reset=1;reg[1055:0]fields=0;wire tx;
camera_view_uart #(.CLK_HZ(1000000),.BAUD(100000),.PERIOD_CYCLES(35000))dut(.*);
integer i,j,k,frame_no,byte_no,stream,checks=0;reg[7:0]got,want;
function automatic[31:0] value_for(input integer f,input integer field_no);
begin value_for=32'h1234abcd^(32'h01030507*field_no)^(f?32'h89ab5678:32'd0);
if(field_no==32)value_for=(9<<2)|(7<<6)|(2<<11)|(1<<13)|(2<<15)|(9<<17)|((10|(4<<4)|128|256|512)<<21);
end endfunction
task set_fields(input integer f);
begin for(i=0;i<33;i=i+1)fields[1055-i*32-:32]=value_for(f,i);end endtask
function automatic[7:0] expected_byte(input integer f,input integer pos);
integer rel,index,offset;reg[31:0]v;reg[3:0]n;
begin
if(pos<6)case(pos)
0:expected_byte="@";1:expected_byte="C";2:expected_byte="A";
3:expected_byte="M";4:expected_byte="7";5:expected_byte=",";
endcase
else if(pos==302)expected_byte=13;
else if(pos==303)expected_byte=10;
else begin
rel=pos-6;index=rel/9;offset=rel%9;v=value_for(f,index);
if(offset==8)expected_byte=",";
else begin n=(v>>(28-4*offset))&15;expected_byte=n<10?"0"+n:"A"+n-10;end
end
end endfunction
initial begin
stream=$fopen("reports.txt","wb");set_fields(0);
repeat(4)@(negedge clk);reset=0;
for(frame_no=0;frame_no<2;frame_no=frame_no+1)begin
for(byte_no=0;byte_no<304;byte_no=byte_no+1)begin
@(negedge tx);repeat(5)@(posedge clk);#1;
if(tx!==0)$fatal(1,"missing start");
got=0;
for(k=0;k<8;k=k+1)begin repeat(10)@(posedge clk);#1;got[k]=tx;end
repeat(10)@(posedge clk);#1;if(tx!==1)$fatal(1,"bad stop");
want=expected_byte(frame_no,byte_no);
if(got!==want)$fatal(1,"frame%0d byte%0d got%02h expected%02h",frame_no,byte_no,got,want);
$fwrite(stream,"%c",got);checks=checks+1;
// Change every field during the first report: it must retain the old snapshot.
if(frame_no==0 && byte_no==20)set_fields(1);
end
end
$fclose(stream);$display("PASS CAM7 UART608 bytes/4864 data bits, prefix/33 fields/CRLF/8N1, atomic snapshot checks=%0d",checks);$finish;
end
initial begin #1000000;$fatal(1,"timeout");end
endmodule'''
    (folder/'tb.sv').write_text(tb,encoding='utf-8')
    production=ROOT/'rtl/view/camera_view_uart.sv'
    questa(folder,[folder/'tb.sv',production])
    spec=importlib.util.spec_from_file_location('gesture_cam7',ROOT/'pc/camera_view.py')
    parser=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser)
    tests=parser.self_test();reports=(folder/'reports.txt').read_bytes().splitlines()
    assert len(reports)==2 and all(len(line)==302 for line in reports)
    for frame_no,line in enumerate(reports):
        decoded=parser.decode(line);assert decoded['protocol']=='CAM7'
        expected=[(0x1234abcd^(0x01030507*i)^(0x89ab5678 if frame_no else 0))&0xffffffff for i in range(33)]
        expected[32]=(9<<2)|(7<<6)|(2<<11)|(1<<13)|(2<<15)|(9<<17)|((10|(4<<4)|128|256|512)<<21)
        assert decoded['all_fields']==expected
    import json
    files=[Path(__file__),folder/'tb.sv',production,ROOT/'pc/camera_view.py',folder/'reports.txt',ROOT/'scripts/simutil.py']
    (folder/'verification.json').write_text(json.dumps(dict(result='PASS',scope='Actual CAM7 UART RTL;608 serial bytes/all33 fields/8N1/CRLF/in-flight atomic snapshot, offline parser only; no serial hardware access',parser_cases=tests['synthetic_cases'],serial_reports=2,serial_bytes=608,sources_sha256={str(p):sha(p) for p in files},logs_sha256={str(p):sha(p) for p in folder.glob('*.log')}),indent=2),encoding='utf-8')
    print('PASS diagnostics',tests['synthetic_cases'],'parser cases and two complete CAM7 UART reports')


if __name__=='__main__':main()
