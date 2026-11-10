"""
FRENTE DE BATALLA - Edición Lobby Battle Royale (Python + Ursina)

    pip install ursina
    python frente_de_batalla.py

W A S D mover | Shift correr | Espacio saltar | Mouse apuntar
Clic disparar | Clic derecho zoom | 1-4 o rueda: cambiar arma
R recargar | G granada | Esc o P pausa
Las opciones y el récord se guardan en frente_de_batalla.json (carpeta de usuario).
"""
import json
import math
import os
import random

from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from ursina.collider import Collider
from panda3d.core import CollisionBox, Point3

C = color.hex

# ------------------------------------------------------------------ armas
ARMAS = [
    dict(n='Fusil de Asalto',   dano=34,  ritmo=.095, cargador=30, reserva=120, recarga=1.7, dispersion=.006,  perdigones=1, auto=True,  retroceso=1.0, zoom=60, largo=.65, col='#2b3d52', rareza='RARO',      col_raro='#1e88e5'),
    dict(n='Pistola Táctica',   dano=30,  ritmo=.2,   cargador=12, reserva=72,  recarga=1.1, dispersion=.003,  perdigones=1, auto=False, retroceso=.6,  zoom=70, largo=.38, col='#2e3a2e', rareza='POCO COMÚN', col_raro='#43a047'),
    dict(n='Escopeta Corredera', dano=16, ritmo=.8,   cargador=6,  reserva=36,  recarga=2.4, dispersion=.045,  perdigones=9, auto=False, retroceso=2.2, zoom=75, largo=.75, col='#3c274d', rareza='ÉPICO',     col_raro='#8e24aa'),
    dict(n='Fusil Pesado',      dano=110, ritmo=1.1,  cargador=5,  reserva=25,  recarga=2.5, dispersion=.0005, perdigones=1, auto=False, retroceso=2.5, zoom=20, largo=.95, col='#543d1a', rareza='LEGENDARIO',col_raro='#f39c12'),
]

DESC_ARMAS = [
    'Automático y polivalente. Ideal para cualquier distancia media.',
    'Semiautomática ágil con recarga ultra veloz.',
    '9 perdigones devastadores a quemarropa.',
    'Gran calibre. Disparo certero letal. Clic derecho: mira telescópica.'
]


class S:
    """Estado global del juego."""
    modo = 'menu'                 # menu | juego | pausa | fin
    panel = 'lobby'               # lobby | armas | config | desplegar
    fov = 90
    sens = 40
    dif = 1
    arma_inicial = 0
    record_ola = 0
    record_bajas = 0
    hp = 100.0
    ola = 0
    bajas = 0
    por_aparecer = 0
    restantes = 0
    t_aparicion = 0.0
    t_ola = 0.0
    arma = 0
    municion = []
    reserva = []
    recargando = False
    t_recarga = 0.0
    enfriamiento = 0.0
    granadas = 3
    t_granada = 0.0
    t_msg = 0.0
    sangre = 0.0
    marcador = 0.0
    enemigos = []
    recogibles = []


RUTA = os.path.join(os.path.expanduser('~'), 'frente_de_batalla.json')
CAMPOS = ('fov', 'sens', 'dif', 'arma_inicial', 'record_ola', 'record_bajas')


def guardar():
    try:
        with open(RUTA, 'w') as f:
            json.dump({k: getattr(S, k) for k in CAMPOS}, f)
    except Exception:
        pass


def cargar():
    try:
        with open(RUTA) as f:
            datos = json.load(f)
        for k in CAMPOS:
            if k in datos:
                setattr(S, k, int(datos[k]))
    except Exception:
        pass
    S.fov = max(70, min(110, S.fov))
    S.sens = max(10, min(100, S.sens))
    S.dif = max(0, min(2, S.dif))
    S.arma_inicial = max(0, min(len(ARMAS) - 1, S.arma_inicial))


cargar()

# ------------------------------------------------------------------ ventana y shaders
app = Ursina(title='Frente de Batalla - Survival Royale', borderless=False)
for nombre in ('fps_counter', 'exit_button', 'entity_counter', 'collider_counter'):
    obj = getattr(window, nombre, None)
    if obj is not None:
        obj.enabled = False
window.color = C('#0d1117')

UI = {}
try:
    from ursina.shaders import lit_with_shadows_shader, unlit_shader
    Entity.default_shader = lit_with_shadows_shader
    UI = dict(shader=unlit_shader)
    sol = DirectionalLight(shadows=True)
    sol.look_at(Vec3(1, -1.2, -.6))
except Exception as e:
    print('Sin shaders avanzados:', e)

try:
    scene.fog_color = C('#0f172a')
    scene.fog_density = (40, 150)
except Exception:
    pass

# ------------------------------------------------------------------ mundo de combate
mundo = Entity()      # todo lo que bloquea balas y enemigos cuelga de acá
estatico = Entity()   # parte visual del escenario; al terminar se fusiona en una sola malla
CAJAS = []            # colisiones del escenario; se juntan en un solo collider
ruinas = []
PUNTOS = []
LADRILLO = ['#6e4a3c', '#7a5442', '#5d3f33', '#8a6249']
CONCRETO = ['#475569', '#334155', '#1e293b']


def bloque(x, z, ancho, alto, largo, col, y=0.0, solido=True):
    if solido:
        caja(x, y + alto / 2, z, ancho, alto, largo)
    return Entity(parent=estatico, model='cube',
                  position=(x, y + alto / 2, z), scale=(ancho, alto, largo), color=C(col))


def caja(x, y, z, ancho, alto, largo):
    CAJAS.append(CollisionBox(Point3(x, y, z), ancho / 2, alto / 2, largo / 2))


def fusionar_escenario():
    """Cientos de cubos quietos -> 1 malla y 1 collider: mismo aspecto, muchas menos llamadas de dibujo."""
    malla = estatico.attachNewNode('malla')
    for e in list(estatico.children):
        e.model.copyTo(malla).setMat(e.model.getMat(malla))
        destroy(e)
    malla.flattenStrong()
    colision = Entity(parent=mundo)
    colision.collider = Collider(colision, CAJAS)


def cerca_de_ruina(p, radio):
    return any((q - p).length() < radio for q in ruinas)


