"""get_forecast — multi-day weather forecast (simulation mode)."""
from __future__ import annotations

import json
import random
import sys
from datetime import date, timedelta
from typing import Any

_CONDITIONS = ["Sunny", "Partly Cloudy", "Cloudy", "Light Rain", "Thunderstorm", "Windy"]

_CITY_BASE: dict[str, float] = {
    "tokyo": 22, "new york": 18, "london": 14,
    "beijing": 20, "sydney": 25,
}


def skill_entry(city: str, days: int = 3, units: str = "metric") -> dict[str, Any]:
    """Return a *days*-day simulated forecast for *city*."""
    days = max(1, min(int(days), 7))
    base_c = _CITY_BASE.get(city.lower(), random.uniform(10, 30))
    unit_label = "°C" if units == "metric" else "°F"

    forecast = []
    for i in range(days):
        temp_c = base_c + random.uniform(-5, 5)
        temp = temp_c if units == "metric" else temp_c * 9 / 5 + 32
        forecast.append({
            "date": str(date.today() + timedelta(days=i + 1)),
            "condition": random.choice(_CONDITIONS),
            "high": round(temp + random.uniform(0, 4), 1),
            "low":  round(temp - random.uniform(0, 4), 1),
            "unit": unit_label,
            "rain_chance": random.randint(0, 80),
        })

    return {
        "success": True,
        "message": f"{city} {days}-day forecast ready",
        "data": {"city": city, "forecast": forecast},
        "next_actions": [],
    }


if __name__ == "__main__":
    import inspect
    params = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    sig = inspect.signature(skill_entry)
    filtered = {k: v for k, v in params.items() if k in sig.parameters}
    result = skill_entry(**filtered)
    print(json.dumps(result))
