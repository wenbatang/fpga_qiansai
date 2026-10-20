"""Run the supported Efinity CLI in a project-local Windows environment."""
from pathlib import Path
import os
import sys

tool = Path(os.environ['EFINITY_HOME'])
sys.path.insert(0, str(tool / 'scripts'))
import efx_run

sys.argv = [str(tool / 'scripts/efx_run.py'), 'style_video.xml', '--flow', 'compile']
efx_run.set_efinity_user_dir_env()
args = efx_run.parse_options()
efx_run.resolve_prj_xml_filename(args)
efx_run.check_paths_ascii(args)
efx_run.build_cmdline_options(args)
raise SystemExit(0 if efx_run.run_flow(args) is True else 1)
