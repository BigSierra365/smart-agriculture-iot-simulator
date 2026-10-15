import random
import uuid
import config
from energy import BatteryController


class PlotSoilState:
    """
    Mantiene el estado físico del suelo de una parcela en memoria,
    garantizando que las variaciones tengan coherencia temporal.
    """

    def __init__(self, plot_id):
        self.plot_id = plot_id
        self.crop = config.PLOTS[plot_id]["crop"]
        self.sensor_ids = config.PLOTS[plot_id]["soil_sensors"]

        # Estado inicial dentro de los rangos orientativos (Sección 3.1)
        self.moisture = random.uniform(22.0, 32.0)  # 10–45 %
        self.temperature = 18.0                     # 8–35 °C
        self.ph = random.uniform(6.0, 7.5)          # 5,5–8,0
        self.ec = random.uniform(0.8, 1.5)          # 0,2–3,0 dS/m

        # Diccionario para las baterías de los dos sensores de la parcela
        self.batteries = {
            self.sensor_ids[0]: BatteryController(initial_level=random.uniform(70.0, 95.0)),
            self.sensor_ids[1]: BatteryController(initial_level=random.uniform(70.0, 95.0))
        }

    def update_from_weather(self, weather_measurements):
        """
        Aplica las reglas meteorológicas (evaporación, lluvia e inercia térmica) al suelo.
        """
        # Regla 5.2: Suelo sin aportes pierde humedad gradualmente (influyen calor y viento)
        temp_air = weather_measurements["air_temperature_c"]
        wind = weather_measurements["wind_speed_ms"]
        evaporation_rate = 0.08 + (temp_air / 180.0) + (wind / 300.0)
        self.moisture -= evaporation_rate

        # Regla 5.5: La lluvia aumenta la humedad del suelo
        rain = weather_measurements["rainfall_mm"]
        if rain > 0:
            self.moisture += rain * 0.45

        # Limitar la humedad a los rangos orientativos (10–45 %)
        self.moisture = max(10.0, min(45.0, self.moisture))

        # Inercia térmica del suelo respecto al aire (8–35 °C)
        self.temperature = (self.temperature * 0.85) + (temp_air * 0.15)
        self.temperature = max(8.0, min(35.0, self.temperature))

    def add_water_from_irrigation(self, liters_applied):
        """
        Regla 5.4: Aumenta la humedad progresivamente cuando recibe agua de riego.
        """
        self.moisture += liters_applied * config.SOIL_ABSORPTION_FACTOR
        self.moisture = min(45.0, self.moisture)

    def generate_sensor_events(self, timestamp, current_solar_radiation):
        """
        Genera los eventos de lectura para los dos sensores de suelo de esta parcela.
        """
        events = []
        for idx, device_id in enumerate(self.sensor_ids):
            var_moisture = random.uniform(-0.4, 0.4)
            var_temp = random.uniform(-0.2, 0.2)

            current_battery = self.batteries[device_id].update(current_solar_radiation)
            if current_battery <= 0.0:
                current_status = "OFFLINE"
            elif current_battery < 15.0:
                current_status = "LOW_BATTERY"
            else:
                current_status = "OK"

            event = {
                "event_id": str(uuid.uuid4()),
                "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "device_id": device_id,
                "event_type": "sensor_reading",
                "farm_id": config.FARM_ID,
                "plot_id": self.plot_id,
                "crop": self.crop,
                "sensor_depth_cm": 15 + (idx * 5),
                "measurements": {
                    "soil_moisture_pct": round(max(10.0, min(45.0, self.moisture + var_moisture)), 1),
                    "soil_temperature_c": round(max(8.0, min(35.0, self.temperature + var_temp)), 1),
                    "soil_ph": round(max(5.5, min(8.0, self.ph + random.uniform(-0.02, 0.02))), 1),
                    "soil_ec_ds_m": round(max(0.2, min(3.0, self.ec + random.uniform(-0.01, 0.01))), 1)
                },
                "battery_pct": current_battery,
                "device_status": current_status
            }
            events.append(event)
        return events