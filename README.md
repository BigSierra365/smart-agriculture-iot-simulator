# Smart Agriculture — Simulador de sensores IoT

Simulador en Python que genera datos sintéticos de la explotación agrícola ficticia **AgroSmart Solutions**: sensores de suelo, estación meteorológica, controladores de riego y alertas. Los eventos se guardan en archivos **JSON Lines** locales para usarlos en futuras prácticas de ingesta, procesamiento y análisis.

**Autor:** Emmanuel Grande Sierra

📖 **Tutorial paso a paso del desarrollo:** [docs/tutorial.md](docs/tutorial.md)

---

## 1. Qué simula

| Parcela | Cultivo | Superficie | Sensores de suelo | Riego |
| --- | --- | --- | --- | --- |
| P001 | Tomates | 2 ha | `SOIL-P001-01`, `SOIL-P001-02` | `IRR-P001-01` |
| P002 | Lechugas | 1,5 ha | `SOIL-P002-01`, `SOIL-P002-02` | `IRR-P002-01` |
| P003 | Maíz | 5 ha | `SOIL-P003-01`, `SOIL-P003-02` | `IRR-P003-01` |
| P004 | Fresas | 1 ha | `SOIL-P004-01`, `SOIL-P004-02` | `IRR-P004-01` |
| P005 | Pimientos | 2 ha | `SOIL-P005-01`, `SOIL-P005-02` | `IRR-P005-01` |

Más una estación meteorológica compartida (`WEATHER-001`): **16 dispositivos** con `device_id` fijo.

El generador **mantiene un estado por parcela** (humedad del suelo, riego, batería), por lo que los valores evolucionan de forma coherente y no son números aleatorios independientes.

## 2. Requisitos

- **Python 3.10 o superior**.
- **Simulador base y pruebas (`main.py`, `tests/`):** solo utilizan la **biblioteca estándar de Python** (no requieren instalar dependencias externas).
- **Lanzador con ventana (`engine.py`):** utiliza `tkinter` (incluido por defecto con Python en Windows).
- **Panel interactivo opcional (`dashboard.py`):** requiere `streamlit`, `pandas` y `plotly` (incluidos en `requirements.txt`).

## 3. Instalación

```bash
git clone [https://github.com/](https://github.com/)BigSierra365/smart-agriculture-iot-simulator.git
cd smart-agriculture-iot-simulator
python -m venv .venv
source .venv/Scripts/activate        # Git Bash en Windows (PowerShell: .\.venv\Scripts\Activate.ps1)
pip install -r requirements.txt      # Opcional: solo necesario para el dashboard en Streamlit

```

## 4. Ejecución

El proyecto ofrece tres herramientas de ejecución y análisis:

```bash
# 1. Ejecutar el simulador por consola (usa los valores de config.py)
python main.py

# 2. Abrir el lanzador gráfico para cambiar parámetros en RAM sin modificar config.py
python engine.py

# 3. Abrir el panel interactivo de telemetría y alertas (opcional)
streamlit run dashboard.py

```

### Parámetros (`config.py`)

| Parámetro | Valor por defecto | Descripción |
| --- | --- | --- |
| `SIMULATION_MODE` | `"LIMITED"` | `"LIMITED"` termina solo; `"CONTINUOUS"` se detiene con `Ctrl+C` |
| `SIMULATION_DURATION` | `10` | Eventos a generar en modo limitado |
| `GENERATION_INTERVAL` | `300` | Segundos que avanza el reloj virtual en cada paso |
| `REALTIME_SLEEP` | `0.0` | Pausa real entre iteraciones (útil en modo continuo) |
| `RANDOM_SEED` | `42` | Semilla para reproducir escenarios (los `event_id` siguen siendo únicos) |
| `ENABLE_ANOMALIES` | `True` | Activa/desactiva las alertas |
| `OUTPUT_DIR` | `"data"` | Carpeta de salida |
| `NUM_PLOTS` | `5` | Número de parcelas |

### Generar 1.000 eventos (modo limitado)

En `config.py`: `SIMULATION_MODE = "LIMITED"` y `SIMULATION_DURATION = 1000`, y después:

> En modo limitado el límite se comprueba al empezar cada parcela, por lo que puede generarse algún evento más.

### Modo continuo

Con `SIMULATION_MODE = "CONTINUOUS"` el simulador no termina hasta pulsar `Ctrl+C`, que se captura para cerrar de forma controlada sin corromper los archivos. También puede lanzarse directamente sin editar `config.py` con:

```bash
python -c "import config, main; config.SIMULATION_MODE='CONTINUOUS'; config.REALTIME_SLEEP=0.5; main.main()"

```

### Archivos de salida

