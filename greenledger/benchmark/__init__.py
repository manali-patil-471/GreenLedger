"""Benchmark-only document understanding contracts and evaluation utilities.

This package is intentionally separate from GreenLedger's production accounting,
OCR, and extraction modules.
"""

from .contract import DocumentPrediction, validate_prediction

__all__ = ["DocumentPrediction", "validate_prediction"]
