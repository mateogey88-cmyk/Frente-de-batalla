"""
FRENTE DE BATALLA - shooter 3D en primera persona (Python + Ursina)

    pip install ursina
    python frente_de_batalla.py

W A S D mover | Shift correr | Espacio saltar | Mouse apuntar
Clic disparar | Clic derecho zoom | 1-4 o rueda: cambiar arma
R recargar | G granada | Esc o P pausa

Las opciones, los puntos, las mejoras de armas y el récord se guardan en
frente_de_batalla.json (en tu carpeta de usuario).
"""
import json
import math
import os
import random

from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController

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
    mejoras = [[0, 0, 0, 0] for _ in ARMAS]
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
INTS = ('fov', 'sens', 'dif', 'arma_inicial', 'record_ola', 'record_bajas', 'puntos')


def guardar():
    try:
        datos = {k: getattr(S, k) for k in INTS}
        datos['mejoras'] = S.mejoras
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
    except Exception:
        pass
    S.fov = max(70, min(110, S.fov))
    S.sens = max(10, min(100, S.sens))
    S.dif = max(0, min(2, S.dif))
    S.arma_inicial = max(0, min(len(ARMAS) - 1, S.arma_inicial))
    S.puntos = max(0, S.puntos)


cargar()


# ------------------------------------------------------------------ ventana, cielo y luces
app = Ursina(title='Frente de Batalla', borderless=False)
for nombre in ('fps_counter', 'exit_button', 'entity_counter', 'collider_counter'):
    obj = getattr(window, nombre, None)
    if obj is not None:
        obj.enabled = False
window.color = C('#8a5a40')


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


def armar_arma(padre, i, manos=False):
    """Modelo 3D de cada arma, hecho de cajas. El frente del arma apunta a +z."""
    g = Entity(parent=padre)
    M, D, W, V, N = '#17191c', '#2c2f34', '#6b4a2b', '#3b4332', '#101112'
    if i == 0:      # fusil de asalto
        pieza(g, (0, 0, 0), (.06, .085, .36), D)
        pieza(g, (0, -.005, .3), (.07, .07, .26), M)
        pieza(g, (0, .012, .52), (.022, .022, .2), M)
        pieza(g, (0, .012, .63), (.04, .04, .07), M)
        pieza(g, (0, -.02, -.3), (.05, .1, .24), V)
        pieza(g, (0, -.095, -.07), (.04, .11, .05), D, rotation_x=10)
        pieza(g, (0, -.13, .07), (.045, .17, .075), M, rotation_x=-8)
        pieza(g, (0, .07, 0), (.035, .04, .16), M)
        gl = [(0, -.115, -.07), (0, -.03, .3)]
    elif i == 1:    # pistola
        pieza(g, (0, .02, .1), (.04, .05, .24), D)
        pieza(g, (0, -.012, .09), (.04, .035, .22), M)
        pieza(g, (0, -.09, -.01), (.04, .12, .06), D, rotation_x=-12)
        pieza(g, (0, -.05, .06), (.03, .01, .07), M)
        pieza(g, (0, .02, .24), (.02, .02, .04), M)
        pieza(g, (0, .052, .0), (.02, .015, .02), M)
        gl = [(0, -.1, -.02), (0, -.05, .06)]
    elif i == 2:    # escopeta
        pieza(g, (0, 0, 0), (.065, .085, .28), D)
        pieza(g, (0, .02, .5), (.04, .04, .55), M)
        pieza(g, (0, -.025, .45), (.035, .035, .42), M)
        pieza(g, (0, -.03, .34), (.065, .055, .18), W)
        pieza(g, (0, -.03, -.3), (.055, .12, .3), W)
        pieza(g, (0, -.08, -.1), (.04, .1, .05), D)
        pieza(g, (0, .045, .76), (.012, .025, .012), M)
        gl = [(0, -.14, -.1), (0, -.04, .34)]
    else:           # francotirador
        pieza(g, (0, 0, .05), (.055, .08, .42), M)
        pieza(g, (0, -.02, -.33), (.055, .11, .32), V)
        pieza(g, (0, .04, -.3), (.05, .04, .18), V)
        pieza(g, (0, .012, .65), (.028, .028, .75), M)
        pieza(g, (0, .012, 1.03), (.045, .045, .08), M)
        pieza(g, (0, .085, .08), (.05, .05, .3), D)
        pieza(g, (0, .085, .26), (.065, .065, .07), D)
        pieza(g, (0, .085, -.07), (.058, .058, .06), D)
        pieza(g, (.055, .02, -.05), (.05, .015, .015), M)
        pieza(g, (0, -.09, .07), (.045, .1, .09), M)
        pieza(g, (0, -.09, -.12), (.04, .1, .05), D)
        gl = [(0, -.115, -.12), (0, -.04, .2)]
    if manos:
        pieza(g, gl[0], (.065, .07, .09), N)
        pieza(g, gl[1], (.075, .06, .11), N)
    return g


