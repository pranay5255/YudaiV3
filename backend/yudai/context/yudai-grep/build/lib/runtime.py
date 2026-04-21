"""Utilities for loading the trained GrepModel and related artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch

from src.model import GrepModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "model.pth"
SUPERVISED_DATA_PATH = PROJECT_ROOT / "datasets" / "example_supervised.jsonl"


def load_model(*, map_location: str | torch.device = "cpu") -> GrepModel:
    """Load the trained GrepModel weights and restore its vocabulary."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Missing trained weights at {MODEL_PATH}. "
            "Run `uv run -m src.train` before attempting inference."
        )

    checkpoint: dict[str, Any] = torch.load(MODEL_PATH, map_location=map_location)
    if "state_dict" not in checkpoint:
        raise ValueError(f"Checkpoint at {MODEL_PATH} is missing 'state_dict'.")

    vocab: dict[str, int] = checkpoint.get("vocab", {})
    label_to_idx: dict[str, int] = checkpoint.get("label_to_idx", {})
    tool_to_idx: dict[str, int] = checkpoint.get("tool_to_idx", {})

    if not vocab or not label_to_idx or not tool_to_idx:
        raise ValueError(
            "Checkpoint is missing vocabulary, label, or tool mapping metadata; "
            "retrain the model with the latest training pipeline."
        )

    model = GrepModel(
        vocab=vocab,
        label_to_idx=label_to_idx,
        tool_to_idx=tool_to_idx,
    )
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    return model


__all__ = ["load_model", "MODEL_PATH", "SUPERVISED_DATA_PATH", "PROJECT_ROOT"]
