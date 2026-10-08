from .adams_oh import AdamsCountyOH
from .base import RecordIn, Source

# Add new county scrapers here.
SOURCES: dict[str, type[Source]] = {s.name: s for s in [AdamsCountyOH]}

__all__ = ["SOURCES", "RecordIn", "Source"]
