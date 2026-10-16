"""
Pruebas automatizadas del simulador IoT (unittest, solo biblioteca estándar).

Cada prueba corresponde a una fila de la tabla de la sección 11 de la práctica
o a una de las reglas de simulación de la sección 5.

Ejecutar desde la carpeta raíz del proyecto:
    python -m unittest discover -s tests -v
"""

import contextlib
import io
import json
import random
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

# Para poder hacer `import config`, `import main`... desde la carpeta tests/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config            # noqa: E402
import main              # noqa: E402
import weather           # noqa: E402
from data_writer import save_event            # noqa: E402
from energy import BatteryController          # noqa: E402
from irrigation import IrrigationController   # noqa: E402
from sensors import PlotSoilState             # noqa: E402

# Archivo donde main.py guarda cada tipo de evento
ARCHIVOS = {
    "sensor_reading": "sensor_readings.jsonl",
    "weather_reading": "weather_readings.jsonl",
    "irrigation_event": "irrigation_events.jsonl",
    "alert": "alerts.jsonl",
}


# ---------------------------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------------------------
def ejecutar_main(carpeta, **ajustes):
    """Ejecuta main.main() guardando en `carpeta`.

    `ajustes` cambia valores de config.py SOLO durante la ejecución
    (tu config.py no se modifica). Devuelve lo que main imprimió.
    """
    # weather.py guarda viento y batería en variables globales: se reinician
    # para que cada ejecución empiece igual.
    weather._current_wind = 3.0
    weather.weather_battery = BatteryController(initial_level=98.0)

    texto = io.StringIO()
    with mock.patch.multiple(config, OUTPUT_DIR=str(carpeta), **ajustes), \
         contextlib.redirect_stdout(texto):
        main.main()
    return texto.getvalue()


def leer_todo(carpeta):
    """Lee los 4 archivos .jsonl y devuelve {tipo_de_evento: [eventos]}."""
    datos = {}
    for tipo, nombre in ARCHIVOS.items():
        ruta = Path(carpeta) / nombre
        lineas = ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []
        datos[tipo] = [json.loads(linea) for linea in lineas]
    return datos


def total_eventos(carpeta):
    return sum(len(lista) for lista in leer_todo(carpeta).values())


def clima(temp=25.0, lluvia=0.0):
    """Medidas de clima fijas (sin azar) para probar el suelo."""
    return {"air_temperature_c": temp, "wind_speed_ms": 3.0, "rainfall_mm": lluvia}


