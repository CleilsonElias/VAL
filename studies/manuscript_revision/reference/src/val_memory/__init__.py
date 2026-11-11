"""Executable reference for VAL; no biological or consciousness equivalence."""

from .core import Observation, VALConfig, VALMemory
from .maths import relational_entropy
from .planning import allocate_ranks, offline_plan, rem_temperature
from .storage import RevisionConflict, SQLiteStore

__version__ = "0.1.0"
__all__ = ["Observation", "VALConfig", "VALMemory", "relational_entropy", "allocate_ranks",
           "offline_plan", "rem_temperature", "RevisionConflict", "SQLiteStore"]

