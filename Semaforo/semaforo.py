#!/usr/bin/env python3
"""Agente Controlador de Semáforos Temporizado (FSM + Tkinter, solo librería estándar)."""

import math
import time
import tkinter as tk
from tkinter import ttk

# ---------------------------------------------------------------------------
# LÓGICA: Máquina de Estados Finitos (sin dependencias de interfaz ni de reloj)
# ---------------------------------------------------------------------------
TOMATE, VERDE, AMARILLO = "TOMATE", "VERDE", "AMARILLO"


class ControladorSemaforo:
    """FSM determinista: TOMATE -> VERDE -> AMARILLO -> TOMATE ..."""

    SIGUIENTE = {TOMATE: VERDE, VERDE: AMARILLO, AMARILLO: TOMATE}
    ESTADO_INICIAL = TOMATE
    MIN_SEG, MAX_SEG = 1, 999

    def __init__(self, tiempo_verde=10, tiempo_amarillo=3, tiempo_tomate=10):
        self.duraciones = {VERDE: tiempo_verde, AMARILLO: tiempo_amarillo, TOMATE: tiempo_tomate}
        self.reiniciar()

    def reiniciar(self):
        self.estado = self.ESTADO_INICIAL
        self.restante = float(self.duraciones[self.estado])

    def set_duracion(self, estado, segundos):
        """Actualiza la duración. Se aplica en la próxima entrada al estado;
        si es el estado actual, se recorta el restante si excede el nuevo valor."""
        segundos = max(self.MIN_SEG, min(self.MAX_SEG, int(segundos)))
        self.duraciones[estado] = segundos
        if estado == self.estado:
            self.restante = min(self.restante, float(segundos))

    def avanzar(self, dt):
        """Consume 'dt' segundos; cambia de estado las veces que haga falta."""
        self.restante -= dt
        while self.restante <= 0:  # termina siempre: duraciones >= 1 s
            self.estado = self.SIGUIENTE[self.estado]
            self.restante += self.duraciones[self.estado]


# ---------------------------------------------------------------------------
# VISTA: Interfaz gráfica
# ---------------------------------------------------------------------------
COLORES = {  # (encendido, apagado)
    TOMATE:   ("#ff3b30", "#4a1512"),
    AMARILLO: ("#ffd60a", "#4d4208"),
    VERDE:    ("#30d158", "#10401c"),
}
NOMBRES = {TOMATE: "TOMATE (ROJO)", AMARILLO: "AMARILLO", VERDE: "VERDE"}
TICK_MS = 100