def hora(h):
    return datetime(2026, 10, 13, h, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Sección 11: validación de los datos generados
# ---------------------------------------------------------------------------
class TestValidacionDeDatos(unittest.TestCase):
    """Se ejecuta el simulador una vez (6.000 eventos) y se revisan los archivos."""

    @classmethod
    def setUpClass(cls):
        cls.carpeta = tempfile.TemporaryDirectory()
        ejecutar_main(cls.carpeta.name, SIMULATION_MODE="LIMITED",
                      SIMULATION_DURATION=6000, ENABLE_ANOMALIES=True)
        cls.datos = leer_todo(cls.carpeta.name)
        cls.eventos = [e for lista in cls.datos.values() for e in lista]

    @classmethod
    def tearDownClass(cls):
        cls.carpeta.cleanup()

    def test_jsonl_valido(self):
        """Todas las líneas de los 4 archivos son un objeto JSON válido."""
        for nombre in ARCHIVOS.values():
            lineas = (Path(self.carpeta.name) / nombre).read_text(encoding="utf-8").splitlines()
            self.assertGreater(len(lineas), 0, f"{nombre} está vacío")
            for numero, linea in enumerate(lineas, start=1):
                try:
                    self.assertIsInstance(json.loads(linea), dict)
                except json.JSONDecodeError:
                    self.fail(f"{nombre}, línea {numero}: no es JSON válido")

    def test_campos_obligatorios(self):
        """Todos los eventos tienen event_id, timestamp y device_id (y los comunes)."""
        for evento in self.eventos:
            for campo in ("event_id", "timestamp", "device_id", "event_type", "farm_id"):
                self.assertTrue(evento.get(campo), f"falta '{campo}' en {evento}")

    def test_event_id_sin_duplicados(self):
        ids = [e["event_id"] for e in self.eventos]
        self.assertEqual(len(ids), len(set(ids)))

    def test_timestamps_utc_iso_8601(self):
        """Formato 2026-10-13T10:00:00Z (la Z indica UTC)."""
        for evento in self.eventos:
            self.assertRegex(evento["timestamp"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
            datetime.strptime(evento["timestamp"], "%Y-%m-%dT%H:%M:%SZ")   # es una fecha real

    def test_dispositivos_simulados(self):
        """Los device_id son exactamente los 16 dispositivos definidos en config.PLOTS."""
        esperados = {config.WEATHER_DEVICE_ID}
        for parcela in config.PLOTS.values():
            esperados.update(parcela["soil_sensors"])
            esperados.add(parcela["irrigation"])
        usados = {e["device_id"] for e in self.eventos}
        self.assertEqual(usados, esperados)

    def test_ciclo_diario(self):
        """Más calor por la tarde que de madrugada, y radiación 0 de noche."""
        lecturas = self.datos["weather_reading"]

        def media_temperatura(horas):
            valores = [e["measurements"]["air_temperature_c"] for e in lecturas
                       if int(e["timestamp"][11:13]) in horas]
            return sum(valores) / len(valores)

        self.assertGreater(media_temperatura({13, 14, 15}), media_temperatura({1, 2, 3}) + 10)

        radiacion_noche = {e["measurements"]["solar_radiation_w_m2"] for e in lecturas
                           if int(e["timestamp"][11:13]) >= 19 or int(e["timestamp"][11:13]) < 6}
        self.assertEqual(radiacion_noche, {0.0})

    def test_riego_coherente(self):
        """ON <=> válvula OPEN, hay caudal solo si está regando y el volumen nunca baja.

        Solo las anomalías simuladas (fuga y fallo de riego) pueden romper esta regla.
        """
        def momentos(codigo):
            return {(a["device_id"], a["timestamp"]) for a in self.datos["alert"]
                    if a["alert_code"] == codigo}

        fugas, fallos = momentos("WATER_LEAK"), momentos("IRRIGATION_FAILURE")
        ultimo_volumen = {}
        for evento in self.datos["irrigation_event"]:
            encendido = evento["irrigation_status"] == "ON"
            caudal = evento["water_flow_l_min"]
            clave = (evento["device_id"], evento["timestamp"])
            self.assertEqual(encendido, evento["valve_status"] == "OPEN")
            if clave in fugas:                    # anomalía: pasa agua con la válvula cerrada
                self.assertGreater(caudal, 0)
            elif clave in fallos:                 # anomalía: riego ON pero sin caudal
                self.assertEqual(caudal, 0.0)
            else:                                 # normal: hay caudal solo si está regando
                self.assertEqual(encendido, caudal > 0)

            dispositivo = evento["device_id"]
            self.assertGreaterEqual(evento["water_volume_l"], ultimo_volumen.get(dispositivo, 0.0))
            ultimo_volumen[dispositivo] = evento["water_volume_l"]

    def test_alertas_identificables(self):
        """Aparecen las 5 anomalías obligatorias, cada una con sus campos."""
        alertas = self.datos["alert"]
        codigos = {a["alert_code"] for a in alertas}
        self.assertEqual(codigos, {"LOW_SOIL_MOISTURE", "HIGH_TEMPERATURE", "IRRIGATION_FAILURE",
                                   "WATER_LEAK", "SENSOR_FAILURE"})
        # La alerta salta cuando el valor medido está al lado "malo" del umbral
        por_debajo = {"LOW_SOIL_MOISTURE", "IRRIGATION_FAILURE"}
        por_encima = {"HIGH_TEMPERATURE", "WATER_LEAK"}
        for alerta in alertas:
            self.assertIn(alerta["severity"], ("WARNING", "CRITICAL"))
            self.assertTrue(alerta["message"].strip())
            medido, umbral = alerta["measured_value"], alerta["threshold_value"]
            if alerta["alert_code"] in por_debajo:
                self.assertLess(medido, umbral)
            elif alerta["alert_code"] in por_encima:
                self.assertGreater(medido, umbral)

    def test_volumen_minimo_1000_eventos(self):
        self.assertGreaterEqual(len(self.eventos), 1000)


# ---------------------------------------------------------------------------
# Sección 5: reglas de simulación (suelo, riego, lluvia, batería)
# ---------------------------------------------------------------------------
class TestReglasDeSimulacion(unittest.TestCase):

    def setUp(self):
        random.seed(42)
        self.suelo = PlotSoilState("P001")
        self.suelo.moisture = 30.0

    def test_suelo_sin_aportes_se_seca(self):
        """Regla 2: sin lluvia ni riego la humedad baja en cada paso."""
        anterior = self.suelo.moisture
        for _ in range(20):
            self.suelo.update_from_weather(clima())
            self.assertLess(self.suelo.moisture, anterior)
            anterior = self.suelo.moisture

    def test_lluvia_sube_la_humedad(self):
        """Regla 5: con lluvia la humedad queda más alta que sin lluvia."""
        otro = PlotSoilState("P001")
        otro.moisture = 30.0
        self.suelo.update_from_weather(clima(lluvia=5.0))
        otro.update_from_weather(clima(lluvia=0.0))
        self.assertGreater(self.suelo.moisture, otro.moisture)

    def test_riego_sube_la_humedad_poco_a_poco(self):
        """Regla 4: cada paso de riego suma un poco de humedad (no salta de golpe)."""
        litros = config.IRRIGATION_FLOW_L_MIN * config.GENERATION_INTERVAL / 60
        valores = [self.suelo.moisture]
        for _ in range(4):
            self.suelo.add_water_from_irrigation(litros)
            valores.append(self.suelo.moisture)
        subidas = [b - a for a, b in zip(valores, valores[1:])]
        self.assertTrue(all(0 < s < 5 for s in subidas))

    def test_riego_se_activa_y_se_detiene_por_umbrales(self):
        """Regla 3: ON bajo el mínimo, sigue ON entre umbrales y OFF al llegar al objetivo."""
        riego = IrrigationController("P001")

        evento, _ = riego.evaluate_and_irrigate(config.IRRIGATION_MIN_MOISTURE - 1, hora(10), 0)
        self.assertEqual((evento["irrigation_status"], evento["valve_status"]), ("ON", "OPEN"))
        self.assertEqual(evento["reason"], "LOW_SOIL_MOISTURE")

        evento, _ = riego.evaluate_and_irrigate(27.0, hora(10), 0)          # entre los dos umbrales
        self.assertEqual(evento["irrigation_status"], "ON")

        evento, litros = riego.evaluate_and_irrigate(config.IRRIGATION_TARGET_MOISTURE, hora(10), 0)
        self.assertEqual((evento["irrigation_status"], evento["valve_status"]), ("OFF", "CLOSED"))
        self.assertEqual(evento["reason"], "TARGET_MOISTURE_REACHED")
        self.assertEqual((evento["water_flow_l_min"], litros), (0.0, 0.0))

    def test_volumen_acumulado_de_riego(self):
        """El volumen suma caudal x tiempo en cada paso y se mantiene al cerrar la válvula."""
        riego = IrrigationController("P001")
        litros_por_paso = config.IRRIGATION_FLOW_L_MIN * config.GENERATION_INTERVAL / 60
        for paso in range(1, 4):
            evento, _ = riego.evaluate_and_irrigate(10.0, hora(10), 0)
            self.assertEqual(evento["water_volume_l"], round(paso * litros_por_paso, 1))
        cerrado, _ = riego.evaluate_and_irrigate(40.0, hora(10), 0)
        self.assertEqual(cerrado["water_volume_l"], evento["water_volume_l"])

    def test_bateria_carga_con_sol_descarga_sin_el_y_respeta_limites(self):
        bateria = BatteryController(initial_level=50.0)
        self.assertLess(bateria.update(0.0), 50.0)           # sin sol baja
        antes = bateria.level
        self.assertGreater(bateria.update(900.0), antes)     # con sol sube
        for _ in range(1000):
            nivel = bateria.update(900.0)
        self.assertEqual(nivel, 100.0)                       # tope en 100
        for _ in range(5000):
            nivel = bateria.update(0.0)
        self.assertEqual(nivel, 0.0)                         # suelo en 0


# ---------------------------------------------------------------------------
# Sección 7 y 8: modos de ejecución y almacenamiento
# ---------------------------------------------------------------------------
class TestModosYAlmacenamiento(unittest.TestCase):

    def setUp(self):
        self.carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(self.carpeta.cleanup)

    def test_modo_limitado_termina_solo(self):
        """Se detiene al llegar al límite de eventos (puede pasarse unos pocos: lo mira por parcela)."""
        ejecutar_main(self.carpeta.name, SIMULATION_MODE="LIMITED", SIMULATION_DURATION=500)
        total = total_eventos(self.carpeta.name)
        self.assertGreaterEqual(total, 500)
        self.assertLess(total, 510)

    def test_modo_continuo_se_detiene_con_ctrl_c_sin_corromper_archivos(self):
        """Simula Ctrl+C: el 3.º 'sleep' lanza KeyboardInterrupt, como haría el teclado."""
        pausas = []

        def pausa_falsa(_segundos):
            pausas.append(1)
            if len(pausas) == 3:
                raise KeyboardInterrupt

        with mock.patch("main.time.sleep", side_effect=pausa_falsa):
            texto = ejecutar_main(self.carpeta.name, SIMULATION_MODE="CONTINUOUS",
                                  SIMULATION_DURATION=10, REALTIME_SLEEP=0.001)

        self.assertIn("Interrupción detectada", texto)          # main lo captura y termina bien
        self.assertGreater(total_eventos(self.carpeta.name), 10)  # el límite de 10 no se aplica
        leer_todo(self.carpeta.name)                              # todas las líneas siguen siendo JSON válido

    def test_misma_semilla_mismos_valores_pero_event_id_distintos(self):
        a, b = Path(self.carpeta.name) / "a", Path(self.carpeta.name) / "b"
        a.mkdir()
        b.mkdir()
        ejecutar_main(a, SIMULATION_DURATION=600, RANDOM_SEED=7)
        ejecutar_main(b, SIMULATION_DURATION=600, RANDOM_SEED=7)
        datos_a, datos_b = leer_todo(a), leer_todo(b)

        for tipo in ("sensor_reading", "weather_reading"):
            self.assertEqual([e["measurements"] for e in datos_a[tipo]],
                             [e["measurements"] for e in datos_b[tipo]])

        ids_a = {e["event_id"] for lista in datos_a.values() for e in lista}
        ids_b = {e["event_id"] for lista in datos_b.values() for e in lista}
        self.assertTrue(ids_a.isdisjoint(ids_b))

    def test_anomalias_desactivadas_no_generan_alertas(self):
        ejecutar_main(self.carpeta.name, SIMULATION_DURATION=3000, ENABLE_ANOMALIES=False)
        self.assertEqual(leer_todo(self.carpeta.name)["alert"], [])

    def test_escritura_jsonl_amplia_sin_sobrescribir_y_en_utf8(self):
        with mock.patch.object(config, "OUTPUT_DIR", self.carpeta.name):
            save_event("prueba.jsonl", {"event_id": "1", "crop": "maíz"})
            save_event("prueba.jsonl", {"event_id": "2", "crop": "fresas"})
        ruta = Path(self.carpeta.name) / "prueba.jsonl"
        lineas = ruta.read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(l)["event_id"] for l in lineas], ["1", "2"])
        self.assertIn("maíz", lineas[0])                  # tilde guardada tal cual, no como í


if __name__ == "__main__":
    unittest.main()
