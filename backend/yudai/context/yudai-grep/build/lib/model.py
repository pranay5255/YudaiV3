from __future__ import annotations

from typing import Dict

import torch
import torch.nn as nn
import torch.nn.functional as F


class GrepModel(nn.Module):
    """Simple RNN encoder that maps natural-language queries to repository targets."""

    def __init__(
        self,
        vocab: Dict[str, int],
        label_to_idx: Dict[str, int],
        tool_to_idx: Dict[str, int],
        *,
        dim: int = 128,
        hidden_dim: int | None = None,
    ) -> None:
        super().__init__()
        if "<pad>" not in vocab or "<unk>" not in vocab:
            raise ValueError("vocab must contain '<pad>' and '<unk>' entries.")
        if not label_to_idx:
            raise ValueError("label_to_idx must contain at least one label.")
        if not tool_to_idx:
            raise ValueError("tool_to_idx must contain at least one label.")

        self.vocab = vocab
        self.label_to_idx = label_to_idx
        self.tool_to_idx = tool_to_idx
        self.idx_to_label = {idx: label for label, idx in label_to_idx.items()}
        self.idx_to_tool = {idx: label for label, idx in tool_to_idx.items()}
        self.pad_idx = vocab["<pad>"]
        self.unk_idx = vocab["<unk>"]

        hidden_dim = hidden_dim or dim
        self.emb = nn.Embedding(len(vocab), dim, padding_idx=self.pad_idx)
        self.rnn = nn.GRU(dim, hidden_dim, batch_first=True)
        self.path_head = nn.Linear(hidden_dim, len(label_to_idx))
        self.tool_head = nn.Linear(hidden_dim, len(tool_to_idx))

    def _tok(self, txt: str) -> torch.Tensor:
        device = self.emb.weight.device
        tokens = [self.vocab.get(w, self.unk_idx) for w in txt.lower().split()]
        if not tokens:
            tokens = [self.pad_idx]
        return torch.tensor(tokens, dtype=torch.long, device=device).unsqueeze(0)

    def forward(self, txt: str) -> dict[str, torch.Tensor]:
        """Return log-probabilities over repository targets and tool classes."""
        embeddings = self.emb(self._tok(txt))
        output, _ = self.rnn(embeddings)
        hidden = output[:, -1, :]
        path_logits = self.path_head(hidden)
        tool_logits = self.tool_head(hidden)
        return {
            "log_path": F.log_softmax(path_logits, dim=-1),
            "log_tool": F.log_softmax(tool_logits, dim=-1),
        }
  