PALETAS = {
    'negro': dict(ropa='#3a4044', chaleco='#24282b', casco='#2c3033', pantalon='#30363a'),
    'verde': dict(ropa='#4a5339', chaleco='#2f3826', casco='#3e4632', pantalon='#3f4733'),
    'arena': dict(ropa='#74694b', chaleco='#524a36', casco='#5e5640', pantalon='#6b6147'),
}


def construir_soldado(padre, paleta='negro', arma_i=0):
    """Soldado táctico: casco, máscara de gas, chaleco, radio y botas. Sirve para enemigos y para el menú."""
    r = Entity(parent=padre)
    P = PALETAS[paleta]
    NEG, GUANTE = '#17191b', '#101112'
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
    pieza(r, (0, 1.71, .195), (.17, .05, .02), '#5d8794', **UI)  # lentes
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
if hasattr(jugador, 'cursor'):
    jugador.cursor.alpha = 0      # la mira propia es la de la interfaz; el controlador necesita que este objeto exista
camera.clip_plane_near = .05
camera.fov = S.fov

arma = Entity(parent=camera)
modelos_fp = [armar_arma(arma, i, manos=True) for i in range(len(ARMAS))]
fogonazo = Entity(parent=arma, model='cube', color=C('#ffd070'), scale=(.12, .12, .1), enabled=False, **UI)


def cambiar_arma(i):
    S.arma, S.recargando, S.enfriamiento = i, False, .3
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


# --- menú: botones a los costados, el soldado queda en el centro
def boton(padre, txt, pos, accion, ancho=.5, alto=.08):
    return Button(parent=padre, text=txt, position=pos, scale=(ancho, alto), color=C('#1d1813'),
                  highlight_color=C('#6a4f2a'), pressed_color=C('#8a6a30'), on_click=accion, **UI)


def limpiar():
    for e in S.enemigos + S.recogibles:
        destroy(e)
    S.enemigos.clear()
    S.recogibles.clear()


TEXTOS_INICIO = ('FRENTE DE\nBATALLA', 'Un soldado, una línea,\nsin refuerzos.\nResistí las oleadas.', 'JUGAR', 'SALIR')


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
        poner(m_aviso, 'No te alcanzan los puntos.')
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


def borrar_record():
    S.record_ola = S.record_bajas = 0
    guardar()
    refrescar_menu()


def refrescar_menu():
    i = S.arma_inicial
    # panel principal
    poner(m_info, 'RÉCORD\n' + (f'Oleada {S.record_ola}  ·  {S.record_bajas} bajas' if S.record_ola else 'Todavía sin récord')
          + f'\n\nPUNTOS\n{S.puntos}\n\nARMA\n{ARMAS[i]["n"]}\n\nDIFICULTAD\n{DIFICULTADES[S.dif][0]}')
    # armería
    for k, b in enumerate(b_armas):
        b.text = f'[ {ARMAS[k]["n"]} ]' if k == i else ARMAS[k]['n']
    poner(m_arma_t, ARMAS[i]['n'].upper())
    poner(m_arma_d, DESC[i])
    for k, (nombre, clave) in enumerate(MEJORAS):
        n = S.mejoras[i][k]
        t, b = filas_mej[k]
        actual = ef(i)[clave]
        if n < NIVEL_MAX:
            sig_n = list(S.mejoras[i])
            sig_n[k] += 1
            poner(t, f'{nombre}: {fmt(clave, actual)}  ->  {fmt(clave, ef(i, sig_n)[clave])}')
            b.text = f'Nv {n}/{NIVEL_MAX} · {costo(n)} pts'
        else:
            poner(t, f'{nombre}: {fmt(clave, actual)}  (máximo)')
            b.text = 'MÁXIMO'
    poner(m_puntos, f'Puntos: {S.puntos}')
    # configuración
    poner(v_sens, str(S.sens))
    poner(v_fov, str(S.fov))
    poner(v_dif, DIFICULTADES[S.dif][0])