class AppSemaforo:
    def __init__(self, root):
        self.root = root
        self.root.title("Agente Controlador de Semáforo")
        self.root.resizable(False, False)

        self.fsm = ControladorSemaforo(10, 3, 10)
        self.corriendo = False
        self.after_id = None
        self.ultimo_t = 0.0

        self._construir_ui()
        self._refrescar()

    # ---------- Construcción de la interfaz ----------
    def _construir_ui(self):
        marco = ttk.Frame(self.root, padding=15)
        marco.grid()

        # Canvas con la carcasa y las 3 luces (Tomate arriba, Amarillo centro, Verde abajo)
        self.canvas = tk.Canvas(marco, width=200, height=430, bg="#f0f0f0", highlightthickness=0)
        self.canvas.grid(row=0, column=0, rowspan=2, padx=(0, 20))
        self.canvas.create_rectangle(35, 15, 165, 415, fill="#1c1c1e", outline="#000", width=3)
        self.luces, self.halos = {}, {}
        for estado, cy in ((TOMATE, 85), (AMARILLO, 215), (VERDE, 345)):
            self.halos[estado] = self.canvas.create_oval(100 - 52, cy - 52, 100 + 52, cy + 52,
                                                         outline="", width=0)
            self.luces[estado] = self.canvas.create_oval(100 - 42, cy - 42, 100 + 42, cy + 42,
                                                         fill=COLORES[estado][1], outline="#000", width=2)

        # Panel derecho
        panel = ttk.Frame(marco)
        panel.grid(row=0, column=1, sticky="n")

        # Monitor de estado en vivo
        mon = ttk.LabelFrame(panel, text="Monitor de estado", padding=10)
        mon.grid(sticky="ew")
        self.lbl_estado = tk.Label(mon, text="", font=("Arial", 16, "bold"), width=16)
        self.lbl_estado.grid()
        self.lbl_cuenta = tk.Label(mon, text="0", font=("Arial", 40, "bold"))
        self.lbl_cuenta.grid()
        ttk.Label(mon, text="segundos para el siguiente cambio").grid()
        self.lbl_modo = ttk.Label(mon, text="DETENIDO", font=("Arial", 10, "bold"))
        self.lbl_modo.grid(pady=(6, 0))

        # Configuración en tiempo real
        cfg = ttk.LabelFrame(panel, text="Configuración (segundos)", padding=10)
        cfg.grid(sticky="ew", pady=12)
        self.vars = {}
        for fila, (estado, etiqueta) in enumerate(((VERDE, "Tiempo verde:"),
                                                   (AMARILLO, "Tiempo amarillo:"),
                                                   (TOMATE, "Tiempo tomate:"))):
            ttk.Label(cfg, text=etiqueta).grid(row=fila, column=0, sticky="w", pady=3)
            var = tk.StringVar(value=str(self.fsm.duraciones[estado]))
            var.trace_add("write", lambda *_a, e=estado: self._config_cambiada(e))
            ttk.Spinbox(cfg, from_=ControladorSemaforo.MIN_SEG, to=ControladorSemaforo.MAX_SEG,
                        textvariable=var, width=6).grid(row=fila, column=1, padx=8)
            self.vars[estado] = var

        # Controles de ejecución
        bar = ttk.Frame(panel)
        bar.grid()
        self.btn_ini = ttk.Button(bar, text="Iniciar", command=self.iniciar)
        self.btn_pau = ttk.Button(bar, text="Pausar", command=self.pausar, state="disabled")
        self.btn_rei = ttk.Button(bar, text="Reiniciar", command=self.reiniciar)
        for i, b in enumerate((self.btn_ini, self.btn_pau, self.btn_rei)):
            b.grid(row=0, column=i, padx=3)

    # ---------- Eventos ----------
    def _config_cambiada(self, estado):
        txt = self.vars[estado].get().strip()
        if txt.isdigit() and ControladorSemaforo.MIN_SEG <= int(txt) <= ControladorSemaforo.MAX_SEG:
            self.fsm.set_duracion(estado, int(txt))
            self._refrescar()
        # Si el valor es inválido se ignora y se conserva el último válido.

    def iniciar(self):
        if self.corriendo:
            return
        self.corriendo = True
        self.ultimo_t = time.monotonic()
        self.btn_ini.config(state="disabled")
        self.btn_pau.config(state="normal")
        self._tick()

    def pausar(self):
        self.corriendo = False
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.btn_ini.config(state="normal")
        self.btn_pau.config(state="disabled")
        self._refrescar()

    def reiniciar(self):
        self.pausar()
        self.fsm.reiniciar()
        self._refrescar()

    # ---------- Bucle no bloqueante ----------
    def _tick(self):
        if not self.corriendo:
            return
        ahora = time.monotonic()
        self.fsm.avanzar(ahora - self.ultimo_t)
        self.ultimo_t = ahora
        self._refrescar()
        self.after_id = self.root.after(TICK_MS, self._tick)

    # ---------- Dibujo ----------
    def _refrescar(self):
        activo = self.fsm.estado
        for estado, item in self.luces.items():
            on = estado == activo
            self.canvas.itemconfig(item, fill=COLORES[estado][0 if on else 1])
            self.canvas.itemconfig(self.halos[estado], outline=COLORES[estado][0] if on else "",
                                   width=4 if on else 0)
        self.lbl_estado.config(text=NOMBRES[activo], bg=COLORES[activo][0],
                               fg="black" if activo != TOMATE else "white")
        self.lbl_cuenta.config(text=str(math.ceil(self.fsm.restante)))
        self.lbl_modo.config(text="EN EJECUCIÓN" if self.corriendo else "DETENIDO")


if __name__ == "__main__":
    ventana = tk.Tk()
    AppSemaforo(ventana)
    ventana.mainloop()