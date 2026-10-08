from .adams_oh import AdamsCountyOH
from .base import RecordIn, Source
from .dallas_tx import DallasCountyTX
from .fortbend_tx import FortBendCountyTX
from .gwinnett_ga import GwinnettCountyGA

# Add new county scrapers here, and record them in data/county_sources.csv.
SOURCES: dict[str, type[Source]] = {s.name: s for s in [AdamsCountyOH, DallasCountyTX, FortBendCountyTX, GwinnettCountyGA]}

__all__ = ["SOURCES", "RecordIn", "Source"]
