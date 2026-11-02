"""Shared regression engine for Lesson 7. No HTTP or deployment coupling."""
__version__ = '1.0.0'

from .config import AnalysisConfig
from .engine import run_analysis
from .models import predict_artifact

__all__ = ['AnalysisConfig', 'run_analysis', 'predict_artifact']
