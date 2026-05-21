# 🛡️ Log Analyzer & Anomaly Detector

Final Year Project — Windows Log Analysis using LogBERT, DeepLog & LLAMA3

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Train DeepLog (run once)
python -c "
from pipeline.parser import parse_file_path
from pipeline.cleaner import run_cleaning_pipeline
from pipeline.features import run_feature_engineering
from models.deeplog import train_deeplog

df = parse_file_path('C:/Logs/SecurityLogs.csv')
df = run_cleaning_pipeline(df)
df_feat, X, y, _, vocab = run_feature_engineering(df)
train_deeplog(X, y, len(vocab))
"

# 3. Train LogBERT (run once)
python -c "
from pipeline.parser import parse_file_path
from pipeline.cleaner import run_cleaning_pipeline
from pipeline.features import run_feature_engineering
from models.logbert import train_logbert

df = parse_file_path('C:/Logs/SecurityLogs.csv')
df = run_cleaning_pipeline(df)
df_feat, X, y, _, vocab = run_feature_engineering(df)
sequences = [row.tolist() for row in X]
train_logbert(sequences)
"

# 4. Start Ollama
ollama run llama3

# 5. Launch app
streamlit run app/main.py
```

---

## 📁 Structure

```
log_anomaly_detector/
├── app/            → Streamlit UI
├── pipeline/       → Ingest → Clean → Features
├── models/         → DeepLog · LogBERT · Ensemble
├── llm/            → LLAMA3 via Ollama
├── data/           → Processed data & saved models
└── utils/          → Constants & helpers
```

---

## 🔑 Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | Streamlit entry point |
| `pipeline/cleaner.py` | Pandas + Drain3 parsing |
| `models/logbert.py` | Primary anomaly detector |
| `models/deeplog.py` | Cross-validator |
| `models/ensemble.py` | Score fusion → Top 15 |
| `llm/ollama_client.py` | LLAMA3 explanations |
| `utils/constants.py` | All config in one place |

---

## 📊 Data Sources (C:/Logs)

- `Security.csv` / `SecurityLogs.csv` → Security events
- `Network.csv` → Network traffic logs  
- `FirewallLogs.csv` / `.txt` → Firewall events
- `SystemLogs.csv` → System events (cross-reference)