"""Optional official VGG download for training only, never needed on the FPGA."""
import torch
if __name__=='__main__':
 torch.hub.load_state_dict_from_url('https://download.pytorch.org/models/vgg19-dcbb9e9d.pth',model_dir=str(__import__('pathlib').Path(torch.hub.get_dir())/'checkpoints'),check_hash=True,map_location='cpu')
 print('VGG ready in the PyTorch cache. It is not a repository or FPGA weight.')
