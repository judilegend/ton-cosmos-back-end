from typing import Dict, Any, List, TypedDict

class PlanetPosition(TypedDict):
    lon: float
    sign: str
    deg: float


class Aspect(TypedDict):
    p1: str
    p2: str
    type: str
    orb: float


class House(TypedDict):
    lon: float
    sign: str


class Transit(TypedDict):
    month: str
    positions: Dict[str, str]


class FullChart(TypedDict):
    birth_chart: Dict[str, Any]
    forecast: List[Transit]