def muro(x, z, largo, a_lo_z):
    s = 0.0
    while s < largo:
        c = min(random.uniform(1.6, 2.8), largo - s)
        medio = s + c / 2
        puerta = largo > 5 and abs(medio - largo / 2) < 1.4
        if not puerta and random.random() > .12:
            h = random.uniform(1, 2.2) if random.random() < .35 else random.uniform(3.2, 6)
            col = random.choice(LADRILLO)
            if a_lo_z:
                bloque(x, z + medio, .5, h, c, col)
            else:
                bloque(x + medio, z, c, h, .5, col)
        s += c


def ruina(cx, cz, w, d):
    muro(cx - w / 2, cz - d / 2, d, True)
    muro(cx + w / 2, cz - d / 2, d, True)
    muro(cx - w / 2, cz - d / 2, w, False)
    muro(cx - w / 2, cz + d / 2, w, False)
    for _ in range(8):
        e = bloque(cx + random.uniform(-w / 2, w / 2), cz + random.uniform(-d / 2, d / 2),
                   random.uniform(.3, 1), random.uniform(.2, .6), random.uniform(.3, 1),
                   random.choice(LADRILLO + CONCRETO), solido=False)
        e.rotation = (random.uniform(-15, 15), random.uniform(0, 180), random.uniform(-15, 15))


def construir_mundo():
    Entity(model='cube', scale=(130, 1, 130), y=-.5, color=C('#242b26'), collider='box')
    for lado in (-1, 1):
        caja(60 * lado, 5, 0, 1, 10, 124)
        caja(0, 5, 60 * lado, 124, 10, 1)

    intentos = 0
    while len(ruinas) < 11 and intentos < 300:
        intentos += 1
        p = Vec3(random.uniform(-50, 50), 0, random.uniform(-50, 50))
        if p.length() < 13 or cerca_de_ruina(p, 17):
            continue
        ruinas.append(p)
        ruina(p.x, p.z, random.uniform(7, 11), random.uniform(6, 10))

    for i in range(7):
        a, r = i * .9 + random.uniform(0, .4), random.uniform(8, 14)
        p = Vec3(math.sin(a) * r, 0, math.cos(a) * r)
        if cerca_de_ruina(p, 8):
            continue
        ancho, largo = (.8, 4.5) if random.random() < .5 else (4.5, .8)
        bloque(p.x, p.z, ancho, .55, largo, '#64748b')
        bloque(p.x, p.z, ancho * .9, .5, largo * .9, '#475569', y=.55)

    for _ in range(12):
        p = Vec3(random.uniform(-52, 52), 0, random.uniform(-52, 52))
        if p.length() < 6 or cerca_de_ruina(p, 8):
            continue
        bloque(p.x, p.z, 1.2, 1.2, 1.2, '#5c4033')

    for x, z in ((-20, -12), (22, 18)):
        if cerca_de_ruina(Vec3(x, 0, z), 8):
            continue
        bloque(x, z, 5, 1.3, 2.6, '#1e293b')
        bloque(x, z, 2, .8, 2, '#334155', y=1.3)

    for _ in range(40):
        ang, rad = random.uniform(0, math.tau), random.uniform(38, 56)
        p = Vec3(max(-56, min(56, math.sin(ang) * rad)), 0, max(-56, min(56, math.cos(ang) * rad)))
        if not cerca_de_ruina(p, 9):
            PUNTOS.append(p)

    fusionar_escenario()


# ------------------------------------------------------------------ jugador en combate
jugador = FirstPersonController(position=(0, .1, 0))
jugador.jump_height = 1.2
if hasattr(jugador, 'cursor'):
    jugador.cursor.alpha = 0
camera.clip_plane_near = .05
camera.fov = S.fov

arma_primera_persona = Entity(parent=camera, model='cube', position=(.25, -.25, .7))
fogonazo = Entity(parent=arma_primera_persona, model='cube', color=C('#ffd070'), scale=(2, 2, .25), z=.55, enabled=False, **UI)


def cambiar_arma(i):
    S.arma, S.recargando, S.enfriamiento = i, False, .3
    a = ARMAS[i]
    arma_primera_persona.scale = (.07, .09, a['largo'])
    arma_primera_persona.color = C(a['col'])
    if lobby_maniqui:
        lobby_maniqui.actualizar_arma(i)


# ------------------------------------------------------------------ LOBBY 3D (ESTILO FORTNITE)
# El lobby se ubica en las alturas (y=300) aislado del mapa de juego.
LOBBY_POS = Vec3(0, 300, 0)
lobby_root = Entity(position=LOBBY_POS)

# Podio y luces de neón
podio = Entity(parent=lobby_root, model='cylinder', scale=(4, .35, 4), color=C('#111827'), y=0)
podio_anillo = Entity(parent=lobby_root, model='cylinder', scale=(4.2, .05, 4.2), color=C('#00d2ff'), y=.2, **UI)
podio_luz = Entity(parent=lobby_root, model='cylinder', scale=(3.4, .08, 3.4), color=C('#1e293b'), y=.36)
foco_lobby = DirectionalLight(parent=lobby_root, y=6, z=-4)
foco_lobby.look_at(Vec3(0, 301.5, 0))

# Pared de fondo futurista del lobby
pared_fondo = Entity(parent=lobby_root, model='quad', scale=(24, 14), position=(0, 6, 7), color=C('#0a0f1d'), **UI)
Entity(parent=lobby_root, model='quad', scale=(20, .08), position=(0, 9.5, 6.9), color=C('#00e5ff'), **UI)
Entity(parent=lobby_root, model='quad', scale=(20, .08), position=(0, 2.5, 6.9), color=C('#7928ca'), **UI)


