"""
Clean the raw DK_SR_CLASSDATA_CHATDKU.csv course schedule export.

Cleaning steps:
  1. Normalize Session values: "1" → "7W1", "2" → "7W2", "MNS" → "Mini Term Week"
  2. Filter to courses starting August 2026 or later
  3. Map Class Status: "A" → "Active", "T" → "Cancelled"
  4. Unify Attributes into 4 canonical categories and drop everything else
  5. Drop the Component column

Usage:
    python scripts/clean_classdata.py [--input PATH] [--output PATH]
"""

import argparse

import pandas as pd

# ── Constants ────────────────────────────────────────────────────────────────
INPUT_PATH = "/datapool/chatdku_external_data/DK_SR_CLASSDATA_CHATDKU.csv"
OUTPUT_PATH = "/datapool/chatdku_external_data/cleaned_classdata.csv"  # TODO: set final output folder

# ── Session mapping ──────────────────────────────────────────────────────────
SESSION_MAP = {
    "1": "7W1",
    "2": "7W2",
    "MNS": "Mini Term Week",
}

# ── Class Status mapping ────────────────────────────────────────────────────
STATUS_MAP = {
    "A": "Active",
    "T": "Cancelled",
}

ENROLLMENT_MAP = {
    "O": "Open",
    "C": "Closed",
}

# ── Attribute normalisation ─────────────────────────────────────────────────
# Each key is a raw token (possibly truncated) that should be mapped to a
# canonical attribute.  Tokens not present here are dropped.
ATTRIBUTE_MAP = {
    # Common Core
    "Common Core": "Common Core",
    # Natural Sciences family
    "Natural Sciences": "Natural Sciences",
    "NS Foundations": "Natural Sciences",
    "NS Foundat": "Natural Sciences",  # truncated variant
    # Social Sciences family
    "Social Sciences": "Social Sciences",
    "SS Foundations": "Social Sciences",
    # Arts and Humanities family
    "Arts and Humanities": "Arts and Humanities",
    "AH Foundations": "Arts and Humanities",
    # Quantitative Reasoning family
    "Quantitative Reasoning": "Quantitative Reasoning",
    "Quantitative Reason": "Quantitative Reasoning",  # truncated variant
    "Quantitative Re": "Quantitative Reasoning",  # truncated variant
    "QR Foundations": "Quantitative Reasoning",
}


def clean_attributes(raw: str) -> str:
    """Map a comma-separated attribute string to canonical categories.

    Keeps only recognised attributes (deduplicated, order-preserved).
    Returns empty string when nothing matches.
    """
    if pd.isna(raw) or not raw.strip():
        return ""
    seen = set()
    result = []
    for token in raw.split(","):
        token = token.strip()
        canonical = ATTRIBUTE_MAP.get(token)
        if canonical and canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return ",".join(result)


def clean(input_path: str, output_path: str) -> None:
    df = pd.read_csv(input_path, encoding="utf-16")

    # 1. Normalise sessions
    df["Session"] = df["Session"].replace(SESSION_MAP)

    # 2. Filter by start date — keep August 2026 onward
    df["Start Date"] = pd.to_datetime(df["Start Date"], format="%m/%d/%Y")
    df = df[df["Start Date"] >= "2026-08-01"].copy()
    df["Start Date"] = df["Start Date"].dt.strftime("%m/%d/%Y")

    # 3. Translate class status
    df["Class Status"] = df["Class Status"].map(STATUS_MAP).fillna(df["Class Status"])
    df["Enrollment Status"] = (
        df["Enrollment Status"].map(ENROLLMENT_MAP).fillna(df["Enrollment Status"])
    )

    # 4. Clean attributes
    df["Attributes"] = df["Attributes"].apply(clean_attributes)

    # 5. Drop Component column
    df = df.drop(columns=["Component", "Class Type"])

    df.to_csv(output_path, index=False)
    print(f"Wrote {len(df)} rows → {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean course schedule CSV")
    parser.add_argument("--input", default=INPUT_PATH)
    parser.add_argument("--output", default=OUTPUT_PATH)
    args = parser.parse_args()
    clean(args.input, args.output)
