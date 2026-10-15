import json
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="Smart Agro IoT - Dashboard",
    page_icon="🌱",
    layout="wide"
)

st.title("🌱 Smart Agriculture IoT — Panel de Telemetría y Alertas")

# --- Carga de datos ---
@st.cache_data
def load_jsonl(filepath: Path) -> pd.DataFrame:
    if not filepath.exists():
        return pd.DataFrame()
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    df = pd.DataFrame(records)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    # Desempaquetar diccionario 'measurements' si existe
    if "measurements" in df.columns:
        meas_df = pd.json_normalize(df["measurements"])
        df = pd.concat([df.drop(columns=["measurements"]), meas_df], axis=1)
    return df

# Barra lateral para configurar ruta y filtros
st.sidebar.header("⚙️ Configuración y Filtros")
data_dir = Path(st.sidebar.text_input("Carpeta de datos (.jsonl)", value="output"))

df_sensors = load_jsonl(data_dir / "sensor_readings.jsonl")
df_weather = load_jsonl(data_dir / "weather_readings.jsonl")
df_irrig = load_jsonl(data_dir / "irrigation_events.jsonl")
df_alerts = load_jsonl(data_dir / "alerts.jsonl")

if df_sensors.empty or df_weather.empty or df_irrig.empty:
    st.warning(f"⚠️ No se encontraron los archivos .jsonl en la carpeta `{data_dir}`. Verifica la ruta en el panel lateral.")
    st.stop()

# Filtros globales en el sidebar
plots = sorted(df_sensors["plot_id"].dropna().unique())
selected_plots = st.sidebar.multiselect("Parcelas (plot_id)", options=plots, default=plots)

# --- KPIs Principales ---
col1, col2, col3, col4, col5 = st.columns(5)

total_rain = df_weather["rainfall_mm"].sum()
max_temp = df_weather["air_temperature_c"].max()
total_water_l = df_irrig.groupby("plot_id")["water_volume_l"].max().sum()
total_alerts = len(df_alerts)
critical_alerts = len(df_alerts[df_alerts["severity"] == "CRITICAL"]) if not df_alerts.empty else 0

col1.metric("🌧️ Lluvia Acumulada", f"{total_rain:.1f} mm")
col2.metric("🌡️ Temp. Máxima Aire", f"{max_temp:.1f} °C")
col3.metric("💧 Volumen Riego Total", f"{total_water_l:,.1f} L")
col4.metric("🚨 Alertas Totales", total_alerts)
col5.metric("🔥 Alertas Críticas", critical_alerts)

st.divider()

# --- Pestañas de Análisis ---
tab1, tab2, tab3, tab4 = st.tabs([
    "🌍 Suelo vs. Riego y Lluvia",
    "☀️ Ciclo Diurno y Meteorología",
    "🚨 Auditoría de Alertas",
    "🔋 Baterías y Salud IoT"
])

# === TAB 1: SUELO, RIEGO Y LLUVIA ===
with tab1:
    st.subheader("Respuesta de la Humedad del Suelo al Riego y la Lluvia")
    plot_choice = st.selectbox("Selecciona una parcela para inspeccionar al detalle:", options=plots)

    df_s_plot = df_sensors[df_sensors["plot_id"] == plot_choice].sort_values("timestamp")
    df_i_plot = df_irrig[df_irrig["plot_id"] == plot_choice].sort_values("timestamp")

    fig1 = make_subplots(specs=[[{"secondary_y": True}]])

    # Líneas de sensores de humedad del suelo (15cm y 20cm)
    for dev_id, group in df_s_plot.groupby("device_id"):
        depth = group["sensor_depth_cm"].iloc[0]
        fig1.add_trace(
            go.Scatter(
                x=group["timestamp"],
                y=group["soil_moisture_pct"],
                mode="lines",
                name=f"{dev_id} ({depth} cm)",
                connectgaps=False # Muestra los huecos cuando hay SENSOR_FAILURE (null)
            ),
            secondary_y=False
        )

    # Caudal de riego (L/min)
    fig1.add_trace(
        go.Scatter(
            x=df_i_plot["timestamp"],
            y=df_i_plot["water_flow_l_min"],
            mode="lines",
            name="Caudal Riego (L/min)",
            line=dict(color="royalblue", dash="dot"),
            fill="tozeroy"
        ),
        secondary_y=True
    )

    # Barras de lluvia (mm)
    fig1.add_trace(
        go.Bar(
            x=df_weather["timestamp"],
            y=df_weather["rainfall_mm"],
            name="Lluvia (mm)",
            marker_color="cyan",
            opacity=0.6
        ),
        secondary_y=True
    )

    # Umbrales de riego (20% encendido, 35% objetivo)
    fig1.add_hline(y=20.0, line_dash="dash", line_color="red", annotation_text="Umbral Mínimo (20%)", secondary_y=False)
    fig1.add_hline(y=35.0, line_dash="dash", line_color="green", annotation_text="Objetivo Riego (35%)", secondary_y=False)

    fig1.update_yaxes(title_text="Humedad del Suelo (%)", secondary_y=False)
    fig1.update_yaxes(title_text="Caudal (L/min) / Lluvia (mm)", secondary_y=True)
    fig1.update_layout(height=480, hovermode="x unified")
    st.plotly_chart(fig1, use_container_width=True)

    # Gráfica de volumen acumulado por parcela
    st.subheader("Volumen de Agua Acumulado por Parcela (L)")
    df_i_filtered = df_irrig[df_irrig["plot_id"].isin(selected_plots)]
    fig_vol = px.line(
        df_i_filtered,
        x="timestamp",
        y="water_volume_l",
        color="plot_id",
        title="Evolución del consumo de agua (water_volume_l)"
    )
    st.plotly_chart(fig_vol, use_container_width=True)

