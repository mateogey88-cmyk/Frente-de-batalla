"""
FRENTE DE BATALLA - shooter 3D en primera persona (Python + Ursina)

    pip install ursina
    python frente_de_batalla.py

W A S D mover | Shift correr | Espacio saltar | Mouse apuntar
Clic disparar | Clic derecho zoom | 1-4 o rueda: cambiar arma
R recargar | G granada | Esc o P pausa
Battle Royale: Z pared | X piso | C rampa | Q salir de construcción

Menú: JUGAR | ARMERÍA (mejoras) | CASILLERO (tus skins) | TIENDA (skins del día) | AJUSTES

Las opciones, tus chapas (la moneda del juego), las mejoras de armas, las skins y el récord se guardan en
frente_de_batalla.json (en tu carpeta de usuario).
"""
import json
import math
import os
import random
from time import time as ahora      # reloj real (la tienda cambia todos los días)

from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from panda3d.core import ClockObject, AntialiasAttrib, loadPrcFileData

C = color.hex          # C('#ff9a30') -> color
ORO, CREMA, GRIS = '#d9a441', '#f1e7d0', '#b9ab8c'

# ------------------------------------------------------------------ armas
# Para agregar un arma nueva: sumá una línea acá y su modelo en armar_arma().
ARMAS = [
    dict(n='Fusil',         dano=34,  ritmo=.095, cargador=30, reserva=120, recarga=1.7, dispersion=.006,  perdigones=1, auto=True,  retroceso=1.0, zoom=60),
    dict(n='Pistola',       dano=30,  ritmo=.2,   cargador=12, reserva=72,  recarga=1.1, dispersion=.003,  perdigones=1, auto=False, retroceso=.6,  zoom=70),
    dict(n='Escopeta',      dano=15,  ritmo=.8,   cargador=6,  reserva=36,  recarga=2.4, dispersion=.045,  perdigones=9, auto=False, retroceso=2.2, zoom=75),
    dict(n='Francotirador', dano=100, ritmo=1.1,  cargador=5,  reserva=25,  recarga=2.5, dispersion=.0005, perdigones=1, auto=False, retroceso=2.5, zoom=20),
]
DESC = ['Automático. Equilibrado.', 'Semiautomática. Rápida y precisa.',
        '9 perdigones. Letal de cerca.', 'Un tiro, una baja. Clic derecho: zoom.']
BOCAS = [.67, .26, .78, 1.07]                       # dónde sale el disparo (largo del arma)
ARMA_FP = [(.22, -.2, .45, .9), (.17, -.16, .35, 1.1), (.22, -.2, .4, .85), (.2, -.19, .3, .62)]  # x, y, z, escala en pantalla
NIVEL_MAX = 5
MEJORAS = [('Daño', 'dano'), ('Cargador', 'cargador'), ('Cadencia', 'ritmo'), ('Recarga', 'recarga')]
DIFICULTADES = [('Fácil', .6), ('Normal', 1.0), ('Difícil', 1.5)]   # (nombre, daño que te hacen)

# --- Skins (trajes del soldado). Para agregar una: sumá un dict a SKINS (se ve sola en casillero y tienda).
# r = rareza (0 común, 1 rara, 2 épica, 3 legendaria). Opcionales: lentes, cresta, hombreras, neon, guante.
# 'neon' además pinta el color de tus balas. La skin 0 es gratis y siempre la tenés.
RAREZA = [('COMÚN', '#9aa3a8'), ('RARA', '#4aa3ff'), ('ÉPICA', '#b25cff'), ('LEGENDARIA', '#ffae2a')]
SKINS = [
    dict(n='Soldado', r=0, precio=0, d='El uniforme de siempre.\nViene con el juego.',
         ropa='#3a4044', chaleco='#24282b', casco='#2c3033', pantalon='#30363a'),
    dict(n='Bosque', r=0, precio=300, d='Camuflaje verde para\nmoverte entre los árboles.',
         ropa='#4a5339', chaleco='#2f3826', casco='#3e4632', pantalon='#3f4733'),
    dict(n='Desierto', r=0, precio=300, d='Tonos arena para\npatrullar terreno seco.',
         ropa='#74694b', chaleco='#524a36', casco='#5e5640', pantalon='#6b6147'),
    dict(n='Nieve', r=0, precio=350, d='Blanco invernal.\nPasás desapercibido.',
         ropa='#d9dee2', chaleco='#aab4bc', casco='#c7ced4', pantalon='#b8c0c6', lentes='#2a3b4a'),
    dict(n='Comando Rojo', r=1, precio=600, d='Fuerzas especiales.\nVisor rojo y hombreras.',
         ropa='#6b1f1f', chaleco='#3a1010', casco='#4a1414', pantalon='#2f2f33', lentes='#ff5a4a', hombreras='#3a1010'),
    dict(n='Cazador Azul', r=1, precio=650, d='Operador nocturno.\nVisor celeste y hombreras.',
         ropa='#1f3f6b', chaleco='#10243a', casco='#14304a', pantalon='#2a2f38', lentes='#6ad0ff', hombreras='#10243a'),
    dict(n='Sombra Neón', r=2, precio=1000, d='Sigilo urbano.\nTus balas brillan en cian.',
         ropa='#15151c', chaleco='#0d0d12', casco='#0d0d12', pantalon='#15151c', lentes='#4fe3ff', neon='#4fe3ff', guante='#0d0d12'),
    dict(n='Samurái', r=2, precio=1100, d='Armadura de guerrero.\nCasco dorado con cresta.',
         ropa='#7a1d1d', chaleco='#2a2a2a', casco='#b8862a', pantalon='#2a1a1a', lentes='#ffd070', cresta='#a01818', hombreras='#b8862a'),
    dict(n='Punk', r=2, precio=1000, d='Cresta rosa y mucha actitud.\nTus balas son rosas.',
         ropa='#2a1a3a', chaleco='#3a1a4a', casco='#1c1224', pantalon='#1c1c26', lentes='#ffe14a', cresta='#ff4fd8', neon='#ff4fd8'),
    dict(n='Robot', r=3, precio=1500, d='Máquina de guerra.\nTus balas son rojas.',
         ropa='#8a9099', chaleco='#5a6068', casco='#a0a8b0', pantalon='#6a7078', lentes='#ff3030', neon='#ff3030', guante='#3a3f45', hombreras='#5a6068'),
    dict(n='Rey Dorado', r=3, precio=1800, d='Oro macizo de pies a cabeza.\nTus balas son doradas.',
         ropa='#c9a030', chaleco='#8a6a18', casco='#e8c040', pantalon='#7a5a14', lentes='#ffffff', neon='#ffe070', cresta='#e8c040', hombreras='#e8c040', guante='#7a5a14'),
    dict(n='Fantasma', r=3, precio=1700, d='Etéreo y silencioso.\nTus balas son violetas.',
         ropa='#e8e8f0', chaleco='#b8b8c8', casco='#f0f0f8', pantalon='#c8c8d8', lentes='#a56bff', neon='#a56bff', guante='#b8b8c8'),
    dict(n='Urbano', r=0, precio=350, d='Gris ciudad.\nSe pierde entre los escombros.',
         ropa='#4a4f58', chaleco='#2c3038', casco='#3a3f48', pantalon='#3a3d44'),
    dict(n='Pirata', r=1, precio=700, d='Capitán de los mares.\nHombreras de cuero.',
         ropa='#5a2a1a', chaleco='#2a1a10', casco='#101010', pantalon='#2a2018', lentes='#ffd070', hombreras='#7a4a22'),
    dict(n='Astronauta', r=1, precio=750, d='Directo desde la órbita.\nVisor ámbar.',
         ropa='#e8eaee', chaleco='#c8ccd2', casco='#f2f4f8', pantalon='#d8dce2', lentes='#ffb030', hombreras='#9aa0aa', guante='#6a7078'),
    dict(n='Ninja', r=1, precio=700, d='Silencioso y letal.\nOjos rojos en la noche.',
         ropa='#1a1a1e', chaleco='#101014', casco='#101014', pantalon='#1a1a1e', lentes='#ff3030'),
    dict(n='Magma', r=2, precio=1200, d='Forjado en lava.\nTus balas son naranjas.',
         ropa='#2a1410', chaleco='#4a1a10', casco='#1a0c0a', pantalon='#2a1410', lentes='#ff9a30', neon='#ff7a1c', cresta='#ff5a10'),
    dict(n='Hielo', r=2, precio=1150, d='Frío como el invierno.\nTus balas son celestes.',
         ropa='#4a7fa8', chaleco='#2a5278', casco='#8ad0f0', pantalon='#3a6a90', lentes='#ffffff', neon='#a8ecff', cresta='#b8f0ff'),
    dict(n='Tóxico', r=2, precio=1100, d='Radiactivo.\nTus balas son verde ácido.',
         ropa='#2a3a1a', chaleco='#1a2410', casco='#1e2a12', pantalon='#2a3318', lentes='#9aff3a', neon='#8aff2a', hombreras='#1a2410'),
    dict(n='Dragón', r=3, precio=2000, d='Escamas de jade y oro.\nTus balas son doradas.',
         ropa='#1a5a3a', chaleco='#0e3a24', casco='#c9a030', pantalon='#12402a', lentes='#ffd34a', neon='#ffd34a', cresta='#c9a030', hombreras='#c9a030', guante='#0e3a24'),
    dict(n='Galaxia', r=3, precio=1900, d='Polvo de estrellas.\nTus balas son violetas.',
         ropa='#241a4a', chaleco='#150e30', casco='#1a1238', pantalon='#1c1440', lentes='#ff4fd8', neon='#b06bff', cresta='#ff4fd8', hombreras='#3a2a7a', guante='#150e30'),
]
PAG = 12                          # skins por página en el casillero

# --- Gráficos: cada opción es un número que indexa su lista de valores
OPC_G = {
    'pant': ['No', 'Sí'],
    'fps_lim': ['30', '60', '120', 'Ilimitado'],
    'sombras': ['Baja', 'Media', 'Alta'],
    'dist': ['Corta', 'Media', 'Larga'],
    'efectos': ['Bajos', 'Normales', 'Altos'],
    'aa': ['No', 'Sí'],
    'ver_fps': ['No', 'Sí'],
}
FPS_LIM = [30, 60, 120, 0]                         # 0 = sin límite
SOMBRAS = [512, 1024, 2048]                        # resolución de las sombras
DIST = [(25, 80), (45, 150), (80, 260)]            # (dónde empieza la niebla, dónde tapa todo)
EFECTOS = [.4, 1.0, 1.6]                           # cuántas chispas y partículas salen

# --- Battle Royale
N_BOTS = 15                       # soldados rivales (vos sos el 16.º)
LADO, ALTO, COSTO_PIEZA = 4, 3, 10   # tamaño de la grilla de construcción, alto de un piso y costo en materiales
HD = [(0, 1), (1, 0), (0, -1), (-1, 0)]   # hacia dónde mirás: +z, +x, -z, -x
# (radio final, segundos de espera, segundos que tarda en cerrarse, daño por segundo fuera de la zona)
FASES = [(62, 30, 22, 1), (42, 22, 18, 2), (26, 18, 15, 4), (14, 14, 12, 7), (5, 10, 10, 10)]
BEAM = {'arma': '#ffd34a', 'municion': '#ff9a30', 'salud': '#5aff7a', 'materiales': '#6ab7ff', 'granada': '#c8c8c8'}


class S:
    """Todo el estado del juego en un solo lugar."""
    modo = 'menu'                 # menu | juego | pausa | fin
    panel = 'principal'           # principal | armas | config
    # se guardan en el disco
    fov = 90
    sens = 40
    dif = 1
    arma_inicial = 0
    record_ola = 0
    record_bajas = 0
    puntos = 0
    br = 0                        # 0 = oleadas, 1 = battle royale
    mejor_puesto = 0
    mejoras = [[0, 0, 0, 0] for _ in ARMAS]
    skin = 0                      # skin equipada (se guarda)
    skins = [0]                   # skins que tenés (se guarda)
    sel_skin = 0                  # skin que estás mirando en casillero / tienda
    pag_loc = 0                   # página del casillero
    # gráficos (se guardan)
    pant = 0
    fps_lim = 3
    sombras = 1
    dist = 1
    efectos = 1
    aa = 0
    ver_fps = 0
    skin_vista = -1               # skin que muestra ahora el soldado del menú
    t_reloj = 0.0
    # partida
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
    kick = 0.0
    gap = .01
    hp_nivel = -1
    hud_arma = -1
    guardada = None               # posición del jugador mientras está el menú de pausa
    enemigos = []
    recogibles = []
    # battle royale
    tiene = [True, True, True, True]   # qué armas tenés
    materiales = 0
    construyendo = None           # 'pared' | 'piso' | 'rampa' | None
    t_construir = 0.0
    piezas = {}
    fant_ok = None
    en_tormenta = False
    zona_clave = None
    z_estado, z_fase, z_t, z_dur, z_dps = 'final', 0, 0.0, 1.0, 1
    z_r, z_cx, z_cz = 85.0, 0.0, 0.0
    z_r0 = z_x0 = z_z0 = z_r1 = z_x1 = z_z1 = 0.0


def ef(i, mej=None):
    """Estadísticas reales del arma i, con las mejoras aplicadas."""
    n = mej if mej is not None else S.mejoras[i]
    a = dict(ARMAS[i])
    a['dano'] = round(a['dano'] * (1 + .12 * n[0]))
    a['cargador'] = int(a['cargador'] * (1 + .2 * n[1]) + .5)
    a['ritmo'] = a['ritmo'] * (.92 ** n[2])
    a['recarga'] = a['recarga'] * (.9 ** n[3])
    return a


