import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import numpy as np
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

from config import IMAGE_SIZE, MEAN, STD

CROPPED_DIR = Path("dataset/cropped")


class PillDataset(Dataset):
    def __init__(self, split="train", train_ratio=0.7, val_ratio=0.15, seed=42):
        """
        split: "train" | "val" | "test"
        비율: train 70% / val 15% / test 15%
        """
        assert split in ("train", "val", "test")
        self.samples = []

        drug_dirs = sorted([d for d in CROPPED_DIR.iterdir() if d.is_dir()])
        self.classes      = [d.name for d in drug_dirs]
        self.class_to_idx = {c: i for i, c in enumerate(self.classes)}

        rng = np.random.default_rng(seed)

        for cls_dir in drug_dirs:
            cls_idx = self.class_to_idx[cls_dir.name]
            images  = sorted(cls_dir.glob("*.png"))
            n       = len(images)

            indices   = rng.permutation(n)
            n_train   = int(n * train_ratio)
            n_val     = int(n * val_ratio)

            if split == "train":
                chosen = indices[:n_train]
            elif split == "val":
                chosen = indices[n_train:n_train + n_val]
            else:
                chosen = indices[n_train + n_val:]

            for i in chosen:
                self.samples.append((images[i], cls_idx))

        self.transform = self._build_transform(split)

    def _build_transform(self, split):
        if split == "train":
            return transforms.Compose([
                transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
                transforms.RandomHorizontalFlip(),
                transforms.RandomVerticalFlip(),
                transforms.RandomRotation(180),
                transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.05, hue=0.0),
                transforms.GaussianBlur(kernel_size=5, sigma=(0.1, 2.0)),
                transforms.ToTensor(),
                transforms.Normalize(MEAN, STD),
            ])
        return transforms.Compose([
            transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(MEAN, STD),
        ])

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_path, cls_idx = self.samples[idx]
        image = Image.open(img_path).convert("RGB")
        return self.transform(image), cls_idx
