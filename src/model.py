import torch
import torch.nn as nn
import timm


class PillClassifier(nn.Module):
    def __init__(self, num_classes: int, use_metadata: bool = True, meta_dim: int = 25, dropout: float = 0.3):
        super().__init__()
        self.use_metadata = use_metadata

        self.backbone = timm.create_model("efficientnet_b4", pretrained=True, num_classes=0)
        feature_dim = self.backbone.num_features  # 1792

        in_dim = feature_dim + meta_dim if use_metadata else feature_dim

        self.head = nn.Sequential(
            nn.Linear(in_dim, 512),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(512, num_classes),
        )

    def freeze_backbone(self):
        for param in self.backbone.parameters():
            param.requires_grad = False

    def unfreeze_backbone(self):
        for param in self.backbone.parameters():
            param.requires_grad = True

    def forward(self, image, meta=None):
        features = self.backbone(image)

        if self.use_metadata and meta is not None:
            features = torch.cat([features, meta], dim=1)

        return self.head(features)
