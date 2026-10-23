"""Independent licensed D-PHY5.8 probe; existing CSI5.15 stays untouched."""
from pathlib import Path
import sys,shutil
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build/dphy_bridge'
sys.path.append('E:/software/efinity/ipm/bin')
from ipm_api_service.design import IPMDesignAPI
def main():
 BUILD.mkdir(parents=True,exist_ok=True)
 for suffix in ('.xml','.peri.xml'):
  shutil.copyfile(ROOT/'build/camera_vga'/('ti60_camera'+suffix),BUILD/('ti60_camera'+suffix))
 api=IPMDesignAPI(device_name='Ti60F225',family_name='Titanium',project_path=BUILD,is_verbose=False)
 api.create_ip(module_name='camera_dphy',vendor='efinixinc.com',library='mipi',name='efx_dphy_rx')
 api.config_ip(module_name='camera_dphy',configs={'NUM_DATA_LANE':'4','HS_BYTECLK_MHZ':'70','CLOCK_FREQ_MHZ':'100',
  'DPHY_CLOCK_MODE':'"Discontinuous"','ENABLE_USER_DESKEWCAL':"1'b0"})
 good,validation,_=api.validate_ip(module_name='camera_dphy');assert good,validation
 print(api.generate_ip(module_name='camera_dphy'))
if __name__=='__main__':main()
