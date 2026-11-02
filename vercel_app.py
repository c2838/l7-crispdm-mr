"""Vercel API entrypoint. Static assets are built into public/ for the CDN."""
import os
import tempfile
from pathlib import Path

os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'l7-matplotlib'))

from l7_service.api import create_app

app=create_app()

# Explicit frontend discovery: these assets are public; only /api/* uses BodyLimit.
# check_dir=False keeps API imports valid after Vercel excludes the CDN directory.
app.frontend('/', directory=Path(__file__).resolve().parent/'web', fallback=None, check_dir=False)
