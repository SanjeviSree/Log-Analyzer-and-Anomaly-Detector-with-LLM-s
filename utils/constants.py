# utils/constants.py
# ─────────────────────────────────────────────
# Central config for the entire project
# ─────────────────────────────────────────────

import os

# ── Data Source ───────────────────────────────
LOG_SOURCE_DIR = "C:/Logs"

LOG_FILES = {
    "security": ["Security.csv", "SecurityLogs.csv"],
    "network":  ["Network.csv"],
    "firewall": ["FirewallLogs.csv", "FirewallLogs.txt"],
    "system":   ["SystemLogs.csv"],
}

# ── Supported Upload Formats ──────────────────
SUPPORTED_FORMATS    = [".json", ".csv", ".xml", ".txt", ".log", ".syslog"]
FORMAT_ERROR_MSG     = (
    "❌ Unsupported file format. Please convert your file to one of: "
    "JSON, CSV, XML, TXT, LOG, SYSLOG"
)

# ── Time Range Options (Live Collection) ──────
TIME_RANGES = {
    "Past 1 Hour":  1,
    "Past 1 Day":   24,
    "Past 3 Days":  72,
    "Past 1 Week":  168,
    "Past 1 Month": 720,
}

# ── Log Types (Live Collection) ───────────────
LOG_TYPES = ["Security", "Network", "Firewall"]

# ── Anomaly Severity Levels ───────────────────
SEVERITY = {
    "CRITICAL": 5,
    "HIGH":     4,
    "MEDIUM":   3,
    "LOW":      2,
    "INFO":     1,
}

SEVERITY_COLOR = {
    "CRITICAL": "#FF4C4C",
    "HIGH":     "#FF8C00",
    "MEDIUM":   "#FFD700",
    "LOW":      "#4FC3F7",
    "INFO":     "#B0BEC5",
}

# ── Top-N Anomalies to Display ────────────────
TOP_N_ANOMALIES = 20   # top 10 highest + bottom 10 lowest severity

# ── Anomaly Types ─────────────────────────────
ANOMALY_TYPES = [
    "Brute Force Attack",
    "Port Scanning",
    "Privilege Escalation",
    "Lateral Movement",
    "Data Exfiltration",
    "Malware Activity",
    "Unauthorized Access",
    "Suspicious Login",
    "DDoS Pattern",
    "Firewall Rule Violation",
    "Unusual Outbound Traffic",
    "Account Lockout Spike",
    "Credential Dumping",
    "Abnormal Process Execution",
    "Repeated Auth Failures",
]

# ── Paths ─────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
MODELS_DIR    = os.path.join(BASE_DIR, "data", "models")
DEEPLOG_MODEL = os.path.join(MODELS_DIR, "deeplog.pt")
LOGBERT_MODEL = os.path.join(MODELS_DIR, "logbert")

# ── DeepLog Hyperparameters ───────────────────
DEEPLOG_CONFIG = {
    "window_size":  10,
    "hidden_size":  64,
    "num_layers":   2,
    "top_k":        9,
    "epochs":       30,
    "batch_size":   64,
    "lr":           0.001,
}

# ── LogBERT Hyperparameters ───────────────────
LOGBERT_CONFIG = {
    "max_length":  32,    # sequence length — short = fast attention
    "mask_ratio":  0.15,  # 15% tokens masked during MLM training
    "epochs":      5,     # 5 epochs with cosine LR is sufficient
    "batch_size":  128,   # large batch = fewer steps per epoch
    "lr":          2e-4,  # tuned for small custom transformer
    "threshold":   0.72,  # anomaly confidence threshold (raised from 0.50)
}

# ── Ensemble Weights ──────────────────────────
LOGBERT_WEIGHT = 0.70   # LogBERT is primary detector
DEEPLOG_WEIGHT = 0.30   # DeepLog is cross-validator

# ── Anomaly Detection Thresholds ─────────────
ANOMALY_THRESHOLD    = 0.65   # lowered from 0.72 — catches more attack patterns
ANOMALY_PERCENTILE   = 75     # top 25% of scores flagged — better for mixed datasets
MIN_SEQUENCE_TOKENS  = 5      # sequences with fewer real tokens are skipped

# ── Ollama / LLAMA3 ───────────────────────────
OLLAMA_URL     = "http://localhost:11434/api/generate"
OLLAMA_MODEL   = "llama3.2:1b"   # fast 1B model — ~20-30s for 20 anomalies
OLLAMA_TIMEOUT = 300             # streaming timeout in seconds