p_principal = Entity(parent=menu)
p_armas = Entity(parent=menu)
p_config = Entity(parent=menu)
paneles = {'principal': p_principal, 'armas': p_armas, 'config': p_config}

panel(menu, (-.58, 0), (.66, 1.1), a=.82, z=.5)                     # paneles laterales
panel(menu, (.58, 0), (.66, 1.1), a=.82, z=.5)
panel(menu, (-.25, 0), (.004, 1.1), ORO, 1, .45)                    # filos dorados
panel(menu, (.25, 0), (.004, 1.1), ORO, 1, .45)

# principal
m_titulo = texto(p_principal, '', (-.86, .47), 3, ORO, (-.5, .5))
m_sub = texto(p_principal, '', (-.86, .29), 1.1, CREMA, (-.5, .5))
b_jugar = boton(p_principal, '', (-.58, .08), accion_jugar)
boton(p_principal, 'ARMERÍA Y MEJORAS', (-.58, -.02), lambda: mostrar_panel('armas'))
boton(p_principal, 'CONFIGURACIÓN', (-.58, -.12), lambda: mostrar_panel('config'))
b_salir = boton(p_principal, '', (-.58, -.22), accion_salir)
m_info = texto(p_principal, '', (.3, .44), 1.25, CREMA, (-.5, .5))
texto(p_principal, 'W A S D  mover\nShift  correr     Espacio  saltar\nClic  disparar     Clic derecho  zoom\n'
                   'R  recargar     G  granada\n1 a 4 o rueda  cambiar de arma\nEsc  pausa',
      (.3, -.2), .85, GRIS, (-.5, .5))

# armería
texto(p_armas, 'ARMERÍA', (-.86, .47), 3, ORO, (-.5, .5))
b_armas = [boton(p_armas, w['n'], (-.58, .2 - k * .1), lambda k=k: elegir_arma(k)) for k, w in enumerate(ARMAS)]
boton(p_armas, 'VOLVER', (-.58, -.3), lambda: mostrar_panel('principal'))
m_arma_t = texto(p_armas, '', (.3, .46), 2, ORO, (-.5, .5))
m_arma_d = texto(p_armas, '', (.3, .385), 1.0, GRIS, (-.5, .5))
filas_mej = []
for _k in range(len(MEJORAS)):
    _y = .24 - _k * .1
    filas_mej.append((texto(p_armas, '', (.3, _y), 1.05, CREMA, (-.5, 0)),
                      boton(p_armas, '', (.76, _y), lambda k=_k: comprar(k), .26, .065)))
m_puntos = texto(p_armas, '', (.3, -.2), 1.4, ORO, (-.5, 0))
m_aviso = texto(p_armas, '', (.3, -.27), 1.0, '#e8472d', (-.5, 0))
texto(p_armas, 'Ganás puntos eliminando enemigos\ny superando oleadas. Las mejoras\nse guardan para la próxima vez.',
      (.3, -.34), .8, GRIS, (-.5, .5))

# configuración
texto(p_config, 'AJUSTES', (-.86, .47), 3, ORO, (-.5, .5))
boton(p_config, 'VOLVER', (-.58, -.3), lambda: mostrar_panel('principal'))


def fila(y, nombre, menos, mas):
    texto(p_config, nombre, (.3, y), 1.1, CREMA, (-.5, 0))
    boton(p_config, '-', (.63, y), menos, .07, .07)
    valor = texto(p_config, '', (.72, y), 1.2)
    boton(p_config, '+', (.81, y), mas, .07, .07)
    return valor


texto(p_config, 'CONFIGURACIÓN', (.3, .46), 2, ORO, (-.5, .5))
v_sens = fila(.28, 'Sensibilidad', lambda: cambiar('sens', -5), lambda: cambiar('sens', 5))
v_fov = fila(.17, 'Campo de visión', lambda: cambiar('fov', -5), lambda: cambiar('fov', 5))
v_dif = fila(.06, 'Dificultad', lambda: cambiar('dif', -1), lambda: cambiar('dif', 1))
texto(p_config, 'La dificultad cambia cuánto daño\nte hacen los enemigos.', (.3, -.03), .85, GRIS, (-.5, .5))
boton(p_config, 'BORRAR RÉCORD', (.58, -.2), borrar_record, .5, .07)