Se amplían en cada ejecución (modo *append*), nunca se sobrescriben. Para empezar de cero, borra los `.jsonl` de la carpeta de salida.

## 5. Estructura del proyecto

```
smart-agriculture-iot-simulator/
├── main.py            # Bucle principal, modos, reloj virtual, Ctrl+C
├── config.py          # Parámetros, umbrales y definición de parcelas
├── energy.py          # Batería (carga solar y descarga)
├── weather.py         # Estación meteorológica
├── sensors.py         # Estado del suelo y sensores
├── irrigation.py      # Controlador de riego
├── anomalies.py       # Detección e inyección de alertas
├── data_writer.py     # Escritura en JSON Lines
├── engine.py          # Lanzador con ventana en modo seguro (Tkinter)
├── dashboard.py       # Panel interactivo de visualización (Streamlit + Plotly)
├── data/              # Muestra de los 4 archivos .jsonl
│   ├── sensor_readings.jsonl
│   ├── weather_readings.jsonl
│   ├── irrigation_events.jsonl
│   └── alerts.jsonl
├── docs/
│   ├── tutorial.md    # Tutorial paso a paso
│   └── img/           # Capturas de evidencia
├── tests/
│   └── test_simulador.py  # 20 pruebas automatizadas (unittest)
├── requirements.txt
├── .gitignore
└── README.md

```

## 6. Esquemas de los eventos

Todos los eventos incluyen `event_id` (UUID4 único), `timestamp` (UTC, ISO 8601 `YYYY-MM-DDTHH:MM:SSZ`), `device_id`, `event_type` y `farm_id`.

### 6.1. `sensor_reading` → `sensor_readings.jsonl`

| Campo | Descripción |
| --- | --- |
| `plot_id`, `crop` | Parcela y cultivo |
| `sensor_depth_cm` | Profundidad del sensor (15 o 20 cm) |
| `measurements.soil_moisture_pct` | Humedad del suelo (10–45 %) |
| `measurements.soil_temperature_c` | Temperatura del suelo (8–35 °C) |
| `measurements.soil_ph` | pH (5,5–8,0) |
| `measurements.soil_ec_ds_m` | Conductividad eléctrica (0,2–3,0 dS/m) |
| `battery_pct`, `device_status` | Batería y estado (`OK`, `LOW_BATTERY`, `OFFLINE`, `ERROR`) |

### 6.2. `weather_reading` → `weather_readings.jsonl`

| Campo | Descripción |
| --- | --- |
| `measurements.air_temperature_c` | Temperatura del aire (5–40 °C) |
| `measurements.air_humidity_pct` | Humedad relativa (20–95 %) |
| `measurements.solar_radiation_w_m2` | Radiación solar (0–1.100 W/m²) |
| `measurements.rainfall_mm` | Lluvia durante el intervalo (0–15 mm) |
| `measurements.wind_speed_ms` | Viento (0–15 m/s) |
| `battery_pct`, `device_status` | Batería y estado |

No lleva `plot_id`: la estación es compartida.

### 6.3. `irrigation_event` → `irrigation_events.jsonl`

| Campo | Descripción |
| --- | --- |
| `plot_id` | Parcela |
| `irrigation_status` | `ON` / `OFF` |
| `valve_status` | `OPEN` / `CLOSED` |
| `water_flow_l_min` | Caudal (L/min) |
| `water_pressure_bar` | Presión (bar) |
| `water_volume_l` | Volumen acumulado desde el inicio de la simulación (L) |
| `reason` | `LOW_SOIL_MOISTURE`, `TARGET_MOISTURE_REACHED` o `PERIODIC_TELEMETRY` |
| `battery_pct`, `device_status` | Batería y estado |

### 6.4. `alert` → `alerts.jsonl`

| Campo | Descripción |
| --- | --- |
| `alert_code` | Código de la anomalía |
| `severity` | `WARNING` o `CRITICAL` |
| `measured_value` | Valor observado que provoca la alerta |
| `threshold_value` | Umbral con el que se compara (misma unidad) |
| `message` | Explicación legible |
| `plot_id` | Parcela afectada (si procede) |

`device_id` es el del dispositivo afectado.

## 7. Reglas de simulación

