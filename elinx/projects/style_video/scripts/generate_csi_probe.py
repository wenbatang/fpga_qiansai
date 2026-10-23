"""Isolated SAME-version CSI 5.15 probe, no modification of current camera IP."""
from pathlib import Path
import sys,shutil,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'build/csi515_probe'
sys.path.append('E:/software/efinity/ipm/bin')
from ipm_api_service.design import IPMDesignAPI
def main():
 component=ET.parse('E:/software/efinity/ipm/ip/efx_csi2/efx_csi2_rx/ipm/ip_component.xml')
 assert component.getroot().find('{http://www.accellera.org/XMLSchema/IPXACT/1685-2014}version').text=='5.15'
 BUILD.mkdir(parents=True,exist_ok=True)
 for suffix in ('.xml','.peri.xml'):shutil.copyfile(ROOT/'build/camera_vga'/('ti60_camera'+suffix),BUILD/('ti60_camera'+suffix))
 api=IPMDesignAPI(device_name='Ti60F225',family_name='Titanium',project_path=BUILD,is_verbose=False)
 api.create_ip(module_name='camera_csi',vendor='efinixinc.com',library='mipi',name='efx_csi2_rx')
 configs={'NUM_DATA_LANE':'4','ASYNC_STAGE':'2','HS_BYTECLK_MHZ':'70','CLOCK_FREQ_MHZ':'100',
  'DPHY_CLOCK_MODE':'"Discontinuous"','PIXEL_FIFO_DEPTH':'1024','AREGISTER':'8','FRAME_MODE':'"GENERIC"',
  'ENABLE_VCX':"1'b0",'Pack_40':"1'b1",'Pack_48':"1'b0",'Pack_56':"1'b0",'Pack_64':"1'b0",
  'MIPI_CSI2_RX_DEBUG':"1'b1",'MIPI_CSI2_RX_PIXEL_SIDEBAND':"1'b1"}
 api.config_ip(module_name='camera_csi',configs=configs)
 good,validation,_=api.validate_ip(module_name='camera_csi');(BUILD/'validation.txt').write_text(str(validation))
 assert good,validation
 print(api.generate_ip(module_name='camera_csi'))
 print('Generated isolated CSI 5.15 RAW10 + pixel-sideband probe')
if __name__=='__main__':main()
