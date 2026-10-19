import os
import sys
import re
import subprocess
import threading
import urllib.parse
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

class GestorTunelGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Servidor Autónomo JSON + Cloudflare Tunnel")
        self.root.geometry("720x600")
        self.root.configure(padx=15, pady=15)

        self.archivos_json = {}  # {nombre_archivo: ruta_completa}
        self.carpeta_modo = None
        self.httpd = None
        self.proceso_cf = None
        self.proceso_http_cmd = None
        self.corriendo = False

        self.crear_interfaz()
        self.autodetectar_cloudflared()
        self.root.protocol("WM_DELETE_WINDOW", self.al_cerrar)

    def crear_interfaz(self):
        #Selección de cloudflared.exe
        frame_cf = tk.LabelFrame(self.root, text=" 1. Ejecutable de Cloudflare (cloudflared.exe) ", padx=10, pady=8)
        frame_cf.pack(fill="x", pady=(0, 10))

        self.ruta_cf_var = tk.StringVar()
        tk.Entry(frame_cf, textvariable=self.ruta_cf_var, width=65).pack(side="left", padx=(0, 10), expand=True, fill="x")
        tk.Button(frame_cf, text="Buscar .exe", command=self.seleccionar_cloudflared).pack(side="right")

        #Selección de archivos JSON o Carpeta
        frame_json = tk.LabelFrame(self.root, text=" 2. Archivos JSON a compartir (en tiempo real) ", padx=10, pady=8)
        frame_json.pack(fill="x", pady=(0, 10))

        btn_frame = tk.Frame(frame_json)
        btn_frame.pack(fill="x")
        tk.Button(btn_frame, text="Seleccionar archivos JSON sueltos", command=self.seleccionar_jsons).pack(side="left", padx=(0, 10))
        tk.Button(btn_frame, text="Seleccionar carpeta completa", command=self.seleccionar_carpeta).pack(side="left")

        self.lbl_seleccion = tk.Label(frame_json, text="Ningún archivo seleccionado", fg="gray", anchor="w", justify="left")
        self.lbl_seleccion.pack(fill="x", pady=(8, 0))

        # Opciones y Control
        frame_ctrl = tk.LabelFrame(self.root, text=" 3. Control del Servidor ", padx=10, pady=8)
        frame_ctrl.pack(fill="x", pady=(0, 10))

        tk.Label(frame_ctrl, text="Puerto local:").pack(side="left")
        self.puerto_var = tk.StringVar(value="8080")
        tk.Entry(frame_ctrl, textvariable=self.puerto_var, width=8).pack(side="left", padx=(5, 15))

        self.consolas_externas_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            frame_ctrl,
            text="Abrir también ventanas CMD independientes",
            variable=self.consolas_externas_var
        ).pack(side="left")

        self.btn_iniciar = tk.Button(
            frame_ctrl, text="▶ INICIAR TODO", bg="#28a745", fg="white",
            font=("Segoe UI", 10, "bold"), padx=15, command=self.alternar_servidor
        )
        self.btn_iniciar.pack(side="right")

        # Enlace Público Generado
        frame_url = tk.LabelFrame(self.root, text=" Enlace Público para los 20 ordenadores ", padx=10, pady=8)
        frame_url.pack(fill="x", pady=(0, 10))

        self.url_var = tk.StringVar(value="Esperando a iniciar el túnel...")
        self.entry_url = tk.Entry(
            frame_url, textvariable=self.url_var, font=("Consolas", 11, "bold"),
            fg="#0056b3", state="readonly"
        )
        self.entry_url.pack(side="left", fill="x", expand=True, padx=(0, 10))
        tk.Button(frame_url, text="Copiar Enlace", command=self.copiar_url).pack(side="right")

        # Consola 
        frame_log = tk.LabelFrame(self.root, text=" Registro de actividad en vivo ", padx=10, pady=8)
        frame_log.pack(fill="both", expand=True)

        self.consola = scrolledtext.ScrolledText(frame_log, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9))
        self.consola.pack(fill="both", expand=True)

    def autodetectar_cloudflared(self):
        posibles_rutas = [
            os.path.expanduser(r"~\Downloads\cloudflared.exe"),
            r"C:\Users\Administrator\Downloads\cloudflared.exe",
            os.path.join(os.getcwd(), "cloudflared.exe")
        ]
        for ruta in posibles_rutas:
            if os.path.isfile(ruta):
                self.ruta_cf_var.set(ruta)
                self.log(f"[OK] cloudflared.exe detectado automáticamente en: {ruta}")
                break

    def seleccionar_cloudflared(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar cloudflared.exe",
            filetypes=[("Ejecutable", "*.exe"), ("Todos los archivos", "*.*")]
        )
        if ruta:
            self.ruta_cf_var.set(ruta)

    def seleccionar_jsons(self):
        rutas = filedialog.askopenfilenames(
            title="Selecciona los archivos JSON a compartir",
            filetypes=[("Archivos JSON", "*.json"), ("Todos los archivos", "*.*")]
        )
        if rutas:
            self.carpeta_modo = None
            self.archivos_json = {os.path.basename(r): r for r in rutas}
            nombres = ", ".join(self.archivos_json.keys())
            self.lbl_seleccion.config(text=f"Archivos ({len(rutas)}): {nombres}", fg="black")
            self.log(f"[INFO] Seleccionados {len(rutas)} archivos JSON: {nombres}")

    def seleccionar_carpeta(self):
        carpeta = filedialog.askdirectory(title="Seleccionar carpeta donde están los JSON")
        if carpeta:
            self.archivos_json = {}
            self.carpeta_modo = carpeta
            self.lbl_seleccion.config(text=f"Carpeta completa: {carpeta}", fg="black")
            self.log(f"[INFO] Carpeta seleccionada: {carpeta}")

    def log(self, mensaje):
        self.consola.insert(tk.END, mensaje + "\n")
        self.consola.see(tk.END)

    def copiar_url(self):
        url = self.url_var.get()
        if url.startswith("https://"):
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            messagebox.showinfo("Copiado", f"Enlace copiado al portapapeles:\n{url}")
        else:
            messagebox.showwarning("Aviso", "Todavía no se ha generado un enlace válido.")

    def alternar_servidor(self):
        if not self.corriendo:
            self.iniciar_todo()
        else:
            self.detener_todo()

    def iniciar_todo(self):
        ruta_cf = self.ruta_cf_var.get().strip()
        if not os.path.isfile(ruta_cf):
            messagebox.showerror("Error", "Selecciona una ruta válida para cloudflared.exe")
            return

        if not self.archivos_json and not self.carpeta_modo:
            messagebox.showerror("Error", "Selecciona primero los archivos JSON o la carpeta que quieres compartir.")
            return

        try:
            puerto = int(self.puerto_var.get().strip())
        except ValueError:
            messagebox.showerror("Error", "El puerto debe ser un número válido (ej. 8080).")
            return

        self.corriendo = True
        self.btn_iniciar.config(text="⏹ DETENER TODO", bg="#dc3545")
        self.url_var.set("Generando túnel en Cloudflare, espera unos segundos...")

        # Si el usuario marcó abrir consola CMD 
        if self.consolas_externas_var.get():
            directorio_base = self.carpeta_modo if self.carpeta_modo else os.path.dirname(list(self.archivos_json.values())[0])
            self.log(f"[CMD] Abriendo servidor HTTP en consola externa (Carpeta: {directorio_base})...")
            self.proceso_http_cmd = subprocess.Popen(
                [sys.executable, "-m", "http.server", str(puerto)],
                cwd=directorio_base,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            self.log("[CMD] Abriendo Cloudflare Tunnel en consola externa...")
            self.proceso_cf = subprocess.Popen(
                [ruta_cf, "tunnel", "--url", f"http://localhost:{puerto}"],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            self.url_var.set("Revisa la ventana negra de Cloudflare para ver el enlace.")
            return

        # Modo autónomo integrado 
        threading.Thread(target=self.levantar_servidor_http, args=(puerto,), daemon=True).start()
        threading.Thread(target=self.levantar_cloudflared, args=(ruta_cf, puerto), daemon=True).start()

    def levantar_servidor_http(self, puerto):
        gui = self

        class LiveJSONHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                ruta_limpia = urllib.parse.unquote(self.path.split("?")[0]).lstrip("/")

                # Si estamos en modo carpeta completa, buscamos todos los JSON de esa carpeta en vivo
                if gui.carpeta_modo:
                    archivos_disponibles = {
                        f: os.path.join(gui.carpeta_modo, f)
                        for f in os.listdir(gui.carpeta_modo)
                        if os.path.isfile(os.path.join(gui.carpeta_modo, f))
                    }
                else:
                    archivos_disponibles = gui.archivos_json

                if ruta_limpia == "":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                    self.end_headers()

                    filas = ""
                    for nombre, ruta_real in archivos_disponibles.items():
                        if os.path.exists(ruta_real):
                            tam = os.path.getsize(ruta_real)
                            mod = datetime.fromtimestamp(os.path.getmtime(ruta_real)).strftime("%d/%m/%Y %H:%M:%S")
                            url_file = urllib.parse.quote(nombre)
                            filas += f"<tr><td><a href='/{url_file}'><b>{nombre}</b></a></td><td>{tam} bytes</td><td>{mod}</td></tr>"

                    html = f"""<!DOCTYPE html>
                    <html><head><meta charset='utf-8'><title>Archivos JSON Compartidos</title>
                    <style>
                        body {{ font-family: Segoe UI, sans-serif; margin: 40px; background: #f8f9fa; }}
                        table {{ border-collapse: collapse; width: 100%; max-width: 700px; background: white; }}
                        th, td {{ padding: 12px; border: 1px solid #dee2e6; text-align: left; }}
                        th {{ background: #343a40; color: white; }}
                        a {{ color: #0066cc; text-decoration: none; }}
                        a:hover {{ text-decoration: underline; }}
                    </style></head>
                    <body>
                        <h2>Archivos disponibles en tiempo real</h2>
                        <p>Pulsa F5 para actualizar o haz clic derecho -> Guardar enlace como...</p>
                        <table>
                            <tr><th>Archivo</th><th>Tamaño</th><th>Última modificación</th></tr>
                            {filas}
                        </table>
                    </body></html>"""
                    self.wfile.write(html.encode("utf-8"))

                elif ruta_limpia in archivos_disponibles and os.path.exists(archivos_disponibles[ruta_limpia]):
                    ruta_real = archivos_disponibles[ruta_limpia]
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    with open(ruta_real, "rb") as f:
                        self.wfile.write(f.read())
                else:
                    self.send_Error(404, "Archivo no encontrado")

            def log_message(self, format, *args):
                gui.root.after(0, gui.log, f"[HTTP] {self.address_string()} - {format % args}")

        try:
            self.httpd = ThreadingHTTPServer(("0.0.0.0", puerto), LiveJSONHandler)
            self.root.after(0, self.log, f"[OK] Servidor HTTP local escuchando en http://localhost:{puerto}")
            self.httpd.serve_forever()
        except Exception as e:
            self.root.after(0, self.log, f"[ERROR HTTP] {e}")

    def levantar_cloudflared(self, ruta_cf, puerto):
        comando = [ruta_cf, "tunnel", "--url", f"http://localhost:{puerto}"]
        self.root.after(0, self.log, f"[INFO] Ejecutando: {' '.join(comando)}")

        try:
            self.proceso_cf = subprocess.Popen(
                comando,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            patron_url = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

            for linea in self.proceso_cf.stdout:
                linea_limpia = linea.strip()
                if linea_limpia:
                    self.root.after(0, self.log, f"[CF] {linea_limpia}")
                    coincidencia = patron_url.search(linea_limpia)
                    if coincidencia:
                        url_encontrada = coincidencia.group(0)
                        self.root.after(0, self.url_var.set, url_encontrada)
                        self.root.after(0, self.log, f"\n>>> ENLACE LISTO: {url_encontrada} <<<\n")

        except Exception as e:
            self.root.after(0, self.log, f"[ERROR CLOUDFLARE] {e}")

    def detener_todo(self):
        self.log("[INFO] Deteniendo servicios...")
        if self.httpd:
            threading.Thread(target=self.httpd.shutdown, daemon=True).start()
            self.httpd = None

        if self.proceso_cf:
            self.proceso_cf.terminate()
            self.proceso_cf = None

        if self.proceso_http_cmd:
            self.proceso_http_cmd.terminate()
            self.proceso_http_cmd = None

        self.corriendo = False
        self.btn_iniciar.config(text="INICIAR TODO", bg="#28a745")
        self.url_var.set("Servidor detenido.")
        self.log("[OK] Todos los servicios se han cerrado correctamente.")

    def al_cerrar(self):
        self.detener_todo()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = GestorTunelGUI(root)
    root.mainloop()