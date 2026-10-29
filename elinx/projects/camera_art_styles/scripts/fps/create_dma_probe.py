"""Create independent C6/RF33 DMA experiment wrappers; no production XML edits."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'rtl/fps'
for source,target,replacements in [
 ('video_cnn_view_pipe.sv','fps_cnn_view.sv',[
  ('video_cnn_view_pipe','fps_cnn_view'),('video_cnn_tile5_pipe','fps_cnn5')]),
 ('video_cnn_async.sv','fps_cnn_async.sv',[
  ('video_cnn_async','fps_cnn_async'),('video_cnn_view_pipe','fps_cnn_view')]),
 ('video_tile_engine_async.sv','fps_tile_engine.sv',[
  ('video_tile_engine_async','fps_tile_engine'),('video_cnn_async','fps_cnn_async'),
  ('TILE_CORE=48,HALO=32','TILE_CORE=640,HALO=16')])]:
 text=(ROOT/'rtl/p720'/source).read_text()
 for old,new in replacements:
  assert old in text,old
  text=text.replace(old,new)
 (OUT/target).write_text('// INDEPENDENT FPS EXPERIMENT. Not used by the signed camera project.\n'+text)
