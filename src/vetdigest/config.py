from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_config(path: str | os.PathLike | None = None) -> dict:
    path = Path(path) if path else ROOT / "config.yaml"
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    base = os.environ.get("REPORT_BASE_URL") or cfg.get("kakao", {}).get("report_base_url") or ""
    cfg.setdefault("kakao", {})["report_base_url"] = base.rstrip("/")
    return cfg


def journal_clause(journals: list[str]) -> str:
    return "(" + " OR ".join(f'"{j}"[ta]' for j in journals) + ")"
