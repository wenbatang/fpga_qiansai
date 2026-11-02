"""Frozen local style IDs, in the user's gesture order."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
WS=ROOT.parents[1]
SOURCE_IDS=[0,2,3,4,34,7,9,15,31,40]
NAMES=['vangogh','ukiyoe','papercut','comic','bamboo_forest','asheville','contrast_of_forms','mondrian','mosaic','misty_mood_leonid_afremov']
LABELS=['梵高旋涡厚涂','浮世绘海浪','彩色剪纸','复古漫画','竹林水墨','阿什维尔抽象','形体对比','蒙德里安几何','彩色马赛克','雨夜厚涂']
CATALOG=[dict(slot=i,gesture=i,source_id=source_id,name=name,label=label) for i,(source_id,name,label) in enumerate(zip(SOURCE_IDS,NAMES,LABELS))]