class ManiquiLobby(Entity):
    """Soldado 3D interactivo en el centro del lobby."""
    def __init__(self):
        super().__init__(parent=lobby_root, position=(0, .36, 0))
        self.t_idle = 0.0

        # Cuerpo
        self.cadera = Entity(parent=self, model='cube', scale=(.5, .3, .3), y=1.0, color=C('#1f2937'))
        self.pierna_izq = Entity(parent=self, model='cube', scale=(.2, .8, .22), position=(-.16, .5, 0), color=C('#111827'))
        self.pierna_der = Entity(parent=self, model='cube', scale=(.2, .8, .22), position=(.16, .5, .05), color=C('#111827'))
        self.bota_izq = Entity(parent=self, model='cube', scale=(.22, .25, .3), position=(-.16, .12, .04), color=C('#030712'))
        self.bota_der = Entity(parent=self, model='cube', scale=(.22, .25, .3), position=(.16, .12, .09), color=C('#030712'))

        # Torso y chaleco táctico
        self.torso = Entity(parent=self, model='cube', scale=(.6, .75, .36), y=1.5, color=C('#374151'))
        self.chaleco = Entity(parent=self.torso, model='cube', scale=(1.08, .85, 1.15), color=C('#1f2937'))
        Entity(parent=self.chaleco, model='cube', scale=(.85, .15, 1.2), y=.2, color=C('#00d2ff'), **UI)

        # Cabeza y casco militar con visor neón
        self.cabeza = Entity(parent=self, model='cube', scale=(.32, .34, .32), y=2.05, color=C('#e5e7eb'))
        self.casco = Entity(parent=self.cabeza, model='cube', scale=(1.12, .6, 1.12), y=.25, color=C('#111827'))
        self.visor = Entity(parent=self.cabeza, model='cube', scale=(.9, .2, .25), position=(0, .05, .5), color=C('#00f0ff'), **UI)

        # Brazos sosteniendo el arma
        self.hombro_izq = Entity(parent=self, model='cube', scale=(.18, .6, .18), position=(-.38, 1.45, .1), rotation=(25, -15, 10), color=C('#374151'))
        self.hombro_der = Entity(parent=self, model='cube', scale=(.18, .6, .18), position=(.36, 1.45, .15), rotation=(45, -25, -10), color=C('#374151'))

        # Arma en mano
        self.holder_arma = Entity(parent=self, position=(.2, 1.35, .4), rotation=(15, -15, 5))
        self.modelo_arma = Entity(parent=self.holder_arma, model='cube', scale=(.08, .12, .65), color=C('#22252a'))
        self.canon_arma = Entity(parent=self.holder_arma, model='cube', scale=(.04, .04, .3), position=(0, .02, .4), color=C('#111111'))

        # Placa de nombre flotante arriba del jugador
        self.placa = Entity(parent=self, position=(0, 2.65, 0), billboard=True)
        self.tag_rango = Text('★ RANGO COMANDANTE ★', parent=self.placa, position=(0, .28), scale=1.3, origin=(0, 0), color=C('#ffea00'), **UI)
        self.tag_nombre = Text('SOLDADO_77', parent=self.placa, position=(0, .14), scale=2.8, origin=(0, 0), color=C('#ffffff'), **UI)
        self.tag_sub = Text(f'RÉCORD: OLA {S.record_ola}  |  {S.record_bajas} BAJAS', parent=self.placa, position=(0, -.02), scale=1.1, origin=(0, 0), color=C('#38bdf8'), **UI)

    def actualizar_arma(self, idx):
        a = ARMAS[idx]
        self.modelo_arma.scale = (.08, .12, a['largo'])
        self.modelo_arma.color = C(a['col'])
        self.tag_sub.text = f'RÉCORD: OLA {S.record_ola}  |  {S.record_bajas} BAJAS'

    def update(self):
        if S.modo != 'menu':
            return
        self.t_idle += time.dt * 2
        # Respiración y ligero movimiento de espera
        self.torso.y = 1.5 + math.sin(self.t_idle) * .02
        self.cabeza.y = 2.05 + math.sin(self.t_idle) * .02
        self.holder_arma.y = 1.35 + math.sin(self.t_idle) * .015
        podio_anillo.rotation_y += time.dt * 25


lobby_maniqui = ManiquiLobby()


# ------------------------------------------------------------------ INTERFAZ (UI FORTNITE)
ORO = '#ffcc00'
CYAN = '#00d2ff'
BLANCO = '#f8fafc'
GRIS_OSCURO = '#0f172a'
GRIS_CARD = '#1e293b'

hud = Entity(parent=camera.ui, enabled=False)
menu = Entity(parent=camera.ui)


def texto(padre, t, pos, esc=1.0, col=BLANCO, origen=(0, 0)):
    return Text(t, parent=padre, position=pos, scale=esc, color=C(col), origin=origen, **UI)


def poner(t, txt):
    if getattr(t, '_ult', None) != txt:
        t._ult = txt
        t.text = txt


# HUD IN-GAME
sangre = Entity(parent=hud, model='quad', scale=(2, 1.2), z=1, color=C('#c80000'), **UI)
sangre.alpha = 0
t_ola = texto(hud, '', (0, .46), 2, ORO)
t_rest = texto(hud, '', (0, .41), 1.1)
t_msg = texto(hud, '', (0, .32), 2, ORO)
t_mun = texto(hud, '', (.85, -.40), 2.5, origen=(.5, 0))
t_gran = texto(hud, '', (.85, -.46), 1.1, origen=(.5, 0))
t_armas = texto(hud, '', (0, -.46), 1, '#94a3b8')
texto(hud, 'SALUD', (-.85, -.40), 1.1, origen=(-.5, 0))
Entity(parent=hud, model='quad', color=C('#1e293b'), scale=(.3, .03), position=(-.85, -.44), origin=(-.5, 0), **UI)
barra = Entity(parent=hud, model='quad', color=C('#22c55e'), scale=(.3, .03), position=(-.85, -.44), origin=(-.5, 0), z=-.1, **UI)
texto(hud, '+', (0, 0), 2)
marca = texto(hud, 'x', (0, 0), 2, '#ef4444')

# ----------------- PANELES DEL MENÚ -----------------
p_lobby = Entity(parent=menu)
p_desplegar = Entity(parent=menu, enabled=False)
p_arsenal = Entity(parent=menu, enabled=False)
p_config = Entity(parent=menu, enabled=False)
p_pausa = Entity(parent=menu, enabled=False)
paneles = {'lobby': p_lobby, 'desplegar': p_desplegar, 'arsenal': p_arsenal, 'config': p_config, 'pausa': p_pausa}


def mostrar_panel(nombre):
    S.panel = nombre
    for k, p in paneles.items():
        p.enabled = (k == nombre)
    if nombre == 'lobby':
        lobby_maniqui.actualizar_arma(S.arma_inicial)
    elif nombre == 'desplegar':
        refrescar_tarjetas_despliegue()
    elif nombre == 'arsenal':
        refrescar_arsenal_completo()


