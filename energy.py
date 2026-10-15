import config


class BatteryController:
    """
    simlacion de la carga y descarga de el sensor
    """
    def __init__(self, initial_level=100.00, base_consumtion=0.065, charge_rate=0.4):
        self.level = float(initial_level)
        # Si se ejecuta desde la ventana (en RAM), usa el valor de la ventana;
        # si se ejecuta normal por consola, usa tus valores originales (0.065, 0.4 y 150)
        self.base_consumtion = getattr(config, "BATTERY_DRAIN_RATE", base_consumtion)
        self.charge_rate = getattr(config, "BATTERY_CHARGE_RATE", charge_rate)
        self.solar_threshold = getattr(config, "SOLAR_CHARGE_THRESHOLD", 150)

    def update(self, solar_radiation_w_m2):
        if solar_radiation_w_m2 > self.solar_threshold:
            self.level += self.charge_rate
        else:
            self.level -= self.base_consumtion

        # limitacion de los valores reales de una bateria
        self.level = max(0.0, min(100.0, self.level))

        return round(self.level, 1)