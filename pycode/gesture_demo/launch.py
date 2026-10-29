"""Launch the visible GUI with normal desktop DLL/COM lookup from Codex."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent;WS=ROOT.parents[1]
sys.path.insert(0,str(WS/'elinx/projects/camera_art_interactive/scripts'))
from desktop_process import run


if __name__=='__main__':
    local=ROOT/'.venv/Scripts/python.exe';python=str(local) if local.exists() else sys.executable
    raise SystemExit(run([python,'-B',str(ROOT/'app.py'),*sys.argv[1:]],ROOT,ROOT/'build/gui_console.log'))