def costo(nivel):
    return 100 + 100 * nivel


def fmt(clave, v):
    if clave == 'ritmo':
        return f'{1 / v:.1f}/s'
    if clave == 'recarga':
        return f'{v:.1f} s'
    return str(v)


# ------------------------------------------------------------------ opciones guardadas
RUTA = os.path.join(os.path.expanduser('~'), 'frente_de_batalla.json')
INTS = ('fov', 'sens', 'dif', 'arma_inicial', 'record_ola', 'record_bajas', 'puntos', 'br', 'mejor_puesto', 'skin', 'pant', 'fps_lim', 'sombras', 'dist', 'efectos', 'aa', 'ver_fps')


def guardar():
    try:
        datos = {k: getattr(S, k) for k in INTS}
        datos['mejoras'] = S.mejoras
        datos['skins'] = list(S.skins)
        with open(RUTA, 'w') as f:
            json.dump(datos, f)
    except Exception:
        pass


def cargar():
    try:
        with open(RUTA) as f:
            datos = json.load(f)
        for k in INTS:
            if k in datos:
                setattr(S, k, int(datos[k]))
        m = datos.get('mejoras')
        if isinstance(m, list) and len(m) == len(ARMAS) and all(isinstance(f, list) and len(f) == 4 for f in m):
            S.mejoras = [[max(0, min(NIVEL_MAX, int(v))) for v in f] for f in m]
        sk = datos.get('skins')
        if isinstance(sk, list):
            S.skins = sorted({int(v) for v in sk if 0 <= int(v) < len(SKINS)} | {0})
    except Exception:
        pass
    S.fov = max(70, min(110, S.fov))
    S.sens = max(10, min(100, S.sens))
    S.dif = max(0, min(2, S.dif))
    S.arma_inicial = max(0, min(len(ARMAS) - 1, S.arma_inicial))
    S.puntos = max(0, S.puntos)
    S.br = 1 if S.br else 0
    for campo, op in OPC_G.items():
        setattr(S, campo, max(0, min(len(op) - 1, getattr(S, campo))))
    if S.skin not in S.skins:
        S.skin = 0
    S.sel_skin = S.skin


cargar()


# ------------------------------------------------------------------ ventana, cielo y luces
if S.aa:
    loadPrcFileData('', 'framebuffer-multisample 1\nmultisamples 4')      # suavizado de bordes (MSAA)
app = Ursina(title='Frente de Batalla', borderless=False)
for nombre in ('fps_counter', 'exit_button', 'entity_counter', 'collider_counter'):
    obj = getattr(window, nombre, None)
    if obj is not None:
        obj.enabled = False
window.color = C('#8a5a40')
if S.aa:
    try:
        scene.setAntialias(AntialiasAttrib.MAuto)
    except Exception:
        pass


def tex(nombre):
    """Devuelve el nombre de una textura si Ursina la trae; si no, None (así nunca falla)."""
    try:
        base = application.package_folder / 'textures'
        for ext in ('.png', '.jpg', '.jpeg'):
            if (base / (nombre + ext)).exists():
                return nombre
    except Exception:
        pass
    return None


T_LADRILLO, T_SUELO, T_RUIDO, T_VINETA = tex('brick'), tex('grass'), tex('noise'), tex('vignette')

UI = {}   # opciones extra para lo que debe verse siempre claro (interfaz, luces)
sol = None
try:
    from ursina.shaders import lit_with_shadows_shader, unlit_shader
    Entity.default_shader = lit_with_shadows_shader
    UI = dict(shader=unlit_shader)
    sol = DirectionalLight(shadows=True)
    sol.look_at(Vec3(.6, -1, .6))
except Exception as e:
    print('Sin iluminación avanzada:', e)
try:
    if tex('sky_sunset'):
        Sky(texture='sky_sunset')
except Exception:
    pass
try:
    scene.fog_color = C('#8a5a40')
    scene.fog_density = (45, 150)
except Exception:
    pass


# ------------------------------------------------------------------ piezas: armas y soldados
def pieza(padre, pos, esc, col, **kw):
    return Entity(parent=padre, model='cube', position=pos, scale=esc, color=C(col), **kw)


_M, _D, _W, _V = '#17191c', '#2c2f34', '#6b4a2b', '#3b4332'
# Cada arma es una lista de cajas: (posición, tamaño, color[, extras]). El frente apunta a +z.
PARTES = [
    [   # fusil de asalto
        ((0, 0, 0), (.06, .085, .36), _D),
        ((0, -.005, .3), (.07, .07, .26), _M),
        ((0, .012, .52), (.022, .022, .2), _M),
        ((0, .012, .63), (.04, .04, .07), _M),
        ((0, -.02, -.3), (.05, .1, .24), _V),
        ((0, -.095, -.07), (.04, .11, .05), _D, dict(rotation_x=10)),
        ((0, -.13, .07), (.045, .17, .075), _M, dict(rotation_x=-8)),
        ((0, .07, 0), (.035, .04, .16), _M),
    ],
    [   # pistola
        ((0, .02, .1), (.04, .05, .24), _D),
        ((0, -.012, .09), (.04, .035, .22), _M),
        ((0, -.09, -.01), (.04, .12, .06), _D, dict(rotation_x=-12)),
        ((0, -.05, .06), (.03, .01, .07), _M),
        ((0, .02, .24), (.02, .02, .04), _M),
        ((0, .052, 0), (.02, .015, .02), _M),
    ],
    [   # escopeta
        ((0, 0, 0), (.065, .085, .28), _D),
        ((0, .02, .5), (.04, .04, .55), _M),
        ((0, -.025, .45), (.035, .035, .42), _M),
        ((0, -.03, .34), (.065, .055, .18), _W),
        ((0, -.03, -.3), (.055, .12, .3), _W),
        ((0, -.08, -.1), (.04, .1, .05), _D),
        ((0, .045, .76), (.012, .025, .012), _M),
    ],
    [   # francotirador
        ((0, 0, .05), (.055, .08, .42), _M),
        ((0, -.02, -.33), (.055, .11, .32), _V),
        ((0, .04, -.3), (.05, .04, .18), _V),
        ((0, .012, .65), (.028, .028, .75), _M),
        ((0, .012, 1.03), (.045, .045, .08), _M),
        ((0, .085, .08), (.05, .05, .3), _D),
        ((0, .085, .26), (.065, .065, .07), _D),
        ((0, .085, -.07), (.058, .058, .06), _D),
        ((.055, .02, -.05), (.05, .015, .015), _M),
        ((0, -.09, .07), (.045, .1, .09), _M),
        ((0, -.09, -.12), (.04, .1, .05), _D),
    ],
]
GUANTES = [[(0, -.115, -.07), (0, -.03, .3)], [(0, -.1, -.02), (0, -.05, .06)],
           [(0, -.14, -.1), (0, -.04, .34)], [(0, -.115, -.12), (0, -.04, .2)]]


def armar_arma(padre, i, manos=False, guante='#101112'):
    """Modelo 3D de cada arma, armado con las cajas de PARTES."""
    g = Entity(parent=padre)
    for parte in PARTES[i]:
        pieza(g, parte[0], parte[1], parte[2], **(parte[3] if len(parte) > 3 else {}))
    if manos:      # guantes (solo en primera persona)
        pieza(g, GUANTES[i][0], (.065, .07, .09), guante)
        pieza(g, GUANTES[i][1], (.075, .06, .11), guante)
    return g


PALETAS = {
    'negro': dict(ropa='#3a4044', chaleco='#24282b', casco='#2c3033', pantalon='#30363a'),
    'verde': dict(ropa='#4a5339', chaleco='#2f3826', casco='#3e4632', pantalon='#3f4733'),
    'arena': dict(ropa='#74694b', chaleco='#524a36', casco='#5e5640', pantalon='#6b6147'),
}


def construir_soldado(padre, paleta='negro', arma_i=0):
    """Soldado táctico: casco, máscara de gas, chaleco, radio y botas. Sirve para enemigos y para el menú."""
    r = Entity(parent=padre)
    P = PALETAS[paleta] if isinstance(paleta, str) else paleta     # nombre de paleta o un dict de skin
    NEG, GUANTE = '#17191b', P.get('guante', '#101112')
    piernas = []
    for lado in (-1, 1):
        piv = Entity(parent=r, position=(lado * .12, .92, 0))   # la cadera: de acá se mueve la pierna
        pieza(piv, (0, -.4, 0), (.19, .8, .23), P['pantalon'])
        pieza(piv, (0, -.84, .05), (.18, .24, .34), NEG)         # bota
        piernas.append(piv)
    pieza(r, (0, .94, 0), (.5, .1, .3), NEG)                     # cinturón
    pieza(r, (0, 1.22, 0), (.5, .58, .3), P['ropa'])             # torso
    pieza(r, (0, 1.26, .02), (.56, .46, .37), P['chaleco'])      # chaleco
    pieza(r, (-.1, 1.12, .21), (.13, .13, .07), NEG)             # cargadores
    pieza(r, (.1, 1.12, .21), (.13, .13, .07), NEG)
    pieza(r, (0, 1.7, 0), (.26, .28, .26), NEG)                  # cabeza (pasamontañas)
    pieza(r, (0, 1.86, 0), (.33, .15, .35), P['casco'])          # casco
    pieza(r, (0, 1.66, .14), (.19, .15, .1), '#0e0f10')          # máscara
    pieza(r, (0, 1.59, .2), (.08, .08, .09), '#2c2e30')          # filtro
    pieza(r, (0, 1.71, .195), (.17, .05, .02), P.get('lentes', '#5d8794'), **UI)  # lentes
    if P.get('cresta'):                                          # cresta sobre el casco
        pieza(r, (0, 2.0, -.02), (.07, .16, .3), P['cresta'])
    if P.get('hombreras'):
        for lado in (-1, 1):
            pieza(r, (lado * .36, 1.5, .06), (.2, .1, .2), P['hombreras'])
    if P.get('neon'):                                            # líneas luminosas
        pieza(r, (0, .95, .165), (.52, .04, .02), P['neon'], **UI)
        pieza(r, (0, 1.4, .215), (.4, .03, .02), P['neon'], **UI)
    pieza(r, (.2, 1.42, -.12), (.08, .13, .06), NEG)             # radio
    pieza(r, (.2, 1.7, -.12), (.014, .5, .014), NEG)             # antena
    for lado in (-1, 1):
        pieza(r, (lado * .34, 1.28, .06), (.13, .4, .14), P['ropa'])     # brazos
    pieza(r, (.18, 1.12, .3), (.1, .1, .34), P['ropa'])          # antebrazos apuntando
    pieza(r, (-.12, 1.14, .44), (.1, .1, .34), P['ropa'])
    pieza(r, (.14, 1.1, .5), (.09, .09, .1), GUANTE)
    pieza(r, (-.08, 1.12, .66), (.09, .09, .1), GUANTE)
    slot = Entity(parent=r, position=(.06, 1.1, .44), scale=.85)
    armar_arma(slot, arma_i)
    r.piernas = piernas
    r.slot = slot
    return r


# ------------------------------------------------------------------ mundo
mundo = Entity()      # todo lo que bloquea balas y enemigos cuelga de acá
decor = Entity()      # adornos sin colisión
ruinas, props, PUNTOS = [], [], []
LADRILLO = ['#6e4a3c', '#7a5442', '#5d3f33', '#8a6249']
CONCRETO = ['#6a6762', '#7c786f', '#5a5752']


def col_ladrillo():
    # con textura de ladrillo el color solo la tiñe, así que va más claro
    if T_LADRILLO:
        return random.choice(['#d8b9a6', '#c9a38e', '#e2c8b8', '#b98f7c'])
    return random.choice(LADRILLO)


def bloque(x, z, ancho, alto, largo, col, y=0.0, solido=True, textura=None, **kw):
    e = Entity(parent=mundo if solido else decor, model='cube', position=(x, y + alto / 2, z),
               scale=(ancho, alto, largo), color=C(col), collider='box' if solido else None, **kw)
    if textura:
        e.texture = textura
        e.texture_scale = (max(ancho, largo) / 1.5, max(.5, alto / 1.5))
    return e


def colision(padre, pos, esc):
    return Entity(parent=padre, model='cube', position=pos, scale=esc, collider='box', visible=False)


def libre(p, r_ruina=9, r_prop=3.5):
    return (not any((q - p).length() < r_ruina for q in ruinas)
            and not any((q - p).length() < r_prop for q in props))


class Llama(Entity):
    """Fuego que titila (barriles, tanques)."""
    def __init__(self, pos, tam=1.0, col='#ff7a1c'):
        super().__init__(model='cube', position=pos, scale=(.5 * tam, .7 * tam, .5 * tam), color=C(col), **UI)
        self.t = random.uniform(0, 6)
        self.base = .7 * tam

    def update(self):
        self.t += time.dt * 10
        self.scale_y = self.base * (.75 + .3 * math.sin(self.t))
        self.rotation_y += 140 * time.dt


def trozo(x, z, medio, c, y, h, a_lo_z, col):
    if h < .2:
        return
    if a_lo_z:
        bloque(x, z + medio, .5, h, c, col, y=y, textura=T_LADRILLO)
    else:
        bloque(x + medio, z, c, h, .5, col, y=y, textura=T_LADRILLO)


