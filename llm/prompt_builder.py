# llm/prompt_builder.py
# ─────────────────────────────────────────────
# Builds prompts for LLAMA3 based on anomaly data
# ─────────────────────────────────────────────

import pandas as pd


def build_summary_prompt(df: pd.DataFrame, log_type: str = "Windows") -> str:
    """
    Builds a prompt asking LLAMA3 for a general summary
    of what the log file contains and its overall risk posture.
    """
    total     = len(df)
    anomalies = df["anomaly_name"].value_counts().head(5).to_dict()
    severities = df["severity"].value_counts().to_dict()

    anom_str = "\n".join([f"  - {k}: {v} occurrences" for k, v in anomalies.items()])
    sev_str  = "\n".join([f"  - {k}: {v}" for k, v in severities.items()])

    return f"""You are a cybersecurity analyst. Analyze the following log anomaly report for a Windows system.

Log Type: {log_type}
Total Anomalies Detected: {total}

Top Anomaly Types:
{anom_str}

Severity Breakdown:
{sev_str}

Write a concise 3-4 sentence executive summary explaining:
1. What type of threat activity is present
2. The overall risk level
3. Which systems or services are most at risk

Be direct, professional, and avoid technical jargon.
"""


def build_anomaly_prompt(row: dict) -> str:
    """
    Builds a per-anomaly prompt asking LLAMA3 for:
    - Explanation of the anomaly
    - Recommended solution
    """
    return f"""You are a Windows security expert. Analyze this detected log anomaly:

Anomaly Name : {row.get('anomaly_name', 'Unknown')}
Anomaly Type : {row.get('type', 'Unknown')}
Severity     : {row.get('severity', 'Unknown')}
Confidence   : {row.get('confidence', 0):.0%}
Log Template : {row.get('log_template', 'N/A')}
Log Sample   : {row.get('raw_log_sample', 'N/A')[:300]}

Respond ONLY in this exact format (no extra text):

EXPLANATION: <one clear sentence explaining what this anomaly means>
SOLUTION: <one concrete action the system admin should take immediately>
"""


def parse_llm_response(response: str) -> tuple[str, str]:
    """
    Parses LLAMA3 response into (explanation, solution).
    Falls back gracefully if format doesn't match.
    """
    explanation = "Unable to generate explanation."
    solution    = "Please review logs manually."

    lines = response.strip().splitlines()
    for line in lines:
        if line.upper().startswith("EXPLANATION:"):
            explanation = line.split(":", 1)[-1].strip()
        elif line.upper().startswith("SOLUTION:"):
            solution = line.split(":", 1)[-1].strip()

    return explanation, solution