"""Verify the durable recovery benchmark's statistical acceptance rule."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_benchmark_module() -> ModuleType:
    path = Path(__file__).parents[1] / "scripts" / "measure_langgraph_recovery.py"
    spec = importlib.util.spec_from_file_location("measure_langgraph_recovery", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("benchmark module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_zero_failure_sample_is_large_enough_for_claimed_recovery_rate() -> None:
    """Require enough zero-failure trials to support a 99.5% lower bound."""
    benchmark = _load_benchmark_module()

    assert benchmark.zero_failure_lower_bound(1_000, 0.95) > 0.995
    assert benchmark.zero_failure_lower_bound(100, 0.95) < 0.995


def test_zero_success_has_no_recovery_lower_bound() -> None:
    """Keep empty or failed measurements from producing a positive claim."""
    benchmark = _load_benchmark_module()

    assert benchmark.zero_failure_lower_bound(0, 0.95) == 0.0