def muro(x, z, largo, a_lo_z, alto):
    s = 0.0
    while s < largo:
        c = min(random.uniform(2.4, 3.8), largo - s)
        medio = s + c / 2
        puerta = largo > 5 and abs(medio - largo / 2) < 1.6
        r = random.random()
        col = col_ladrillo()
        if puerta:
            trozo(x, z, medio, c, 2.4, alto - 2.4, a_lo_z, col)                 # dintel sobre la puerta
        elif r < .22:
            trozo(x, z, medio, c, 0, random.uniform(.8, 2.2), a_lo_z, col)      # derrumbado
        elif r < .55:
            trozo(x, z, medio, c, 0, 1.0, a_lo_z, col)                          # ventana
            trozo(x, z, medio, c, 2.1, alto - 2.1, a_lo_z, col)
        else:
            trozo(x, z, medio, c, 0, alto, a_lo_z, col)
        s += c


def ruina(cx, cz, w, d):
    alto = random.uniform(4.2, 6.2)
    muro(cx - w / 2, cz - d / 2, d, True, alto)
    muro(cx + w / 2, cz - d / 2, d, True, alto)
    muro(cx - w / 2, cz - d / 2, w, False, alto)
    muro(cx - w / 2, cz + d / 2, w, False, alto)
    bloque(cx, cz, w - .6, .04, d - .6, '#4a433b', solido=False, textura=T_RUIDO)           # piso
    bloque(cx + random.uniform(-w / 4, w / 4), cz + random.uniform(-d / 4, d / 4),
           random.uniform(w * .35, w * .55), .25, random.uniform(d * .35, d * .55),
           random.choice(CONCRETO), y=3.4, textura=T_RUIDO)                                  # losa del techo
    for _ in range(2):                                                                       # escombros
        e = bloque(cx + random.uniform(-w / 2, w / 2), cz + random.uniform(-d / 2, d / 2),
                   random.uniform(.3, 1), random.uniform(.2, .6), random.uniform(.3, 1),
                   random.choice(LADRILLO + CONCRETO), solido=False)
        e.rotation = (random.uniform(-15, 15), random.uniform(0, 180), random.uniform(-15, 15))


# --- vehículos y objetos
def jeep(p):
    g = Entity(parent=mundo, position=(p.x, 0, p.z), rotation_y=random.choice((0, 90, 180, 270)) + random.uniform(-15, 15))
    col = random.choice(['#4a5143', '#5a5a52', '#6a3a2a', '#3a4a5a'])
    pieza(g, (0, .7, 0), (1.9, .7, 3.8), col)
    pieza(g, (0, 1.3, -.3), (1.7, .6, 1.9), col)
    pieza(g, (0, 1.32, .66), (1.5, .4, .05), '#0c0d0e')
    for sx in (-.98, .98):
        for zz in (-1.2, 1.2):
            pieza(g, (sx, .4, zz), (.3, .8, .8), '#0e0e0f')
    colision(g, (0, .95, 0), (2, 1.7, 4))


def camion(p):
    g = Entity(parent=mundo, position=(p.x, 0, p.z), rotation_y=random.choice((0, 90, 180, 270)) + random.uniform(-10, 10))
    pieza(g, (0, 1.7, -1.0), (2.4, 2.2, 4.4), '#4b5240')
    pieza(g, (0, 1.25, 2.2), (2.3, 1.6, 1.8), '#3f4636')
    pieza(g, (0, 1.6, 3.12), (1.9, .6, .05), '#0c0d0e')
    for sx in (-1.2, 1.2):
        for zz in (-2.3, .3, 2.3):
            pieza(g, (sx, .55, zz), (.35, 1.1, 1.1), '#0e0e0f')
    colision(g, (0, 1.5, .4), (2.6, 3, 6.2))


def tanque(p):
    g = Entity(parent=mundo, position=(p.x, 0, p.z), rotation_y=random.uniform(0, 360))
    cas, osc = '#3a3f35', '#1c1e1b'
    pieza(g, (0, .85, 0), (2.8, .9, 5.4), cas)
    for l in (-1, 1):
        pieza(g, (l * 1.6, .6, 0), (.7, 1.1, 5.8), osc)
        for k in (-1.8, 0, 1.8):
            pieza(g, (l * 1.98, .55, k), (.12, .7, .8), '#2a2d28')
    pieza(g, (0, 1.65, -.3), (2.1, .8, 2.4), cas, rotation_y=random.uniform(-25, 25))
    pieza(g, (0, 1.7, 2.3), (.22, .22, 3.3), osc)
    pieza(g, (.55, 2.15, -.6), (.6, .12, .6), osc)
    colision(g, (0, 1.1, 0), (3.6, 2.2, 5.8))
    if random.random() < .5:
        Llama(Vec3(p.x, 2.4, p.z), 1.2)


def barril(p, fuego=False):
    bloque(p.x, p.z, .8, 1.1, .8, '#6a2a1a')
    if fuego:
        Llama(Vec3(p.x, 1.45, p.z), .8)
        Llama(Vec3(p.x, 1.4, p.z), .5, '#ffd050')


def barrera(x, z, rot):
    bloque(x, z, .6, .9, 3, '#8a867e', rotation_y=rot, textura=T_RUIDO)
    props.append(Vec3(x, 0, z))


def farola(x, z):
    bloque(x, z, .18, 5, .18, '#2a2c2e')
    pieza(decor, (x, 5.0, z), (.9, .1, .12), '#2a2c2e')
    pieza(decor, (x + .4, 4.93, z), (.45, .1, .3), '#ffd9a0', **UI)


def arbol(p):
    bloque(p.x, p.z, .35, 3.4, .35, '#3b2e22')
    for a in (-40, 35):
        pieza(decor, (p.x + math.sin(math.radians(a)) * .5, 3.2, p.z), (.12, 1.5, .12), '#3b2e22', rotation_z=a)


def en_sectores(fn, n, radio=4, minimo=14):
    puestos, intentos = 0, 0
    while puestos < n and intentos < 120:
        intentos += 1
        p = Vec3(random.uniform(-54, 54), 0, random.uniform(-54, 54))
        if p.length() < minimo or not libre(p, 8, radio):
            continue
        fn(p)
        props.append(p)
        puestos += 1


def construir_mundo():
    # suelo y muro exterior
    Entity(model='cube', scale=(130, 1, 130), y=-.5, color=C('#b8a26a' if T_SUELO else '#5a4631'),
           texture=T_SUELO, texture_scale=(40, 40), collider='box')
    for lado in (-1, 1):
        bloque(0, 60.6 * lado, 122, 3.2, .8, '#8a867e', textura=T_RUIDO)
        bloque(60.6 * lado, 0, .8, 3.2, 122, '#8a867e', textura=T_RUIDO)
    for _ in range(10):     # manchas de tierra
        pieza(decor, (random.uniform(-55, 55), .012, random.uniform(-55, 55)),
              (random.uniform(3, 9), .02, random.uniform(3, 9)),
              random.choice(['#4a3a28', '#6b5a3d', '#3f3326']), rotation_y=random.uniform(0, 180))

    # calles en cruz con líneas y plaza central
    pieza(decor, (0, .025, 0), (124, .05, 12), '#2e2e31', texture=T_RUIDO)
    pieza(decor, (0, .026, 0), (12, .05, 124), '#2e2e31', texture=T_RUIDO)
    pieza(decor, (0, .04, 0), (11, .04, 11), '#4a4640', texture=T_RUIDO)
    for v in range(-55, 56, 10):
        if abs(v) > 8:
            pieza(decor, (v, .06, 0), (2.6, .02, .2), '#d8b54a')
            pieza(decor, (0, .06, v), (.2, .02, 2.6), '#d8b54a')

    # edificios en ruinas, uno en cada manzana
    intentos = 0
    while len(ruinas) < 10 and intentos < 400:
        intentos += 1
        p = Vec3(random.uniform(-48, 48), 0, random.uniform(-48, 48))
        if abs(p.x) < 12.5 or abs(p.z) < 12.5 or any((q - p).length() < 18 for q in ruinas):
            continue
        ruinas.append(p)
        ruina(p.x, p.z, random.uniform(7, 10.5), random.uniform(6, 9.5))

    # barreras y vehículos sobre las calles
    for x, z, rot in ((-16, 2.5, 20), (17, -2.5, -20), (2.5, -19, 75), (-2.5, 21, 100)):
        barrera(x, z, rot)
    for fn, x, z in ((jeep, -28, -2), (camion, 33, 2.5), (jeep, 2.5, -33), (jeep, -2.5, 38)):
        p = Vec3(x, 0, z)
        fn(p)
        props.append(p)
    en_sectores(tanque, 2, 6)
    en_sectores(jeep, 2, 4)
    en_sectores(lambda p: barril(p, True), 3, 3)
    en_sectores(barril, 3, 3)
    en_sectores(arbol, 7, 3)

    # farolas a lo largo de las calles
    for t in (-40, -20, 20, 40):
        farola(t, 8)
        farola(8, t)

    # sacos de arena cerca del centro
    for i in range(7):
        a, r = i * .9 + random.uniform(0, .4), random.uniform(9, 15)
        p = Vec3(math.sin(a) * r, 0, math.cos(a) * r)
        if not libre(p, 8, 3):
            continue
        ancho, largo = (.8, 4.5) if random.random() < .5 else (4.5, .8)
        bloque(p.x, p.z, ancho, .55, largo, '#8a7a55')
        bloque(p.x, p.z, ancho * .9, .5, largo * .9, '#8a7a55', y=.55)
        props.append(p)

    # cajas
    def caja(p):
        bloque(p.x, p.z, 1.2, 1.2, 1.2, '#6a4a2a', rotation_y=random.uniform(0, 90))
        if random.random() < .4:
            bloque(p.x, p.z, 1.1, 1.1, 1.1, '#7a5a34', y=1.2)
    en_sectores(caja, 12, 2.5, 7)

    # edificios lejanos y columnas de humo
    for i in range(22):
        ang, rad, h = i / 22 * math.tau, random.uniform(95, 130), random.uniform(15, 45)
        pieza(decor, (math.sin(ang) * rad, h / 2, math.cos(ang) * rad),
              (random.uniform(8, 20), h, random.uniform(8, 20)), random.choice(['#2a1f20', '#1e1618', '#33262a']))
    for ang in (.7, 2.4, 4.1):
        e = pieza(decor, (math.sin(ang) * 110, 40, math.cos(ang) * 110), (6, 80, 6), '#2a2420')
        e.alpha = .5

    # puntos donde aparecen los enemigos
    for _ in range(40):
        ang, rad = random.uniform(0, math.tau), random.uniform(38, 56)
        p = Vec3(max(-56, min(56, math.sin(ang) * rad)), 0, max(-56, min(56, math.cos(ang) * rad)))
        if libre(p, 9, 3):
            PUNTOS.append(p)
    if not PUNTOS:
        PUNTOS.append(Vec3(40, 0, 40))


# ------------------------------------------------------------------ jugador y arma en primera persona
jugador = FirstPersonController(position=(0, .1, 0))
jugador.jump_height = 1.2
if hasattr(jugador, 'cursor') and jugador.cursor is not None:
    jugador.cursor.alpha = 0      # la mira propia es la de la interfaz; el controlador necesita que este objeto exista
camera.clip_plane_near = .05
camera.fov = S.fov

arma = Entity(parent=camera)
def guante_skin():
    return SKINS[S.skin].get('guante', '#101112')


def color_traza():
    return SKINS[S.skin].get('neon', '#ffd28a')


modelos_fp = [armar_arma(arma, i, manos=True, guante=guante_skin()) for i in range(len(ARMAS))]
fogonazo = Entity(parent=arma, model='cube', color=C('#ffd070'), scale=(.12, .12, .1), enabled=False, **UI)


def aplicar_graficos(inicial=False):
    """Aplica las opciones gráficas. Cada una va en su try: si tu versión de Ursina no la soporta, se ignora."""
    try:
        if S.pant or not inicial:
            window.fullscreen = bool(S.pant)
    except Exception:
        pass
    try:
        reloj = ClockObject.getGlobalClock()
        lim = FPS_LIM[S.fps_lim]
        if lim:
            reloj.setMode(ClockObject.MLimited)
            reloj.setFrameRate(lim)
        elif not inicial:
            reloj.setMode(ClockObject.MNormal)
    except Exception:
        pass
    try:
        if sol is not None and (S.sombras != 1 or not inicial):
            r = SOMBRAS[S.sombras]
            sol.shadow_map_resolution = Vec2(r, r)
            sol._light.set_shadow_caster(True, r, r)
    except Exception:
        pass
    try:
        scene.fog_density = DIST[S.dist]
    except Exception:
        pass
    try:
        fc = getattr(window, 'fps_counter', None)
        if fc is not None:
            fc.enabled = bool(S.ver_fps)
    except Exception:
        pass


def reconstruir_fp():
    """Rearma las armas en primera persona (para que los guantes tomen el color de la skin)."""
    for m in modelos_fp:
        destroy(m)
    modelos_fp[:] = [armar_arma(arma, i, manos=True, guante=guante_skin()) for i in range(len(ARMAS))]
    for k, m in enumerate(modelos_fp):
        m.enabled = (k == S.arma)


