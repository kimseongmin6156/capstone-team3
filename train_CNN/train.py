"""
EfficientNet-B4 알약 분류 모델 학습 (bbox 크롭 이미지 기반).

실행: 프로젝트 루트에서
  python train_CNN/train.py
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.amp import autocast, GradScaler
from tqdm import tqdm

from config import (
    BATCH_SIZE, NUM_WORKERS, DEVICE,
    EPOCHS_FROZEN, EPOCHS_FINETUNE,
    LR_FROZEN, LR_FINETUNE, DROPOUT,
    CHECKPOINT_DIR,
)
from src.model import PillClassifier
from train_CNN.dataset_cnn import PillDataset


def train_one_epoch(model, loader, optimizer, criterion, device, scaler):
    model.train()
    total_loss, correct, total = 0.0, 0, 0

    pbar = tqdm(loader, leave=True, ncols=90, desc="  train")
    for images, labels in pbar:
        images, labels = images.to(device), labels.to(device)

        optimizer.zero_grad()
        with autocast(device_type="cuda"):
            outputs = model(images)
            loss    = criterion(outputs, labels)

        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

        total_loss += loss.item() * images.size(0)
        correct    += (outputs.argmax(1) == labels).sum().item()
        total      += images.size(0)
        pbar.set_postfix(loss=f"{loss.item():.4f}", acc=f"{correct/total:.4f}")

    return total_loss / total, correct / total


@torch.no_grad()
def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss, correct, total = 0.0, 0, 0

    for images, labels in tqdm(loader, leave=True, ncols=90, desc="    val"):
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        loss    = criterion(outputs, labels)

        total_loss += loss.item() * images.size(0)
        correct    += (outputs.argmax(1) == labels).sum().item()
        total      += images.size(0)

    return total_loss / total, correct / total


def main():
    device = torch.device(DEVICE if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    train_ds = PillDataset(split="train")
    val_ds   = PillDataset(split="val")
    test_ds  = PillDataset(split="test")
    num_classes = len(train_ds.classes)
    print(f"Classes: {num_classes}, Train: {len(train_ds)}, Val: {len(val_ds)}, Test: {len(test_ds)}")

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,  num_workers=NUM_WORKERS, pin_memory=True)
    val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False, num_workers=NUM_WORKERS, pin_memory=True)
    test_loader  = DataLoader(test_ds,  batch_size=BATCH_SIZE, shuffle=False, num_workers=NUM_WORKERS, pin_memory=True)

    torch.backends.cudnn.benchmark = True

    model     = PillClassifier(num_classes=num_classes, use_metadata=False, dropout=DROPOUT).to(device)
    criterion = nn.CrossEntropyLoss()
    scaler    = GradScaler()

    # Stage 1: backbone frozen
    print("\n[Stage 1] Backbone frozen")
    model.freeze_backbone()
    optimizer    = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=LR_FROZEN)
    best_val_acc = 0.0

    for epoch in range(1, EPOCHS_FROZEN + 1):
        tr_loss, tr_acc = train_one_epoch(model, train_loader, optimizer, criterion, device, scaler)
        vl_loss, vl_acc = evaluate(model, val_loader, criterion, device)
        print(f"  Epoch {epoch:02d} | loss {tr_loss:.4f} acc {tr_acc:.4f} | val_loss {vl_loss:.4f} val_acc {vl_acc:.4f}")

        if vl_acc > best_val_acc:
            best_val_acc = vl_acc
            torch.save({"epoch": epoch, "model": model.state_dict(), "classes": train_ds.classes},
                       CHECKPOINT_DIR / "cnn_best.pt")

    # Stage 2: full fine-tune
    print("\n[Stage 2] Fine-tuning")
    model.unfreeze_backbone()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR_FINETUNE)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS_FINETUNE)

    patience, no_improve = 3, 0
    for epoch in range(1, EPOCHS_FINETUNE + 1):
        tr_loss, tr_acc = train_one_epoch(model, train_loader, optimizer, criterion, device, scaler)
        vl_loss, vl_acc = evaluate(model, val_loader, criterion, device)
        scheduler.step()
        print(f"  Epoch {epoch:02d} | loss {tr_loss:.4f} acc {tr_acc:.4f} | val_loss {vl_loss:.4f} val_acc {vl_acc:.4f}")

        if vl_acc > best_val_acc:
            best_val_acc = vl_acc
            no_improve   = 0
            torch.save({"epoch": epoch, "model": model.state_dict(), "classes": train_ds.classes},
                       CHECKPOINT_DIR / "cnn_best.pt")
        else:
            no_improve += 1
            if no_improve >= patience:
                print(f"\n  Early stopping (patience={patience})")
                break

    print(f"\nBest val acc: {best_val_acc:.4f}")
    print(f"Checkpoint: {CHECKPOINT_DIR / 'cnn_best.pt'}")

    # Test 평가
    print("\n[Test 평가]")
    ckpt  = torch.load(CHECKPOINT_DIR / "cnn_best.pt", map_location=device)
    model.load_state_dict(ckpt["model"])
    te_loss, te_acc = evaluate(model, test_loader, criterion, device)
    print(f"  Test loss: {te_loss:.4f}  Test acc: {te_acc:.4f}")


if __name__ == "__main__":
    main()
