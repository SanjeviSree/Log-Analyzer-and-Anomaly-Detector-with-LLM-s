# models/logbert.py
# ─────────────────────────────────────────────
# LogBERT — Lightweight custom BERT for log sequences
# Optimized for CPU training: small model + sampled data
# Trains in ~3-5 mins on CPU with 59K sequences
# ─────────────────────────────────────────────

import os
import random
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from utils.constants import LOGBERT_CONFIG, LOGBERT_MODEL
from utils.helpers import ensure_dirs, normalize_scores

# ── Speed constants (tuned for CPU) ──────────
MAX_TRAIN_SEQUENCES = 10000   # sample from full set — enough for good MLM
MAX_LEN             = 32      # attention is O(n²) — 32 vs 64 = 4x faster
D_MODEL             = 64      # was 128 — 4x fewer params in attention
N_HEAD              = 2       # was 4
N_LAYERS            = 2       # keep 2 — depth matters more than width
BATCH_SIZE          = 128     # was 64 — larger batches = fewer steps per epoch


# ── Model ─────────────────────────────────────

class LogEmbedding(nn.Module):
    def __init__(self, vocab_size, d_model, max_len, dropout):
        super().__init__()
        self.token_emb    = nn.Embedding(vocab_size + 2, d_model, padding_idx=0)
        self.position_emb = nn.Embedding(max_len, d_model)
        self.norm         = nn.LayerNorm(d_model)
        self.dropout      = nn.Dropout(dropout)

    def forward(self, x):
        pos = torch.arange(x.size(1), device=x.device).unsqueeze(0)
        return self.dropout(self.norm(self.token_emb(x) + self.position_emb(pos)))


class LogBERTModel(nn.Module):
    """
    Ultra-light BERT: d_model=64, 2 heads, 2 layers, max_len=32
    ~120K params — trains in ~3 mins on CPU for 10K sequences
    """
    def __init__(self, vocab_size, d_model=D_MODEL, nhead=N_HEAD,
                 num_layers=N_LAYERS, max_len=MAX_LEN, dropout=0.1):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model    = d_model

        self.embedding  = LogEmbedding(vocab_size, d_model, max_len, dropout)

        encoder_layer   = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead,
            dim_feedforward=d_model * 4,
            dropout=dropout, batch_first=True,
            norm_first=True                      # pre-norm: more stable, faster convergence
        )
        self.encoder  = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.mlm_head = nn.Linear(d_model, vocab_size + 2)

    def forward(self, x):
        return self.mlm_head(self.encoder(self.embedding(x)))


# ── Dataset ───────────────────────────────────

class LogMLMDataset(Dataset):
    def __init__(self, sequences, vocab_size, max_len=MAX_LEN, mask_ratio=0.15):
        self.sequences  = sequences
        self.vocab_size = vocab_size
        self.max_len    = max_len
        self.mask_ratio = mask_ratio
        self.mask_id    = vocab_size + 1

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        seq       = self.sequences[idx][: self.max_len]
        pad_len   = self.max_len - len(seq)
        input_ids = list(seq) + [0] * pad_len
        labels    = [-100] * self.max_len

        for i, tok in enumerate(input_ids):
            if tok == 0:
                continue
            if random.random() < self.mask_ratio:
                labels[i]    = tok
                input_ids[i] = self.mask_id

        return (
            torch.tensor(input_ids, dtype=torch.long),
            torch.tensor(labels,    dtype=torch.long),
        )


# ── Training ──────────────────────────────────

