import json
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# ==============================================================================
# PARÁMETROS OFICIALES + BATERÍA (EJECUCIÓN EN RAM SIN TOCAR CONFIG.PY)
# ==============================================================================
PARAMETERS = [
    # --- CATEGORÍA 1: GENERAL Y EJECUCIÓN ---
    {
        "key": "SIMULATION_MODE",
        "label": "Modo de Simulación",
        "type": "choice",
        "choices": ["LIMITED", "CONTINUOUS"],
        "default": "LIMITED",
        "category": "⚙️ General y Ejecución",
        "help": (
            "• LIMITED: Genera el número de eventos indicado en SIMULATION_DURATION y termina.\n"
            "• CONTINUOUS: Genera eventos sin parar hasta detener el proceso."
        )
    },
    {
        "key": "SIMULATION_DURATION",
        "label": "Límite de Eventos (SIMULATION_DURATION)",
        "type": "int",
        "default": 1000000,
        "min": 16,
        "max": 5000000,
        "category": "⚙️ General y Ejecución",
        "help": (
            "Límite de eventos para el modo LIMITED.\n"
            "• Valor oficial del proyecto: 1,000,000 eventos (~217 días).\n"
            "• Prueba rápida de 25 horas: 5,000 eventos.\n"
            "Rango permitido: 16 a 5,000,000."
        )
    },
    {
        "key": "GENERATION_INTERVAL",
        "label": "Intervalo del Reloj Virtual (seg)",
        "type": "int",
        "default": 300,
        "min": 60,
        "max": 3600,
        "category": "⚙️ General y Ejecución",
        "help": (
            "Segundos que avanza el reloj simulado en cada paso.\n"
            "• Valor oficial requerido: 300 segundos (5 minutos)."
        )
    },
    {
        "key": "REALTIME_SLEEP",
        "label": "Pausa Real entre Pasos (seg)",
        "type": "float",
        "default": 0.0,
        "min": 0.0,
        "max": 10.0,
        "category": "⚙️ General y Ejecución",
        "help": (
            "Pausa real en segundos entre iteraciones.\n"
            "• 0.0: Velocidad máxima.\n"
            "• 0.5 a 2.0: Útil en modo CONTINUOUS."
        )
    },
    {
        "key": "RANDOM_SEED",
        "label": "Semilla Aleatoria (RANDOM_SEED)",
        "type": "int",
        "default": 42,
        "min": 1,
        "max": 999999,
        "category": "⚙️ General y Ejecución",
        "help": "Fija la semilla aleatoria (42 por defecto) para que siempre salgan los mismos datos."
    },
    {
        "key": "ENABLE_ANOMALIES",
        "label": "Activar Anomalías y Alertas",
        "type": "choice",
        "choices": ["True", "False"],
        "default": "True",
        "category": "⚙️ General y Ejecución",
        "help": "Activa (True) o desactiva (False) la aparición de fallos y alertas."
    },

    # --- CATEGORÍA 2: BATERÍA Y ENERGÍA SOLAR (NUEVO) ---
    {
        "key": "SOLAR_CHARGE_THRESHOLD",
        "label": "Radiación Mínima para Cargar (W/m²)",
        "type": "float",
        "default": 150.0,
        "min": 50.0,
        "max": 500.0,
        "category": "🔋 Batería y Energía Solar",
        "help": (
            "Umbral de radiación solar a partir del cual las placas solares cargan la batería.\n"
            "• Valor predeterminado: 150.0 W/m².\n"
            "Por debajo de este valor, la batería se descarga."
        )
    },
    {
        "key": "BATTERY_CHARGE_RATE",
        "label": "Tasa de Carga Solar por Paso (%)",
        "type": "float",
        "default": 0.4,
        "min": 0.05,
        "max": 5.0,
        "category": "🔋 Batería y Energía Solar",
        "help": (
            "Porcentaje que sube la batería cada 5 minutos cuando hay sol suficiente (> 150 W/m²).\n"
            "• Valor predeterminado: 0.4 % por paso (tope máximo en 100.0 %)."
        )
    },
    {
        "key": "BATTERY_DRAIN_RATE",
        "label": "Consumo / Descarga por Paso (%)",
        "type": "float",
        "default": 0.065,
        "min": 0.01,
        "max": 2.0,
        "category": "🔋 Batería y Energía Solar",
        "help": (
            "Porcentaje que consume el dispositivo cada 5 minutos durante la noche o sin sol.\n"
            "• Valor predeterminado: 0.07 % por paso."
        )
    },

    # --- CATEGORÍA 3: RIEGO Y SUELO ---
    {
        "key": "IRRIGATION_MIN_MOISTURE",
        "label": "Humedad Mínima Activación Riego (%)",
        "type": "float",
        "default": 20.0,
        "min": 10.0,
        "max": 30.0,
        "category": "🌱 Umbrales de Riego y Suelo",
        "help": "Si la humedad del suelo baja de este porcentaje, se activa el riego (Oficial: 20.0 %)."
    },
    {
        "key": "IRRIGATION_TARGET_MOISTURE",
        "label": "Humedad Objetivo Fin de Riego (%)",
        "type": "float",
        "default": 35.0,
        "min": 25.0,
        "max": 55.0,
        "category": "🌱 Umbrales de Riego y Suelo",
        "help": "Si alcanza este porcentaje, se detiene el riego (Oficial: 35.0 %)."
    },
    {
        "key": "IRRIGATION_FLOW_L_MIN",
        "label": "Caudal Nominal de Riego (L/min)",
        "type": "float",
        "default": 35.5,
        "min": 15.0,
        "max": 60.0,
        "category": "🌱 Umbrales de Riego y Suelo",
        "help": "Caudal nominal en litros por minuto cuando riega (Oficial: 35.5 L/min)."
    },
    {
        "key": "IRRIGATION_PRESSURE_BAR",
        "label": "Presión Nominal de Riego (bar)",
        "type": "float",
        "default": 2.3,
        "min": 1.0,
        "max": 4.5,
        "category": "🌱 Umbrales de Riego y Suelo",
        "help": "Presión nominal del agua en bares (Oficial: 2.3 bar)."
    },
    {
        "key": "SOIL_ABSORPTION_FACTOR",
        "label": "Factor Absorción del Suelo",
        "type": "float",
        "default": 0.02,
        "min": 0.005,
        "max": 0.1,
        "category": "🌱 Umbrales de Riego y Suelo",
        "help": "Subida progresiva de humedad por litro de agua aplicado (Oficial: 0.02)."
    },

    # --- CATEGORÍA 4: ALERTAS Y ANOMALÍAS ---
    {
        "key": "ALERT_HIGH_TEMP_THRESHOLD",
        "label": "Umbral Alerta Temperatura Aire (°C)",
        "type": "float",
        "default": 38.0,
        "min": 30.0,
        "max": 45.0,
        "category": "🚨 Probabilidades y Umbrales de Alerta",
        "help": "Umbral para disparar la alerta HIGH_TEMPERATURE (Oficial: 38.0 °C)."
    },
    {
        "key": "ALERT_MIN_FLOW_THRESHOLD",
        "label": "Umbral Caudal Mínimo Riego (L/min)",
        "type": "float",
        "default": 5.0,
        "min": 1.0,
        "max": 15.0,
        "category": "🚨 Probabilidades y Umbrales de Alerta",
        "help": "Caudal mínimo exigido cuando el riego está en ON para no dar fallo (Oficial: 5.0 L/min)."
    },
    {
        "key": "PROB_SENSOR_FAILURE",
        "label": "Probabilidad Fallo Sensor (0-1)",
        "type": "float",
        "default": 0.005,
        "min": 0.0001,
        "max": 0.05,
        "category": "🚨 Probabilidades y Umbrales de Alerta",
        "help": "Probabilidad de fallo en lectura de sensor de suelo (Oficial: 0.005)."
    },
    {
        "key": "PROB_IRRIGATION_FAILURE",
        "label": "Probabilidad Fallo Riego (0-1)",
        "type": "float",
        "default": 0.02,
        "min": 0.001,
        "max": 0.15,
        "category": "🚨 Probabilidades y Umbrales de Alerta",
        "help": "Probabilidad de fallo de caudal cuando riega (Oficial: 0.02)."
    },
    {
        "key": "PROB_WATER_LEAK",
        "label": "Probabilidad Fuga de Agua (0-1)",
        "type": "float",
        "default": 0.005,
        "min": 0.0001,
        "max": 0.05,
        "category": "🚨 Probabilidades y Umbrales de Alerta",
        "help": "Probabilidad de fuga con válvula cerrada (Oficial: 0.005)."
    },
    {
        "key": "PROB_HEATWAVE",
        "label": "Probabilidad Pico de Calor (0-1)",
        "type": "float",
        "default": 0.04,
        "min": 0.001,
        "max": 0.20,
        "category": "🚨 Probabilidades y Umbrales de Alerta",
        "help": "Probabilidad de pico de calor en horas centrales (Oficial: 0.04)."
    }
]


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 28
        y = self.widget.winfo_rooty() + 20
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw, text=self.text, justify=tk.LEFT,
            background="#2b2b3c", foreground="#ffffff",
            relief=tk.SOLID, borderwidth=1,
            font=("Segoe UI", 9), padx=10, pady=6, wraplength=360
        )
        label.pack()

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class SafeEngineApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🛡️ Lanzador Seguro Smart Agro IoT (config.py intacto)")
        self.geometry("840x720")
        self.configure(bg="#1e1e2e")
        self.resizable(True, True)

        self.vars = {}
        self._build_ui()

    def _build_ui(self):
        header = tk.Frame(self, bg="#181825", pady=12, padx=20)
        header.pack(fill=tk.X)

        tk.Label(
            header, text="🛡️ Panel de Simulación — Modo Protegido (Solo Memoria RAM)",
            font=("Segoe UI", 14, "bold"), bg="#181825", fg="#a6e3a1"
        ).pack(anchor="w")
        tk.Label(
            header,
            text=(
                "🔒 Tu archivo config.py NUNCA se modifica. "
                "Pasa el ratón por ℹ️ para ver las ayudas y rangos recomendados."
            ),
            font=("Segoe UI", 9), bg="#181825", fg="#f9e2af"
        ).pack(anchor="w", pady=(3, 0))

        container = tk.Frame(self, bg="#1e1e2e", padx=20, pady=10)
        container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(container, bg="#1e1e2e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.scroll_frame = tk.Frame(canvas, bg="#1e1e2e")

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw", width=780)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        categories = {}
        for p in PARAMETERS:
            categories.setdefault(p["category"], []).append(p)

        for cat_name, params in categories.items():
            cat_frame = tk.LabelFrame(
                self.scroll_frame, text=f" {cat_name} ",
                font=("Segoe UI", 10, "bold"),
                bg="#1e1e2e", fg="#89b4fa", bd=1, relief=tk.GROOVE, padx=12, pady=8
            )
            cat_frame.pack(fill=tk.X, pady=8)

            for idx, param in enumerate(params):
                self._create_row(cat_frame, param, idx)

        footer = tk.Frame(self, bg="#181825", pady=12, padx=20)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        btn_reset = tk.Button(
            footer, text="🔄 Restaurar Todos los Predeterminados",
            command=self.reset_all_defaults,
            bg="#45475a", fg="#ffffff", activebackground="#585b70",
            font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=12, pady=7, cursor="hand2"
        )
        btn_reset.pack(side=tk.LEFT)

        btn_run_custom = tk.Button(
            footer, text="▶️ Ejecutar con Valores de la Ventana (En RAM)",
            command=self.run_in_memory,
            bg="#89b4fa", fg="#11111b", activebackground="#b4befe",
            font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=14, pady=7, cursor="hand2"
        )
        btn_run_custom.pack(side=tk.RIGHT, padx=(8, 0))

        btn_run_official = tk.Button(
            footer, text="⚡ Ejecutar Oficial Directo",
            command=self.run_official,
            bg="#a6e3a1", fg="#11111b", activebackground="#94e2d5",
            font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=14, pady=7, cursor="hand2"
        )
        btn_run_official.pack(side=tk.RIGHT)

    def _create_row(self, parent, param, idx):
        key = param["key"]
        default_str = str(param["default"])

        var = tk.StringVar(value=default_str)
        self.vars[key] = (var, param)

        info_lbl = tk.Label(
            parent, text="ℹ️", font=("Segoe UI", 10),
            bg="#1e1e2e", fg="#f9e2af", cursor="question_arrow"
        )
        info_lbl.grid(row=idx, column=0, padx=(0, 6), pady=4, sticky="w")
        ToolTip(info_lbl, param["help"])

        lbl = tk.Label(
            parent, text=param["label"], font=("Segoe UI", 9),
            bg="#1e1e2e", fg="#cdd6f4", width=36, anchor="w"
        )
        lbl.grid(row=idx, column=1, padx=2, pady=4, sticky="w")
        ToolTip(lbl, param["help"])

        if param["type"] == "choice":
            widget = ttk.Combobox(
                parent, textvariable=var, values=param["choices"],
                state="readonly", width=14, font=("Consolas", 9)
            )
        else:
            widget = tk.Entry(
                parent, textvariable=var, width=16,
                font=("Consolas", 9), bg="#313244", fg="#ffffff",
                insertbackground="#ffffff", relief=tk.FLAT
            )
        widget.grid(row=idx, column=2, padx=6, pady=4)

        range_txt = f"Oficial: {default_str}"
        if "min" in param and "max" in param:
            range_txt += f"  [{param['min']} - {param['max']}]"
        def_lbl = tk.Label(
            parent, text=range_txt, font=("Segoe UI", 8),
            bg="#1e1e2e", fg="#9399b2", width=28, anchor="w"
        )
        def_lbl.grid(row=idx, column=3, padx=4, pady=4, sticky="w")

        btn_ind = tk.Button(
            parent, text="↺", command=lambda v=var, d=default_str: v.set(d),
            bg="#313244", fg="#cdd6f4", activebackground="#45475a",
            font=("Segoe UI", 8, "bold"), relief=tk.FLAT, width=3, cursor="hand2"
        )
        btn_ind.grid(row=idx, column=4, padx=2, pady=4)
        ToolTip(btn_ind, f"Restaurar a {default_str}")

    def reset_all_defaults(self):
        for key, (var, param) in self.vars.items():
            var.set(str(param["default"]))
        messagebox.showinfo(
            "Valores Oficiales Restaurados",
            "Todos los parámetros han vuelto a los valores predeterminados oficiales."
        )

    def validate_and_collect(self) -> dict | None:
        overrides = {}
        for key, (var, param) in self.vars.items():
            raw = var.get().strip()
            try:
                if param["type"] == "int":
                    val = int(raw)
                elif param["type"] == "float":
                    val = float(raw)
                else:
                    val = (raw == "True") if raw in ("True", "False") else raw

                if "min" in param and val < param["min"]:
                    messagebox.showerror(
                        "Valor fuera de rango",
                        f"'{param['label']}' no puede ser menor que {param['min']}.\n"
                        f"(Valor predeterminado: {param['default']})"
                    )
                    return None
                if "max" in param and val > param["max"]:
                    messagebox.showerror(
                        "Valor fuera de rango",
                        f"'{param['label']}' no puede superar {param['max']}.\n"
                        f"(Valor predeterminado: {param['default']})"
                    )
                    return None

                overrides[key] = val
            except ValueError:
                messagebox.showerror(
                    "Formato inválido",
                    f"El campo '{param['label']}' requiere un número válido."
                )
                return None

        if overrides["IRRIGATION_MIN_MOISTURE"] >= overrides["IRRIGATION_TARGET_MOISTURE"]:
            messagebox.showerror(
                "Incoherencia lógica",
                "La humedad mínima de activación debe ser menor que la humedad objetivo."
            )
            return None

        overrides["ALERT_LOW_MOISTURE_THRESHOLD"] = overrides["IRRIGATION_MIN_MOISTURE"]
        return overrides

    def _find_main_script(self) -> Path | None:
        for candidate in ["main.py", "src/main.py", "simulator.py"]:
            p = Path(candidate)
            if p.exists():
                return p
        return None

    def run_official(self):
        self.reset_all_defaults()
        main_script = self._find_main_script()
        if not main_script:
            messagebox.showwarning("Aviso", "No se encontró 'main.py' en esta carpeta.")
            return
        subprocess.Popen([sys.executable, str(main_script)])
        messagebox.showinfo(
            "Ejecución Oficial Iniciada",
            f"🚀 Se ha lanzado '{main_script}' usando directamente tu config.py intacto."
        )

    def run_in_memory(self):
        overrides = self.validate_and_collect()
        if overrides is None:
            return

        main_script = self._find_main_script()
        if not main_script:
            messagebox.showwarning("Aviso", "No se encontró 'main.py' en esta carpeta.")
            return

        overrides_json = json.dumps(overrides)
        runner_code = (
            f"import json, runpy, config; "
            f"overrides = json.loads({repr(overrides_json)}); "
            f"[setattr(config, k, v) for k, v in overrides.items()]; "
            f"runpy.run_path({repr(str(main_script))}, run_name='__main__')"
        )

        subprocess.Popen([sys.executable, "-c", runner_code])
        messagebox.showinfo(
            "Simulación en RAM Iniciada",
            "🚀 Simulación en marcha con los parámetros de la ventana (incluyendo batería).\n\n"
            "🔒 Tu archivo config.py en disco NO ha sido modificado."
        )


if __name__ == "__main__":
    app = SafeEngineApp()
    app.mainloop()