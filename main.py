import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import subprocess
import os
import sqlite3
from datetime import datetime
import threading
import time
from plyer import notification

# ----------- BASE DE DATOS (SQLite) ------------

def crear_base_de_datos():
    if not os.path.exists("config.db"):
        try:
            conn = sqlite3.connect("config.db")
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS configuracion (
                    id INTEGER PRIMARY KEY,
                    ruta_mysql_bin TEXT,
                    usuario TEXT,
                    host TEXT,
                    puerto TEXT,
                    base_de_datos TEXT,
                    password TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS importaciones (
                    id INTEGER PRIMARY KEY,
                    base_de_datos TEXT,
                    fecha_hora TEXT
                )
            ''')
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            print(f"Error al crear la base de datos: {e}")

def guardar_configuracion_en_db():
    usuario = entrada_usuario.get()
    host = entrada_host.get()
    puerto = entrada_puerto.get()

    if not all([usuario, host, puerto]):
        messagebox.showerror("Error", "Usuario, host y puerto son obligatorios para guardar.")
        return

    ruta = entrada_ruta.get()
    base = entrada_base.get()
    password = entrada_password.get()

    try:
        conn = sqlite3.connect("config.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM configuracion")
        cursor.execute(
            "INSERT INTO configuracion (ruta_mysql_bin, usuario, host, puerto, base_de_datos, password) VALUES (?, ?, ?, ?, ?, ?)",
            (ruta, usuario, host, puerto, base, password)
        )
        conn.commit()
        conn.close()
        messagebox.showinfo("Guardado", "Configuración guardada correctamente.")
    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Error al guardar la configuración: {e}")

def cargar_configuracion():
    if not os.path.exists("config.db"):
        return None
    try:
        conn = sqlite3.connect("config.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM configuracion LIMIT 1")
        fila = cursor.fetchone()
        conn.close()
        return fila[1:] if fila else None
    except sqlite3.Error as e:
        print(f"Error al cargar configuración: {e}")
        return None

def verificar_importacion_previa(nombre_bd):
    conn = sqlite3.connect("config.db")
    cursor = conn.cursor()
    cursor.execute("SELECT fecha_hora FROM importaciones WHERE base_de_datos = ? ORDER BY id DESC LIMIT 1", (nombre_bd,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else None

def registrar_importacion(nombre_bd):
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect("config.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO importaciones (base_de_datos, fecha_hora) VALUES (?, ?)", (nombre_bd, fecha_actual))
    conn.commit()
    conn.close()

from plyer import notification

def notificar(nombre_db, tiempo):
    notification.notify(
        title="Importación completada",
        message=f"La base de datos '{nombre_db}' fue importada correctamente en {tiempo} segundos.",
        timeout=10
    )


# ----------- FUNCIONES PRINCIPALES ------------

def seleccionar_directorio():
    archivo_mysql = filedialog.askopenfilename(title="Selecciona mysql.exe", filetypes=[("Ejecutables", "mysql.exe")])
    if archivo_mysql:
        ruta = os.path.dirname(archivo_mysql)
        entrada_ruta.delete(0, tk.END)
        entrada_ruta.insert(0, ruta)

def importar_bd():
    archivo_sql = filedialog.askopenfilename(title="Selecciona el archivo .sql", filetypes=[("SQL files", "*.sql")])
    if not archivo_sql:
        return

    def tarea_importar():
        ruta = entrada_ruta.get()
        usuario = entrada_usuario.get()
        host = entrada_host.get()
        puerto = entrada_puerto.get()
        base = entrada_base.get()
        password = entrada_password.get()

        if not all([ruta, usuario, host, puerto, base, password]):
            messagebox.showerror("Error", "Completa todos los campos antes de importar.")
            return

        mysql_path = os.path.join(ruta, "mysql.exe")
        comando_crear = [mysql_path, "-h", host, "-u", usuario, f"-P{puerto}", f"-p{password}", "-e", f"CREATE DATABASE IF NOT EXISTS `{base}`;"]

        inicio = time.time()
        tiempo_transcurrido = [0]
        detener_tiempo = threading.Event()

        def actualizar_tiempo():
            while not detener_tiempo.is_set() and barra_progreso.winfo_exists():
                etiqueta_tiempo.config(text=f"Importando... {tiempo_transcurrido[0]} segundos transcurridos")
                time.sleep(1)
                tiempo_transcurrido[0] += 1

        threading.Thread(target=actualizar_tiempo, daemon=True).start()
        barra_progreso.start()

        try:
            subprocess.run(comando_crear, check=True)
            ultima_fecha = verificar_importacion_previa(base)
            if ultima_fecha:
                continuar = messagebox.askyesno("Importación previa detectada",
                                                f"La base de datos '{base}' ya fue importada el {ultima_fecha}.\n¿Deseás continuar y sobreescribir?")
                if not continuar:
                    detener_tiempo.set()
                    barra_progreso.stop()
                    etiqueta_tiempo.config(text="Importación cancelada por el usuario.")
                    return

            comando = [mysql_path, "-h", host, "-u", usuario, f"-P{puerto}", f"-p{password}", base]
            with open(archivo_sql, "rb") as archivo:
                subprocess.run(comando, stdin=archivo, check=True)

            registrar_importacion(base)
            tiempo_total = int(time.time() - inicio)
            messagebox.showinfo("Éxito", f"Base de datos importada correctamente en {tiempo_total} segundos.")

        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"No se pudo importar la base de datos.\n\n{e}")
        except FileNotFoundError:
            messagebox.showerror("Error", "mysql.exe no encontrado. Verificá la ruta.")
        finally:
            detener_tiempo.set()
            barra_progreso.stop()

            #Notiificar una vez levantada la bd
            notificar(base, tiempo_total)
            etiqueta_tiempo.config(text=f"Importación finalizada en {tiempo_transcurrido[0]} segundos.")

            


    threading.Thread(target=tarea_importar).start()

# ----------- INTERFAZ GRÁFICA ------------

crear_base_de_datos()
config = cargar_configuracion()

ventana = tk.Tk()
ventana.title("Importador de Base de Datos MySQL")

tk.Label(ventana, text="Ruta a mysql.exe (bin):").pack()
entrada_ruta = tk.Entry(ventana, width=50)
entrada_ruta.pack()
tk.Button(ventana, text="Seleccionar mysql.exe", command=seleccionar_directorio).pack(pady=3)

tk.Label(ventana, text="Usuario MySQL *:").pack()
entrada_usuario = tk.Entry(ventana, width=30)
entrada_usuario.pack()

tk.Label(ventana, text="Host *:").pack()
entrada_host = tk.Entry(ventana, width=30)
entrada_host.pack()

tk.Label(ventana, text="Puerto *:").pack()
entrada_puerto = tk.Entry(ventana, width=30)
entrada_puerto.pack()

tk.Label(ventana, text="Base de Datos:").pack()
entrada_base = tk.Entry(ventana, width=30)
entrada_base.pack()

tk.Label(ventana, text="Contraseña (para importar):").pack()
entrada_password = tk.Entry(ventana, show="*", width=30)
entrada_password.pack()

tk.Button(ventana, text="Guardar configuración", command=guardar_configuracion_en_db).pack(pady=5)
tk.Button(ventana, text="Seleccionar archivo .sql e importar", command=importar_bd).pack(pady=10)

tk.Label(ventana, text="Progreso:").pack()
barra_progreso = ttk.Progressbar(ventana, mode="indeterminate", length=300)
barra_progreso.pack(pady=5)

etiqueta_tiempo = tk.Label(ventana, text="Tiempo transcurrido: 0 segundos")
etiqueta_tiempo.pack()

if config:
    entrada_ruta.insert(0, config[0])
    entrada_usuario.insert(0, config[1])
    entrada_host.insert(0, config[2])
    entrada_puerto.insert(0, config[3])
    entrada_base.insert(0, config[4])
    entrada_password.insert(0, config[5])

ventana.mainloop()
