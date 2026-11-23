"""Corunis evals: synthetic corpora, tuning question sets, a model harness and a scorer.

Everything here runs on the standard library. PDF corpora need pypdf, the server's optional extra.
"""

from __future__ import annotations

import sys
from pathlib import Path

EVALS = Path(__file__).resolve().parents[1]
REPO = EVALS.parent
SERVER = REPO / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))
