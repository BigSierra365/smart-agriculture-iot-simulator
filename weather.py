import random
import uuid
import math
import config
from energy import BatteryController

weather_battery = BatteryController(initial_level=98.0)
_current_wind = 3.0


def generate_weather_event(timestamp):
    """
    Genera un evento de la estación meteorológica compartida con ciclo diurno coherente.
    """
    global _current_wind

    # 1. Ciclo diario usando la hora del timestamp
    hour = timestamp.hour + timestamp.minute / 60.0

    # Temperatura (Rango: 5–40 °C) - Pico de calor a las 14:00, más frío a las 02:00
    base_temp = 24.5 + 11.5 * math.sin((hour - 8) * math.pi / 12)
    temp = base_temp + random.uniform(-1.2, 1.2)

    # Posibilidad de pico de calor en horas centrales (12:00 a 16:00) para superar 38 °C
    if 12 <= hour <= 16 and random.random() < config.PROB_HEATWAVE:
        temp += random.uniform(3.0, 5.0)

    temp = max(5.0, min(40.0, temp))

    # Radiación solar (Rango: 0–1.100 W/m²) - Solo de día (06:00 a 18:00)
    if 6 <= hour <= 18:
        solar = 950.0 * math.sin((hour - 6) * math.pi / 12) + random.uniform(-20.0, 20.0)
    else:
        solar = 0.0
    solar = max(0.0, min(1100.0, solar))

    # Precipitación (Rango: 0–15 mm)
    rainfall = random.uniform(1.0, 15.0) if random.random() < 0.02 else 0.0

    # Humedad relativa coherente (Rango: 20–95 %): inversa a la temperatura y sube con la lluvia
    base_humidity = 85.0 - ((temp - 5.0) / 35.0) * 55.0
    if rainfall > 0:
        base_humidity += 15.0
    humidity = max(20.0, min(95.0, base_humidity + random.uniform(-3.0, 3.0)))

    # Viento con evolución gradual (Rango: 0–15 m/s)
    _current_wind = max(0.0, min(15.0, _current_wind + random.uniform(-0.8, 0.8)))

    # Estado de la batería
    current_battery = weather_battery.update(solar)
    if current_battery <= 0.0:
        current_status = "OFFLINE"
    elif current_battery < 15.0:
        current_status = "LOW_BATTERY"
    else:
        current_status = "OK"

    # 2. Construcción del evento JSON
    event = {
        "event_id": str(uuid.uuid4()),
        "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "device_id": config.WEATHER_DEVICE_ID,
        "event_type": "weather_reading",
        "farm_id": config.FARM_ID,
        "measurements": {
            "air_temperature_c": round(temp, 1),
            "air_humidity_pct": round(humidity, 1),
            "solar_radiation_w_m2": round(solar, 1),
            "rainfall_mm": round(rainfall, 1),
            "wind_speed_ms": round(_current_wind, 1)
        },
        "battery_pct": current_battery,
        "device_status": current_status
    }

    return event