# --- vitrina: un rincón lejano del mapa donde el soldado posa en el centro del menú
VITRINA_Z = 300
soldado_menu = None


def construir_vitrina():
    global soldado_menu
    v = Entity(position=(0, 0, VITRINA_Z))
    pieza(v, (0, -.15, 3.2), (5, .3, 5), '#1a1714')
    pieza(v, (0, .01, 3.2), (4.2, .02, 4.2), ORO, **UI)
    pieza(v, (0, .02, 3.2), (4.0, .02, 4.0), '#14110f')
    pieza(v, (0, 6, 11), (46, 26, .5), '#14100c', **UI)
    soldado_menu = construir_soldado(v, 'negro', S.arma_inicial)
    soldado_menu.position = (0, .04, 3.2)
    soldado_menu.rotation_y = 160


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
    b_jugar.text = jugar
    b_salir.text = salir
    poner(m_aviso, '')
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
    for _ in range(n):
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
        self.cool = 1.5
        self.lado = random.choice((-1, 1))
        self.t_lado = 2.0
        self.t_vista = 0.0
        self.ve = False
        self.paso = random.uniform(0, 6)
        self.modelo = construir_soldado(self, random.choice(('negro', 'negro', 'verde', 'arena')),
                                        random.choice((0, 0, 0, 2, 3)))
        # cajas invisibles donde pegan las balas: cuerpo y cabeza
        self.cuerpo = Entity(parent=self, model='cube', position=(0, 1.0, 0), scale=(.62, 1.2, .42), collider='box', visible=False)
        self.cabeza = Entity(parent=self, model='cube', position=(0, 1.78, 0), scale=(.36, .4, .4), collider='box', visible=False)
        for parte in (self.cuerpo, self.cabeza):
            parte.enemigo = self        # así la bala sabe a quién le pegó
        S.enemigos.append(self)

    def update(self):
        if S.modo != 'juego' or not self.vivo:
            return
        dt = time.dt
        self.cool -= dt
        self.t_lado -= dt
        self.t_vista -= dt
        dx, dz = jugador.x - self.x, jugador.z - self.z
        d = math.hypot(dx, dz) or .001
        hacia = Vec3(dx / d, 0, dz / d)
        lateral = Vec3(hacia.z * self.lado, 0, -hacia.x * self.lado)

        if self.t_lado <= 0:
            self.lado = -self.lado
            self.t_lado = random.uniform(1.5, 3.5)
        if self.t_vista <= 0:
            self.t_vista = .3
            ojos = self.position + Vec3(0, 1.4, 0)
            mira_a = jugador.position + Vec3(0, 1.5, 0) - ojos
            self.ve = not raycast(ojos, mira_a.normalized(), distance=mira_a.length(), traverse_target=mundo).hit

        mv = lateral * .6 if (d < self.pref and self.ve) else hacia
        if raycast(self.position + Vec3(0, 1, 0), mv.normalized(), distance=1.5, traverse_target=mundo).hit:
            mv = lateral
        camina = d > 1.5
        if camina:
            self.position += mv * self.vel * dt
        self.x = max(-58, min(58, self.x))
        self.z = max(-58, min(58, self.z))
        self.rotation_y = math.degrees(math.atan2(dx, dz))
        self.paso += dt * self.vel * 2.4
        giro = math.sin(self.paso) * 35 if camina else 0
        self.modelo.piernas[0].rotation_x = giro
        self.modelo.piernas[1].rotation_x = -giro

        if self.ve and d < 60 and self.cool <= 0:
            self.disparar(d)

    def disparar(self, d):
        self.cool = max(.4, random.uniform(.9, 1.7) - min(.5, S.ola * .04))
        r = math.radians(self.rotation_y)
        origen = self.position + Vec3(math.sin(r) * .95, 1.2, math.cos(r) * .95)
        punteria = max(.08, min(.55, .5 - d / 70 + S.ola * .012))
        blanco = jugador.position + Vec3(0, 1.5, 0)
        acierta = random.random() < punteria
        if not acierta:
            blanco += Vec3(random.uniform(-2, 2), random.uniform(-1, 1), random.uniform(-2, 2))
        destello(origen)
        trazador(origen, blanco, '#ff6a3a')
        if acierta:
            dano_jugador(random.uniform(5, 9) * (1 + S.ola * .03) * DIFICULTADES[S.dif][1])

    def golpe(self, dano, cabeza, punto):
        if not self.vivo:
            return
        self.hp -= dano
        chispas(punto, '#8a0f0f', 8, 3, .06, .5)
        S.marcador = 1.0
        if self.hp <= 0:
            self.morir(cabeza)

    def morir(self, cabeza):
        self.vivo = False
        S.enemigos.remove(self)
        self.cuerpo.collider = None
        self.cabeza.collider = None
        self.animate('rotation_x', -90, duration=.4)
        destroy(self, delay=8)
        S.bajas += 1
        S.restantes -= 1
        S.puntos += 20 if cabeza else 10
        if cabeza:
            mensaje('Disparo a la cabeza  +20')
        if random.random() < .22:
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
        sub = f'Llegaste a la oleada {S.ola}\ncon {S.bajas} bajas.'
        if (S.ola, S.bajas) > (S.record_ola, S.record_bajas):
            S.record_ola, S.record_bajas = S.ola, S.bajas
            sub += '\n¡Nuevo récord!'
        abrir_menu('CAÍSTE EN\nCOMBATE', sub, 'JUGAR DE NUEVO', 'SALIR AL MENÚ')


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
        mensaje(f'Oleada {S.ola}   +{premio} pts')
    else:
        mensaje(f'Oleada {S.ola}')


