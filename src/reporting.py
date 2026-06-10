"""Helpers for turning verification output into tables and summary text."""

from __future__ import annotations

from typing import Dict, List

import pandas as pd


def checks_to_dataframe(result: Dict[str, object]) -> pd.DataFrame:
    checks: List[Dict[str, object]] = result.get("checks", [])  # type: ignore[assignment]
    if not checks:
        return pd.DataFrame(columns=["Field", "Expected", "Found", "Status", "Score", "Notes"])
    rows = []
    for check in checks:
        rows.append(
            {
                "Field": check.get("field", ""),
                "Expected": check.get("expected", ""),
                "Found": check.get("found", ""),
                "Status": check.get("status", ""),
                "Score": check.get("score", ""),
                "Notes": check.get("notes", ""),
            }
        )
    return pd.DataFrame(rows)


def result_summary(result: Dict[str, object], filename: str | None = None) -> str:
    name = f" for **{filename}**" if filename else ""
    return (
        f"### Result{name}: {result.get('overall_status')}\n"
        f"Confidence: **{result.get('confidence')}%**  \n"
        f"Pass: **{result.get('pass_count')}**, Review: **{result.get('review_count')}**, Fail: **{result.get('fail_count')}**"
    )
