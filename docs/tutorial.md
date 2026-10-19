# Tutorial: Simulador de sensores IoT — Smart Agriculture

Este tutorial explica, paso a paso, cómo se ha desarrollado y probado el simulador. Está dividido en tres partes:

1. [Planteamiento y desarrollo](#parte-1-planteamiento-y-desarrollo)
2. [Pruebas unitarias](#parte-2-pruebas-unitarias)
3. [Conexión con servidor](#parte-3-conexión-con-servidor)

---

# Parte 1. Planteamiento y desarrollo

## 1.1. Qué se quiere conseguir

AgroSmart Solutions gestiona una explotación agrícola con cinco parcelas. El departamento de Ingeniería de Datos necesita **datos sintéticos de dispositivos IoT** para usarlos en futuras prácticas de ingesta, procesamiento y análisis. En esta práctica solo se **generan y guardan en archivos locales**.

| Parcela | Cultivo | Superficie | Sensores de suelo | Riego |
| --- | --- | --- | --- | --- |
| P001 | Tomates | 2 ha | `SOIL-P001-01`, `SOIL-P001-02` | `IRR-P001-01` |
| P002 | Lechugas | 1,5 ha | `SOIL-P002-01`, `SOIL-P002-02` | `IRR-P002-01` |
| P003 | Maíz | 5 ha | `SOIL-P003-01`, `SOIL-P003-02` | `IRR-P003-01` |
| P004 | Fresas | 1 ha | `SOIL-P004-01`, `SOIL-P004-02` | `IRR-P004-01` |
| P005 | Pimientos | 2 ha | `SOIL-P005-01`, `SOIL-P005-02` | `IRR-P005-01` |

Además hay una **estación meteorológica compartida** (`WEATHER-001`). En total son **16 dispositivos** con un `device_id` fijo.

La idea clave del enunciado es que **no basta con generar números aleatorios independientes**: cada parcela debe tener un estado que evolucione con el tiempo (el suelo se seca, la lluvia lo moja, el riego lo humedece, etc.).

## 1.2. Estructura del proyecto

Cada archivo tiene una única responsabilidad, así se puede leer y probar por separado.

```
smart-agriculture-iot-simulator/
├── main.py          # Bucle principal: modos, reloj virtual, parada con Ctrl+C
├── config.py        # Parámetros, umbrales y definición de parcelas
├── energy.py        # Batería de los dispositivos (carga solar y descarga)
├── weather.py       # Estación meteorológica
├── sensors.py       # Estado del suelo de cada parcela y sensores
├── irrigation.py    # Controlador de riego
├── anomalies.py     # Detección e inyección de alertas
├── data_writer.py   # Escritura en JSON Lines
├── engine.py        # Lanzador con ventana (Tkinter)
├── data/            # Muestra de los 4 archivos .jsonl
├── docs/tutorial.md # Este tutorial
├── tests/           # Pruebas automatizadas
├── requirements.txt
├── .gitignore
└── README.md
```

## 1.3. Preparar el entorno

El proyecto **solo usa la biblioteca estándar de Python** (`random`, `json`, `uuid`, `datetime`, `math`, `unittest`...). La ventana de `engine.py` usa `tkinter`, que viene incluido con Python en Windows.

```bash
mkdir smart-agriculture-iot-simulator
cd smart-agriculture-iot-simulator
git init
python -m venv .venv
source .venv/Scripts/activate      # Git Bash en Windows
mkdir data docs tests
```

En `requirements.txt` solo se indica que no hay dependencias externas, y en `.gitignore` se excluyen `.venv/`, `__pycache__/`, logs y las carpetas de ejecuciones grandes.

## 1.4. Configuración (`config.py`)

Todo lo que se puede querer cambiar está en un único sitio: nada de números "a fuego" dentro de las funciones.

```python
# Parámetros generales de ejecución
NUM_PLOTS = 5
GENERATION_INTERVAL = 300     # Segundos que avanza el reloj virtual en cada paso (5 min)
SIMULATION_DURATION = 10      # Límite de eventos para el modo limitado
SIMULATION_MODE = "LIMITED"   # Opciones: "LIMITED" o "CONTINUOUS"
REALTIME_SLEEP = 0.0          # Pausa real en segundos entre iteraciones
RANDOM_SEED = 42
ENABLE_ANOMALIES = True
OUTPUT_DIR = "data"

# Umbrales y parámetros de riego y suelo
IRRIGATION_MIN_MOISTURE = 20.0     # Si baja de 20 %, se activa el riego
IRRIGATION_TARGET_MOISTURE = 35.0  # Si alcanza 35 %, se detiene el riego
IRRIGATION_FLOW_L_MIN = 35.5       # Caudal nominal (L/min)
SOIL_ABSORPTION_FACTOR = 0.02      # Subida de humedad por litro aplicado
```

Las parcelas se definen en un diccionario `PLOTS`, de donde salen el cultivo, los identificadores de los sensores y el del riego:

```python
PLOTS = {
    "P001": {"crop": "tomates", "area": 2.0,
             "soil_sensors": ["SOIL-P001-01", "SOIL-P001-02"], "irrigation": "IRR-P001-01"},
    ...
}
```

## 1.5. Batería (`energy.py`)

Los dispositivos tienen batería con placa solar: **cargan si hay sol suficiente y se descargan si no**. Es una clase pequeña que reutilizan la estación, los sensores y el riego.

```python
def update(self, solar_radiation_w_m2):
    if solar_radiation_w_m2 > self.solar_threshold:
        self.level += self.charge_rate
    else:
        self.level -= self.base_consumtion

    # limitación de los valores reales de una batería
    self.level = max(0.0, min(100.0, self.level))
    return round(self.level, 1)
```

Con el nivel se calcula el `device_status`: `OK`, `LOW_BATTERY` (menos del 15 %) u `OFFLINE` (0 %).

## 1.6. Estación meteorológica (`weather.py`)

Genera un evento `weather_reading` en cada paso, usando la **hora del reloj virtual** para que haya ciclo día/noche.

**Temperatura:** una curva senoidal con máximo a las 14:00 y mínimo a las 02:00, más un pequeño ruido.

```python
base_temp = 24.5 + 11.5 * math.sin((hour - 8) * math.pi / 12)
temp = base_temp + random.uniform(-1.2, 1.2)
```

**Pico de calor:** entre las 12:00 y las 16:00 hay una probabilidad (`PROB_HEATWAVE`) de sumar 3–5 °C, lo que permite superar el umbral de 38 °C y generar la alerta `HIGH_TEMPERATURE`.

**Radiación solar:** solo de día (06:00–18:00); de noche vale exactamente 0.

```python
if 6 <= hour <= 18:
    solar = 950.0 * math.sin((hour - 6) * math.pi / 12) + random.uniform(-20.0, 20.0)
else:
    solar = 0.0
```

**Lluvia, humedad y viento:**
- Llueve con un 2 % de probabilidad por paso (entre 1 y 15 mm).
- La humedad del aire es **inversa a la temperatura** y sube 15 puntos si llueve.
- El viento evoluciona poco a poco (suma o resta hasta 0,8 m/s por paso) en lugar de saltar.

**Comprobación:** salida real de un día completo (cada 3 horas):

```
hora   temp(°C)  radiación(W/m²)  humedad(%)
00:00    15.3         0.0            69.1
03:00    13.4         0.0            73.5
06:00    18.4         5.3            66.1
09:00    28.4       684.6            49.4
12:00    33.8       966.3            37.9
15:00    35.4       654.0            34.6
18:00    30.1         0.0            44.1
21:00    21.0         0.0            61.1
```

La temperatura sube de día y baja de noche, la radiación nocturna es 0 y la humedad del aire hace lo contrario que la temperatura.

## 1.7. Suelo y sensores (`sensors.py`)

La clase `PlotSoilState` guarda el **estado real del suelo de una parcela** (humedad, temperatura, pH y conductividad). Así cada lectura depende de la anterior.

Cada paso, el clima afecta al suelo:

```python
evaporation_rate = 0.08 + (temp_air / 180.0) + (wind / 300.0)
self.moisture -= evaporation_rate          # sin aportes, el suelo se seca

if rain > 0:
    self.moisture += rain * 0.45           # la lluvia lo humedece

self.moisture = max(10.0, min(45.0, self.moisture))   # rango de la práctica
```

- **Más calor y más viento → se seca más rápido.**
- **La temperatura del suelo tiene inercia:** se acerca poco a poco a la del aire (`0.85 · suelo + 0.15 · aire`).
- **El riego** suma humedad en proporción a los litros: `litros × SOIL_ABSORPTION_FACTOR`.

`generate_sensor_events()` crea una lectura por cada uno de los dos sensores de la parcela (a 15 y 20 cm de profundidad), añadiendo un pequeño ruido a lo que mide cada uno.

## 1.8. Controlador de riego (`irrigation.py`)

`IrrigationController` mantiene el estado de la válvula y el volumen acumulado. Funciona con **dos umbrales** (histéresis): se enciende por debajo del mínimo y no se apaga hasta llegar al objetivo.

```python
if self.status == "OFF" and current_moisture < self.moisture_threshold:      # < 20 %
    self.status = "ON";  self.valve = "OPEN";   reason = "LOW_SOIL_MOISTURE"

elif self.status == "ON" and current_moisture >= self.target_moisture:       # >= 35 %
    self.status = "OFF"; self.valve = "CLOSED"; reason = "TARGET_MOISTURE_REACHED"
```

Mientras riega, el caudal es el nominal (35,5 L/min) y en cada paso de 5 minutos se aplican `35,5 × 5 = 177,5 L`, que se suman al volumen acumulado y suben la humedad del suelo unos 3,55 puntos. Si está apagado, caudal y presión valen 0. De esta forma **estado, válvula, caudal y volumen son siempre coherentes**.

**Comprobación:** un ciclo real de riego de la parcela P003:

```
01:05  ON   OPEN    35.5 L/min  volumen 177.5 L   LOW_SOIL_MOISTURE
...
01:25  OFF  CLOSED   0.0 L/min  volumen 710.0 L   TARGET_MOISTURE_REACHED
```

## 1.9. Anomalías y alertas (`anomalies.py`)

La función `detect_and_generate_alerts(evento, timestamp)` revisa cada evento y devuelve una lista de alertas. Cubre las cinco anomalías obligatorias:

| Código | Gravedad | Cuándo se produce |
| --- | --- | --- |
| `LOW_SOIL_MOISTURE` | WARNING | La humedad medida baja de 20 % |
| `HIGH_TEMPERATURE` | WARNING | La temperatura del aire supera 38 °C |
| `SENSOR_FAILURE` | CRITICAL | Probabilidad de 0,5 %: el sensor pierde la lectura (humedad `None`, estado `ERROR`) |
| `IRRIGATION_FAILURE` | CRITICAL | Probabilidad de 2 % con el riego en ON: caudal y presión pasan a 0 |
| `WATER_LEAK` | CRITICAL | Probabilidad de 0,5 % con la válvula cerrada: aparece un caudal de 2–10 L/min |

Las dos primeras son **detecciones** (salen de los datos); las otras tres son **fallos inyectados** con `random.random() < probabilidad`. Todas las probabilidades y umbrales están en `config.py`.

Cada alerta incluye `event_id`, `timestamp`, `device_id`, `event_type`, `alert_code`, `severity`, `measured_value`, `threshold_value` y `message`, y el `plot_id` si procede.

## 1.10. Guardado en JSON Lines (`data_writer.py`)

```python
def save_event(filename, event_data):
    filepath = os.path.join(config.OUTPUT_DIR, filename)
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(json.dumps(event_data, ensure_ascii=False) + '\n')
```

- `'a'` (*append*): **nunca se sobrescribe** lo anterior.
- Un objeto JSON por línea, en UTF-8 (`ensure_ascii=False` guarda "maíz" tal cual).
- Cada tipo de evento va a su archivo: `sensor_readings.jsonl`, `weather_readings.jsonl`, `irrigation_events.jsonl` y `alerts.jsonl`.

## 1.11. Programa principal (`main.py`)

`main.py` une todas las piezas. En cada paso del **reloj virtual**:

1. Se genera el evento meteorológico (y sus alertas).
2. Para cada parcela:
   1. El clima actualiza el suelo (evaporación, lluvia, temperatura).
   2. Los dos sensores leen el estado actual.
   3. El controlador de riego decide con la humedad actual.
   4. Si regó, el agua aumenta la humedad del suelo.
3. El reloj avanza `GENERATION_INTERVAL` segundos (300 = 5 minutos).

Puntos importantes:

- **Semilla:** `random.seed(config.RANDOM_SEED)` al empezar, así que con la misma semilla salen los mismos valores. Los `event_id` usan `uuid.uuid4()`, que **no depende de esa semilla**, por lo que siguen siendo únicos entre ejecuciones.
- **Reloj virtual:** empieza a las 00:00 UTC del día de la ejecución y avanza 5 minutos por paso. No hace falta esperar: se pueden generar días enteros en segundos, y con `REALTIME_SLEEP` se puede ralentizar.
- **Modo limitado:** el bucle se detiene cuando `event_count >= SIMULATION_DURATION`. Como el límite se comprueba al empezar cada parcela, puede pasarse unos pocos eventos.
- **Modo continuo:** el bucle no tiene fin. Se detiene con `Ctrl+C`, que se captura con `except KeyboardInterrupt` para cerrar la simulación de forma controlada.
- **Coherencia ante un fallo de riego:** si una anomalía deja el caudal a 0 con el riego en ON, se **resta ese volumen** del acumulado y no se añade agua al suelo, porque en realidad no salió agua.

```python
if irrigation_event["irrigation_status"] == "ON" and irrigation_event["water_flow_l_min"] == 0.0:
    plots_irrigation[plot_id].water_volume_l = max(
        0.0, plots_irrigation[plot_id].water_volume_l - liters_applied
    )
    irrigation_event["water_volume_l"] = round(plots_irrigation[plot_id].water_volume_l, 1)
    liters_applied = 0.0
```

## 1.12. Lanzador con ventana (`engine.py`)

Para no tener que editar `config.py` cada vez, `engine.py` abre una ventana (Tkinter) con todos los parámetros, sus rangos válidos y una ayuda al pasar el ratón.

- Valida los valores (rangos y que el umbral mínimo de riego sea menor que el objetivo).
- Lanza `main.py` en **otro proceso** sobrescribiendo los valores **solo en memoria**:

```python
runner_code = (
    f"import json, runpy, config; "
    f"overrides = json.loads({repr(overrides_json)}); "
    f"[setattr(config, k, v) for k, v in overrides.items()]; "
    f"runpy.run_path({repr(str(main_script))}, run_name='__main__')"
)
subprocess.Popen([sys.executable, "-c", runner_code])
```

Así **`config.py` nunca se modifica en disco**. Hay un botón para restaurar los valores oficiales y otro para ejecutar directamente con ellos.

## 1.13. Ejecución y resultados

Hay dos formas de lanzar el simulador:

```bash
# 1) Editar config.py (SIMULATION_MODE, SIMULATION_DURATION...) y ejecutar
python main.py

# 2) Usar la ventana
python engine.py
```

**Modo limitado, 1.000 eventos** (`SIMULATION_MODE = "LIMITED"`, `SIMULATION_DURATION = 1000`):

```
--- Iniciando simulador IoT AgroSmart ---
Modo: LIMITED | Intervalo: 300s | Semilla: 42
Límite configurado: 1000 eventos
--- Simulación completada ---
Total eventos generados: 1000
Fecha virtual final: 2026-10-16T05:15:00Z
Archivos guardados en el directorio: data/
```

**Modo continuo** (`SIMULATION_MODE = "CONTINUOUS"`): se detiene con `Ctrl+C` y muestra `[!] Interrupción detectada por el usuario (Ctrl+C). Cerrando archivos de forma segura...`.

Líneas guardadas en cada archivo en la ejecución de 1.000 eventos:

```
  620 data/sensor_readings.jsonl
   63 data/weather_readings.jsonl
  310 data/irrigation_events.jsonl
    7 data/alerts.jsonl
 1000 total
```

Una línea real de cada archivo:

```json
{"event_id": "20725658-1e6c-4888-a312-f5fc94348b85", "timestamp": "2026-10-16T00:00:00Z", "device_id": "SOIL-P001-01", "event_type": "sensor_reading", "farm_id": "FARM001", "plot_id": "P001", "crop": "tomates", "sensor_depth_cm": 15, "measurements": {"soil_moisture_pct": 28.1, "soil_temperature_c": 17.6, "soil_ph": 6.1, "soil_ec_ds_m": 1.0}, "battery_pct": 75.5, "device_status": "OK"}
```
```json
{"event_id": "b8c8fb5c-f516-4fb7-815e-79a3ce6df1b3", "timestamp": "2026-10-16T00:00:00Z", "device_id": "WEATHER-001", "event_type": "weather_reading", "farm_id": "FARM001", "measurements": {"air_temperature_c": 15.3, "air_humidity_pct": 69.1, "solar_radiation_w_m2": 0.0, "rainfall_mm": 0.0, "wind_speed_ms": 3.8}, "battery_pct": 97.9, "device_status": "OK"}
```
```json
{"event_id": "1c8c4014-b8a4-414f-b725-418dbd4ba987", "timestamp": "2026-10-16T01:05:00Z", "device_id": "IRR-P003-01", "event_type": "irrigation_event", "farm_id": "FARM001", "plot_id": "P003", "irrigation_status": "ON", "valve_status": "OPEN", "water_flow_l_min": 35.5, "water_pressure_bar": 2.3, "water_volume_l": 177.5, "reason": "LOW_SOIL_MOISTURE", "battery_pct": 92.3, "device_status": "OK"}
```
```json
{"event_id": "3f0ca19f-8af0-4ee7-8aa8-539fc208c6c3", "timestamp": "2026-10-16T00:05:00Z", "device_id": "SOIL-P003-02", "event_type": "alert", "farm_id": "FARM001", "alert_code": "SENSOR_FAILURE", "severity": "CRITICAL", "measured_value": 0.0, "threshold_value": 0.0, "message": "Ausencia de lectura o pérdida de comunicación con el sensor", "plot_id": "P003"}
```

> Los archivos se amplían en cada ejecución. Para una muestra limpia hay que borrar antes los `.jsonl` de la carpeta de salida.

---

# Parte 2. Pruebas unitarias

## 2.1. Objetivo y herramienta

Las pruebas comprueban de forma automática que el simulador cumple la tabla de la **sección 11** del enunciado y las reglas de simulación de la **sección 5**. Se usa **`unittest`**, que viene con Python, así que no hay que instalar nada.

Todas las pruebas están en un único archivo: `tests/test_simulador.py`.

## 2.2. Cómo está organizado el archivo

| Clase | Pruebas | Qué comprueba |
| --- | --- | --- |
| `TestValidacionDeDatos` | 9 | Ejecuta el simulador una vez (6.000 eventos) y revisa los archivos generados |
| `TestReglasDeSimulacion` | 6 | Suelo, lluvia, riego, umbrales, volumen y batería |
| `TestModosYAlmacenamiento` | 5 | Modo limitado, modo continuo, semilla, anomalías desactivadas y escritura |

## 2.3. Técnicas utilizadas

**Ejecutar `main.py` sin tocar `config.py`.** Un ayudante cambia los parámetros solo durante la prueba (`mock.patch.multiple`), guarda los datos en una carpeta temporal y captura lo que se imprime:

```python
def ejecutar_main(carpeta, **ajustes):
    # weather.py guarda viento y batería en variables globales: se reinician
    weather._current_wind = 3.0
    weather.weather_battery = BatteryController(initial_level=98.0)

    texto = io.StringIO()
    with mock.patch.multiple(config, OUTPUT_DIR=str(carpeta), **ajustes), \
         contextlib.redirect_stdout(texto):
        main.main()
    return texto.getvalue()
```

**Carpetas temporales.** Las pruebas nunca escriben en la carpeta `data/` real: usan `tempfile.TemporaryDirectory()` y se borra sola al terminar.

**Clima fijo.** Para probar el suelo sin aleatoriedad se le pasa un clima inventado con valores concretos:

```python
def clima(temp=25.0, lluvia=0.0):
    return {"air_temperature_c": temp, "wind_speed_ms": 3.0, "rainfall_mm": lluvia}
```

**Simular `Ctrl+C`.** Se sustituye `time.sleep` por una función que lanza `KeyboardInterrupt` en la tercera llamada, igual que haría el teclado:

```python
def pausa_falsa(_segundos):
    pausas.append(1)
    if len(pausas) == 3:
        raise KeyboardInterrupt

with mock.patch("main.time.sleep", side_effect=pausa_falsa):
    texto = ejecutar_main(self.carpeta.name, SIMULATION_MODE="CONTINUOUS",
                          SIMULATION_DURATION=10, REALTIME_SLEEP=0.001)
```

## 2.4. Ejemplos de pruebas

**Regla 2 — el suelo sin aportes se seca:**

```python
def test_suelo_sin_aportes_se_seca(self):
    anterior = self.suelo.moisture
    for _ in range(20):
        self.suelo.update_from_weather(clima())
        self.assertLess(self.suelo.moisture, anterior)
        anterior = self.suelo.moisture
```

**Regla 6 — el riego es coherente.** Solo las anomalías simuladas (fuga y fallo de riego) pueden romper la relación entre estado, válvula y caudal:

```python
if clave in fugas:                    # anomalía: pasa agua con la válvula cerrada
    self.assertGreater(caudal, 0)
elif clave in fallos:                 # anomalía: riego ON pero sin caudal
    self.assertEqual(caudal, 0.0)
else:                                 # normal: hay caudal solo si está regando
    self.assertEqual(encendido, caudal > 0)
```

**Alertas correctas.** No basta con que existan: el valor medido debe estar del lado "malo" del umbral.

```python
por_debajo = {"LOW_SOIL_MOISTURE", "IRRIGATION_FAILURE"}
por_encima = {"HIGH_TEMPERATURE", "WATER_LEAK"}
...
if alerta["alert_code"] in por_debajo:
    self.assertLess(medido, umbral)
elif alerta["alert_code"] in por_encima:
    self.assertGreater(medido, umbral)
```

## 2.5. Correspondencia con la tabla de validación del enunciado

| Prueba del enunciado | Prueba automática |
| --- | --- |
| Validación JSONL | `test_jsonl_valido` |
| Campos obligatorios | `test_campos_obligatorios` |
| Unicidad | `test_event_id_sin_duplicados` |
| Tiempos | `test_timestamps_utc_iso_8601` |
| Dispositivos | `test_dispositivos_simulados` |
| Comportamiento temporal | `test_ciclo_diario` |
| Riego y lluvia | `test_suelo_sin_aportes_se_seca`, `test_lluvia_sube_la_humedad`, `test_riego_sube_la_humedad_poco_a_poco`, `test_riego_se_activa_y_se_detiene_por_umbrales`, `test_volumen_acumulado_de_riego`, `test_riego_coherente` |
| Anomalías | `test_alertas_identificables`, `test_anomalias_desactivadas_no_generan_alertas` |
| Modo limitado | `test_modo_limitado_termina_solo` |
| Modo continuo | `test_modo_continuo_se_detiene_con_ctrl_c_sin_corromper_archivos` |
| Volumen mínimo (≥ 1.000 eventos) | `test_volumen_minimo_1000_eventos` |
| Semilla reproducible con `event_id` únicos | `test_misma_semilla_mismos_valores_pero_event_id_distintos` |
| Escritura que amplía sin sobrescribir | `test_escritura_jsonl_amplia_sin_sobrescribir_y_en_utf8` |
| Batería | `test_bateria_carga_con_sol_descarga_sin_el_y_respeta_limites` |

## 2.6. Ejecutar las pruebas

Desde la carpeta raíz del proyecto:

```bash
python -m unittest discover -s tests -v
```

Resultado real:

```
test_anomalias_desactivadas_no_generan_alertas ... ok
test_escritura_jsonl_amplia_sin_sobrescribir_y_en_utf8 ... ok
test_misma_semilla_mismos_valores_pero_event_id_distintos ... ok
test_modo_continuo_se_detiene_con_ctrl_c_sin_corromper_archivos ... ok
test_modo_limitado_termina_solo ... ok
test_bateria_carga_con_sol_descarga_sin_el_y_respeta_limites ... ok
test_lluvia_sube_la_humedad ... ok
test_riego_se_activa_y_se_detiene_por_umbrales ... ok
test_riego_sube_la_humedad_poco_a_poco ... ok
test_suelo_sin_aportes_se_seca ... ok
test_volumen_acumulado_de_riego ... ok
test_alertas_identificables ... ok
test_campos_obligatorios ... ok
test_ciclo_diario ... ok
test_dispositivos_simulados ... ok
test_event_id_sin_duplicados ... ok
test_jsonl_valido ... ok
test_riego_coherente ... ok
test_timestamps_utc_iso_8601 ... ok
test_volumen_minimo_1000_eventos ... ok

----------------------------------------------------------------------
Ran 20 tests in 3.465s

OK
```

## 2.7. Comprobar que las pruebas detectan errores

Una prueba que siempre pasa no sirve. Para comprobar que estas **sí fallan cuando el código está mal**, se puede estropear una línea a propósito, ejecutar las pruebas y volver a dejarla como estaba. Por ejemplo, en `data_writer.py`:

```python
with open(filepath, 'a', encoding='utf-8') as f:   # correcto
with open(filepath, 'w', encoding='utf-8') as f:   # estropeado: sobrescribe
```

Con el cambio, las pruebas de escritura, de unicidad y de volumen mínimo fallan, porque cada línea nueva borra las anteriores. Otros cambios que hacen fallar alguna prueba:

| Cambio de prueba | Prueba que falla |
| --- | --- |
| Radiación nocturna distinta de 0 en `weather.py` | `test_ciclo_diario` |
| Quitar `self.water_volume_l += liters_applied` en `irrigation.py` | `test_volumen_acumulado_de_riego` |
| Cambiar `-=` por `+=` en la evaporación de `sensors.py` | `test_suelo_sin_aportes_se_seca` |
| Invertir `<` por `>` en la alerta de humedad de `anomalies.py` | `test_alertas_identificables` |
| Poner un `event_id` fijo en las alertas | `test_event_id_sin_duplicados` |

## 2.8. Limitaciones y detalles a tener en cuenta

- Las pruebas de datos dependen de la semilla 42 (la de `config.py`): con otra semilla pueden cambiar los valores concretos, pero las reglas que se comprueban deben seguir cumpliéndose.
- El modo limitado puede generar unos pocos eventos más que el límite (la prueba admite un margen de 10), porque el límite se comprueba al empezar cada parcela.
- `weather.py` guarda el viento y la batería en variables globales del módulo. Por eso las pruebas las reinician antes de cada ejecución; en una ejecución normal (`python main.py`, un proceso nuevo) no hay ningún problema.
- El lanzador con ventana (`engine.py`) no tiene pruebas automáticas, porque depende de una interfaz gráfica.

---

# Parte 3. Conexión con servidor
## Parte 3. Conexión con servidor

### 3.1. Qué se quiere conseguir y problema de red

El simulador se ejecuta en un equipo con **Windows Server** (`10.105.0.3`), donde se generan los cuatro archivos de salida en la carpeta `data/` (`sensor_readings.jsonl`, `weather_readings.jsonl`, `irrigation_events.jsonl` y `alerts.jsonl`). El objetivo es que el resto de ordenadores (hasta 20 equipos) puedan acceder a estos archivos y descargarlos a medida que se actualizan, sin necesidad de instalar programas adicionales en cada ordenador cliente.

La idea inicial fue activar el servidor OpenSSH en el Windows Server y conectarse desde los demás equipos mediante **FileZilla (SFTP)** por el puerto `22`:

```text
Estado: Conectando a 10.105.0.3:22...
Error:  La conexión superó el tiempo de espera después de 20 segundos de inactividad
Error:  No se pudo conectar al servidor
```

Al estar en una red escolar con subredes aisladas y cortafuegos interno, cualquier intento de conexión entrante directa hacia la IP privada `10.105.0.3` (tanto por el puerto `22` de SSH como por el puerto `8080` en navegador) devuelve `ERR_CONNECTION_TIMED_OUT`. Además, en una red de centro educativo no es posible abrir puertos en el router (Port Forwarding).

### 3.2. Alternativas probadas y descartadas

| Opción | Motivo de descarte |
| :--- | :--- |
| **SSH / SFTP con FileZilla (puerto 22)** | Bloqueado por el aislamiento entre redes/subredes del centro (`ERR_CONNECTION_TIMED_OUT`). |
| **VPN en malla (Tailscale)** | Obliga a instalar el programa e iniciar sesión en los 20 ordenadores cliente. |
| **GitHub Gist** | Si los archivos `.jsonl` cambian o crecen, obliga a resubirlos manualmente cada vez y no soporta archivos grandes (de decenas de GB). |
| **Ngrok / Zrok** | Tienen límites de transferencia en sus planes gratuitos (p. ej., 10 GB/día en Zrok), insuficientes cuando se manejan archivos de ~30 GB. |

### 3.3. Solución adoptada: servidor HTTP de Python + Cloudflare Tunnel

Para sortear el bloqueo de la red sin tocar el router y sin instalar nada en los ordenadores cliente, se combinan dos herramientas en el Windows Server:

1. **`http.server` (incluido en Python)**: expone la carpeta `data/` en el propio servidor a través de `http://localhost:8080`.
2. **Cloudflare Tunnel (`cloudflared.exe`)**: abre una conexión saliente desde el Windows Server hacia Cloudflare por el puerto `443` (tráfico HTTPS estándar, que el cortafuegos del centro sí permite) y genera una dirección pública temporal (`https://*.trycloudflare.com`) sin límite de tráfico.

De esta forma, cuando el simulador añade nuevas líneas a los `.jsonl`, cualquier compañero que entre al enlace o recargue la página obtiene directamente el archivo actualizado en disco.

### 3.4. Puesta en marcha paso a paso en el Windows Server

**Paso 1 — Iniciar el servidor web local en la carpeta de datos**

En una primera consola, se entra en la carpeta donde están los `.jsonl` del proyecto y se levanta el servidor HTTP de Python en el puerto `8080`:

```powershell
cd data
python -m http.server 8080
```

La consola queda a la escucha en `http://localhost:8080`.

**Paso 2 — Descargar y lanzar el túnel de Cloudflare**

Se descarga el ejecutable oficial [`cloudflared-windows-amd64.exe`](https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe) y se renombra a `cloudflared.exe`.

En una segunda ventana de PowerShell (situada en la carpeta donde está `cloudflared.exe`), se lanza el túnel apuntando al puerto `8080` local:

```powershell
.\cloudflared.exe tunnel --url http://localhost:8080
```

Comprobación con la salida real en el Windows Server (`10.105.0.3`):

```text
PS C:\Users\Administrator\Downloads> .\cloudflared.exe tunnel --url http://localhost:8080
2026-10-15T10:41:50Z INF Requesting new quick Tunnel on trycloudflare.com...
2026-10-15T10:41:56Z INF +--------------------------------------------------------------------------------------------+
2026-10-15T10:41:56Z INF |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
2026-10-15T10:41:56Z INF |  [https://observe-princess-disposal-baskets.trycloudflare.com](https://observe-princess-disposal-baskets.trycloudflare.com)                               |
2026-10-15T10:41:56Z INF +--------------------------------------------------------------------------------------------+
2026-10-15T10:41:56Z INF ICMP proxy will use 10.105.0.3 as source for IPv4
2026-10-15T10:41:56Z INF +-------------------------------------------------------------------------------------+
2026-10-15T10:41:56Z INF |                                CONNECTIVITY PRE-CHECKS                              |
2026-10-15T10:41:56Z INF +-------------------------------------------------------------------------------------+
2026-10-15T10:41:56Z INF |  COMPONENT         TARGET                     STATUS  DETAILS                       |
2026-10-15T10:41:56Z INF |  DNS Resolution    region1.v2.argotunnel.com  PASS    DNS Resolved successfully     |
2026-10-15T10:41:56Z INF |  UDP Connectivity  region1.v2.argotunnel.com  PASS    QUIC connection successful    |
2026-10-15T10:41:56Z INF |  TCP Connectivity  region1.v2.argotunnel.com  PASS    HTTP/2 connection successful  |
2026-10-15T10:41:56Z INF |  Cloudflare API    api.cloudflare.com:443     PASS    API is reachable              |
2026-10-15T10:41:56Z INF |  SUMMARY: Environment is healthy. cloudflared will use 'quic' as primary protocol.  |
2026-10-15T10:41:56Z INF +-------------------------------------------------------------------------------------+
2026-10-15T10:41:56Z INF Registered tunnel connection connIndex=0 connection=50c1992c-535e-4b12-ba7e-6a06cd144685 event=0 ip=198.41.192.167 location=mad06 protocol=quic
```

### 3.5. Acceso desde el resto de ordenadores

Con ambas consolas abiertas en el servidor, el resto de equipos solo necesitan abrir el navegador y entrar en el enlace generado por Cloudflare (en la prueba, `https://observe-princess-disposal-baskets.trycloudflare.com`):

* Se muestra directamente el listado con los 4 archivos (`sensor_readings.jsonl`, `weather_readings.jsonl`, `irrigation_events.jsonl` y `alerts.jsonl`).
* Para guardarlos en el equipo local basta con hacer **clic derecho → Guardar enlace como...** sobre cada archivo (o pulsar `F5` si se han generado nuevos datos en el servidor).
* También se pueden descargar por consola con `curl -O <URL>/sensor_readings.jsonl`.

### 3.6. Limitaciones y detalles a tener en cuenta

* **Mantener las dos consolas abiertas**: tanto la consola de `python -m http.server 8080` como la de `cloudflared.exe` deben permanecer en ejecución mientras se estén compartiendo los archivos. Si se cierra cualquiera de las dos, el enlace deja de funcionar.
* **URL aleatoria en cada inicio**: el modo rápido sin cuenta (`trycloudflare.com`) asigna un subdominio aleatorio cada vez que se ejecuta el comando. Si no se detiene el proceso, la dirección se mantiene fija durante toda la sesión aunque los archivos `.jsonl` cambien por dentro.
* **Uso de `.\` en PowerShell**: Windows PowerShell no ejecuta por defecto binarios de la carpeta actual si no se indica la ruta relativa (`.\cloudflared.exe`).
