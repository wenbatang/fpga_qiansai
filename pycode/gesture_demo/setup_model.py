"""Download Google's official task bundle; inputs never leave this computer."""
from pathlib import Path
import hashlib,json,urllib.request,zipfile
ROOT=Path(__file__).resolve().parent
URL='https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task'


def main():
    path=ROOT/'assets/hand_landmarker.task';path.parent.mkdir(exist_ok=True)
    if not path.exists():urllib.request.urlretrieve(URL,path)
    assert zipfile.is_zipfile(path)
    with zipfile.ZipFile(path) as bundle:assert set(bundle.namelist())=={'hand_detector.tflite','hand_landmarks_detector.tflite'}
    manifest=dict(source=URL,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size)
    path.with_suffix('.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print('MODEL READY',manifest)


if __name__=='__main__':main()
