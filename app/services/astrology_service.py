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
        # swe.set_ephe_path('/usr/share/ephe/')
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

        chiron_res = swe.calc_ut(jd, swe.CHIRON)
        planet_data["Chiron"] = self._format_position(self._extract_lon(chiron_res))

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

    def calculate_solar_return(self, natal_sun_lon: float, birth_month: int, birth_day: int, target_year: int, lat: float, lon: float) -> Dict[str, Any]:
        jd_start = swe.julday(target_year, birth_month, birth_day, 12.0)
        
        def get_diff(jd):
            res = swe.calc_ut(jd, swe.SUN)
            sun_lon = self._extract_lon(res)
            diff = sun_lon - natal_sun_lon
            return (diff + 180) % 360 - 180
            
        a = jd_start - 3.0
        b = jd_start + 3.0
        fa = get_diff(a)
        fb = get_diff(b)
        
        if fa * fb > 0:
            for offset in range(-15, 16, 2):
                a = jd_start + offset
                b = jd_start + offset + 2
                fa = get_diff(a)
                fb = get_diff(b)
                if fa * fb <= 0:
                    break
                    
        for _ in range(50):
            if abs(b - a) < 1e-6:
                break
            try:
                c = b - fb * (b - a) / (fb - fa)
            except ZeroDivisionError:
                c = (a + b) / 2.0
            fc = get_diff(c)
            if abs(fc) < 1e-7:
                a = b = c
                break
            if fa * fc < 0:
                b = c
                fb = fc
            else:
                a = c
                fa = fc
                
        jd_sr = (a + b) / 2.0
        
        sr_planets = {}
        for name, pid in self.planets_map.items():
            sr_planets[name] = self._format_position(self._extract_lon(swe.calc_ut(jd_sr, pid)))
        sr_planets["Chiron"] = self._format_position(self._extract_lon(swe.calc_ut(jd_sr, swe.CHIRON)))
            
        sr_houses, sr_ascmc = swe.houses(jd_sr, lat, lon, b'P')
        sr_houses_data = {i + 1: self._format_position(float(h)) for i, h in enumerate(sr_houses)}
        
        y, m, d, h_frac = swe.revjul(jd_sr)
        hour = int(h_frac)
        min_frac = (h_frac - hour) * 60
        minute = int(min_frac)
        second = int((min_frac - minute) * 60)
        
        sr_datetime = datetime(y, m, d, hour, minute, second, tzinfo=timezone.utc)
        
        return {
            "solar_return_jd": jd_sr,
            "solar_return_datetime": sr_datetime.isoformat(),
            "planets": sr_planets,
            "ascendant": self._format_position(sr_ascmc[0]),
            "houses": sr_houses_data
        }

    def calculate_transits(self, jd_start: float, natal_planets: Dict[str, Any], orbs: Dict[int, float]) -> Dict[str, Any]:
        transiting_pids = {
            "Mars": swe.MARS,
            "Jupiter": swe.JUPITER,
            "Saturne": swe.SATURN,
            "Uranus": swe.URANUS,
            "Neptune": swe.NEPTUNE,
            "Pluton": swe.PLUTO
        }
        
        aspect_angles = {0: "Conjonction", 60: "Sextile", 90: "Carré", 120: "Trigone", 180: "Opposition"}
        
        aspect_windows = []
        stations = []
        
        prev_speeds = {}
        active_aspects = {}
        
        for day_offset in range(365):
            jd = jd_start + day_offset
            y, m, d, _ = swe.revjul(jd)
            current_date = date(y, m, d)
            
            for tp_name, tp_id in transiting_pids.items():
                res = swe.calc_ut(jd, tp_id)
                tp_lon = self._extract_lon(res)
                tp_speed = float(res[0][3]) if isinstance(res[0], (list, tuple)) else float(res[3])
                
                if tp_name in prev_speeds:
                    prev_sp = prev_speeds[tp_name]
                    if prev_sp < 0 and tp_speed >= 0:
                        stations.append({
                            "planet": tp_name,
                            "type": "Directe",
                            "date": current_date.isoformat(),
                            "lon": round(tp_lon, 4)
                        })
                    elif prev_sp > 0 and tp_speed <= 0:
                        stations.append({
                            "planet": tp_name,
                            "type": "Rétrograde",
                            "date": current_date.isoformat(),
                            "lon": round(tp_lon, 4)
                        })
                prev_speeds[tp_name] = tp_speed
                
                for np_name, np_data in natal_planets.items():
                    if "lon" not in np_data:
                        continue
                    np_lon = np_data["lon"]
                    diff = abs(tp_lon - np_lon)
                    diff = diff if diff <= 180 else 360 - diff
                    
                    for angle, asp_name in aspect_angles.items():
                        orb_limit = orbs.get(angle, 5.0)
                        orb = abs(diff - angle)
                        if orb <= orb_limit:
                            key = (tp_name, np_name, asp_name)
                            if key not in active_aspects:
                                active_aspects[key] = []
                            active_aspects[key].append({
                                "date": current_date.isoformat(),
                                "orb": round(orb, 2)
                            })
                        else:
                            key = (tp_name, np_name, asp_name)
                            if key in active_aspects and len(active_aspects[key]) > 0:
                                window_days = active_aspects.pop(key)
                                peak = min(window_days, key=lambda x: x["orb"])
                                aspect_windows.append({
                                    "transiting_planet": tp_name,
                                    "natal_planet": np_name,
                                    "aspect": asp_name,
                                    "start_date": window_days[0]["date"],
                                    "end_date": window_days[-1]["date"],
                                    "peak_date": peak["date"],
                                    "peak_orb": peak["orb"]
                                })
                                
        for key, window_days in active_aspects.items():
            if len(window_days) > 0:
                peak = min(window_days, key=lambda x: x["orb"])
                aspect_windows.append({
                    "transiting_planet": key[0],
                    "natal_planet": key[1],
                    "aspect": key[2],
                    "start_date": window_days[0]["date"],
                    "end_date": window_days[-1]["date"],
                    "peak_date": peak["date"],
                    "peak_orb": peak["orb"]
                })
                
        return {
            "aspect_windows": aspect_windows,
            "stations": stations
        }

    def calculate_saturn_returns(self, birth_date: date, natal_saturn_lon: float) -> List[Dict[str, Any]]:
        returns = []
        age_ranges = [(27, 33), (56, 62)]
        
        for r_num, (min_age, max_age) in enumerate(age_ranges, 1):
            start_year = birth_date.year + min_age
            end_year = birth_date.year + max_age
            
            jd_start = swe.julday(start_year, 1, 1, 0.0)
            jd_end = swe.julday(end_year, 12, 31, 0.0)
            
            step = 10.0
            jd = jd_start
            prev_diff = None
            crossing_jds = []
            
            while jd <= jd_end:
                res = swe.calc_ut(jd, swe.SATURN)
                sat_lon = self._extract_lon(res)
                diff = (sat_lon - natal_saturn_lon + 180) % 360 - 180
                
                if prev_diff is not None:
                    if prev_diff * diff <= 0:
                        a = jd - step
                        b = jd
                        fa = prev_diff
                        fb = diff
                        for _ in range(30):
                            c = (a + b) / 2.0
                            res_c = swe.calc_ut(c, swe.SATURN)
                            fc = (self._extract_lon(res_c) - natal_saturn_lon + 180) % 360 - 180
                            if abs(fc) < 1e-6:
                                a = b = c
                                break
                            if fa * fc < 0:
                                b = c
                                fb = fc
                            else:
                                a = c
                                fa = fc
                        crossing_jds.append((a + b) / 2.0)
                
                prev_diff = diff
                jd += step
                
            crossing_dates = []
            for c_jd in crossing_jds:
                y, m, d, _ = swe.revjul(c_jd)
                crossing_dates.append(date(y, m, d).isoformat())
                
            if crossing_dates:
                returns.append({
                    "return_number": r_num,
                    "approximate_age_range": f"{min_age}-{max_age} ans",
                    "exact_dates": crossing_dates
                })
                
        return returns

    def _run_forecast_calculation(self, b_date: date, b_time: time, tz_name: str, lat: float, lon: float) -> Dict[str, Any]:
        jd = self._get_jd_from_params(b_date, b_time, tz_name)
        
        # Natal Sun for Solar Return
        sun_res = swe.calc_ut(jd, swe.SUN)
        natal_sun_lon = self._extract_lon(sun_res)
        
        # Natal Saturn for Saturn Return
        saturn_res = swe.calc_ut(jd, swe.SATURN)
        natal_saturn_lon = self._extract_lon(saturn_res)
        
        # Natal planets for Transits aspects
        planet_data = {}
        for name, pid in self.planets_map.items():
            planet_data[name] = self._format_position(self._extract_lon(swe.calc_ut(jd, pid)))
            
        nodes_res = swe.calc_ut(jd, swe.TRUE_NODE)
        n_nord = self._extract_lon(nodes_res)
        planet_data["Noeud Nord"] = self._format_position(n_nord)
        planet_data["Noeud Sud"] = self._format_position((n_nord + 180) % 360)
        
        chiron_res = swe.calc_ut(jd, swe.CHIRON)
        planet_data["Chiron"] = self._format_position(self._extract_lon(chiron_res))
        
        # Solar Return for current calendar year
        current_year = datetime.now().year
        solar_return = self.calculate_solar_return(natal_sun_lon, b_date.month, b_date.day, current_year, lat, lon)
        
        # Saturn Return timing
        saturn_returns = self.calculate_saturn_returns(b_date, natal_saturn_lon)
        
        # Transits aspects over next 12 months (starting from today)
        today = datetime.now()
        jd_today = swe.julday(today.year, today.month, today.day, 12.0)
        
        from app.core.config import settings
        orbs = {
            0: getattr(settings, "TRANSIT_ORB_CONJUNCTION", 5.0),
            60: getattr(settings, "TRANSIT_ORB_SEXTILE", 4.0),
            90: getattr(settings, "TRANSIT_ORB_SQUARE", 5.0),
            120: getattr(settings, "TRANSIT_ORB_TRINE", 5.0),
            180: getattr(settings, "TRANSIT_ORB_OPPOSITION", 5.0)
        }
        
        transits_data = self.calculate_transits(jd_today, planet_data, orbs)
        
        return {
            "solar_return": solar_return,
            "saturn_returns": saturn_returns,
            "transits": transits_data,
            "natal_sun_longitude": natal_sun_lon,
            "natal_saturn_longitude": natal_saturn_lon
        }

    async def get_full_chart(self, b_date: date, b_time: time, tz_name: str, lat: float, lon: float) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._run_heavy_calculation, b_date, b_time, tz_name, lat, lon)

    async def get_forecast_chart(self, b_date: date, b_time: time, tz_name: str, lat: float, lon: float) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._run_forecast_calculation, b_date, b_time, tz_name, lat, lon)