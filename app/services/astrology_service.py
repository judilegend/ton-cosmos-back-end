import asyncio
import calendar
import swisseph as swe
from zoneinfo import ZoneInfo
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, date, timezone, timedelta

class AstrologyService:
    _executor = ThreadPoolExecutor(max_workers=4)

    def __init__(self):
        swe.set_ephe_path('/usr/share/ephe')
        self.planets_map = {
            "Soleil": swe.SUN, "Lune": swe.MOON, "Mercure": swe.MERCURY,
            "Vénus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
            "Saturne": swe.SATURN, "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE,
            "Pluton": swe.PLUTO
        }
        self.signs = [
            "Bélier", "Taureau", "Gémeaux", "Cancer", "Lion", "Vierge",
            "Balance", "Scorpion", "Sagittaire", "Capricorne", "Verseau", "Poissons"
        ]

    def _get_jd_from_params(self, b_date: date, b_time: time, tz_name: str) -> float:
        local_dt = datetime.combine(b_date, b_time).replace(tzinfo=ZoneInfo(tz_name))
        utc_dt = local_dt.astimezone(timezone.utc)
        return swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour + (utc_dt.minute / 60.0) + (utc_dt.second / 3600.0))

    def _extract_lon(self, result: Any) -> float:
        return float(result[0][0] if isinstance(result, (list, tuple)) and isinstance(result[0], (list, tuple)) else (result[0] if isinstance(result, (list, tuple)) else result))

    def _get_sign(self, lon: float) -> str:
        return self.signs[int((lon % 360) // 30)]

    def _format_position(self, lon: float) -> Dict[str, Any]:
        lon = lon % 360
        return {"lon": round(lon, 4), "sign": self._get_sign(lon), "deg": round(lon % 30, 2)}

    def _calculate_aspects_sync(self, planets: Dict[str, Any]) -> List[Dict[str, Any]]:
        aspects = {0: "Conjonction", 60: "Sextile", 90: "Carré", 120: "Trigone", 180: "Opposition"}
        results = []
        names = list(planets.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                diff = abs(planets[names[i]]["lon"] - planets[names[j]]["lon"])
                diff = diff if diff <= 180 else 360 - diff
                for angle, name in aspects.items():
                    orb = abs(diff - angle)
                    if orb <= 5:
                        results.append({"p1": names[i], "p2": names[j], "type": name, "orb": round(orb, 2)})
        return results

    def _run_heavy_calculation(self, b_date: date, b_time: time, tz_name: str, lat: float, lon: float) -> Dict[str, Any]:
        jd = self._get_jd_from_params(b_date, b_time, tz_name)
        
        # 1. Calcul natal
        planet_data = {}
        for name, pid in self.planets_map.items():
            planet_data[name] = self._format_position(self._extract_lon(swe.calc_ut(jd, pid)))

        nodes_res = swe.calc_ut(jd, swe.TRUE_NODE)
        n_nord = self._extract_lon(nodes_res)
        planet_data["Noeud Nord"] = self._format_position(n_nord)
        planet_data["Noeud Sud"] = self._format_position((n_nord + 180) % 360)

        houses, ascmc = swe.houses(jd, lat, lon, b'P')
        houses_data = {i + 1: self._format_position(float(h)) for i, h in enumerate(houses)}
        
        # 2. Calcul des prévisions
        forecast = []
        slow_planets = {"Jupiter": swe.JUPITER, "Saturne": swe.SATURN, "Pluton": swe.PLUTO}
        
        MONTHS_FR = [
            "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
        ]
        
        for i in range(1, 13):
            target_month = b_date.month + i
            year_offset = (target_month - 1) // 12
            actual_month = (target_month - 1) % 12 + 1
            future_year = b_date.year + year_offset
            
            future_jd = swe.julday(future_year, actual_month, 1, 0)
            
            month_name = MONTHS_FR[actual_month]
            
            pos_at_date = {}
            for name, pid in slow_planets.items():
                res = swe.calc_ut(future_jd, pid)
                pos_at_date[name] = self._get_sign(self._extract_lon(res))
            
            forecast.append({
                "period": f"{month_name} {future_year}",
                "positions": pos_at_date
            })
        
        return {
            "birth_chart": {
                "planets": planet_data,
                "ascendant": self._format_position(ascmc[0]),
                "houses": houses_data,
                "aspects": self._calculate_aspects_sync(planet_data)
            },
            "forecast": forecast
        }

    async def get_full_chart(self, b_date: date, b_time: time, tz_name: str, lat: float, lon: float) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._run_heavy_calculation, b_date, b_time, tz_name, lat, lon)