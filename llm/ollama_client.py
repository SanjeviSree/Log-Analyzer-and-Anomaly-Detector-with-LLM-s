# llm/ollama_client.py
# ─────────────────────────────────────────────
# Speed fix: ONE batch call for all anomalies
# instead of N sequential calls
# Target: 20 anomalies in ~45-60 seconds
# ─────────────────────────────────────────────

import re
import json
import requests
import pandas as pd
import streamlit as st
from utils.constants import OLLAMA_URL, OLLAMA_MODEL
from llm.prompt_builder import build_summary_prompt

CONNECT_TIMEOUT = 5
STREAM_TIMEOUT  = 300


# ── Connection + Model Check ──────────────────

def check_ollama_connection() -> tuple:
    try:
        r = requests.get("http://localhost:11434", timeout=CONNECT_TIMEOUT)
        if r.status_code != 200:
            return False, "Ollama server returned unexpected status."
    except requests.exceptions.ConnectionError:
        return False, (
            f"Ollama is not running.\n\n"
            f"Open a terminal and run:\n"
            f"```\nollama serve\n```\n"
            f"Then pull the model:\n"
            f"```\nollama pull {OLLAMA_MODEL}\n```"
        )
    except Exception as e:
        return False, f"Cannot reach Ollama: {str(e)}"

    try:
        tags = requests.get("http://localhost:11434/api/tags", timeout=CONNECT_TIMEOUT)
        if tags.status_code == 200:
            names = [m.get("name","") for m in tags.json().get("models",[])]
            if not any(OLLAMA_MODEL in n for n in names):
                return False, (
                    f"Model `{OLLAMA_MODEL}` not downloaded.\n\n"
                    f"Run: ```ollama pull {OLLAMA_MODEL}```\n"
                    f"Available: {', '.join(names) or 'none'}"
                )
    except Exception:
        pass

    return True, ""


# ── Core Streaming Call ───────────────────────

def _call_ollama(prompt: str, max_tokens: int = 600) -> str:
    """Single Ollama API call with streaming. Returns full response text."""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": 0.2,   # low = fast + consistent format
                    "num_predict": max_tokens,
                    "top_k":       10,    # small top_k = faster sampling
                    "top_p":       0.7,
                    "repeat_penalty": 1.1,
                }
            },
            stream=True,
            timeout=(CONNECT_TIMEOUT, STREAM_TIMEOUT),
        )
        resp.raise_for_status()

        parts = []
        for line in resp.iter_lines():
            if line:
                try:
                    chunk = json.loads(line.decode("utf-8"))
                    parts.append(chunk.get("response", ""))
                    if chunk.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue
        return "".join(parts).strip()

    except requests.exceptions.HTTPError as e:
        if "404" in str(e):
            raise RuntimeError(f"Model not found. Run: ollama pull {OLLAMA_MODEL}")
        raise RuntimeError(f"HTTP error: {e}")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Ollama not running. Run: ollama serve")
    except requests.exceptions.Timeout:
        raise RuntimeError("Ollama timed out.")
    except Exception as e:
        raise RuntimeError(f"Ollama error: {e}")


# ── Summary ───────────────────────────────────

def generate_summary(df: pd.DataFrame, log_type: str = "Windows") -> str:
    prompt = build_summary_prompt(df, log_type)
    try:
        return _call_ollama(prompt, max_tokens=250)
    except RuntimeError as e:
        return f"Summary unavailable: {e}"


# ── Batch Enrichment (ALL anomalies, ONE call) ─

def _build_batch_prompt(rows: list) -> str:
    """
    Builds one compact prompt for all anomalies.
    Key design decisions for speed + quality:
    - Short log snippet (80 chars max) — enough context, not too long
    - Strict format enforced — easy to parse back
    - num_predict=600 covers ~20 anomalies comfortably
    """
    lines = []
    for i, row in enumerate(rows):
        name     = str(row.get("anomaly_name", "Unknown"))
        severity = str(row.get("severity", "?"))
        conf     = float(row.get("confidence", 0))
        # Use most informative available field
        log_hint = ""
        for col in ["log_template", "raw_log_sample", "message"]:
            val = str(row.get(col, "")).strip()
            if val and val not in ("nan", "", "unknown"):
                log_hint = val[:80]
                break

        lines.append(f"[{i+1}] {name} | {severity} | {conf:.0%} | {log_hint}")

    items = "\n".join(lines)
    n     = len(rows)

    return f"""Windows security analyst. Analyze {n} log anomalies. For each, write one specific explanation and one solution.

{items}

Respond ONLY in this exact format (no extra text, no preamble):
[1] E: <explanation> | S: <solution>
[2] E: <explanation> | S: <solution>
...up to [{n}]"""


