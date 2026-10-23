"""Record immutable training sources, then run the six-style experiment."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
from art6_catalog import ROOT,RUN,prepare

def main():
 if (RUN/'complete.json').exists():raise FileExistsError('Preserve completed experiment; use a new RUN directory for another training generation')
 prepare();RUN.mkdir(parents=True,exist_ok=True)
 files=['train_art6.py','art6_catalog.py','hardware_network.py','style_network.py','train_style.py','train_optimized.py','export_hardware.py','start_art6.py']
 hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files}
 receipt=RUN/'launch_sources.json'
 if receipt.exists() and json.loads(receipt.read_text())!=hashes:raise ValueError('Existing launch source set differs; choose a fresh experiment')
 receipt.write_text(json.dumps(hashes,indent=2))
 archive=RUN/'source_snapshot';archive.mkdir(exist_ok=True)
 for name in files:
  target=archive/name
  if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=hashes[name]:raise ValueError('Changed source snapshot '+name)
  if not target.exists():shutil.copy2(ROOT/name,target)
 subprocess.run([sys.executable,'-u',str(ROOT/'train_art6.py'),*sys.argv[1:]],cwd=ROOT,check=True)
if __name__=='__main__':main()
