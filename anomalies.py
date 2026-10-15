import random
import uuid
import config


def detect_and_generate_alerts(event, timestamp):
    """
    Analiza un evento generado (sensor_reading, weather_reading, irrigation_event)
    y devuelve una lista de alertas si detecta o inyecta anomalías.
    """
    alerts = []

    # 1. Anomalías en sensores de suelo
    if event["event_type"] == "sensor_reading":
        measurements = event["measurements"]
        moisture = measurements["soil_moisture_pct"]

        # LOW_SOIL_MOISTURE: Humedad por debajo del umbral configurado
        if moisture is not None and moisture < config.ALERT_LOW_MOISTURE_THRESHOLD:
            alerts.append(_create_alert_event(
                event, timestamp, "LOW_SOIL_MOISTURE", "WARNING",
                measured_value=moisture, threshold=config.ALERT_LOW_MOISTURE_THRESHOLD,
                message="Humedad del suelo por debajo del umbral"
            ))

        # SENSOR_FAILURE: Lecturas defectuosas o ausencia de lectura
        if random.random() < config.PROB_SENSOR_FAILURE:
            event["measurements"]["soil_moisture_pct"] = None
            event["device_status"] = "ERROR"
            alerts.append(_create_alert_event(
                event, timestamp, "SENSOR_FAILURE", "CRITICAL",
                measured_value=0.0, threshold=0.0,
                message="Ausencia de lectura o pérdida de comunicación con el sensor"
            ))

    # 2. Anomalías meteorológicas
    elif event["event_type"] == "weather_reading":
        temp = event["measurements"]["air_temperature_c"]

        # HIGH_TEMPERATURE: Temperatura excesiva
        if temp > config.ALERT_HIGH_TEMP_THRESHOLD:
            alerts.append(_create_alert_event(
                event, timestamp, "HIGH_TEMPERATURE", "WARNING",
                measured_value=temp, threshold=config.ALERT_HIGH_TEMP_THRESHOLD,
                message="Temperatura del aire excesiva detectada"
            ))

    # 3. Anomalías en el sistema de riego
    elif event["event_type"] == "irrigation_event":
        status = event["irrigation_status"]
        valve = event["valve_status"]

        # IRRIGATION_FAILURE: Riego activado sin caudal esperado
        if status == "ON" and random.random() < config.PROB_IRRIGATION_FAILURE:
            event["water_flow_l_min"] = 0.0
            event["water_pressure_bar"] = 0.0
            alerts.append(_create_alert_event(
                event, timestamp, "IRRIGATION_FAILURE", "CRITICAL",
                measured_value=0.0, threshold=config.ALERT_MIN_FLOW_THRESHOLD,
                message="Riego activado sin caudal suficiente"
            ))

        # WATER_LEAK: Flujo inesperado con válvula cerrada
        elif valve == "CLOSED" and random.random() < config.PROB_WATER_LEAK:
            fake_leak_flow = round(random.uniform(2.0, 10.0), 1)
            event["water_flow_l_min"] = fake_leak_flow
            alerts.append(_create_alert_event(
                event, timestamp, "WATER_LEAK", "CRITICAL",
                measured_value=fake_leak_flow, threshold=0.0,
                message="Flujo inesperado detectado con la válvula cerrada"
            ))

    return alerts


def _create_alert_event(source_event, timestamp, code, severity, measured_value, threshold, message):
    """Función auxiliar para construir el diccionario de la alerta."""
    alert = {
        "event_id": str(uuid.uuid4()),
        "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "device_id": source_event["device_id"],
        "event_type": "alert",
        "farm_id": config.FARM_ID,
        "alert_code": code,
        "severity": severity,
        "measured_value": round(measured_value, 2) if measured_value is not None else None,
        "threshold_value": threshold,
        "message": message
    }

    if "plot_id" in source_event:
        alert["plot_id"] = source_event["plot_id"]

    return alert