# Barra superior estilo Fortnite
top_bar = Entity(parent=menu)
Entity(parent=top_bar, model='quad', scale=(2, .1), position=(0, .45), color=C('#090d16'), **UI)
Entity(parent=top_bar, model='quad', scale=(2, .004), position=(0, .40), color=C(CYAN), **UI)

texto(top_bar, 'FRENTE DE BATALLA', (-.85, .45), 2.0, ORO, origen=(-.5, 0))


def tab_btn(txt, x, panel_destino):
    return Button(parent=top_bar, text=txt, position=(x, .45), scale=(.2, .06),
                  color=C('#111827'), highlight_color=C('#1f2937'), pressed_color=C('#374151'),
                  on_click=lambda: mostrar_panel(panel_destino), **UI)


tab_btn('LOBBY', -.25, 'lobby')
tab_btn('ARSENAL', 0.0, 'arsenal')
tab_btn('AJUSTES', .25, 'config')

# Perfil del jugador en esquina superior derecha
tarjeta_perfil = Entity(parent=top_bar, position=(.75, .45))
Entity(parent=tarjeta_perfil, model='quad', scale=(.32, .065), color=C('#1e293b'), **UI)
perfil_nombre = texto(tarjeta_perfil, 'SOLDADO_77  ★ LVL 50', (-.14, .01), 1.0, BLANCO, origen=(-.5, 0))
perfil_record = texto(tarjeta_perfil, f'Récord: Ola {S.record_ola}', (-.14, -.02), .8, CYAN, origen=(-.5, 0))

# --- PANEL LOBBY (Principal)
# Botón JUGAR gigante en esquina inferior derecha
b_jugar_cont = Entity(parent=p_lobby, position=(.62, -.32))
Entity(parent=b_jugar_cont, model='quad', scale=(.48, .18), color=C('#1e293b'), **UI)
Entity(parent=b_jugar_cont, model='quad', scale=(.46, .16), color=C(ORO), **UI)
b_jugar = Button(parent=b_jugar_cont, text='', scale=(.46, .16), color=C('#ffbe0b'),
                 highlight_color=C('#ffd000'), pressed_color=C('#e0a800'),
                 on_click=lambda: mostrar_panel('desplegar'), **UI)
texto(b_jugar_cont, '¡JUGAR!', (0, .02), 3.0, '#000000', origen=(0, 0))
texto(b_jugar_cont, 'SUPERVIVENCIA SOLITARIO', (0, -.04), 1.0, '#473200', origen=(0, 0))

# Tarjeta informativa del arma equipada en la izquierda
c_info = Entity(parent=p_lobby, position=(-.65, -.28))
Entity(parent=c_info, model='quad', scale=(.45, .25), color=C('#090d16cc'), **UI)
Entity(parent=c_info, model='quad', scale=(.45, .005), position=(0, .12), color=C(CYAN), **UI)
texto(c_info, 'EQUIPAMIENTO ACTUAL', (-.2, .08), 1.0, CYAN, origen=(-.5, 0))
m_arma_lobby_nom = texto(c_info, '', (-.2, .02), 1.8, ORO, origen=(-.5, 0))
m_arma_lobby_rar = texto(c_info, '', (-.2, -.04), 1.1, BLANCO, origen=(-.5, 0))
texto(c_info, 'Clic en ¡JUGAR! para elegir arma y desplegar', (-.2, -.09), .8, '#94a3b8', origen=(-.5, 0))

# --- PANEL SELECCIÓN DE ARMA Y DESPLIEGUE (CARDS CON VISTA 3D)
# Fondo semitransparente oscuro
Entity(parent=p_desplegar, model='quad', scale=(2, 1.2), color=C('#050811ee'), z=1, **UI)
texto(p_desplegar, 'SELECCIONA TU ARMA DE DESPLIEGUE', (0, .32), 2.5, ORO)
texto(p_desplegar, 'Elige con qué arma descenderás al campo de batalla', (0, .26), 1.1, '#94a3b8')

tarjetas_armas = []
mini_armas_3d = []


def seleccionar_arma_despliegue(idx):
    S.arma_inicial = idx
    cambiar_arma(idx)
    guardar()
    refrescar_tarjetas_despliegue()


def iniciar_despliegue():
    nueva_partida()


for i, w in enumerate(ARMAS):
    # Base de la tarjeta estilo Fortnite
    card_x = -.63 + i * .42
    card = Entity(parent=p_desplegar, position=(card_x, -.02))

    # Borde y fondo con color de rareza
    Entity(parent=card, model='quad', scale=(.38, .46), color=C(w['col_raro']), **UI)
    fondo_tarjeta = Entity(parent=card, model='quad', scale=(.36, .44), color=C(GRIS_OSCURO), **UI)

    # Cabecera de rareza
    Entity(parent=card, model='quad', scale=(.36, .07), position=(0, .185), color=C(w['col_raro']), **UI)
    texto(card, w['rareza'], (0, .185), 1.0, BLANCO)

    # Nombre
    texto(card, w['n'], (0, .11), 1.3, BLANCO)

    # Foto / Miniatura 3D del arma dentro de la tarjeta
    visor_3d = Entity(parent=card, position=(0, .01, -.2), rotation=(15, -35, 10))
    cuerpo_mini = Entity(parent=visor_3d, model='cube', scale=(.08, .12, w['largo']), color=C(w['col']))
    Entity(parent=visor_3d, model='cube', scale=(.04, .04, .25), position=(0, .02, w['largo'] / 2 + .1), color=C('#111111'))
    mini_armas_3d.append(visor_3d)

    # Estadísticas
    texto(card, f'Daño: {w["dano"]}   |   Cargador: {w["cargador"]}', (0, -.09), .9, '#cbd5e1')
    texto(card, f'Cadencia: {round(1/w["ritmo"], 1)} dps', (0, -.13), .9, '#94a3b8')

    # Botón seleccionar
    btn_sel = Button(parent=card, text='SELECCIONAR', position=(0, -.18), scale=(.32, .06),
                     color=C('#334155'), highlight_color=C('#475569'),
                     on_click=lambda i=i: seleccionar_arma_despliegue(i), **UI)
    tarjetas_armas.append((card, btn_sel, fondo_tarjeta, w['col_raro']))