def cambiar_arma(i):
    S.arma, S.recargando, S.enfriamiento = i, False, .3
    S.construyendo = None
    for k, m in enumerate(modelos_fp):
        m.enabled = (k == i)
    x, y, z, esc = ARMA_FP[i]
    arma.position = (x, y, z)
    arma.scale = esc
    arma.rotation_x = 0
    fogonazo.z = BOCAS[i]


# ------------------------------------------------------------------ interfaz
hud = Entity(parent=camera.ui)
menu = Entity(parent=camera.ui)


def texto(padre, t, pos, esc=1.0, col=CREMA, origen=(0, 0)):
    return Text(t, parent=padre, position=pos, scale=esc, color=C(col), origin=origen)


def poner(t, txt):
    """Cambia el texto solo si cambió (evita regenerarlo en cada frame)."""
    if getattr(t, '_ult', None) != txt:
        t._ult = txt
        t.text = txt


def panel(padre, pos, esc, col='#0b0907', a=.6, z=.2):
    e = Entity(parent=padre, model='quad', position=(pos[0], pos[1], z), scale=esc, color=C(col), **UI)
    e.alpha = a
    return e


def barra(padre, pos, ancho, alto, col, z=.1):
    return Entity(parent=padre, model='quad', origin=(-.5, 0), position=(pos[0], pos[1], z),
                  scale=(ancho, alto), color=C(col), **UI)


# --- HUD del combate
vineta = Entity(parent=hud, model='quad', texture=T_VINETA, color=C('#c00000'), scale=(2.4, 1.4), z=2, **UI)
vineta.alpha = 0

panel(hud, (0, .435), (.58, .12))                                   # oleada (arriba al centro)
t_ola = texto(hud, '', (0, .462), 1.9, ORO)
t_rest = texto(hud, '', (0, .427), 1.0)
barra(hud, (-.25, .4), .5, .008, '#2a2420', .15)
b_ola = barra(hud, (-.25, .4), .5, .008, '#c4452d', .1)

panel(hud, (-.68, .455), (.4, .09))                                 # puntos y bajas (arriba a la izquierda)
t_puntos = texto(hud, '', (-.86, .475), 1.2, ORO, (-.5, 0))
t_bajas = texto(hud, '', (-.86, .44), 1.0, CREMA, (-.5, 0))

panel(hud, (-.65, -.4), (.44, .16))                                 # salud (abajo a la izquierda)
texto(hud, 'SALUD', (-.85, -.345), .9, GRIS, (-.5, 0))
t_hp = texto(hud, '', (-.85, -.41), 3, CREMA, (-.5, 0))
barra(hud, (-.69, -.415), .24, .022, '#2a2420', .15)
b_hp = barra(hud, (-.69, -.415), .24, .022, '#5aa04a', .1)

panel(hud, (.62, -.4), (.5, .16))                                   # munición (abajo a la derecha)
t_armanom = texto(hud, '', (.4, -.345), 1.0, ORO, (-.5, 0))
t_mun = texto(hud, '', (.69, -.405), 3.2, CREMA, (.5, 0))
t_res = texto(hud, '', (.71, -.415), 1.3, GRIS, (-.5, 0))
t_gran = texto(hud, '', (.4, -.455), .9, GRIS, (-.5, 0))

tiles, t_tiles = [], []                                             # las 4 armas (abajo al centro)
for _i in range(len(ARMAS)):
    _x = -.27 + _i * .18
    tiles.append(panel(hud, (_x, -.455), (.165, .07), a=.55))
    t_tiles.append(texto(hud, '', (_x, -.455), .7))

t_msg = texto(hud, '', (0, .3), 2.2, ORO)
t_estado = texto(hud, '', (0, -.1), 1.3)
t_hint = texto(hud, '', (0, -.2), 1.0, '#4fe3ff')

MAPA, MAPA_X, MAPA_Y = .24, .74, .27                                # minimapa con la zona (Battle Royale)
mapa_g = Entity(parent=hud, enabled=False)
panel(mapa_g, (MAPA_X, MAPA_Y), (MAPA, MAPA), '#0b0907', .6, .2)
mapa_pts = [Entity(parent=mapa_g, model='quad', color=C('#a56bff'), scale=.007, **UI) for _ in range(28)]
mapa_yo = Entity(parent=mapa_g, model='quad', color=C('#ffe14a'), scale=.011, **UI)

fantasma = Entity(model='cube', color=C('#4fe3ff'), enabled=False, **UI)   # muestra dónde va la pieza
fantasma.alpha = .35
muro_zona = [Entity(model='cube', color=C('#8a3cff'), enabled=False, **UI) for _ in range(40)]   # pared de la tormenta
for _m in muro_zona:
    _m.alpha = .3

mira_g = Entity(parent=hud)                                         # mira que se abre al moverte y disparar
mira = [Entity(parent=mira_g, model='quad', color=C(CREMA), scale=_e, **UI)
        for _e in ((.003, .02), (.003, .02), (.02, .003), (.02, .003))]
Entity(parent=mira_g, model='quad', color=C(CREMA), scale=.004, **UI)
marca_g = Entity(parent=hud, enabled=False)                         # marca de impacto
for _rz in (45, -45):
    Entity(parent=marca_g, model='quad', color=C('#e8472d'), scale=(.04, .004), rotation_z=_rz, **UI)
scope_g = Entity(parent=hud, enabled=False)                         # mira del francotirador
Entity(parent=scope_g, model='quad', texture=T_VINETA, color=C('#000000'), scale=(2.4, 1.4), z=1.5, **UI)
Entity(parent=scope_g, model='quad', color=C('#000000'), scale=(.9, .002), z=1.4, **UI)
Entity(parent=scope_g, model='quad', color=C('#000000'), scale=(.002, .9), z=1.4, **UI)


def mensaje(txt):
    poner(t_msg, txt)
    S.t_msg = 1.8


# --- menú: pestañas arriba (JUGAR / ARMERÍA / AJUSTES); el soldado queda en el centro
def _vacio(txt):
    return not (txt and txt.strip())


def boton(padre, txt, pos, accion, ancho=.5, alto=.08, col='#1d1813', hl='#6a4f2a', txt_col=None):
    # ARREGLO: Ursina falla (IndexError en Text.align) si el botón se crea con texto vacío o solo
    # espacios. Por eso un botón "sin texto" arranca con un punto, que se vuelve transparente.
    b = Button(parent=padre, text=('.' if _vacio(txt) else txt), position=pos, scale=(ancho, alto), color=C(col),
               highlight_color=C(hl), pressed_color=C('#8a6a30'), on_click=accion, **UI)
    b._txt_col = C(txt_col) if txt_col else None
    poner_boton(b, txt)
    return b


def poner_boton(b, txt):
    """Cambia el texto de un botón y mantiene el color del texto que tenía.
    Si el texto está vacío, deja un punto transparente (así nunca se rompe el alineador de texto)."""
    vacio = _vacio(txt)
    b.text = '.' if vacio else txt
    try:
        if vacio:
            b.text_color = color.clear
        elif getattr(b, '_txt_col', None) is not None:
            b.text_color = b._txt_col
    except Exception:
        pass


def icono_arma(padre, i, pos, ancho_max=.42, alto_max=.1):
    """'Foto' del arma: se dibuja de costado con rectángulos de colores (usa las mismas cajas que el modelo 3D)."""
    partes = PARTES[i]
    zs = [p[0][2] - p[1][2] / 2 for p in partes] + [p[0][2] + p[1][2] / 2 for p in partes]
    ys = [p[0][1] - p[1][1] / 2 for p in partes] + [p[0][1] + p[1][1] / 2 for p in partes]
    k = min(ancho_max / (max(zs) - min(zs)), alto_max / (max(ys) - min(ys)))
    cz, cy = (max(zs) + min(zs)) / 2, (max(ys) + min(ys)) / 2
    g = Entity(parent=padre, position=(pos[0], pos[1], -.05))
    for n, p in enumerate(partes):
        Entity(parent=g, model='quad', position=((p[0][2] - cz) * k, (p[0][1] - cy) * k, -.01 * n),
               scale=(p[1][2] * k, p[1][1] * k), color=C(p[2]), **UI)
    return g


def limpiar():
    for e in S.enemigos + S.recogibles:
        destroy(e)
    S.enemigos.clear()
    S.recogibles.clear()
    for pz in list(S.piezas.values()):
        destroy(pz)
    S.piezas = {}


TEXTOS_INICIO = ('FRENTE DE\nBATALLA', 'Un soldado, una línea,\nsin refuerzos.\nResistí las oleadas.', 'JUGAR', 'SALIR')
TAB_X = {'principal': -.55, 'armas': -.33, 'casillero': -.11, 'tienda': .11, 'graficos': .33, 'config': .55}


def accion_jugar():
    if S.modo == 'pausa':
        entrar_al_juego()
    else:
        nueva_partida()


def accion_salir():
    if S.modo == 'menu':
        application.quit()
    else:
        limpiar()
        S.modo = 'menu'
        abrir_menu(*TEXTOS_INICIO)


def mostrar_panel(nombre):
    S.panel = nombre
    for n, pn in paneles.items():
        pn.enabled = (n == nombre)
    subray.x = TAB_X[nombre]
    if nombre == 'casillero':
        S.sel_skin = S.skin                    # el casillero arranca mirando tu skin equipada
        S.pag_loc = S.skin // PAG
    elif nombre == 'tienda':
        S.sel_skin = tienda_ids()[0]           # la tienda arranca con la skin destacada del día
    aviso_skin('')
    vista_previa()
    refrescar_skins()


def elegir_arma(i):
    S.arma_inicial = i
    if S.modo == 'pausa':
        cambiar_arma(i)
    poner(m_aviso, '')
    vitrina_arma(i)
    refrescar_menu()
    guardar()


def comprar(k):
    i = S.arma_inicial
    n = S.mejoras[i][k]
    if n >= NIVEL_MAX:
        return
    if S.puntos < costo(n):
        poner(m_aviso, 'No te alcanzan las chapas.')
        return
    S.puntos -= costo(n)
    S.mejoras[i][k] += 1
    poner(m_aviso, '¡Mejora comprada!')
    guardar()
    refrescar_menu()


def cambiar(campo, paso):
    if campo == 'sens':
        S.sens = max(10, min(100, S.sens + paso))
    elif campo == 'fov':
        S.fov = max(70, min(110, S.fov + paso))
        camera.fov = S.fov
    else:
        S.dif = max(0, min(2, S.dif + paso))
    refrescar_menu()
    guardar()


def cambiar_modo():
    S.br = 1 - S.br
    guardar()
    refrescar_menu()


def borrar_record():
    S.record_ola = S.record_bajas = 0
    guardar()
    refrescar_menu()


def refrescar_menu():
    i = S.arma_inicial
    # JUGAR
    poner_boton(b_modo, 'MODO: BATTLE ROYALE' if S.br else 'MODO: OLEADAS')
    poner(m_info, 'RÉCORD OLEADAS\n' + (f'Oleada {S.record_ola}  ·  {S.record_bajas} bajas' if S.record_ola else 'Todavía sin récord')
          + '\n\nMEJOR PUESTO BR\n' + (f'#{S.mejor_puesto}' if S.mejor_puesto else 'Todavía sin puesto')
          + f'\n\nCHAPAS\n{S.puntos}\n\nDIFICULTAD\n{DIFICULTADES[S.dif][0]}\n\nSKIN\n{SKINS[S.skin]["n"]}')
    # ARMERÍA
    for k, m in enumerate(marcos):
        m.enabled = (k == i)
    poner(m_arma_t, ARMAS[i]['n'].upper())
    poner(m_arma_d, DESC[i])
    for k, (nombre, clave) in enumerate(MEJORAS):
        n = S.mejoras[i][k]
        t, b = filas_mej[k]
        actual = ef(i)[clave]
        if n < NIVEL_MAX:
            sig_n = list(S.mejoras[i])
            sig_n[k] += 1
            poner(t, f'{nombre}: {fmt(clave, actual)} -> {fmt(clave, ef(i, sig_n)[clave])}')
            poner_boton(b, f'Nv {n}/{NIVEL_MAX} · {costo(n)} chapas')
        else:
            poner(t, f'{nombre}: {fmt(clave, actual)}  (máximo)')
            poner_boton(b, 'MÁXIMO')
    poner(m_puntos, f'Chapas: {S.puntos}')
    # AJUSTES
    poner(v_sens, str(S.sens))
    poner(v_fov, str(S.fov))
    poner(v_dif, DIFICULTADES[S.dif][0])
    for campo, t in v_graf.items():
        poner(t, OPC_G[campo][getattr(S, campo)])
    refrescar_skins()


CONTROLES = ('W A S D  mover\nShift  correr     Espacio  saltar\nClic  disparar     Clic derecho  zoom\n'
             'R  recargar     G  granada\n1 a 4 o rueda  cambiar de arma\nEsc  pausa\n'
             'Battle Royale:  Z pared   X piso   C rampa   Q salir')

p_principal = Entity(parent=menu)
p_armas = Entity(parent=menu)
p_config = Entity(parent=menu)
p_casillero = Entity(parent=menu)
p_tienda = Entity(parent=menu)
p_graf = Entity(parent=menu)
paneles = {'principal': p_principal, 'armas': p_armas, 'casillero': p_casillero, 'tienda': p_tienda,
           'graficos': p_graf, 'config': p_config}

