# models/deeplog.py
# ─────────────────────────────────────────────
# DeepLog — LSTM-based log anomaly detection
# Used as cross-validator alongside LogBERT
# ─────────────────────────────────────────────

import os
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from utils.constants import DEEPLOG_CONFIG, DEEPLOG_MODEL
from utils.helpers import ensure_dirs, normalize_scores


# ── Model Architecture ────────────────────────

class DeepLogLSTM(nn.Module):
    def __init__(self, vocab_size: int, hidden: int, layers: int):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=1,
            hidden_size=hidden,
            num_layers=layers,
            batch_first=True
        )
        self.fc = nn.Linear(hidden, vocab_size + 1)  # +1 for unknown token

    def forward(self, x):
        # x: (batch, window_size) → (batch, window_size, 1)
        x = x.float().unsqueeze(-1)
        out, _ = self.lstm(x)
        logits = self.fc(out[:, -1, :])  # take last timestep
        return logits


# ── Training ──────────────────────────────────

def train_deeplog(X: np.ndarray, y: np.ndarray, vocab_size: int):
    """
    Trains DeepLog on normal log sequences.
    Args:
        X           : (N, window_size) array of token sequences
        y           : (N,) array of next-token labels
        vocab_size  : number of unique log templates
    Saves model to data/models/deeplog.pt
    """
    cfg = DEEPLOG_CONFIG
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[DeepLog] Training on {device} | {len(X)} sequences")

    X_t = torch.tensor(X, dtype=torch.long)
    y_t = torch.tensor(y, dtype=torch.long)
    dataset = TensorDataset(X_t, y_t)
    loader  = DataLoader(dataset, batch_size=cfg["batch_size"], shuffle=True)

    model = DeepLogLSTM(vocab_size, cfg["hidden_size"], cfg["num_layers"]).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg["lr"])
    criterion = nn.CrossEntropyLoss()

    model.train()
    for epoch in range(cfg["epochs"]):
        total_loss = 0.0
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            logits = model(xb)
            loss   = criterion(logits, yb)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        avg = total_loss / len(loader)
        if (epoch + 1) % 5 == 0:
            print(f"  Epoch {epoch+1}/{cfg['epochs']}  Loss: {avg:.4f}")

    # Save
    ensure_dirs(os.path.dirname(DEEPLOG_MODEL))
    torch.save({
        "model_state": model.state_dict(),
        "vocab_size":  vocab_size,
        "config":      cfg,
    }, DEEPLOG_MODEL)
    print(f"[DeepLog] Model saved → {DEEPLOG_MODEL}")
    return model


# ── Inference ─────────────────────────────────

def load_deeplog() -> tuple:
    """Loads saved DeepLog model. Returns (model, config)."""
    if not os.path.exists(DEEPLOG_MODEL):
        raise FileNotFoundError(
            f"DeepLog model not found at {DEEPLOG_MODEL}. Run training first."
        )
    checkpoint = torch.load(DEEPLOG_MODEL, map_location="cpu")
    cfg        = checkpoint["config"]
    vocab_size = checkpoint["vocab_size"]

    model = DeepLogLSTM(vocab_size, cfg["hidden_size"], cfg["num_layers"])
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model, cfg


def score_sequences_deeplog(X: np.ndarray, y: np.ndarray) -> list[float]:
    """
    Scores each sequence. Returns anomaly scores in [0, 1].
    Anomaly = true next event NOT in top-k predicted events.
    Score 1.0 = definitely anomalous, 0.0 = normal.
    """
    model, cfg = load_deeplog()
    top_k  = cfg["top_k"]
    device = torch.device("cpu")

    X_t = torch.tensor(X, dtype=torch.long)
    y_t = torch.tensor(y, dtype=torch.long)

    scores = []
    model.eval()
    with torch.no_grad():
        for i in range(len(X_t)):
            xb     = X_t[i].unsqueeze(0).to(device)
            logits = model(xb)
            topk   = torch.topk(logits, top_k, dim=1).indices.squeeze().tolist()

            actual = y_t[i].item()
            if actual not in topk:
                # Anomaly — score = 1 - (rank / vocab_size) approximately
                probs  = torch.softmax(logits, dim=1).squeeze()
                rank   = (probs.argsort(descending=True) == actual).nonzero(as_tuple=True)[0].item()
                score  = min(1.0, rank / max(len(probs), 1))
            else:
                # Normal — score based on how confidently it predicted the right event
                prob  = torch.softmax(logits, dim=1).squeeze()[actual].item()
                score = 1.0 - prob  # low prob of correct → higher anomaly score

            scores.append(score)

    return normalize_scores(scores)


# ── Convenience Entry Point ───────────────────

def run_deeplog_inference(X: np.ndarray, y: np.ndarray) -> list[float]:
    """Called by ensemble.py. Returns per-sequence anomaly scores."""
    return score_sequences_deeplog(X, y)