# Botón gigante para desplegarse
btn_desplegar = Button(parent=p_desplegar, text='', position=(0, -.36), scale=(.55, .11),
                       color=C(ORO), highlight_color=C('#ffe066'), on_click=iniciar_despliegue, **UI)
texto(btn_desplegar, '¡CONFIRMAR Y DESPLEGARSE!', (0, .01), 1.8, '#000000')
Button(parent=p_desplegar, text='VOLVER AL LOBBY', position=(-.7, -.42), scale=(.24, .06),
       color=C('#1e293b'), on_click=lambda: mostrar_panel('lobby'), **UI)


def refrescar_tarjetas_despliegue():
    for i, (card, btn, fondo_t, col_r) in enumerate(tarjetas_armas):
        es_activa = (i == S.arma_inicial)
        if es_activa:
            fondo_t.color = C('#1e293b')
            btn.color = C(col_r)
            btn.text = '✓ EQUIPADA'
            card.scale = 1.05
        else:
            fondo_t.color = C(GRIS_OSCURO)
            btn.color = C('#1e293b')
            btn.text = 'EQUIPAR'
            card.scale = 1.0

    w = ARMAS[S.arma_inicial]
    poner(m_arma_lobby_nom, w['n'])
    poner(m_arma_lobby_rar, f'Rareza: {w["rareza"]}')


# --- PANEL ARSENAL (Inspección detallada)
Entity(parent=p_arsenal, model='quad', scale=(2, 1.2), color=C('#050811f5'), z=1, **UI)
texto(p_arsenal, 'ARSENAL COMPLETO', (0, .32), 2.5, ORO)
m_arsenal_desc = texto(p_arsenal, '', (0, .24), 1.2, '#94a3b8')
b_arsenal_lista = []


def refrescar_arsenal_completo():
    w = ARMAS[S.arma_inicial]
    m_arsenal_desc.text = f'Inspeccionando armamento militar reglamentario. Arma activa: {w["n"]}'
    for i, b in enumerate(b_arsenal_lista):
        b.color = C(ARMAS[i]['col_raro']) if i == S.arma_inicial else C('#1e293b')


for i, w in enumerate(ARMAS):
    b = Button(parent=p_arsenal, text=f'{w["rareza"]}\n{w["n"]}', position=(-.54 + i * .36, .05),
               scale=(.32, .22), color=C('#1e293b'), highlight_color=C('#334155'),
               on_click=lambda i=i: (seleccionar_arma_despliegue(i), refrescar_arsenal_completo()), **UI)
    b_arsenal_lista.append(b)

Button(parent=p_arsenal, text='VOLVER', position=(0, -.3), scale=(.3, .07),
       color=C('#1e293b'), on_click=lambda: mostrar_panel('lobby'), **UI)

# --- PANEL CONFIGURACIÓN
Entity(parent=p_config, model='quad', scale=(2, 1.2), color=C('#050811f5'), z=1, **UI)
texto(p_config, 'CONFIGURACIÓN DE COMBATE', (0, .32), 2.5, ORO)
DIFICULTADES = [('Fácil', .6), ('Normal', 1.0), ('Difícil', 1.5)]


def fila_config(y, nombre, menos, mas):
    texto(p_config, nombre, (-.5, y), 1.4, origen=(-.5, 0))
    Button(p_config, text='-', position=(.15, y), scale=(.06, .06), color=C('#1e293b'), on_click=menos, **UI)
    val = texto(p_config, '', (.35, y), 1.4)
    Button(p_config, text='+', position=(.55, y), scale=(.06, .06), color=C('#1e293b'), on_click=mas, **UI)
    return val


def cambiar_cfg(campo, delta):
    if campo == 'sens':
        S.sens = max(10, min(100, S.sens + delta))
    elif campo == 'fov':
        S.fov = max(70, min(110, S.fov + delta))
        camera.fov = S.fov
    else:
        S.dif = max(0, min(2, S.dif + delta))
    refrescar_cfg_txt()
    guardar()


def borrar_record():
    S.record_ola = S.record_bajas = 0
    guardar()
    refrescar_cfg_txt()
    lobby_maniqui.actualizar_arma(S.arma_inicial)


v_sens = fila_config(.14, 'Sensibilidad del ratón', lambda: cambiar_cfg('sens', -5), lambda: cambiar_cfg('sens', 5))
v_fov = fila_config(.03, 'Campo de visión (FOV)', lambda: cambiar_cfg('fov', -5), lambda: cambiar_cfg('fov', 5))
v_dif = fila_config(-.08, 'Dificultad de los enemigos', lambda: cambiar_cfg('dif', -1), lambda: cambiar_cfg('dif', 1))


def refrescar_cfg_txt():
    v_sens.text = str(S.sens)
    v_fov.text = str(S.fov)
    v_dif.text = DIFICULTADES[S.dif][0]
    perfil_record.text = f'Récord: Ola {S.record_ola}'


Button(p_config, text='RESTABLECER RÉCORD', position=(0, -.2), scale=(.38, .06), color=C('#991b1b'), on_click=borrar_record, **UI)
Button(p_config, text='VOLVER', position=(0, -.3), scale=(.3, .07), color=C('#1e293b'), on_click=lambda: mostrar_panel('lobby'), **UI)

# --- PANEL PAUSA Y GAME OVER
Entity(parent=p_pausa, model='quad', scale=(2, 1.2), color=C('#050811e5'), z=1, **UI)
pausa_titulo = texto(p_pausa, 'PAUSA', (0, .28), 3.5, ORO)
pausa_sub = texto(p_pausa, 'Combate suspendido temporalmente', (0, .18), 1.2, '#94a3b8')
b_pausa_reanudar = Button(p_pausa, text='CONTINUAR', position=(0, .02), scale=(.4, .08), color=C('#22c55e'), on_click=lambda: entrar_al_juego(), **UI)
Button(p_pausa, text='SALIR AL MENÚ PRINCIPAL', position=(0, -.12), scale=(.4, .08), color=C('#1e293b'), on_click=lambda: volver_al_menu(), **UI)


