"""Local/API entry point. Public Vercel deployment remains a later approved stage."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
from pathlib import Path
from l7_service.api import create_app
app=create_app(Path(__file__).resolve().parent/'web')