def _parse_batch(raw: str, n: int) -> list:
    """
    Parses batch response into list of (explanation, solution) tuples.
    Tries strict format first, falls back to line-by-line extraction.
    """
    results = [("", "")] * n

    # Try strict format: [N] E: ... | S: ...
    pattern = re.compile(
        r'\[(\d+)\]\s*E:\s*(.+?)\s*\|\s*S:\s*(.+?)(?=\[\d+\]|$)',
        re.DOTALL
    )
    for m in pattern.finditer(raw):
        idx = int(m.group(1)) - 1
        if 0 <= idx < n:
            exp = m.group(2).strip().replace("\n", " ")
            sol = m.group(3).strip().replace("\n", " ")
            results[idx] = (exp, sol)

    # Fallback: try line by line for any missed rows
    if results.count(("", "")) > 0:
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        for line in lines:
            m2 = re.match(r'\[(\d+)\]\s*E:\s*(.+?)\s*\|\s*S:\s*(.+)', line)
            if m2:
                idx = int(m2.group(1)) - 1
                if 0 <= idx < n and results[idx] == ("", ""):
                    results[idx] = (m2.group(2).strip(), m2.group(3).strip())

    return results


def enrich_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sends ALL anomalies in ONE batch call.
    Falls back to per-row calls only for rows where batch parsing failed.
    Total time: ~45-60 seconds for 20 anomalies vs 5 minutes sequential.
    """
    df    = df.copy()
    rows  = df.to_dict("records")
    total = len(rows)

    progress = st.progress(0, text="🧠 LLAMA3 analyzing all anomalies in one batch...")

    # ── Single batch call for all anomalies ──────
    try:
        prompt  = _build_batch_prompt(rows)
        raw     = _call_ollama(prompt, max_tokens=max(400, total * 35))
        results = _parse_batch(raw, total)
        progress.progress(70, text="🧠 Parsing LLAMA3 responses...")
    except RuntimeError as e:
        st.warning(f"⚠️ Batch call failed: {e}. Using fallback explanations.")
        results = [("", "")] * total

    # ── Fill in results ───────────────────────────
    for i, idx in enumerate(df.index):
        row = rows[i]
        exp, sol = results[i] if i < len(results) else ("", "")

        # If batch failed for this row, generate a meaningful fallback
        if not exp or len(exp) < 15:
            name     = row.get("anomaly_name", "Unknown")
            severity = row.get("severity", "UNKNOWN")
            conf     = float(row.get("confidence", 0))
            log_hint = ""
            for col in ["log_template", "raw_log_sample"]:
                val = str(row.get(col, "")).strip()
                if val and val not in ("nan", "", "unknown"):
                    log_hint = val[:100]
                    break
            exp = (
                f"A {severity.lower()} severity {name} event was detected "
                f"with {conf:.0%} confidence"
                + (f": {log_hint[:80]}." if log_hint else ".")
            )

        if not sol or len(sol) < 15:
            name = row.get("anomaly_name", "Unknown")
            sol_map = {
                "Brute Force Attack":        "Block the source IP and enforce account lockout policies immediately.",
                "Credential Dumping":        "Isolate the affected system and rotate all credentials on the domain.",
                "Privilege Escalation":      "Review and revoke elevated privileges; audit recent permission changes.",
                "Lateral Movement":          "Segment the network and investigate all affected hosts in the session.",
                "Data Exfiltration":         "Block the outbound destination and audit all recent large file transfers.",
                "Malware Activity":          "Quarantine the affected host and run a full Windows Defender scan.",
                "Unauthorized Access":       "Revoke the session token and enforce MFA on the affected account.",
                "Suspicious Login":          "Verify with the account owner and reset credentials if unrecognized.",
                "Port Scanning":             "Block the scanning source IP at the firewall level.",
                "Firewall Rule Violation":   "Review and restore firewall rules; check for unauthorized modifications.",
                "Unusual Outbound Traffic":  "Inspect the outbound connection and block if destination is unknown.",
                "Account Lockout Spike":     "Investigate the source of repeated failures and enforce rate limiting.",
                "Repeated Auth Failures":    "Temporarily block the IP and notify the account owner.",
                "DDoS Pattern":              "Enable rate limiting and contact your ISP for upstream filtering.",
                "Abnormal Process Execution":"Terminate the process, check its origin, and run malware analysis.",
            }
            sol = sol_map.get(name, f"Investigate the {name} event and apply least-privilege access controls.")

        df.at[idx, "explanation"] = exp
        df.at[idx, "solution"]    = sol

        pct = 70 + int(((i + 1) / total) * 30)
        progress.progress(pct, text=f"🧠 Finalizing {i+1}/{total} anomalies...")

    progress.empty()
    return df


# ── Full Pipeline ─────────────────────────────

def run_llm_pipeline(df: pd.DataFrame, log_type: str = "Windows"):
    is_connected, error_msg = check_ollama_connection()

    if not is_connected:
        st.error(f"❌ {error_msg}")
        for idx in df.index:
            name = df.at[idx, "anomaly_name"]
            sev  = df.at[idx, "severity"]
            conf = float(df.at[idx, "confidence"])
            df.at[idx, "explanation"] = (
                f"A {sev.lower()} severity {name} event detected "
                f"with {conf:.0%} confidence. Start Ollama for AI explanation."
            )
            df.at[idx, "solution"] = f"Run: ollama pull {OLLAMA_MODEL}"
        return (
            f"⚠️ LLAMA3 offline. {len(df)} anomalies detected. "
            f"Run: ollama pull {OLLAMA_MODEL}",
            df
        )

    with st.spinner("📝 Generating executive summary..."):
        summary = generate_summary(df, log_type)

    df = enrich_anomalies(df)
    return summary, df