# ------------------------------------------------------------------ CONTROL DEL FLUJO
def abrir_menu():
    S.modo = 'menu'
    menu.enabled = True
    hud.enabled = False
    top_bar.enabled = True
    mouse.locked = False
    jugador.enabled = False

    # Situar la cámara en el lobby frente al maniquí 3D
    camera.position = LOBBY_POS + Vec3(0, 1.6, -3.8)
    camera.rotation = (5, 0, 0)
    camera.fov = 70

    mostrar_panel('lobby')
    refrescar_cfg_txt()


def volver_al_menu():
    limpiar()
    abrir_menu()


def entrar_al_juego():
    S.modo = 'juego'
    S.enfriamiento = .3
    menu.enabled = False
    hud.enabled = True
    mouse.locked = True
    jugador.enabled = True
    camera.fov = S.fov
    cambiar_arma(S.arma_inicial)


def mensaje(txt):
    poner(t_msg, txt)
    S.t_msg = 1.8


def limpiar():
    for e in S.enemigos + S.recogibles:
        destroy(e)
    S.enemigos.clear()
    S.recogibles.clear()


# ------------------------------------------------------------------ COMBATE Y EFECTOS
class Efectos(Entity):
    """Chispas y trazadores reciclados: en vez de crear y destruir entidades
    (y animaciones) en cada disparo, se reusan y se mueven todas juntas acá."""
    def __init__(self):
        super().__init__()
        self.libres = {'chispa': [], 'trazador': []}
        self.activos = []      # [entidad, tipo, inicio, recorrido, vida, t]

    def tomar(self, tipo, col):
        libres = self.libres[tipo]
        if libres:
            e = libres.pop()
            e.enabled = True
        else:
            e = Entity(model='cube', add_to_scene_entities=False, **UI)
        e.color = col
        return e

    def update(self):
        dt = time.dt
        quedan = []
        for q in self.activos:
            e, tipo, inicio, recorrido, vida, t = q
            t += dt
            if t >= vida:
                e.enabled = False
                self.libres[tipo].append(e)
                continue
            q[5] = t
            if recorrido is not None:
                e.position = inicio + recorrido * curve.out_quad(t / vida)
            quedan.append(q)
        self.activos = quedan


efectos = Efectos()


def chispas(pos, col, n, vel, tam, vida=.5):
    col = C(col)
    pos = Vec3(*pos)
    for _ in range(n):
        p = efectos.tomar('chispa', col)
        p.position = pos
        p.scale = tam
        d = Vec3(random.uniform(-1, 1), random.uniform(0, 1.2), random.uniform(-1, 1)).normalized()
        efectos.activos.append([p, 'chispa', pos, d * random.uniform(.4, 1) * vel * vida, vida, 0.0])


def trazador(a, b, col):
    t = efectos.tomar('trazador', C(col))
    t.position = (a + b) / 2
    t.scale = (.03, .03, (b - a).length())
    t.look_at(b)
    efectos.activos.append([t, 'trazador', None, None, .06, 0.0])


def explosion(p):
    chispas(p, '#ff9a30', 35, 9, .3, .7)
    chispas(p + Vec3(0, .5, 0), '#2a2522', 20, 4, .5, 1.2)
    bola = Entity(model='sphere', position=p + Vec3(0, 1, 0), scale=1, color=C('#ffb050'), **UI)
    bola.animate_scale(7, .25)
    bola.fade_out(duration=.3)
    destroy(bola, delay=.35)
    for e in list(S.enemigos):
        d = (e.position - p).length()
        if d < 9:
            e.golpe(160 * (1 - d / 9), False, e.position + Vec3(0, 1.2, 0))
    d = (jugador.position - p).length()
    if d < 8:
        dano_jugador(60 * (1 - d / 8))


class Enemigo(Entity):
    def __init__(self, pos, velocidad, preferida):
        super().__init__(position=pos + Vec3(0, .1, 0))
        self.hp, self.vel, self.pref = 100.0, velocidad, preferida
        self.vivo = True
        self.cool = 1.5
        self.lado = random.choice((-1, 1))
        self.t_lado = 2.0
        self.t_vista = 0.0
        self.ve = False
        self.t_obstaculo = 0.0
        self.obstaculo = False
        uniforme = random.choice(('#334155', '#1e293b', '#0f172a'))
        self.cuerpo = Entity(parent=self, model='cube', color=C(uniforme), position=(0, 1.1, 0), scale=(.55, .9, .35), collider='box')
        self.cabeza = Entity(parent=self, model='cube', color=C('#e2e8f0'), position=(0, 1.75, 0), scale=(.32, .32, .32), collider='box')
        Entity(parent=self, model='cube', color=C('#ef4444'), position=(0, 1.8, .17), scale=(.2, .08, .05), **UI)  # visor rojo
        Entity(parent=self, model='cube', color=C('#020617'), position=(0, .35, 0), scale=(.4, .7, .28))
        Entity(parent=self, model='cube', color=C('#1c1e1f'), position=(.2, 1.2, .4), scale=(.08, .1, .7))
        for parte in (self.cuerpo, self.cabeza):
            parte.enemigo = self
        S.enemigos.append(self)

    def update(self):
        if S.modo != 'juego' or not self.vivo:
            return
        dt = time.dt
        self.cool -= dt
        self.t_lado -= dt
        self.t_vista -= dt
        self.t_obstaculo -= dt
        dx, dz = jugador.x - self.x, jugador.z - self.z
        d = math.hypot(dx, dz) or .001
        dir = Vec3(dx / d, 0, dz / d)
        lateral = Vec3(dir.z * self.lado, 0, -dir.x * self.lado)

        if self.t_lado <= 0:
            self.lado = -self.lado
            self.t_lado = random.uniform(1.5, 3.5)
        if self.t_vista <= 0:
            self.t_vista = .3
            ojos = self.position + Vec3(0, 1.4, 0)
            hacia = jugador.position + Vec3(0, 1.5, 0) - ojos
            self.ve = not raycast(ojos, hacia.normalized(), distance=hacia.length(), traverse_target=mundo).hit

        mv = lateral * .6 if (d < self.pref and self.ve) else dir
        if self.t_obstaculo <= 0:      # no hace falta mirar cada frame si hay una pared adelante
            self.t_obstaculo = .1
            self.obstaculo = raycast(self.position + Vec3(0, 1, 0), mv.normalized(), distance=1.5, traverse_target=mundo).hit
        if self.obstaculo:
            mv = lateral
        if d > 1.5:
            self.position += mv * self.vel * dt
        self.x = max(-58, min(58, self.x))
        self.z = max(-58, min(58, self.z))
        self.rotation_y = math.degrees(math.atan2(dx, dz))

        if self.ve and d < 60 and self.cool <= 0:
            self.disparar(d)

    def disparar(self, d):
        self.cool = max(.4, random.uniform(.9, 1.7) - min(.5, S.ola * .04))
        r = math.radians(self.rotation_y)
        origen = self.position + Vec3(math.sin(r) * .9, 1.25, math.cos(r) * .9)
        punteria = max(.08, min(.55, .5 - d / 70 + S.ola * .012))
        blanco = jugador.position + Vec3(0, 1.5, 0)
        acierta = random.random() < punteria
        if not acierta:
            blanco += Vec3(random.uniform(-2, 2), random.uniform(-1, 1), random.uniform(-2, 2))
        trazador(origen, blanco, '#ff4757')
        if acierta:
            dano_jugador(random.uniform(5, 9) * (1 + S.ola * .03) * DIFICULTADES[S.dif][1])

    def golpe(self, dano, cabeza, punto):
        if not self.vivo:
            return
        self.hp -= dano
        chispas(punto, '#ff4757', 8, 3, .06, .5)
        S.marcador = 1.0
        if self.hp <= 0:
            self.morir(cabeza)

    def morir(self, cabeza):
        self.vivo = False
        S.enemigos.remove(self)
        self.cuerpo.collider = None
        self.cabeza.collider = None
        self.animate('rotation_x', -90, duration=.4)
        destroy(self, delay=6)
        S.bajas += 1
        S.restantes -= 1
        if cabeza:
            mensaje('¡DISPARO A LA CABEZA!')
        if random.random() < .25:
            Recogible(self.position)