def aparecer():
    lejos = [p for p in PUNTOS if (p - jugador.position).length() > 28] or PUNTOS
    Enemigo(random.choice(lejos), min(4.2, 2.2 + S.ola * .15) * random.uniform(.9, 1.1), random.uniform(12, 22))


def nueva_partida():
    limpiar()
    S.guardada = None
    S.ola, S.bajas, S.hp, S.granadas = 0, 0, 100.0, 3
    S.t_aparicion = S.t_ola = 0.0
    S.municion = [ef(i)['cargador'] for i in range(len(ARMAS))]
    S.reserva = [a['reserva'] for a in ARMAS]
    jugador.position = (0, .1, 0)
    jugador.rotation_y = 0
    jugador.camera_pivot.rotation_x = 0
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
            else:
                chispas(fin, '#ffc060', 5, 5, .04, .35)
        trazador(boca, fin, '#ffd28a')


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


def pausar():
    S.modo = 'pausa'
    S.arma_inicial = S.arma
    abrir_menu('PAUSA', 'Tu partida te espera.', 'CONTINUAR', 'SALIR AL MENÚ')


# ------------------------------------------------------------------ bucle principal
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
        return
    a = ef(S.arma)

    # movimiento y arma
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
    arma.x = lerp(arma.x, 0 if zoom else ARMA_FP[S.arma][0], min(1, dt * 10))
    mirilla = S.arma == 3 and zoom and camera.fov < 45
    arma.visible = not mirilla
    scope_g.enabled = mirilla
    mira_g.enabled = not mirilla

    # oleadas
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
    poner(t_ola, f'OLEADA {S.ola}')
    poner(t_rest, f'Enemigos restantes: {S.restantes}' if S.restantes > 0 else 'Oleada despejada')
    b_ola.scale_x = max(.001, .5 * max(0, S.restantes) / max(1, 4 + S.ola * 3))
    poner(t_puntos, f'PUNTOS  {S.puntos}')
    poner(t_bajas, f'BAJAS  {S.bajas}')
    poner(t_armanom, ARMAS[S.arma]['n'].upper())
    poner(t_mun, str(S.municion[S.arma]))
    poner(t_res, f'/ {S.reserva[S.arma]}')
    poner(t_gran, f'GRANADAS  {S.granadas}')
    if S.recargando:
        poner(t_estado, 'RECARGANDO...')
    elif S.municion[S.arma] == 0 and S.reserva[S.arma] == 0:
        poner(t_estado, 'SIN MUNICIÓN')
    else:
        poner(t_estado, '')
    for i, t in enumerate(t_tiles):
        poner(t, f'{i + 1}  {ARMAS[i]["n"]}\n{S.municion[i]} / {S.reserva[i]}')
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
abrir_menu(*TEXTOS_INICIO)
app.run()