def train_logbert(sequences: list):
    """
    Trains LogBERT on a sampled subset of sequences.
    Full 59K takes too long on CPU — 10K gives equivalent quality
    because log templates repeat heavily (vocab=7483, patterns are limited).
    """
    cfg    = LOGBERT_CONFIG
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # ── Sample sequences for speed ────────────
    if len(sequences) > MAX_TRAIN_SEQUENCES:
        train_seqs = random.sample(sequences, MAX_TRAIN_SEQUENCES)
        print(f"[LogBERT] Sampled {MAX_TRAIN_SEQUENCES:,} / {len(sequences):,} sequences for training")
    else:
        train_seqs = sequences

    vocab_size = max(max(s) for s in train_seqs if s) + 1
    max_len    = MAX_LEN

    print(f"[LogBERT] Vocab:{vocab_size} | SeqLen:{max_len} | d_model:{D_MODEL} | Device:{device}")
    print(f"[LogBERT] Batches per epoch: {len(train_seqs) // BATCH_SIZE + 1}")

    dataset = LogMLMDataset(train_seqs, vocab_size, max_len, cfg["mask_ratio"])
    loader  = DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=2,          # parallel data loading
        pin_memory=False,
        persistent_workers=True # keep workers alive between epochs
    )

    model = LogBERTModel(
        vocab_size=vocab_size,
        d_model=D_MODEL, nhead=N_HEAD,
        num_layers=N_LAYERS, max_len=max_len,
        dropout=0.1
    ).to(device)

    total_params = sum(p.numel() for p in model.parameters())
    print(f"[LogBERT] Model params: {total_params:,}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg["lr"], weight_decay=0.01)
    criterion = nn.CrossEntropyLoss(ignore_index=-100)

    # Cosine LR schedule — better convergence in fewer epochs
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=cfg["epochs"]
    )

    model.train()
    print(f"[LogBERT] Starting {cfg['epochs']} epochs...")

    for epoch in range(cfg["epochs"]):
        total_loss = 0.0
        for input_ids, labels in loader:
            input_ids = input_ids.to(device)
            labels    = labels.to(device)

            optimizer.zero_grad(set_to_none=True)   # faster than zero_grad()
            logits = model(input_ids)
            loss   = criterion(
                logits.view(-1, vocab_size + 2),
                labels.view(-1)
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item()

        scheduler.step()
        avg = total_loss / len(loader)
        # Print every epoch so you can see progress
        print(f"  Epoch {epoch+1}/{cfg['epochs']}  Loss: {avg:.4f}  LR: {scheduler.get_last_lr()[0]:.2e}")

    # Save
    ensure_dirs(LOGBERT_MODEL)
    save_path = os.path.join(LOGBERT_MODEL, "logbert.pt")
    torch.save({
        "model_state": model.state_dict(),
        "vocab_size":  vocab_size,
        "max_len":     max_len,
        "d_model":     D_MODEL,
        "nhead":       N_HEAD,
        "num_layers":  N_LAYERS,
        "config":      cfg,
    }, save_path)
    print(f"[LogBERT] Saved → {save_path}")
    return model


# ── Inference ─────────────────────────────────

def load_logbert():
    save_path = os.path.join(LOGBERT_MODEL, "logbert.pt")
    if not os.path.exists(save_path):
        raise FileNotFoundError(
            f"LogBERT model not found at {save_path}. Run train_models.py first."
        )
    ckpt       = torch.load(save_path, map_location="cpu", weights_only=True)
    vocab_size = ckpt["vocab_size"]
    max_len    = ckpt.get("max_len",    MAX_LEN)
    d_model    = ckpt.get("d_model",    D_MODEL)
    nhead      = ckpt.get("nhead",      N_HEAD)
    num_layers = ckpt.get("num_layers", N_LAYERS)

    model = LogBERTModel(
        vocab_size=vocab_size,
        d_model=d_model, nhead=nhead,
        num_layers=num_layers, max_len=max_len,
        dropout=0.0                              # no dropout at inference
    )
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    return model, vocab_size, max_len


def score_sequences_logbert(sequences: list) -> list:
    """
    Batch inference — scores all sequences in one pass for speed.
    High reconstruction loss = anomaly.
    """
    model, vocab_size, max_len = load_logbert()
    device    = torch.device("cpu")
    mask_id   = vocab_size + 1
    criterion = nn.CrossEntropyLoss(ignore_index=-100, reduction="mean")

    # Build all tensors at once
    all_input, all_labels = [], []
    for seq in sequences:
        seq_t     = seq[:max_len]
        pad_len   = max_len - len(seq_t)
        input_ids = list(seq_t) + [0] * pad_len
        labels    = [-100] * max_len
        masked    = list(input_ids)
        for i, tok in enumerate(masked):
            if tok != 0:
                labels[i] = tok
                masked[i] = mask_id
        all_input.append(masked)
        all_labels.append(labels)

    # Score in batches of 256 for memory efficiency
    scores    = []
    infer_bs  = 256
    model.eval()

    with torch.no_grad():
        for i in range(0, len(all_input), infer_bs):
            xb  = torch.tensor(all_input[i:i+infer_bs],  dtype=torch.long)
            lb  = torch.tensor(all_labels[i:i+infer_bs], dtype=torch.long)
            out = model(xb)                              # (B, seq, vocab+2)

            for j in range(len(xb)):
                loss = criterion(
                    out[j].view(-1, vocab_size + 2),
                    lb[j].view(-1)
                )
                scores.append(loss.item() if not torch.isnan(loss) else 0.0)

    return normalize_scores(scores)


def run_logbert_inference(sequences: list) -> list:
    return score_sequences_logbert(sequences)