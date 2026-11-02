"""User's explicit, current handshape contract; no legacy label assumptions."""
SPEC_VERSION='user_20261102_v1'
SHAPES=[
 'five_fingers_curved_into_O',
 'index_only',
 'index_middle',
 'middle_ring_little',
 'index_middle_ring_little',
 'open_five_finger_palm',
 'thumb_little',
 'thumb_index_little',
 'thumb_index',
 'hooked_index',
]
ASL_CLASSES={0:'o',1:'d',2:'v',3:'f',4:'b',6:'y',8:'l',9:'x'}
SOURCE_STYLE_IDS=[0,2,3,4,34,7,9,15,31,40]
LEGACY_POSITIVES={1:1,2:2,4:4,5:5,6:6,8:8,9:9}
# Legacy fists/three/pinches do NOT silently become the new0/3/7.
