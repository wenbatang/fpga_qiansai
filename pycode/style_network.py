"""Compact feed-forward style network; inference does not require VGG."""
from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F


class ConvNorm(nn.Module):
    def __init__(self, incoming: int, outgoing: int, stride: int = 1, activate: bool = True):
        super().__init__()
        layers = [nn.ReflectionPad2d(1), nn.Conv2d(incoming, outgoing, 3, stride=stride),
                  nn.InstanceNorm2d(outgoing, affine=True)]
        if activate:
            layers.append(nn.ReLU(inplace=False))
        self.layers = nn.Sequential(*layers)

    def forward(self, x):
        return self.layers(x)


class ResidualBlock(nn.Module):
    def __init__(self, channels: int):
        super().__init__()
        self.layers = nn.Sequential(ConvNorm(channels, channels), ConvNorm(channels, channels, activate=False))

    def forward(self, x):
        return x + self.layers(x)


class StyleNetwork(nn.Module):
    def __init__(self, base_channels: int = 16, residual_blocks: int = 3, monochrome: bool = False):
        super().__init__()
        c = base_channels
        self.config = {"base_channels": c, "residual_blocks": residual_blocks, "monochrome": monochrome}
        self.encoder = nn.Sequential(ConvNorm(3, c), ConvNorm(c, c * 2, 2), ConvNorm(c * 2, c * 4, 2))
        self.residual = nn.Sequential(*(ResidualBlock(c * 4) for _ in range(residual_blocks)))
        self.up1 = ConvNorm(c * 4, c * 2)
        self.up2 = ConvNorm(c * 2, c)
        self.output = nn.Sequential(nn.ReflectionPad2d(1), nn.Conv2d(c, 1 if monochrome else 3, 3))

    def forward(self, x):
        height, width = x.shape[-2:]
        x = self.residual(self.encoder(x))
        x = self.up1(F.interpolate(x, scale_factor=2, mode="nearest"))
        x = self.up2(F.interpolate(x, size=(height, width), mode="nearest"))
        x = torch.sigmoid(self.output(x))
        return x.repeat(1, 3, 1, 1) if self.config["monochrome"] else x


def load_network(checkpoint, device="cpu"):
    data = torch.load(checkpoint, map_location="cpu", weights_only=True)
    model = StyleNetwork(**data["network_config"])
    model.load_state_dict(data["model"])
    model.to(device).eval()
    return model, data