panel(menu, (-.58, -.035), (.66, .93), a=.82, z=.5)                 # paneles laterales
panel(menu, (.58, -.035), (.66, .93), a=.82, z=.5)
panel(menu, (-.25, -.035), (.004, .93), ORO, 1, .45)                # filos dorados
panel(menu, (.25, -.035), (.004, .93), ORO, 1, .45)
panel(menu, (0, .46), (1.9, .085), a=.8, z=.45)                     # barra de pestañas
for _n, _t in (('principal', 'JUGAR'), ('armas', 'ARMERÍA'), ('casillero', 'CASILLERO'),
               ('tienda', 'TIENDA'), ('graficos', 'GRÁFICOS'), ('config', 'AJUSTES')):
    boton(menu, _t, (TAB_X[_n], .46), lambda n=_n: mostrar_panel(n), .21, .06, '#14110d', '#4a3a22')
subray = panel(menu, (-.55, .425), (.21, .006), ORO, 1, .1)

# pestaña JUGAR
m_titulo = texto(p_principal, '', (-.86, .39), 3, ORO, (-.5, .5))
m_sub = texto(p_principal, '', (-.86, .19), 1.1, CREMA, (-.5, .5))
b_modo = boton(p_principal, 'MODO', (-.58, .01), lambda: cambiar_modo(), .5, .07, '#2a2036', '#4a3a66')
b_jugar = boton(p_principal, 'JUGAR', (-.58, -.1), accion_jugar, .5, .1, '#e8d82a', '#fff25a', '#14110d')
b_salir = boton(p_principal, 'SALIR', (-.58, -.22), accion_salir, .5, .07)
m_info = texto(p_principal, '', (.3, .39), 1.25, CREMA, (-.5, .5))
texto(p_principal, CONTROLES, (.3, -.2), .85, GRIS, (-.5, .5))

# pestaña ARMERÍA: una tarjeta por arma, con su nombre y su "foto" abajo
marcos, b_armas = [], []
for _k, _w in enumerate(ARMAS):
    _yc = .3 - _k * .2
    marcos.append(panel(p_armas, (-.58, _yc), (.6, .2), ORO, 1, .3))
    b_armas.append(boton(p_armas, '', (-.58, _yc), lambda k=_k: elegir_arma(k), .56, .18, '#4a3f33', '#6b5840'))
    _nombre = texto(p_armas, _w['n'].upper(), (-.58, _yc + .065), 1.1, CREMA)
    _nombre.z = -.05
    icono_arma(p_armas, _k, (-.58, _yc - .025))
m_arma_t = texto(p_armas, '', (.3, .39), 2, ORO, (-.5, .5))
m_arma_d = texto(p_armas, '', (.3, .315), 1.0, GRIS, (-.5, .5))
filas_mej = []
for _k in range(len(MEJORAS)):
    _y = .2 - _k * .1
    filas_mej.append((texto(p_armas, '', (.3, _y), .9, CREMA, (-.5, 0)),
                      boton(p_armas, '', (.74, _y), lambda k=_k: comprar(k), .34, .065)))
m_puntos = texto(p_armas, '', (.3, -.2), 1.4, ORO, (-.5, 0))
m_aviso = texto(p_armas, '', (.3, -.27), 1.0, '#e8472d', (-.5, 0))
texto(p_armas, 'Ganás chapas eliminando enemigos\ny superando oleadas. Las mejoras\nse guardan para la próxima vez.',
      (.3, -.34), .8, GRIS, (-.5, .5))

# pestañas CASILLERO y TIENDA (skins)
_cache_tienda = [None, None]


