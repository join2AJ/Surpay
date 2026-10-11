from .adams_oh import AdamsCountyOH
from .calhoun_sc import CalhounCountySC
from .chatham_ga import ChathamCountyGA
from .clayton_ga import ClaytonCountyGA
from .cobb_ga import CobbCountyGA
from .collier_fl import CollierCountyFL
from .cuyahoga_oh import CuyahogaCountyOH, CuyahogaTreasurerOH
from .dallas_tx import DallasCountyTX
from .dekalb_ga import DeKalbCountyGA
from .denton_tx import DentonCountyTX
from .ector_tx import EctorCountyTX
from .forsyth_ga import ForsythCountyGA
from .fortbend_tx import FortBendCountyTX
from .gwinnett_ga import GwinnettCountyGA
from .manatee_fl import ManateeCountyFL
from .marion_fl import MarionCountyFL
from .modoc_ca import ModocCountyCA
from .mohave_az import MohaveCountyAZ
from .montgomery_oh import MontgomeryCountyOH
from .santarosa_fl import SantaRosaCountyFL
from .taylor_fl import TaylorCountyFL
from .volusia_fl import VolusiaCountyFL
from .wise_tx import WiseCountyTX
from .base import RecordIn, Source

# Add new county scrapers here, and record them in data/county_sources.csv.
SOURCES: dict[str, type[Source]] = {s.name: s for s in [
    AdamsCountyOH, CalhounCountySC, ChathamCountyGA, ClaytonCountyGA, CobbCountyGA, CollierCountyFL, CuyahogaCountyOH, CuyahogaTreasurerOH, DallasCountyTX, DeKalbCountyGA, DentonCountyTX, EctorCountyTX, ForsythCountyGA, FortBendCountyTX, GwinnettCountyGA, ManateeCountyFL, MarionCountyFL, ModocCountyCA, MohaveCountyAZ, MontgomeryCountyOH, SantaRosaCountyFL, TaylorCountyFL, VolusiaCountyFL, WiseCountyTX,
]}

__all__ = ["SOURCES", "RecordIn", "Source"]
