"""Structured metrics for RAG pipeline observability.

Accumulates timing and quality data throughout a generation run.
Cheap to collect (conditional on verbose level), zero overhead at
verbose=0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class RetrievalStats:
    """Metrics from one retriever.retrieve() call."""

    query_length: int = 0
    candidates_fetched: int = 0
    results_kept: int = 0
    total_chars: int = 0
    elapsed_s: float = 0.0
    scores: List[float] = field(default_factory=list)

    @property
    def avg_score(self) -> float:
        return sum(self.scores) / len(self.scores) if self.scores else 0.0

    @property
    def min_score(self) -> float:
        return min(self.scores) if self.scores else 0.0


@dataclass
class LlmCallMetrics:
    """Metrics from one chat() call."""

    elapsed_s: float = 0.0
    input_chars: int = 0
    output_chars: int = 0

    @property
    def input_tokens_est(self) -> int:
        return self.input_chars // 4

    @property
    def output_tokens_est(self) -> int:
        return self.output_chars // 4

    @property
    def throughput_tok_s(self) -> float:
        if self.elapsed_s <= 0:
            return 0.0
        return self.output_tokens_est / self.elapsed_s


@dataclass
class TargetMetrics:
    """Metrics for one target file generation."""

    target_path: str = ""
    retrieval: RetrievalStats = field(default_factory=RetrievalStats)
    llm: LlmCallMetrics = field(default_factory=LlmCallMetrics)


@dataclass
class RagMetrics:
    """Accumulated metrics for one generation run."""

    embedding_load_time_s: float = 0.0
    index_load_time_s: float = 0.0
    corpus_files: int = 0
    corpus_chunks: int = 0
    targets: List[TargetMetrics] = field(default_factory=list)

    @property
    def total_retrieval_time_s(self) -> float:
        return sum(t.retrieval.elapsed_s for t in self.targets)

    @property
    def total_llm_time_s(self) -> float:
        return sum(t.llm.elapsed_s for t in self.targets)