class Granada(Entity):
    def __init__(self):
        super().__init__(model='sphere', scale=.2, color=C('#2ed573'), position=camera.world_position)
        self.v = camera.forward * 17 + Vec3(0, 4, 0)
        self.t = 1.8

    def update(self):
        if S.modo != 'juego':
            return
        dt = time.dt
        self.v = self.v + Vec3(0, -22 * dt, 0)
        mov = self.v * dt
        if raycast(self.position, self.v.normalized(), distance=mov.length() + .15, traverse_target=mundo).hit:
            self.v = Vec3(-self.v.x * .4, self.v.y, -self.v.z * .4)
        else:
            self.position += mov
        if self.y < .1:
            self.y = .1
            self.v = Vec3(self.v.x * .6, -self.v.y * .4, self.v.z * .6)
        self.t -= dt
        if self.t <= 0:
            explosion(self.position)
            destroy(self)


class Recogible(Entity):
    def __init__(self, pos):
        self_salud = random.random() < .5
        super().__init__(model='cube', position=pos + Vec3(0, .4, 0), scale=(.5, .35, .4),
                         color=C('#00d2ff' if self_salud else '#ffa502'))
        self.salud = self_salud
        S.recogibles.append(self)

    def update(self):
        if S.modo != 'juego':
            return
        self.rotation_y += 90 * time.dt
        if (jugador.position - self.position).length() < 1.8:
            if self.salud:
                S.hp = min(100, S.hp + 35)
                mensaje('Escudo / Salud +35')
            else:
                for i, a in enumerate(ARMAS):
                    S.reserva[i] += a['cargador'] * 2
                mensaje('Munición pesada reabastecida')
            S.recogibles.remove(self)
            destroy(self)


def dano_jugador(n):
    S.hp -= n
    S.sangre = 1.0
    if S.hp <= 0 and S.modo == 'juego':
        S.modo = 'fin'
        sub = f'Alcanzaste la Oleada {S.ola} eliminando a {S.bajas} hostiles.'
        if (S.ola, S.bajas) > (S.record_ola, S.record_bajas):
            S.record_ola, S.record_bajas = S.ola, S.bajas
            guardar()
            sub += '\n¡NUEVO RÉCORD DE COMBATE!'
        pausa_titulo.text = 'CAÍSTE EN COMBATE'
        pausa_titulo.color = C('#ef4444')
        pausa_sub.text = sub
        b_pausa_reanudar.text = 'JUGAR DE NUEVO'
        b_pausa_reanudar.on_click = lambda: nueva_partida()
        menu.enabled = True
        hud.enabled = False
        top_bar.enabled = False
        mouse.locked = False
        jugador.enabled = False
        mostrar_panel('pausa')


def siguiente_ola():
    S.ola += 1
    S.por_aparecer = 4 + S.ola * 3
    S.restantes = S.por_aparecer
    if S.ola > 1:
        for i, a in enumerate(ARMAS):
            S.reserva[i] += a['cargador']
        S.hp = min(100, S.hp + 20)
        S.granadas = min(4, S.granadas + 1)
    mensaje(f'OLEADA {S.ola}')


def aparecer():
    lejos = [p for p in PUNTOS if (p - jugador.position).length() > 28] or PUNTOS
    Enemigo(random.choice(lejos), min(4.2, 2.2 + S.ola * .15) * random.uniform(.9, 1.1), random.uniform(12, 22))


def nueva_partida():
    limpiar()
    S.ola, S.bajas, S.hp, S.granadas = 0, 0, 100.0, 3
    S.t_aparicion = S.t_ola = 0.0
    S.municion = [a['cargador'] for a in ARMAS]
    S.reserva = [a['reserva'] for a in ARMAS]
    jugador.position = (0, .1, 0)
    jugador.rotation_y = 0
    jugador.camera_pivot.rotation_x = 0
    siguiente_ola()
    entrar_al_juego()


