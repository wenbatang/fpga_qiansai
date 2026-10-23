"""Generate a new minimal Sapphire instance; never modify reference IP."""
from pathlib import Path
import json, os, sys, shutil
ROOT = Path(__file__).resolve().parents[1]
WS = ROOT.parents[2]
BUILD = ROOT / 'build/camera_ppi'
EF = Path(os.environ.get('EFINITY_HOME', 'E:/software/efinity'))
sys.path.append(str(EF / 'ipm/bin'))
from ipm_api_service.design import IPMDesignAPI

def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    project = BUILD / 'ti60_camera.xml'
    if not project.exists():
        template=WS/'elinx/projects/uart_style_tiles/build/vga/ti60_style.xml'
        project.write_text(template.read_text().replace('name="ti60_style"','name="ti60_camera"'),encoding='utf-8')
    # This is a fail-closed placeholder until build_firmware.py supplies the
    # real Intel HEX. It loops without touching I/O, SPI, or external memory.
    boot = BUILD / 'firmware.hex'
    if not boot.exists():
        boot.write_text(':02000004F90001\n:040000006F0000008D\n:00000001FF\n')
    api = IPMDesignAPI(device_name='Ti60F225', family_name='Titanium',
                       project_path=BUILD, is_verbose=True)
    # API instances keep configuration in memory, even when a settings file
    # exists. Re-create this project's own instance for every fresh generation.
    api.create_ip(module_name='control_soc', vendor='efinixinc.com',
                  library='soc', name='efx_soc')
    settings = {
        'Frequency':'100', 'OCRSize':'32768', 'Cache':"1'b0",
        'DDR':"1'b0", 'AXIMaster':"1'b0", 'AXISlave':"1'b0",
        'SPI0':"1'b0", 'UART0':"1'b0", 'I2C0':"1'b0",
        'GPIO0':"1'b0", 'DEBUG':"1'b0", 'CO_DEBUG':"1'b0",
        'APBSlave0':"1'b1", 'APBSlave0_Size':'65536',
        'USER_0_INTR':"1'b1", 'USER_0_INTR_ID':'16',
        'HexFile_PathEnable':"1'b1", 'HexFile_Path':'"'+boot.as_posix()+'"',
        'SW_REMOVED':"1'b1"
    }
    api.config_ip(module_name='control_soc', configs=settings)
    good, validation, templates = api.validate_ip(module_name='control_soc')
    (BUILD / 'soc_validation.txt').write_text(str(validation), encoding='utf-8')
    if not good:
        raise RuntimeError('Sapphire parameter validation failed: '+str(validation))
    result = api.generate_ip(module_name='control_soc')
    print(result)
    if not (BUILD / 'ip/control_soc/control_soc.v').exists():
        raise RuntimeError('No generated Sapphire wrapper')
    print('Sapphire generated in', BUILD)

if __name__ == '__main__':
    main()
