import random
import uuid
import config
from energy import BatteryController


class IrrigationController:
    """
    Controla el riego de una parcela. Mantiene el estado de la válvula
    y calcula el volumen de agua acumulado.
    """

    def __init__(self, plot_id):
        self.plot_id = plot_id
        self.device_id = config.PLOTS[plot_id]["irrigation"]

        # Umbrales configurables
        self.moisture_threshold = config.IRRIGATION_MIN_MOISTURE
        self.target_moisture = config.IRRIGATION_TARGET_MOISTURE

        # Estado inicial (apagado)
        self.status = "OFF"
        self.valve = "CLOSED"
        self.water_volume_l = 0.0

        self.battery = BatteryController(initial_level=random.uniform(85.0, 99.0))

    def evaluate_and_irrigate(self, current_moisture, timestamp, current_solar_radiation):
        """
        Evalúa si es necesario regar basándose en la humedad actual del suelo.
        Devuelve una tupla: (evento_json, litros_aplicados)
        """
        liters_applied = 0.0
        reason = "PERIODIC_TELEMETRY"

        # Lógica de activación / desactivación
        if self.status == "OFF" and current_moisture < self.moisture_threshold:
            self.status = "ON"
            self.valve = "OPEN"
            reason = "LOW_SOIL_MOISTURE"

        elif self.status == "ON" and current_moisture >= self.target_moisture:
            self.status = "OFF"
            self.valve = "CLOSED"
            reason = "TARGET_MOISTURE_REACHED"

        # Cálculo de caudal y volumen acumulado
        if self.status == "ON" and self.valve == "OPEN":
            flow_l_min = config.IRRIGATION_FLOW_L_MIN
            pressure = config.IRRIGATION_PRESSURE_BAR
            minutes_passed = config.GENERATION_INTERVAL / 60.0
            liters_applied = flow_l_min * minutes_passed
            self.water_volume_l += liters_applied
        else:
            flow_l_min = 0.0
            pressure = 0.0

        current_battery = self.battery.update(current_solar_radiation)
        if current_battery <= 0.0:
            current_status = "OFFLINE"
        elif current_battery < 15.0:
            current_status = "LOW_BATTERY"
        else:
            current_status = "OK"

        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "device_id": self.device_id,
            "event_type": "irrigation_event",
            "farm_id": config.FARM_ID,
            "plot_id": self.plot_id,
            "irrigation_status": self.status,
            "valve_status": self.valve,
            "water_flow_l_min": round(flow_l_min, 1),
            "water_pressure_bar": round(pressure, 1),
            "water_volume_l": round(self.water_volume_l, 1),
            "reason": reason,
            "battery_pct": current_battery,
            "device_status": current_status
        }

        return event, liters_applied