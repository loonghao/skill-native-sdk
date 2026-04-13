"""get_current — current weather conditions (simulation mode)."""
from __future__ import annotations

import json
import random
import sys
from typing import Any

_CONDITIONS = ["Sunny", "Partly Cloudy", "Cloudy", "Light Rain", "Thunderstorm", "Foggy", "Windy"]

_CITY_SEEDS: dict[str, dict] = {
    "tokyo":    {"temp_c": 22, "humidity": 65, "condition": "Partly Cloudy"},
    "new york": {"temp_c": 18, "humidity": 55, "condition": "Sunny"},
    "london":   {"temp_c": 14, "humidity": 80, "condition": "Cloudy"},
    "beijing":  {"temp_c": 20, "humidity": 50, "condition": "Foggy"},
    "sydney":   {"temp_c": 25, "humidity": 60, "condition": "Sunny"},
}


def skill_entry(city: str, units: str = "metric") -> dict[str, Any]:
    """Return simulated current weather for *city*."""
    seed = _CITY_SEEDS.get(city.lower())
    if seed:
        temp_c = seed["temp_c"] + random.uniform(-2, 2)
        humidity = seed["humidity"]
        condition = seed["condition"]
    else:
        temp_c = random.uniform(10, 35)
        humidity = random.randint(40, 90)
        condition = random.choice(_CONDITIONS)

    temp = temp_c if units == "metric" else temp_c * 9 / 5 + 32
    unit_label = "°C" if units == "metric" else "°F"

    return {
        "success": True,
        "message": f"{city}: {condition}, {temp:.1f}{unit_label}, humidity {humidity}%",
        "data": {
            "city": city,
            "temperature": round(temp, 1),
            "unit": unit_label,
            "condition": condition,
            "humidity": humidity,
        },
        "next_actions": ["get_forecast"],
    }


if __name__ == "__main__":
    import inspect
    params = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    sig = inspect.signature(skill_entry)
    filtered = {k: v for k, v in params.items() if k in sig.parameters}
    result = skill_entry(**filtered)
    print(json.dumps(result))
