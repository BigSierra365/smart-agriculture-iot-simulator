import datetime
import random
import time
import config
from weather import generate_weather_event
from sensors import PlotSoilState
from irrigation import IrrigationController
from data_writer import save_event
from anomalies import detect_and_generate_alerts


def main():
    # Inicializar semilla aleatoria para reproducibilidad (Sección 7)
    random.seed(config.RANDOM_SEED)

    # Establecer la fecha de inicio virtual en UTC
    current_time = datetime.datetime.now(datetime.timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    print("--- Iniciando simulador IoT AgroSmart ---")
    print(
        f"Modo: {config.SIMULATION_MODE} | Intervalo: {config.GENERATION_INTERVAL}s | "
        f"Semilla: {config.RANDOM_SEED}"
    )
    if config.SIMULATION_MODE == "LIMITED":
        print(f"Límite configurado: {config.SIMULATION_DURATION} eventos")
    else:
        print("Ejecutando en modo continuo. Pulsa Ctrl+C para detener de forma segura.")

    # 1. INICIALIZAR EL ESTADO DE LAS PARCELAS
    plots_soil = {}
    plots_irrigation = {}
    for plot_id in config.PLOTS.keys():
        plots_soil[plot_id] = PlotSoilState(plot_id)
        plots_irrigation[plot_id] = IrrigationController(plot_id)

    event_count = 0

    # 2. BUCLE PRINCIPAL (Con parada controlada para modo continuo y limitado)
    try:
        while config.SIMULATION_MODE == "CONTINUOUS" or event_count < config.SIMULATION_DURATION:

            # A) EVENTO METEOROLÓGICO (Compartido para toda la explotación)
            weather_event = generate_weather_event(current_time)
            current_solar = weather_event["measurements"]["solar_radiation_w_m2"]

            if config.ENABLE_ANOMALIES:
                alerts = detect_and_generate_alerts(weather_event, current_time)
                for alert in alerts:
                    save_event("alerts.jsonl", alert)
                    event_count += 1

            save_event("weather_readings.jsonl", weather_event)
            event_count += 1

            # B) ITERAR SOBRE CADA PARCELA
            for plot_id in config.PLOTS.keys():
                if config.SIMULATION_MODE == "LIMITED" and event_count >= config.SIMULATION_DURATION:
                    break

                # B.1: El clima afecta al suelo (evaporación, lluvia y temperatura)
                plots_soil[plot_id].update_from_weather(weather_event["measurements"])

                # B.2: Los sensores de suelo leen el estado actual de la parcela
                sensor_events = plots_soil[plot_id].generate_sensor_events(current_time, current_solar)
                for s_event in sensor_events:
                    if config.ENABLE_ANOMALIES:
                        alerts = detect_and_generate_alerts(s_event, current_time)
                        for alert in alerts:
                            save_event("alerts.jsonl", alert)
                            event_count += 1

                    save_event("sensor_readings.jsonl", s_event)
                    event_count += 1

                # B.3: El controlador de riego evalúa la humedad actual y decide si regar
                current_avg_moisture = plots_soil[plot_id].moisture
                irrigation_event, liters_applied = plots_irrigation[plot_id].evaluate_and_irrigate(
                    current_avg_moisture, current_time, current_solar
                )

                if config.ENABLE_ANOMALIES:
                    alerts = detect_and_generate_alerts(irrigation_event, current_time)
                    for alert in alerts:
                        save_event("alerts.jsonl", alert)
                        event_count += 1

                # Coherencia ante IRRIGATION_FAILURE: si el caudal cayó a 0.0, no salió agua
                if irrigation_event["irrigation_status"] == "ON" and irrigation_event["water_flow_l_min"] == 0.0:
                    plots_irrigation[plot_id].water_volume_l = max(
                        0.0, plots_irrigation[plot_id].water_volume_l - liters_applied
                    )
                    irrigation_event["water_volume_l"] = round(plots_irrigation[plot_id].water_volume_l, 1)
                    liters_applied = 0.0

                save_event("irrigation_events.jsonl", irrigation_event)
                event_count += 1

                # B.4: Si el riego aplicó agua efectivamente, aumenta la humedad del suelo
                if liters_applied > 0:
                    plots_soil[plot_id].add_water_from_irrigation(liters_applied)

            # C) AVANZAR EL RELOJ VIRTUAL
            current_time += datetime.timedelta(seconds=config.GENERATION_INTERVAL)

            if config.REALTIME_SLEEP > 0:
                time.sleep(config.REALTIME_SLEEP)

    except KeyboardInterrupt:
        print("\n[!] Interrupción detectada por el usuario (Ctrl+C). Cerrando archivos de forma segura...")

    print("--- Simulación completada ---")
    print(f"Total eventos generados: {event_count}")
    print(f"Fecha virtual final: {current_time.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"Archivos guardados en el directorio: {config.OUTPUT_DIR}/")


if __name__ == "__main__":
    main()