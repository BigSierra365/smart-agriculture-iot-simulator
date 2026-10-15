import os

# Parámetros generales de ejecución
NUM_PLOTS = 5
GENERATION_INTERVAL = 300     # Segundos que avanza el reloj virtual en cada paso (5 min)
SIMULATION_DURATION = 10  # Límite de eventos para el modo limitado
SIMULATION_MODE = "LIMITED"   # Opciones: "LIMITED" o "CONTINUOUS"
REALTIME_SLEEP = 0.0          # Pausa real en segundos entre iteraciones (útil en modo CONTINUOUS, ej. 0.5)
RANDOM_SEED = 42
ENABLE_ANOMALIES = True
OUTPUT_DIR = "data--"

# Identificadores generales
FARM_ID = "FARM001"
WEATHER_DEVICE_ID = "WEATHER-001"

# Umbrales y parámetros de riego y suelo
IRRIGATION_MIN_MOISTURE = 20.0     # Si baja de 20%, se activa el riego
IRRIGATION_TARGET_MOISTURE = 35.0  # Si alcanza 35%, se detiene el riego
IRRIGATION_FLOW_L_MIN = 35.5       # Caudal nominal (L/min)
IRRIGATION_PRESSURE_BAR = 2.3      # Presión nominal (bar)
SOIL_ABSORPTION_FACTOR = 0.02      # Subida progresiva de humedad por litro aplicado

# Umbrales y probabilidades de alertas/anomalías
ALERT_LOW_MOISTURE_THRESHOLD = 20.0
ALERT_HIGH_TEMP_THRESHOLD = 38.0
ALERT_MIN_FLOW_THRESHOLD = 5.0

PROB_SENSOR_FAILURE = 0.005      # 0.5% de probabilidad de fallo en lectura de sensor
PROB_IRRIGATION_FAILURE = 0.02   # 2.0% de probabilidad de fallo de caudal cuando riega
PROB_WATER_LEAK = 0.005          # 0.5% de probabilidad de fuga con válvula cerrada
PROB_HEATWAVE = 0.04             # 4.0% de probabilidad de pico de calor en horas centrales

# Definición de parcelas y sus dispositivos simulados
PLOTS = {
    "P001": {"crop": "tomates", "area": 2.0, "soil_sensors": ["SOIL-P001-01", "SOIL-P001-02"], "irrigation": "IRR-P001-01"},
    "P002": {"crop": "lechugas", "area": 1.5, "soil_sensors": ["SOIL-P002-01", "SOIL-P002-02"], "irrigation": "IRR-P002-01"},
    "P003": {"crop": "maíz", "area": 5.0, "soil_sensors": ["SOIL-P003-01", "SOIL-P003-02"], "irrigation": "IRR-P003-01"},
    "P004": {"crop": "fresas", "area": 1.0, "soil_sensors": ["SOIL-P004-01", "SOIL-P004-02"], "irrigation": "IRR-P004-01"},
    "P005": {"crop": "pimientos", "area": 2.0, "soil_sensors": ["SOIL-P005-01", "SOIL-P005-02"], "irrigation": "IRR-P005-01"}
}

# Crear el directorio de salida si no existe
os.makedirs(OUTPUT_DIR, exist_ok=True)