def disparar():
    a = ARMAS[S.arma]
    if S.recargando or S.enfriamiento > 0:
        return
    if S.municion[S.arma] <= 0:
        recargar()
        return
    S.municion[S.arma] -= 1
    S.enfriamiento = a['ritmo']
    jugador.camera_pivot.rotation_x -= a['retroceso'] * .3 + random.uniform(0, .2)
    jugador.rotation_y += random.uniform(-.2, .2)
    arma_primera_persona.z = .6
    arma_primera_persona.animate_z(.7, .1)
    fogonazo.enabled = True
    invoke(setattr, fogonazo, 'enabled', False, delay=.05)

    origen = camera.world_position
    boca = origen + camera.forward * 1.0 + camera.right * .25 - camera.up * .2
    moviendo = any(held_keys[k] for k in 'wasd')
    disp = a['dispersion'] + (.012 if moviendo else 0)
    for _ in range(a['perdigones']):
        d = (camera.forward + camera.right * random.uniform(-disp, disp) + camera.up * random.uniform(-disp, disp)).normalized()
        fin = origen + d * 120
        tiro = raycast(origen, d, distance=200, ignore=[jugador])
        if tiro.hit:
            fin = tiro.world_point
            enemigo = getattr(tiro.entity, 'enemigo', None)
            if enemigo:
                cabeza = tiro.entity is enemigo.cabeza
                enemigo.golpe(min(120, a['dano'] * 2.8) if cabeza else a['dano'], cabeza, fin)
            else:
                chispas(fin, '#ffc060', 5, 5, .04, .35)
        trazador(boca, fin, '#ffd28a')


def recargar():
    a = ARMAS[S.arma]
    if S.recargando or S.municion[S.arma] >= a['cargador'] or S.reserva[S.arma] <= 0:
        return
    S.recargando = True
    S.t_recarga = a['recarga']
    arma_primera_persona.animate_y(-.5, a['recarga'] / 2, curve=curve.out_quad)
    arma_primera_persona.animate_y(-.25, a['recarga'] / 2, delay=a['recarga'] / 2, curve=curve.in_quad)


def lanzar_granada():
    if S.granadas <= 0 or S.t_granada > 0:
        return
    S.granadas -= 1
    S.t_granada = .8
    Granada()


def pausar():
    S.modo = 'pausa'
    pausa_titulo.text = 'PAUSA'
    pausa_titulo.color = C(ORO)
    pausa_sub.text = 'Combate suspendido. Ajusta tu táctica.'
    b_pausa_reanudar.text = 'CONTINUAR'
    b_pausa_reanudar.on_click = lambda: entrar_al_juego()
    menu.enabled = True
    hud.enabled = False
    top_bar.enabled = False
    mouse.locked = False
    jugador.enabled = False
    mostrar_panel('pausa')


# ------------------------------------------------------------------ INPUT & UPDATE
def input(key):
    if S.modo == 'juego':
        if key == 'left mouse down' and not ARMAS[S.arma]['auto']:
            disparar()
        elif key == 'r':
            recargar()
        elif key == 'g':
            lanzar_granada()
        elif key in ('1', '2', '3', '4'):
            cambiar_arma(int(key) - 1)
        elif key == 'scroll up':
            cambiar_arma((S.arma - 1) % len(ARMAS))
        elif key == 'scroll down':
            cambiar_arma((S.arma + 1) % len(ARMAS))
        elif key in ('escape', 'p'):
            pausar()
    elif key in ('escape', 'p'):
        if S.modo == 'pausa':
            entrar_al_juego()
        elif S.panel != 'lobby':
            mostrar_panel('lobby')


def update():
    dt = time.dt

    # Rotación suave de los modelos de armas 3D en las tarjetas
    if S.modo == 'menu' and S.panel == 'desplegar':
        for mini in mini_armas_3d:
            mini.rotation_y += dt * 35

    if S.modo != 'juego':
        return

    a = ARMAS[S.arma]
    corre = held_keys['left shift'] or held_keys['shift']
    jugador.speed = (8.5 if corre else 5.5) * (.85 if S.recargando else 1)
    S.enfriamiento -= dt
    S.t_granada -= dt

    if held_keys['left mouse'] and a['auto']:
        disparar()

    if S.recargando:
        S.t_recarga -= dt
        if S.t_recarga <= 0:
            S.recargando = False
            n = min(a['cargador'] - S.municion[S.arma], S.reserva[S.arma])
            S.municion[S.arma] += n
            S.reserva[S.arma] -= n

    zoom = held_keys['right mouse']
    camera.fov = lerp(camera.fov, a['zoom'] if zoom else S.fov, min(1, dt * 12))
    jugador.mouse_sensitivity = Vec2(S.sens, S.sens) * (camera.fov / S.fov)
    arma_primera_persona.visible = not (S.arma == 3 and zoom and camera.fov < 45)

    # Oleadas
    S.t_aparicion -= dt
    if S.por_aparecer > 0 and len(S.enemigos) < min(8, 3 + S.ola) and S.t_aparicion <= 0:
        aparecer()
        S.por_aparecer -= 1
        S.t_aparicion = random.uniform(.8, 2)
    if S.restantes <= 0 and S.t_ola <= 0:
        S.t_ola = 4
    if S.t_ola > 0:
        S.t_ola -= dt
        if S.t_ola <= 0:
            siguiente_ola()

    # HUD
    S.sangre = max(0, S.sangre - dt * .9)
    S.marcador = max(0, S.marcador - dt * 5)
    S.t_msg -= dt
    if S.t_msg <= 0:
        poner(t_msg, '')
    sangre.alpha = min(1, S.sangre + (.35 if S.hp < 30 else 0))
    marca.enabled = S.marcador > 0
    barra.scale_x = .3 * max(0, S.hp) / 100
    poner(t_ola, f'OLEADA {S.ola}')
    poner(t_rest, f'ENEMIGOS EN EL SECTOR: {S.restantes}' if S.restantes > 0 else '¡ZONA DESPEJADA!')
    poner(t_mun, ('RECARGANDO' if S.recargando else str(S.municion[S.arma])) + f' / {S.reserva[S.arma]}')
    poner(t_gran, f'GRANADAS: {S.granadas}')
    poner(t_armas, '   '.join(
        ('[{} {}]' if i == S.arma else '{} {}').format(i + 1, w['n'])
        for i, w in enumerate(ARMAS)))


# ------------------------------------------------------------------ ARRANQUE
construir_mundo()
S.municion = [a['cargador'] for a in ARMAS]
S.reserva = [a['reserva'] for a in ARMAS]
cambiar_arma(S.arma_inicial)
abrir_menu()
app.run()