| Regla | Cómo se implementa |
| --- | --- |
| **Ciclo diario** | Temperatura senoidal (máx. 14:00, mín. 02:00) con ruido. Radiación solar solo entre las 06:00 y las 18:00; de noche es 0. |
| **Suelo sin aportes** | Cada paso pierde humedad por evaporación: `0,08 + temp/180 + viento/300` puntos. Más calor y viento, más rápido se seca. |
| **Lluvia** | 2 % de probabilidad por paso (1–15 mm). Suma `lluvia × 0,45` puntos de humedad. La humedad del aire sube con la lluvia. |
| **Riego** | Se activa (`ON`/`OPEN`) con humedad < **20 %** y se detiene al alcanzar **35 %** (histéresis). Caudal nominal 35,5 L/min y presión 2,3 bar. |
| **Efecto del riego** | Cada litro aplicado suma `0,02` puntos de humedad (`SOIL_ABSORPTION_FACTOR`), de forma progresiva. |
| **Coherencia de dispositivos** | Estado, válvula, caudal y volumen acumulado son compatibles; el volumen nunca disminuye salvo fallo de riego simulado. |
| **Batería** | Carga +0,4 con radiación > 150 W/m²; si no, descarga −0,065. Limitada a 0–100 %. `LOW_BATTERY` por debajo del 15 % y `OFFLINE` al 0 %. |
| **Reloj virtual** | Empieza a las 00:00 UTC y avanza `GENERATION_INTERVAL` segundos por paso, sin esperar en tiempo real. |
| **Semilla** | `random.seed(RANDOM_SEED)`; los `event_id` usan `uuid4` y no dependen de ella. |

### Anomalías (alertas)

| Código | Gravedad | Condición | Umbral / probabilidad (`config.py`) |
| --- | --- | --- | --- |
| `LOW_SOIL_MOISTURE` | WARNING | Humedad medida < umbral | `ALERT_LOW_MOISTURE_THRESHOLD = 20.0` |
| `HIGH_TEMPERATURE` | WARNING | Temperatura del aire > umbral | `ALERT_HIGH_TEMP_THRESHOLD = 38.0` |
| `SENSOR_FAILURE` | CRITICAL | Sensor sin lectura (humedad `None`, estado `ERROR`) | `PROB_SENSOR_FAILURE = 0.005` |
| `IRRIGATION_FAILURE` | CRITICAL | Riego en `ON` sin caudal | `PROB_IRRIGATION_FAILURE = 0.02` (caudal mínimo `5.0`) |
| `WATER_LEAK` | CRITICAL | Caudal con la válvula cerrada | `PROB_WATER_LEAK = 0.005` |

Las dos primeras se **detectan** en los datos; las otras tres se **inyectan** con una probabilidad. Con `ENABLE_ANOMALIES = False` no se genera ninguna alerta. Los datos son sintéticos y los umbrales didácticos, no recomendaciones agronómicas.

## 8. Pruebas y evidencias

### 8.1. Pruebas automatizadas

```bash
python -m unittest discover -s tests -v

```

Son 20 pruebas (`tests/test_simulador.py`) agrupadas en tres bloques: validación de datos, reglas de simulación y modos/almacenamiento. Las pruebas se ejecutan en directorios temporales aislados y no modifican `config.py` ni la carpeta `data/` real. Detalle en la [Parte 2 del tutorial](https://www.google.com/search?q=docs/tutorial.md%23parte-2-pruebas-unitarias).

### 8.2. Resumen frente a la tabla de validación de la práctica

| Prueba | Resultado | Cómo se comprueba (`tests/test_simulador.py`) |
| --- | --- | --- |
| Validación JSONL | ✅ Todas las líneas son JSON válido | `test_jsonl_valido` |
| Campos obligatorios | ✅ `event_id`, `timestamp`, `device_id` en todos | `test_campos_obligatorios` |
| Unicidad | ✅ 0 `event_id` duplicados | `test_event_id_sin_duplicados` |
| Tiempos | ✅ Todos en formato UTC ISO 8601 | `test_timestamps_utc_iso_8601` |
| Dispositivos | ✅ Los 16 `device_id` definidos | `test_dispositivos_simulados` |
| Comportamiento temporal | ✅ Más calor de tarde, radiación 0 de noche | `test_ciclo_diario` |
| Riego y lluvia | ✅ El suelo responde a los aportes | `test_lluvia_sube_la_humedad`, `test_riego_*` |
| Anomalías | ✅ Alertas identificables almacenadas | `test_alertas_identificables` |
| Modo limitado | ✅ Finaliza automáticamente según configuración | `test_modo_limitado_termina_solo` |
| Modo continuo | ✅ Se detiene con `Ctrl+C` sin corromper archivos | `test_modo_continuo_se_detiene_con_ctrl_c_sin_corromper_archivos` |
| Volumen mínimo | ✅ ≥ 1.000 eventos en una ejecución de prueba | `test_volumen_minimo_1000_eventos` |

## 9. Muestra de datos

La carpeta `data/` contiene una muestra pequeña y representativa de los cuatro tipos de evento. No se suben datasets voluminosos (ver `.gitignore`).

## 10. Notas

* `weather.py` guarda el viento y la batería como variables del módulo; en una ejecución normal (`python main.py`, proceso nuevo) no hay ningún problema.
* No se publican secretos, credenciales ni información sensible.