def tienda_ids():
    """Las 6 skins de la tienda de hoy: 1 legendaria, 2 épicas, 2 raras y 1 común. Cambian cada día."""
    dia = int(ahora() // 86400)
    if _cache_tienda[0] != dia:
        rnd = random.Random(dia)
        ids = []
        for r, n in ((3, 1), (2, 2), (1, 2), (0, 1)):
            pool = [i for i, sk in enumerate(SKINS) if sk['r'] == r and sk['precio'] > 0]
            ids += rnd.sample(pool, min(n, len(pool)))
        _cache_tienda[0], _cache_tienda[1] = dia, ids
    return _cache_tienda[1]


def icono_skin(padre, pos, alto, sk):
    """'Foto' de la skin: un soldadito dibujado con rectángulos de colores."""
    g = Entity(parent=padre, position=(pos[0], pos[1], -.05))
    k = alto / 1.1
    n = [0]

    def q(x, y, w, h, col):
        Entity(parent=g, model='quad', position=(x * k, y * k, -.01 * n[0]), scale=(w * k, h * k), color=C(col), **UI)
        n[0] += 1
    NEG = '#17191b'
    for lado in (-1, 1):
        q(lado * .1, -.3, .17, .4, sk['pantalon'])
        q(lado * .1, -.47, .19, .08, NEG)
        q(lado * .27, .07, .1, .32, sk['ropa'])
    q(0, .05, .38, .36, sk['ropa'])
    q(0, .06, .32, .28, sk['chaleco'])
    q(0, -.12, .38, .04, NEG)
    q(0, .34, .2, .2, NEG)
    q(0, .44, .25, .09, sk['casco'])
    q(0, .33, .15, .05, sk.get('lentes', '#5d8794'))
    if sk.get('cresta'):
        q(0, .53, .06, .1, sk['cresta'])
    if sk.get('hombreras'):
        for lado in (-1, 1):
            q(lado * .27, .22, .14, .07, sk['hombreras'])
    if sk.get('neon'):
        q(0, -.12, .39, .02, sk['neon'])
        q(0, .16, .3, .02, sk['neon'])
    return g


def crear_tarjeta(padre, pos, ancho, alto, accion, esc):
    """Tarjeta de una skin: marco del color de su rareza, dibujo, nombre y estado."""
    x, y = pos
    g = Entity(parent=padre)             # grupo: sirve para esconder la tarjeta entera
    t = dict(sid=-1, padre=g, grupo=g, pos=pos, alto=alto, icono=None)
    t['sel'] = panel(g, (x, y), (ancho + .014, alto + .014), CREMA, 1, .36)
    t['marco'] = panel(g, (x, y), (ancho, alto), '#808080', 1, .3)
    t['btn'] = boton(g, '', (x, y), accion, ancho - .012, alto - .012, '#1d1813', '#3a3025')
    t['velo'] = panel(g, (x, y), (ancho - .012, alto - .012), '#0b0907', .6, -.3)
    t['nombre'] = texto(g, '', (x, y + alto / 2 - .02), esc, CREMA)
    t['nombre'].z = -.4
    t['estado'] = texto(g, '', (x, y - alto / 2 + .02), esc * .9, GRIS)
    t['estado'].z = -.4
    return t


def actualizar_tarjeta(t, i, estado, col_estado, velo, sel):
    sk = SKINS[i]
    t['grupo'].enabled = True
    if t['sid'] != i:
        t['sid'] = i
        if t['icono'] is not None:
            destroy(t['icono'])
        t['icono'] = icono_skin(t['padre'], (t['pos'][0], t['pos'][1] + t['alto'] * .01), t['alto'] * .5, sk)
        t['marco'].color = C(RAREZA[sk['r']][1])
        poner(t['nombre'], sk['n'].upper())
    poner(t['estado'], estado)
    t['estado'].color = C(col_estado)
    t['velo'].enabled = velo
    t['sel'].enabled = sel


def crear_detalle(padre, tab):
    d = {}
    d['nombre'] = texto(padre, '', (.3, .39), 1.8, ORO, (-.5, .5))
    d['rareza'] = texto(padre, '', (.3, .32), 1.0, GRIS, (-.5, .5))
    d['desc'] = texto(padre, '', (.3, .26), 1.0, CREMA, (-.5, .5))
    d['precio'] = texto(padre, '', (.3, .08), 1.3, ORO, (-.5, 0))
    d['btn'] = boton(padre, '', (.58, -.03), lambda: accion_skin(tab), .5, .09, '#e8d82a', '#fff25a', '#14110d')
    d['puntos'] = texto(padre, '', (.3, -.14), 1.2, ORO, (-.5, 0))
    d['aviso'] = texto(padre, '', (.3, -.21), 1.0, '#e8472d', (-.5, 0))
    if tab == 'tienda':
        ayuda = 'La tienda se renueva todos los días.\nGanás chapas eliminando enemigos\ny superando oleadas.'
    else:
        ayuda = 'Las skins son solo estética: no cambian\ntus estadísticas. Algunas pintan\nel color de tus balas.'
    texto(padre, ayuda, (.3, -.3), .8, GRIS, (-.5, .5))
    return d


def actualizar_detalle(d, tab):
    i = S.sel_skin
    sk = SKINS[i]
    rn, rc = RAREZA[sk['r']]
    poner(d['nombre'], sk['n'].upper())
    poner(d['rareza'], rn)
    d['rareza'].color = C(rc)
    poner(d['desc'], sk['d'])
    if S.skin == i:
        txt, precio = 'EQUIPADA', 'Es tu skin actual'
    elif i in S.skins:
        txt, precio = 'EQUIPAR', 'En tu casillero'
    elif tab == 'tienda':
        txt, precio = f'COMPRAR  {sk["precio"]} chapas', f'Precio: {sk["precio"]} chapas'
    else:
        txt, precio = 'IR A LA TIENDA', f'Bloqueada  ·  {sk["precio"]} chapas'
    poner(d['precio'], precio)
    poner_boton(d['btn'], txt)
    poner(d['puntos'], f'Tus chapas: {S.puntos}')


detalles = {}


def aviso_skin(txt):
    for d in detalles.values():
        poner(d['aviso'], txt)


def elegir_skin(i):
    S.sel_skin = i
    aviso_skin('')
    vista_previa()
    refrescar_skins()


def equipar_skin(i):
    if i not in S.skins:
        return
    S.skin = i
    reconstruir_fp()
    aviso_skin('¡Skin equipada!')
    guardar()
    refrescar_menu()


def comprar_skin(i):
    if i in S.skins or i not in tienda_ids():
        return
    precio = SKINS[i]['precio']
    if S.puntos < precio:
        aviso_skin(f'Te faltan {precio - S.puntos} chapas.')
        return
    S.puntos -= precio
    S.skins = sorted(set(S.skins) | {i})
    aviso_skin('¡Comprada! Ya está en tu casillero.')
    guardar()
    refrescar_menu()


def accion_skin(tab):
    i = S.sel_skin
    if i in S.skins:
        equipar_skin(i)
    elif tab == 'tienda':
        comprar_skin(i)
    else:
        mostrar_panel('tienda')


def poner_reloj():
    resto = int(86400 - ahora() % 86400)
    poner(m_reloj, f'Se renueva en {resto // 3600} h {resto % 3600 // 60} min')


def actualizar_reloj():
    if _cache_tienda[0] != int(ahora() // 86400):
        refrescar_skins()          # pasó la medianoche: tienda nueva
    else:
        poner_reloj()


def refrescar_skins():
    ids = tienda_ids()
    for slot, t in enumerate(tarj_loc):
        i = S.pag_loc * PAG + slot
        if i >= len(SKINS):
            t['grupo'].enabled = False
            continue
        if S.skin == i:
            est, col = 'EQUIPADA', ORO
        elif i in S.skins:
            est, col = 'COMPRADA', GRIS
        else:
            est, col = 'BLOQUEADA', '#a86a6a'
        actualizar_tarjeta(t, i, est, col, i not in S.skins, S.panel == 'casillero' and S.sel_skin == i)
    for j, t in enumerate(tarj_tienda):
        i = ids[j]
        if S.skin == i:
            est, col = 'EQUIPADA', ORO
        elif i in S.skins:
            est, col = 'COMPRADA', GRIS
        else:
            est, col = f'{SKINS[i]["precio"]} chapas', ORO
        actualizar_tarjeta(t, i, est, col, i in S.skins, S.panel == 'tienda' and S.sel_skin == i)
    actualizar_detalle(detalles['casillero'], 'casillero')
    actualizar_detalle(detalles['tienda'], 'tienda')
    poner(m_cont, f'{len(S.skins)} / {len(SKINS)}')
    poner(m_pag, f'Página {S.pag_loc + 1} / {NPAG}')
    poner_reloj()


# CASILLERO: todas las skins en una grilla (las que no tenés se ven oscuras)
texto(p_casillero, 'CASILLERO', (-.86, .39), 2.2, ORO, (-.5, .5))
m_cont = texto(p_casillero, '', (-.3, .375), 1.0, GRIS, (.5, 0))
NPAG = (len(SKINS) + PAG - 1) // PAG
tarj_loc = []
for _i in range(PAG):
    tarj_loc.append(crear_tarjeta(p_casillero, (-.78 + (_i % 3) * .205, .22 - (_i // 3) * .18), .19, .165,
                                  lambda sl=_i: elegir_skin(S.pag_loc * PAG + sl), .7))


def cambiar_pag(paso):
    S.pag_loc = (S.pag_loc + paso) % NPAG
    refrescar_skins()


boton(p_casillero, '<', (-.72, -.455), lambda: cambiar_pag(-1), .08, .05)
m_pag = texto(p_casillero, '', (-.58, -.455), 1.0, CREMA)
boton(p_casillero, '>', (-.44, -.455), lambda: cambiar_pag(1), .08, .05)
detalles['casillero'] = crear_detalle(p_casillero, 'casillero')

# TIENDA: 6 skins que cambian todos los días
texto(p_tienda, 'TIENDA', (-.86, .39), 2.2, ORO, (-.5, .5))
m_reloj = texto(p_tienda, '', (-.86, .3), .85, GRIS, (-.5, 0))
tarj_tienda = []
for _j in range(len(tienda_ids())):
    tarj_tienda.append(crear_tarjeta(p_tienda, (-.72 + (_j % 2) * .29, .165 - (_j // 2) * .23), .27, .21,
                                     lambda j=_j: elegir_skin(tienda_ids()[j]), .9))
detalles['tienda'] = crear_detalle(p_tienda, 'tienda')

# pestaña GRÁFICOS
texto(p_graf, 'GRÁFICOS', (-.86, .39), 2.2, ORO, (-.5, .5))
FILAS_G = [('Pantalla completa', 'pant'), ('Límite de FPS', 'fps_lim'), ('Sombras', 'sombras'),
           ('Distancia de visión', 'dist'), ('Efectos', 'efectos'), ('Suavizado de bordes', 'aa'),
           ('Mostrar FPS', 'ver_fps')]


def cambiar_g(campo, paso):
    setattr(S, campo, (getattr(S, campo) + paso) % len(OPC_G[campo]))
    aplicar_graficos()
    refrescar_menu()
    guardar()


def preset_g(n):
    """Calidad rápida: 0 baja, 1 media, 2 alta (sombras, distancia, efectos y suavizado)."""
    S.sombras, S.dist, S.efectos, S.aa = n, n, n, (1 if n == 2 else 0)
    aplicar_graficos()
    refrescar_menu()
    guardar()


v_graf = {}
for _k, (_nombre, _campo) in enumerate(FILAS_G):
    _y = .27 - _k * .09
    texto(p_graf, _nombre, (-.86, _y), 1.0, CREMA, (-.5, 0))
    boton(p_graf, '-', (-.5, _y), lambda c=_campo: cambiar_g(c, -1), .06, .06)
    v_graf[_campo] = texto(p_graf, '', (-.4, _y), 1.1)
    boton(p_graf, '+', (-.3, _y), lambda c=_campo: cambiar_g(c, 1), .06, .06)
texto(p_graf, 'El suavizado de bordes se aplica\nal reiniciar el juego.', (-.86, -.37), .8, GRIS, (-.5, .5))
texto(p_graf, 'CALIDAD RÁPIDA', (.3, .39), 2, ORO, (-.5, .5))
for _n, _t in enumerate(('BAJA', 'MEDIA', 'ALTA')):
    boton(p_graf, _t, (.58, .22 - _n * .11), lambda n=_n: preset_g(n), .5, .08)
texto(p_graf, 'Ajusta sombras, distancia de visión,\nefectos y suavizado de una vez.\n\nSi el juego va lento, probá Baja\no bajá el límite de FPS.',
      (.3, -.14), .9, GRIS, (-.5, .5))

# pestaña AJUSTES
texto(p_config, 'AJUSTES', (-.86, .39), 3, ORO, (-.5, .5))


def fila(y, nombre, menos, mas):
    texto(p_config, nombre, (-.86, y), 1.0, CREMA, (-.5, 0))
    boton(p_config, '-', (-.5, y), menos, .06, .06)
    valor = texto(p_config, '', (-.4, y), 1.1)
    boton(p_config, '+', (-.3, y), mas, .06, .06)
    return valor


v_sens = fila(.17, 'Sensibilidad', lambda: cambiar('sens', -5), lambda: cambiar('sens', 5))
v_fov = fila(.07, 'Campo de visión', lambda: cambiar('fov', -5), lambda: cambiar('fov', 5))
v_dif = fila(-.03, 'Dificultad', lambda: cambiar('dif', -1), lambda: cambiar('dif', 1))
texto(p_config, 'La dificultad cambia cuánto daño\nte hacen los enemigos.', (-.86, -.11), .85, GRIS, (-.5, .5))
boton(p_config, 'BORRAR RÉCORD', (-.58, -.3), borrar_record, .5, .07)
texto(p_config, 'CONTROLES', (.3, .39), 2, ORO, (-.5, .5))
texto(p_config, CONTROLES, (.3, .3), 1.0, CREMA, (-.5, .5))


# --- vitrina: un rincón lejano del mapa, tipo lobby, donde el soldado posa en el centro del menú
VITRINA_Z = 300
soldado_menu = None
vitrina_ent = None


def construir_vitrina():
    global soldado_menu, vitrina_ent
    v = Entity(position=(0, 0, VITRINA_Z))
    pieza(v, (0, -.5, 30), (200, 1, 200), '#3b2f45', texture=T_RUIDO)           # piso de la plaza
    pieza(v, (0, -.15, 3.2), (5, .3, 5), '#1a1a24')                             # plataforma
    pieza(v, (0, .01, 3.2), (4.3, .02, 4.3), '#4fe3ff', **UI)                   # borde brillante
    pieza(v, (0, .02, 3.2), (4.0, .02, 4.0), '#161a24')
    for x in (-8, 8):                                                           # plataformas vacías a los costados
        pieza(v, (x, -.1, 5.5), (3, .2, 3), '#2a2c38')
        pieza(v, (x, .01, 5.5), (2.6, .02, 2.6), '#8a7aa0', **UI)
    for x, col in ((-15, '#ff4fd8'), (-10, '#4fe3ff'), (11, '#ff4fd8'), (16, '#4fe3ff'), (-22, '#4fe3ff'), (22, '#ff4fd8')):
        h = random.uniform(10, 20)                                              # torres con neón
        pieza(v, (x, h / 2, 26), (4, h, 4), '#241d2e')
        pieza(v, (x, h / 2, 23.9), (.5, h * .9, .1), col, **UI)
    vitrina_ent = v
    S.skin_vista = S.skin
    soldado_menu = construir_soldado(v, SKINS[S.skin], S.arma_inicial)
    soldado_menu.position = (0, .04, 3.2)
    soldado_menu.rotation_y = 160


def vista_previa():
    """El soldado del menú muestra la skin que estás mirando (casillero/tienda) o la equipada."""
    global soldado_menu
    i = S.sel_skin if S.panel in ('casillero', 'tienda') else S.skin
    if soldado_menu is not None and i == S.skin_vista:
        return
    S.skin_vista = i
    ry = soldado_menu.rotation_y if soldado_menu is not None else 160
    if soldado_menu is not None:
        destroy(soldado_menu)
    soldado_menu = construir_soldado(vitrina_ent, SKINS[i], S.arma_inicial)
    soldado_menu.position = (0, .04, 3.2)
    soldado_menu.rotation_y = ry


def vitrina_arma(i):
    for c in list(soldado_menu.slot.children):
        destroy(c)
    armar_arma(soldado_menu.slot, i)


def a_vitrina():
    jugador.position = (0, .1, VITRINA_Z)
    jugador.rotation_y = 0
    jugador.camera_pivot.rotation_x = 16


def abrir_menu(titulo, sub, jugar, salir):
    if S.modo == 'pausa' and S.guardada is None:
        S.guardada = (Vec3(jugador.position), jugador.rotation_y, jugador.camera_pivot.rotation_x)
    guardar()
    poner(m_titulo, titulo)
    poner(m_sub, sub)
    poner_boton(b_jugar, jugar)
    poner_boton(b_salir, salir)
    poner(m_aviso, '')
    b_modo.enabled = (S.modo != 'pausa')      # el modo no se cambia en plena partida
    vitrina_arma(S.arma_inicial)
    refrescar_menu()
    mostrar_panel('principal')
    menu.enabled = True
    hud.enabled = False
    mouse.locked = False
    jugador.enabled = False
    a_vitrina()
    camera.fov = S.fov


def entrar_al_juego():
    if S.guardada:
        pos, ry, rx = S.guardada
        jugador.position = pos
        jugador.rotation_y = ry
        jugador.camera_pivot.rotation_x = rx
        S.guardada = None
    S.modo = 'juego'
    S.enfriamiento = .3
    S.hud_arma = -1
    menu.enabled = False
    hud.enabled = True
    mouse.locked = True
    jugador.enabled = True


# ------------------------------------------------------------------ efectos
def chispas(pos, col, n, vel, tam, vida=.5):
    for _ in range(max(1, int(round(n * EFECTOS[S.efectos])))):
        p = Entity(model='cube', position=pos, scale=tam, color=C(col), **UI)
        d = Vec3(random.uniform(-1, 1), random.uniform(0, 1.2), random.uniform(-1, 1)).normalized()
        p.animate_position(pos + d * random.uniform(.4, 1) * vel * vida, duration=vida, curve=curve.out_quad)
        destroy(p, delay=vida)


def trazador(a, b, col):
    t = Entity(model='cube', position=(a + b) / 2, scale=(.03, .03, (b - a).length()), color=C(col), **UI)
    t.look_at(b)
    destroy(t, delay=.06)


def destello(pos, tam=.2):
    f = Entity(model='cube', position=pos, scale=tam, color=C('#ffd070'), rotation=(random.uniform(0, 90),) * 3, **UI)
    destroy(f, delay=.06)


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


# ------------------------------------------------------------------ enemigos, granadas, botín
class Enemigo(Entity):
    def __init__(self, pos, velocidad, preferida):
        super().__init__(position=pos + Vec3(0, .1, 0))
        self.hp, self.vel, self.pref = 100.0, velocidad, preferida
        self.vivo = True
        self.cool = random.uniform(1.0, 2.0)
        self.lado = random.choice((-1, 1))
        self.t_lado = 2.0
        self.t_vista = 0.0
        self.t_obst = 0.0
        self.bloq = False
        self.obj = None          # a quién ve y le dispara
        self.meta = None         # hacia quién camina
        self.paso = random.uniform(0, 6)
        self.arma_i = random.choice((0, 0, 0, 2, 3))
        self.modelo = construir_soldado(self, random.choice(('negro', 'negro', 'verde', 'arena')), self.arma_i)
        # cajas invisibles donde pegan las balas: cuerpo y cabeza
        self.cuerpo = Entity(parent=self, model='cube', position=(0, 1.0, 0), scale=(.62, 1.2, .42), collider='box', visible=False)
        self.cabeza = Entity(parent=self, model='cube', position=(0, 1.78, 0), scale=(.36, .4, .4), collider='box', visible=False)
        for parte in (self.cuerpo, self.cabeza):
            parte.enemigo = self        # así la bala sabe a quién le pegó
        S.enemigos.append(self)

    def elegir_objetivo(self):
        """En oleadas persigue al jugador. En Battle Royale elige al más cercano que vea (jugador u otro soldado)."""
        ojos = self.position + Vec3(0, 1.4, 0)
        cand = [jugador] + ([e for e in S.enemigos if e is not self] if S.br else [])
        cand.sort(key=lambda c: (c.position - self.position).length())
        self.obj = None
        for c in cand[:3]:
            if (c.position - self.position).length() > 60:
                break
            v = c.position + Vec3(0, 1.4, 0) - ojos
            if not raycast(ojos, v.normalized(), distance=v.length(), traverse_target=mundo).hit:
                self.obj = c
                break
        if self.obj is not None:
            self.meta = self.obj
        elif not S.br or (cand[0].position - self.position).length() < 45:
            self.meta = cand[0]
        else:
            self.meta = None

    def update(self):
        if S.modo != 'juego' or not self.vivo:
            return
        dt = time.dt
        self.cool -= dt
        self.t_lado -= dt
        self.t_vista -= dt
        self.t_obst -= dt
        if S.br and fuera_de_zona(self.position):
            self.herir(S.z_dps * dt)                       # la tormenta también los lastima
            if not self.vivo:
                return
        if self.t_vista <= 0:
            self.t_vista = .3
            self.elegir_objetivo()
        huye = S.br and fuera_de_zona(self.position, -4)   # corre hacia el centro de la zona segura
        if huye or self.meta is None:
            destino = Vec3(S.z_cx, 0, S.z_cz) if S.br else jugador.position
        else:
            destino = self.meta.position
        dx, dz = destino.x - self.x, destino.z - self.z
        d = math.hypot(dx, dz) or .001
        hacia = Vec3(dx / d, 0, dz / d)
        lateral = Vec3(hacia.z * self.lado, 0, -hacia.x * self.lado)
        if self.t_lado <= 0:
            self.lado = -self.lado
            self.t_lado = random.uniform(1.5, 3.5)

        combate = self.obj is not None and not huye
        mv = lateral * .6 if (combate and d < self.pref) else hacia
        if self.t_obst <= 0:
            self.t_obst = .12
            self.bloq = raycast(self.position + Vec3(0, 1, 0), mv.normalized(), distance=1.5, traverse_target=mundo).hit
        if self.bloq:
            mv = lateral
        camina = d > (1.5 if (self.meta is not None and not huye) else 4)
        if camina:
            self.position += mv * self.vel * dt
        self.x = max(-58, min(58, self.x))
        self.z = max(-58, min(58, self.z))
        self.rotation_y = math.degrees(math.atan2(dx, dz))
        self.paso += dt * self.vel * 2.4
        giro = math.sin(self.paso) * 35 if camina else 0
        self.modelo.piernas[0].rotation_x = giro
        self.modelo.piernas[1].rotation_x = -giro

        if combate and d < 60 and self.cool <= 0:
            self.disparar(self.obj, d)

    def disparar(self, objetivo, d):
        self.cool = max(.4, random.uniform(.9, 1.7) - min(.5, S.ola * .04))
        r = math.radians(self.rotation_y)
        origen = self.position + Vec3(math.sin(r) * .95, 1.2, math.cos(r) * .95)
        punteria = max(.08, min(.55, .5 - d / 70 + S.ola * .012))
        blanco = objetivo.position + Vec3(0, 1.5 if objetivo is jugador else 1.3, 0)
        acierta = random.random() < punteria
        if not acierta:
            blanco += Vec3(random.uniform(-2, 2), random.uniform(-1, 1), random.uniform(-2, 2))
        destello(origen)
        trazador(origen, blanco, '#ff6a3a')
        if acierta:
            if objetivo is jugador:
                dano_jugador(random.uniform(5, 9) * (1 + S.ola * .03) * DIFICULTADES[S.dif][1])
            else:
                objetivo.golpe(random.uniform(8, 16), False, blanco, False)

    def golpe(self, dano, cabeza, punto, jug=True):
        if not self.vivo:
            return
        self.hp -= dano
        chispas(punto, '#8a0f0f', 8, 3, .06, .5)
        if jug:
            S.marcador = 1.0
        if self.hp <= 0:
            self.morir(cabeza, jug)

    def herir(self, n):
        self.hp -= n
        if self.hp <= 0:
            self.morir(False, False)

    def morir(self, cabeza, jug=True):
        self.vivo = False
        S.enemigos.remove(self)
        self.cuerpo.collider = None
        self.cabeza.collider = None
        self.animate('rotation_x', -90, duration=.4)
        destroy(self, delay=8)
        S.restantes -= 1
        if jug:
            S.bajas += 1
            S.puntos += 20 if cabeza else 10
            if S.br:
                S.materiales += 30
                mensaje(f'Bajaste a un soldado  ·  quedan {len(S.enemigos) + 1}')
            elif cabeza:
                mensaje('Disparo a la cabeza  +20')
        if S.br:
            soltar_botin(self.position, self.arma_i)
        elif random.random() < .22:
            Recogible(self.position)


class Granada(Entity):
    def __init__(self):
        super().__init__(model='sphere', scale=.2, color=C('#2a3322'), position=camera.world_position)
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
    """Botín del modo oleadas: botiquín o munición."""
    def __init__(self, pos):
        super().__init__(position=pos + Vec3(0, .45, 0))
        self.salud = random.random() < .5
        if self.salud:
            pieza(self, (0, 0, 0), (.55, .4, .4), '#eeeeee')
            pieza(self, (0, 0, .205), (.3, .08, .02), '#c4202a')
            pieza(self, (0, 0, .205), (.08, .3, .02), '#c4202a')
        else:
            pieza(self, (0, 0, 0), (.6, .35, .4), '#4d5a2e')
            pieza(self, (0, 0, .205), (.5, .08, .02), ORO)
        S.recogibles.append(self)

    def update(self):
        if S.modo != 'juego':
            return
        self.rotation_y += 90 * time.dt
        if (jugador.position - self.position).length() < 1.8:
            if self.salud:
                curar(35)
                mensaje('Botiquín +35')
            else:
                dar_municion()
                mensaje('Munición repuesta')
            S.recogibles.remove(self)
            destroy(self)


# ------------------------------------------------------------------ Battle Royale: botín
class Botin(Entity):
    """Objeto en el suelo con una columna de luz: armas, munición, botiquines, materiales y granadas."""
    def __init__(self, pos, tipo, i=0):
        super().__init__(position=pos + Vec3(0, .55, 0))
        self.tipo, self.i = tipo, i
        if tipo == 'arma':
            armar_arma(self, i).scale = 1.4
        elif tipo == 'municion':
            pieza(self, (0, 0, 0), (.5, .3, .35), '#4d5a2e')
            pieza(self, (0, 0, .18), (.4, .06, .02), ORO)
        elif tipo == 'salud':
            pieza(self, (0, 0, 0), (.5, .38, .38), '#eeeeee')
            pieza(self, (0, 0, .195), (.28, .07, .02), '#c4202a')
            pieza(self, (0, 0, .195), (.07, .28, .02), '#c4202a')
        elif tipo == 'materiales':
            pieza(self, (0, 0, 0), (.55, .4, .45), '#b98b50')
            pieza(self, (0, .05, .23), (.5, .06, .02), '#7a5a30')
        else:
            pieza(self, (0, 0, 0), (.3, .3, .3), '#2a3322')
        haz = Entity(parent=self, model='cube', position=(0, 1.2, 0), scale=(.1, 2.4, .1), color=C(BEAM[tipo]), **UI)
        haz.alpha = .45
        S.recogibles.append(self)

    def update(self):
        if S.modo != 'juego':
            return
        self.rotation_y += 90 * time.dt
        if (jugador.position - self.position).length() < 2.0:
            self.recoger()

    def recoger(self):
        t = self.tipo
        if t == 'arma':
            S.tiene[self.i] = True
            S.reserva[self.i] += ARMAS[self.i]['reserva'] // 2
            if S.municion[self.i] == 0:
                S.municion[self.i] = ef(self.i)['cargador']
            cambiar_arma(self.i)
            mensaje(f'Recogiste: {ARMAS[self.i]["n"]}')
        elif t == 'municion':
            for k in range(len(ARMAS)):
                if S.tiene[k]:
                    S.reserva[k] += ef(k)['cargador'] * 2
            mensaje('Munición')
        elif t == 'salud':
            curar(35)
            mensaje('Botiquín +35')
        elif t == 'materiales':
            S.materiales += 100
            mensaje('Materiales +100')
        else:
            S.granadas = min(6, S.granadas + 2)
            mensaje('Granadas +2')
        S.recogibles.remove(self)
        destroy(self)


def soltar_botin(p, arma_i):
    def cerca():
        return p + Vec3(random.uniform(-.7, .7), 0, random.uniform(-.7, .7))
    Botin(cerca(), 'materiales')
    if random.random() < .6:
        Botin(cerca(), 'municion')
    if random.random() < .4:
        Botin(cerca(), 'salud')
    if random.random() < .5:
        Botin(cerca(), 'arma', arma_i)


def punto_libre():
    for _ in range(60):
        p = Vec3(random.uniform(-50, 50), 0, random.uniform(-50, 50))
        if libre(p, 6, 2.5):
            return p
    return Vec3(random.uniform(-50, 50), 0, random.uniform(-50, 50))


def repartir_botin():
    """Las armas están dentro de los edificios; lo demás, repartido por el mapa."""
    sitios = [Vec3(r.x + random.uniform(-2, 2), 0, r.z + random.uniform(-2, 2)) for r in ruinas]
    random.shuffle(sitios)
    for k, i in enumerate((0, 0, 0, 2, 2, 2, 3, 3)):
        Botin(sitios[k] if k < len(sitios) else punto_libre(), 'arma', i)
    for tipo, n in (('municion', 5), ('salud', 5), ('materiales', 6), ('granada', 2)):
        for _ in range(n):
            Botin(punto_libre(), tipo)


# ------------------------------------------------------------------ Battle Royale: zona que se cierra
def fuera_de_zona(p, margen=0):
    return math.hypot(p.x - S.z_cx, p.z - S.z_cz) > S.z_r + margen


def iniciar_fase():
    """Elige la próxima zona (siempre dentro de la actual) y arranca la cuenta atrás."""
    if S.z_fase >= len(FASES):
        S.z_estado = 'final'
        return
    rf, espera, dur, dps = FASES[S.z_fase]
    S.z_estado, S.z_t, S.z_dur, S.z_dps = 'espera', float(espera), float(dur), dps
    S.z_r0, S.z_x0, S.z_z0 = S.z_r, S.z_cx, S.z_cz
    ang, mov = random.uniform(0, math.tau), max(0, S.z_r0 - rf) * random.uniform(.2, .8)
    S.z_r1, S.z_x1, S.z_z1 = rf, S.z_x0 + math.cos(ang) * mov, S.z_z0 + math.sin(ang) * mov
    mensaje(f'La zona se cierra en {espera} s')


def actualizar_zona(dt):
    if S.z_estado == 'final':
        return
    S.z_t -= dt
    if S.z_estado == 'espera':
        if S.z_t <= 0:
            S.z_estado, S.z_t = 'encoge', S.z_dur
            mensaje('¡La zona se está cerrando!')
    else:
        f = 1 - max(0, S.z_t) / S.z_dur
        S.z_r = lerp(S.z_r0, S.z_r1, f)
        S.z_cx = lerp(S.z_x0, S.z_x1, f)
        S.z_cz = lerp(S.z_z0, S.z_z1, f)
        if S.z_t <= 0:
            S.z_fase += 1
            iniciar_fase()


def actualizar_muro_zona():
    clave = (round(S.z_r, 1), round(S.z_cx, 1), round(S.z_cz, 1))
    if clave == S.zona_clave:
        return
    S.zona_clave = clave
    n = len(muro_zona)
    ancho = math.tau * S.z_r / n * 1.08
    for k, e in enumerate(muro_zona):
        th = k / n * math.tau
        e.enabled = S.z_r < 80
        e.position = (S.z_cx + math.cos(th) * S.z_r, 20, S.z_cz + math.sin(th) * S.z_r)
        e.scale = (ancho, 40, .8)
        e.rotation_y = math.degrees(math.atan2(-math.cos(th), -math.sin(th)))


def actualizar_minimapa():
    k = MAPA / 130
    n = len(mapa_pts)
    for j, pt in enumerate(mapa_pts):
        th = j / n * math.tau
        x, z = S.z_cx + math.cos(th) * S.z_r, S.z_cz + math.sin(th) * S.z_r
        pt.enabled = abs(x) < 64 and abs(z) < 64
        pt.position = (MAPA_X + x * k, MAPA_Y + z * k, -.1)
    mapa_yo.position = (MAPA_X + jugador.x * k, MAPA_Y + jugador.z * k, -.2)


# ------------------------------------------------------------------ Battle Royale: construcción
class Pieza(Entity):
    """Pared, piso o rampa que construís. Se rompe a balazos."""
    def __init__(self, info):
        super().__init__(parent=mundo, model='cube', position=info['pos'], scale=info['esc'],
                         rotation=(info['rot'][0], info['rot'][1], 0), color=C('#c9a064'),
                         collider='box', texture=T_RUIDO)
        self.es_pieza = True
        self.hp = 160 if info['tipo'] == 'pared' else 220
        self.clave = info['clave']
        S.piezas[self.clave] = self

    def golpe(self, dano):
        self.hp -= dano
        chispas(self.world_position, '#c9a064', 4, 3, .08, .3)
        if self.hp <= 0:
            S.piezas.pop(self.clave, None)
            destroy(self)


def calcular_pieza(tipo):
    """Dónde iría la pieza si construís ahora: siempre en tu casilla o en la de adelante, pegada a la grilla."""
    lv = max(0, int(round((jugador.y - .1) / ALTO)))                    # piso en el que estás parado
    h = int(round(jugador.rotation_y / 90)) % 4                        # hacia dónde mirás (0 = +z)
    dx, dz = HD[h]
    mx = (math.floor(jugador.x / LADO) + .5) * LADO                    # centro de tu casilla
    mz = (math.floor(jugador.z / LADO) + .5) * LADO
    rot = (0, 0)
    if tipo == 'pared':
        pos = (mx + dx * LADO / 2, lv * ALTO + ALTO / 2, mz + dz * LADO / 2)
        esc = (LADO, ALTO, .3) if dz else (.3, ALTO, LADO)
    elif tipo == 'piso':
        arriba = jugador.camera_pivot.rotation_x < -25                 # mirando para arriba: techo
        pos = (mx + dx * LADO, (lv + (1 if arriba else 0)) * ALTO + .1, mz + dz * LADO)
        esc = (LADO, .2, LADO)
    else:
        pos = (mx + dx * LADO, lv * ALTO + ALTO / 2 + .1, mz + dz * LADO)
        esc = (LADO, .25, math.hypot(LADO, ALTO))
        rot = (-math.degrees(math.atan2(ALTO, LADO)), h * 90)
    clave = (tipo, round(pos[0], 1), round(pos[1], 1), round(pos[2], 1), h if tipo == 'rampa' else 0)
    return dict(tipo=tipo, pos=pos, esc=esc, rot=rot, clave=clave)


def construir():
    if not S.construyendo or S.t_construir > 0:
        return
    info = calcular_pieza(S.construyendo)
    if S.materiales < COSTO_PIEZA:
        mensaje('Te faltan materiales')
        S.t_construir = .5
        return
    if info['clave'] in S.piezas:
        return
    S.materiales -= COSTO_PIEZA
    S.t_construir = .1
    Pieza(info)


# ------------------------------------------------------------------ reglas del juego
def curar(n):
    S.hp = min(100, S.hp + n)


def dar_municion():
    for i in range(len(ARMAS)):
        S.reserva[i] += ef(i)['cargador'] * (2 if i == S.arma else 1)


def dano_jugador(n):
    S.hp -= n
    S.sangre = 1.0
    if S.hp <= 0 and S.modo == 'juego':
        S.modo = 'fin'
        if S.br:
            puesto = len(S.enemigos) + 1
            premio = S.bajas * 15 + max(0, N_BOTS + 1 - puesto) * 8
            S.puntos += premio
            if S.mejor_puesto == 0 or puesto < S.mejor_puesto:
                S.mejor_puesto = puesto
            abrir_menu('ELIMINADO', f'Puesto #{puesto} de {N_BOTS + 1}\n{S.bajas} bajas  ·  +{premio} chapas',
                       'JUGAR DE NUEVO', 'SALIR AL MENÚ')
            return
        sub = f'Llegaste a la oleada {S.ola}\ncon {S.bajas} bajas.'
        if (S.ola, S.bajas) > (S.record_ola, S.record_bajas):
            S.record_ola, S.record_bajas = S.ola, S.bajas
            sub += '\n¡Nuevo récord!'
        abrir_menu('CAÍSTE EN\nCOMBATE', sub, 'JUGAR DE NUEVO', 'SALIR AL MENÚ')


def victoria():
    S.modo = 'fin'
    premio = S.bajas * 15 + 100 + N_BOTS * 8
    S.puntos += premio
    S.mejor_puesto = 1
    abrir_menu('¡VICTORIA\nMAGISTRAL!', f'Puesto #1 de {N_BOTS + 1}\n{S.bajas} bajas  ·  +{premio} chapas',
               'JUGAR DE NUEVO', 'SALIR AL MENÚ')


def siguiente_ola():
    S.ola += 1
    S.por_aparecer = 4 + S.ola * 3
    S.restantes = S.por_aparecer
    if S.ola > 1:
        premio = 25 * (S.ola - 1)
        S.puntos += premio
        dar_municion()
        curar(15)
        S.granadas = min(4, S.granadas + 1)
        mensaje(f'Oleada {S.ola}   +{premio} chapas')
    else:
        mensaje(f'Oleada {S.ola}')


def aparecer():
    lejos = [p for p in PUNTOS if (p - jugador.position).length() > 28] or PUNTOS
    Enemigo(random.choice(lejos), min(4.2, 2.2 + S.ola * .15) * random.uniform(.9, 1.1), random.uniform(12, 22))


def iniciar_br():
    """Battle Royale: arrancás solo con la pistola, tenés que buscar armas, y la zona se cierra."""
    S.tiene = [False, True, False, False]
    S.municion = [0, ef(1)['cargador'], 0, 0]
    S.reserva = [0, ARMAS[1]['reserva'] // 2, 0, 0]
    S.materiales, S.granadas = 200, 1
    p = punto_libre()
    jugador.position = (p.x, .1, p.z)
    jugador.rotation_y = random.choice((0, 90, 180, 270))
    cambiar_arma(1)
    S.z_fase, S.z_r, S.z_cx, S.z_cz, S.zona_clave = 0, 85.0, 0.0, 0.0, None
    iniciar_fase()
    repartir_botin()
    for _ in range(N_BOTS):
        for _i in range(40):
            q = punto_libre()
            if (q - jugador.position).length() > 22:
                break
        Enemigo(q, random.uniform(2.6, 3.6), random.uniform(12, 20))
    S.restantes = N_BOTS
    mensaje(f'Battle Royale: quedan {N_BOTS + 1}')


def nueva_partida():
    limpiar()
    S.guardada = None
    S.ola, S.bajas, S.hp, S.granadas = 0, 0, 100.0, 3
    S.t_aparicion = S.t_ola = 0.0
    S.municion = [ef(i)['cargador'] for i in range(len(ARMAS))]
    S.reserva = [a['reserva'] for a in ARMAS]
    S.tiene = [True] * len(ARMAS)
    S.materiales = 0
    S.construyendo = None
    jugador.position = (0, .1, 0)
    jugador.rotation_y = 0
    jugador.camera_pivot.rotation_x = 0
    if S.br:
        iniciar_br()
    else:
        cambiar_arma(S.arma_inicial)
        siguiente_ola()
    entrar_al_juego()


def disparar():
    a = ef(S.arma)
    if S.recargando or S.enfriamiento > 0:
        return
    if S.municion[S.arma] <= 0:
        recargar()
        return
    S.municion[S.arma] -= 1
    S.enfriamiento = a['ritmo']
    S.kick = 1.0
    jugador.camera_pivot.rotation_x -= a['retroceso'] * .3 + random.uniform(0, .2)
    jugador.rotation_y += random.uniform(-.2, .2)
    z0 = ARMA_FP[S.arma][2]
    arma.z = z0 - .08
    arma.animate_z(z0, .1)
    arma.rotation_x = -3
    arma.animate('rotation_x', 0, duration=.12)
    fogonazo.enabled = True
    invoke(setattr, fogonazo, 'enabled', False, delay=.05)

    origen = camera.world_position
    boca = fogonazo.world_position
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
                enemigo.golpe(min(100, a['dano'] * 3) if cabeza else a['dano'], cabeza, fin)
            elif getattr(tiro.entity, 'es_pieza', False):
                tiro.entity.golpe(a['dano'])
            else:
                chispas(fin, '#ffc060', 5, 5, .04, .35)
        trazador(boca, fin, color_traza())


def recargar():
    a = ef(S.arma)
    if S.recargando or S.municion[S.arma] >= a['cargador'] or S.reserva[S.arma] <= 0:
        return
    S.recargando = True
    S.t_recarga = a['recarga']
    y0 = ARMA_FP[S.arma][1]
    arma.animate_y(y0 - .25, a['recarga'] / 2, curve=curve.out_quad)
    arma.animate_y(y0, a['recarga'] / 2, delay=a['recarga'] / 2, curve=curve.in_quad)


def lanzar_granada():
    if S.granadas <= 0 or S.t_granada > 0:
        return
    S.granadas -= 1
    S.t_granada = .8
    Granada()


def elegir_arma_slot(i):
    if S.tiene[i]:
        cambiar_arma(i)
    else:
        mensaje(f'Todavía no tenés: {ARMAS[i]["n"]}')


def pausar():
    S.modo = 'pausa'
    S.arma_inicial = S.arma
    S.construyendo = None
    abrir_menu('PAUSA', 'Tu partida te espera.', 'CONTINUAR', 'SALIR AL MENÚ')


# ------------------------------------------------------------------ bucle principal
def input(key):
    if S.modo == 'juego':
        if key == 'left mouse down' and not ARMAS[S.arma]['auto'] and not S.construyendo:
            disparar()
        elif key == 'r':
            recargar()
        elif key == 'g':
            lanzar_granada()
        elif key in ('1', '2', '3', '4'):
            elegir_arma_slot(int(key) - 1)
        elif key in ('scroll up', 'scroll down'):
            paso = -1 if key == 'scroll up' else 1
            for k in range(1, len(ARMAS)):
                i = (S.arma + paso * k) % len(ARMAS)
                if S.tiene[i]:
                    cambiar_arma(i)
                    break
        elif key in ('z', 'x', 'c') and S.br:
            tipo = {'z': 'pared', 'x': 'piso', 'c': 'rampa'}[key]
            S.construyendo = None if S.construyendo == tipo else tipo
        elif key == 'q':
            S.construyendo = None
        elif key in ('escape', 'p'):
            pausar()
    elif key == 'enter':
        accion_jugar()
    elif key in ('escape', 'p'):
        if S.panel != 'principal':
            mostrar_panel('principal')
        elif S.modo == 'pausa':
            entrar_al_juego()


def update():
    dt = time.dt
    if S.modo != 'juego':
        soldado_menu.rotation_y += 28 * dt        # el soldado gira despacio en el menú
        S.t_reloj -= dt
        if S.t_reloj <= 0:
            S.t_reloj = 1.0
            actualizar_reloj()
        return
    a = ef(S.arma)

    # movimiento, arma y construcción
    corre = held_keys['left shift'] or held_keys['shift']
    jugador.speed = (8.5 if corre else 5.5) * (.85 if S.recargando else 1)
    S.enfriamiento -= dt
    S.t_granada -= dt
    S.t_construir -= dt
    if S.construyendo:
        if held_keys['left mouse']:
            construir()
    elif held_keys['left mouse'] and a['auto']:
        disparar()
    if S.recargando:
        S.t_recarga -= dt
        if S.t_recarga <= 0:
            S.recargando = False
            n = min(a['cargador'] - S.municion[S.arma], S.reserva[S.arma])
            S.municion[S.arma] += n
            S.reserva[S.arma] -= n
    zoom = held_keys['right mouse'] and not S.construyendo
    camera.fov = lerp(camera.fov, a['zoom'] if zoom else S.fov, min(1, dt * 12))
    jugador.mouse_sensitivity = Vec2(S.sens, S.sens) * (camera.fov / S.fov)
    arma.x = lerp(arma.x, 0 if zoom else ARMA_FP[S.arma][0], min(1, dt * 10))
    mirilla = S.arma == 3 and zoom and camera.fov < 45
    arma.visible = not mirilla and not S.construyendo
    scope_g.enabled = mirilla
    mira_g.enabled = not mirilla
    if S.construyendo:                                          # la pieza "fantasma" que muestra dónde va
        info = calcular_pieza(S.construyendo)
        fantasma.enabled = True
        fantasma.position = info['pos']
        fantasma.scale = info['esc']
        fantasma.rotation = (info['rot'][0], info['rot'][1], 0)
        ok = S.materiales >= COSTO_PIEZA and info['clave'] not in S.piezas
        if ok != S.fant_ok:
            S.fant_ok = ok
            fantasma.color = C('#4fe3ff' if ok else '#ff4f4f')
            fantasma.alpha = .35
    else:
        fantasma.enabled = False

    # reglas del modo
    fuera = False
    if S.br:
        actualizar_zona(dt)
        actualizar_muro_zona()
        fuera = fuera_de_zona(jugador.position)
        if fuera:
            dano_jugador(S.z_dps * dt)
        if S.modo != 'juego':
            return
        if not S.enemigos:
            victoria()
            return
    else:
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

    # mira dinámica y efectos de pantalla
    S.sangre = max(0, S.sangre - dt * .9)
    S.marcador = max(0, S.marcador - dt * 5)
    S.kick = max(0, S.kick - dt * 6)
    moviendo = any(held_keys[k] for k in 'wasd')
    S.gap = lerp(S.gap, .007 + (.012 if moviendo else 0) + S.kick * .025, min(1, dt * 14))
    mira[0].y = S.gap + .012
    mira[1].y = -S.gap - .012
    mira[2].x = S.gap + .012
    mira[3].x = -S.gap - .012
    if fuera != S.en_tormenta:
        S.en_tormenta = fuera
        vineta.color = C('#7a2cff' if fuera else '#c00000')
    vineta.alpha = min(1, S.sangre + (.4 if S.hp < 30 else 0)) * (1 if T_VINETA else .4)
    marca_g.enabled = S.marcador > 0

    # textos y barras
    S.t_msg -= dt
    if S.t_msg <= 0:
        poner(t_msg, '')
    hp = max(0, S.hp)
    b_hp.scale_x = max(.001, .24 * hp / 100)
    nivel = 0 if hp > 60 else (1 if hp > 30 else 2)
    if nivel != S.hp_nivel:
        S.hp_nivel = nivel
        b_hp.color = C(('#5aa04a', '#d9a441', '#c4452d')[nivel])
    poner(t_hp, str(int(math.ceil(hp))))
    poner(t_puntos, f'CHAPAS  {S.puntos}')
    poner(t_bajas, f'BAJAS  {S.bajas}')
    mapa_g.enabled = bool(S.br)
    if S.br:
        vivos = len(S.enemigos) + 1
        if S.z_estado == 'encoge':
            zona = 'ZONA CERRÁNDOSE'
        elif S.z_estado == 'espera':
            zona = f'Zona en {int(max(0, S.z_t))} s'
        else:
            zona = 'ZONA FINAL'
        poner(t_ola, 'BATTLE ROYALE')
        poner(t_rest, f'Vivos: {vivos}   ·   {zona}')
        b_ola.scale_x = max(.001, .5 * vivos / (N_BOTS + 1))
        poner(t_gran, f'GRANADAS  {S.granadas}    MATERIALES  {S.materiales}')
        actualizar_minimapa()
    else:
        poner(t_ola, f'OLEADA {S.ola}')
        poner(t_rest, f'Enemigos restantes: {S.restantes}' if S.restantes > 0 else 'Oleada despejada')
        b_ola.scale_x = max(.001, .5 * max(0, S.restantes) / max(1, 4 + S.ola * 3))
        poner(t_gran, f'GRANADAS  {S.granadas}')
    poner(t_armanom, ARMAS[S.arma]['n'].upper())
    poner(t_mun, str(S.municion[S.arma]))
    poner(t_res, f'/ {S.reserva[S.arma]}')
    if fuera:
        poner(t_estado, 'FUERA DE LA ZONA')
    elif S.recargando:
        poner(t_estado, 'RECARGANDO...')
    elif S.municion[S.arma] == 0 and S.reserva[S.arma] == 0:
        poner(t_estado, 'SIN MUNICIÓN')
    else:
        poner(t_estado, '')
    poner(t_hint, 'CONSTRUIR:  Z pared   X piso   C rampa   Q salir   clic = colocar' if S.construyendo else '')
    for i, t in enumerate(t_tiles):
        poner(t, f'{i + 1}  {ARMAS[i]["n"]}\n{S.municion[i]} / {S.reserva[i]}' if S.tiene[i] else f'{i + 1}  ---')
    if S.arma != S.hud_arma:
        S.hud_arma = S.arma
        for i, p in enumerate(tiles):
            sel = i == S.arma
            p.color = C(ORO if sel else '#0b0907')
            p.alpha = .9 if sel else .55
            t_tiles[i].color = C('#14110d' if sel else CREMA)


# ------------------------------------------------------------------ arranque
construir_mundo()
construir_vitrina()
S.municion = [ef(i)['cargador'] for i in range(len(ARMAS))]
S.reserva = [a['reserva'] for a in ARMAS]
cambiar_arma(S.arma_inicial)
aplicar_graficos(True)
abrir_menu(*TEXTOS_INICIO)
app.run()
