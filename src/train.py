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
from src.dataset import PillDataset
from src.model import PillClassifier


def train_one_epoch(model, loader, optimizer, criterion, device, use_metadata, scaler):
    model.train()
    total_loss, correct, total = 0.0, 0, 0

    pbar = tqdm(loader, leave=True, ncols=90, desc="  train")
    for batch in pbar:
        if use_metadata:
            images, meta, labels = batch
            meta = meta.to(device)
        else:
            images, labels = batch
            meta = None

        images, labels = images.to(device), labels.to(device)

        optimizer.zero_grad()
        with autocast(device_type="cuda"):
            outputs = model(images, meta)
            loss = criterion(outputs, labels)

        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

        total_loss += loss.item() * images.size(0)
        correct += (outputs.argmax(1) == labels).sum().item()
        total += images.size(0)

        pbar.set_postfix(loss=f"{loss.item():.4f}", acc=f"{correct/total:.4f}")

    return total_loss / total, correct / total


@torch.no_grad()
def evaluate(model, loader, criterion, device, use_metadata):
    model.eval()
    total_loss, correct, total = 0.0, 0, 0

    for batch in tqdm(loader, leave=True, ncols=90, desc="    val"):
        if use_metadata:
            images, meta, labels = batch
            meta = meta.to(device)
        else:
            images, labels = batch
            meta = None

        images, labels = images.to(device), labels.to(device)
        with autocast(device_type="cuda"):
            outputs = model(images, meta)
            loss = criterion(outputs, labels)

        total_loss += loss.item() * images.size(0)
        correct += (outputs.argmax(1) == labels).sum().item()
        total += images.size(0)

    return total_loss / total, correct / total


def main():
    use_metadata = False
    device = torch.device(DEVICE if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    train_ds = PillDataset(split="train", use_metadata=use_metadata)
    val_ds   = PillDataset(split="val",   use_metadata=use_metadata)
    num_classes = len(train_ds.classes)
    print(f"Classes: {num_classes}, Train: {len(train_ds)}, Val: {len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,  num_workers=NUM_WORKERS, pin_memory=True)
    val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False, num_workers=NUM_WORKERS, pin_memory=True)

    torch.backends.cudnn.benchmark = True

    model = PillClassifier(num_classes=num_classes, use_metadata=use_metadata, dropout=DROPOUT).to(device)
    criterion = nn.CrossEntropyLoss()
    scaler = GradScaler()

    # 1단계: backbone frozen
    print("\n[Stage 1] Backbone frozen")
    model.freeze_backbone()
    optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=LR_FROZEN)

    best_val_acc = 0.0
    for epoch in range(1, EPOCHS_FROZEN + 1):
        tr_loss, tr_acc = train_one_epoch(model, train_loader, optimizer, criterion, device, use_metadata, scaler)
        vl_loss, vl_acc = evaluate(model, val_loader, criterion, device, use_metadata)
        print(f"  Epoch {epoch:02d} | loss {tr_loss:.4f} acc {tr_acc:.4f} | val_loss {vl_loss:.4f} val_acc {vl_acc:.4f}")

        if vl_acc > best_val_acc:
            best_val_acc = vl_acc
            torch.save({"epoch": epoch, "model": model.state_dict(), "classes": train_ds.classes},
                       CHECKPOINT_DIR / "best.pt")

    # 2단계: backbone unfreeze (fine-tune)
    print("\n[Stage 2] Fine-tuning")
    model.unfreeze_backbone()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR_FINETUNE)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS_FINETUNE)

    patience, no_improve = 3, 0
    for epoch in range(1, EPOCHS_FINETUNE + 1):
        tr_loss, tr_acc = train_one_epoch(model, train_loader, optimizer, criterion, device, use_metadata, scaler)
        vl_loss, vl_acc = evaluate(model, val_loader, criterion, device, use_metadata)
        scheduler.step()
        print(f"  Epoch {epoch:02d} | loss {tr_loss:.4f} acc {tr_acc:.4f} | val_loss {vl_loss:.4f} val_acc {vl_acc:.4f}")

        if vl_acc > best_val_acc:
            best_val_acc = vl_acc
            no_improve = 0
            torch.save({"epoch": epoch, "model": model.state_dict(), "classes": train_ds.classes},
                       CHECKPOINT_DIR / "best.pt")
        else:
            no_improve += 1
            if no_improve >= patience:
                print(f"\n  Early stopping (patience={patience})")
                break

    print(f"\nBest val acc: {best_val_acc:.4f}")
    print(f"Checkpoint saved to {CHECKPOINT_DIR / 'best.pt'}")


if __name__ == "__main__":
    main()