# === TAB 2: METEOROLOGÍA ===
with tab2:
    st.subheader("Curva Solar, Temperatura y Humedad Relativa (`WEATHER-001`)")
    fig_w = make_subplots(specs=[[{"secondary_y": True}]])

    fig_w.add_trace(
        go.Scatter(
            x=df_weather["timestamp"],
            y=df_weather["solar_radiation_w_m2"],
            name="Radiación Solar (W/m²)",
            line=dict(color="orange"),
            fill="tozeroy"
        ),
        secondary_y=False
    )

    fig_w.add_trace(
        go.Scatter(
            x=df_weather["timestamp"],
            y=df_weather["air_temperature_c"],
            name="Temp. Aire (°C)",
            line=dict(color="crimson", width=2)
        ),
        secondary_y=True
    )

    fig_w.add_trace(
        go.Scatter(
            x=df_weather["timestamp"],
            y=df_weather["air_humidity_pct"],
            name="Humedad Aire (%)",
            line=dict(color="teal", dash="dot")
        ),
        secondary_y=True
    )

    fig_w.add_hline(y=38.0, line_dash="dash", line_color="red", annotation_text="Umbral Alerta Temp (38 °C)", secondary_y=True)
    fig_w.update_yaxes(title_text="Radiación Solar (W/m²)", secondary_y=False)
    fig_w.update_yaxes(title_text="Temperatura (°C) / Humedad (%)", secondary_y=True)
    fig_w.update_layout(height=500, hovermode="x unified")
    st.plotly_chart(fig_w, use_container_width=True)

# === TAB 3: ALERTAS ===
with tab3:
    st.subheader("Verificación de las 5 Anomalías Obligatorias")
    if not df_alerts.empty:
        col_a1, col_a2 = st.columns([1, 2])

        with col_a1:
            alert_counts = df_alerts["alert_code"].value_counts().reset_index()
            alert_counts.columns = ["alert_code", "count"]
            fig_bar = px.bar(
                alert_counts,
                x="alert_code",
                y="count",
                color="alert_code",
                text_auto=True,
                title="Conteo por Código de Alerta"
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_a2:
            fig_timeline = px.scatter(
                df_alerts,
                x="timestamp",
                y="device_id",
                color="alert_code",
                symbol="severity",
                size_max=12,
                hover_data=["message", "measured_value", "threshold_value"],
                title="Línea Temporal de Anomalías por Dispositivo"
            )
            fig_timeline.update_traces(marker=dict(size=10))
            st.plotly_chart(fig_timeline, use_container_width=True)

        st.dataframe(
            df_alerts.sort_values("timestamp", ascending=False),
            use_container_width=True
        )
    else:
        st.info("No hay alertas registradas.")

# === TAB 4: BATERÍAS Y SALUD ===
with tab4:
    st.subheader("Ciclo de Descarga Nocturna y Recarga Solar (> 150 W/m²)")
    df_bat = pd.concat([
        df_sensors[["timestamp", "device_id", "battery_pct", "device_status"]],
        df_irrig[["timestamp", "device_id", "battery_pct", "device_status"]],
        df_weather[["timestamp", "device_id", "battery_pct", "device_status"]]
    ])

    fig_bat = px.line(
        df_bat.sort_values("timestamp"),
        x="timestamp",
        y="battery_pct",
        color="device_id",
        title="Nivel de Batería (%) en Todos los Dispositivos"
    )
    fig_bat.add_vline(
        x=pd.to_datetime("2026-10-14T06:35:00Z"),
        line_dash="dash",
        line_color="orange"
    )
    st.plotly_chart(fig_bat, use_container_width=True)