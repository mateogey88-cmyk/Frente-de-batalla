"""
FRENTE DE BATALLA - shooter 3D en primera persona (Python + Ursina)

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

C = color.hex          # C('#ff9a30') -> color

# ------------------------------------------------------------------ armas
# Para agregar un arma nueva: sumá una línea a esta lista.
ARMAS = [
    dict(n='Fusil',         dano=34,  ritmo=.095, cargador=30, reserva=120, recarga=1.7, dispersion=.006,  perdigones=1, auto=True,  retroceso=1.0, zoom=60, largo=.6,  col='#22252a'),
    dict(n='Pistola',       dano=30,  ritmo=.2,   cargador=12, reserva=72,  recarga=1.1, dispersion=.003,  perdigones=1, auto=False, retroceso=.6,  zoom=70, largo=.35, col='#2d3036'),
    dict(n='Escopeta',      dano=15,  ritmo=.8,   cargador=6,  reserva=36,  recarga=2.4, dispersion=.045,  perdigones=9, auto=False, retroceso=2.2, zoom=75, largo=.7,  col='#5a3a22'),
    dict(n='Francotirador', dano=100, ritmo=1.1,  cargador=5,  reserva=25,  recarga=2.5, dispersion=.0005, perdigones=1, auto=False, retroceso=2.5, zoom=20, largo=.9,  col='#1c2a1c'),
]


class S:
    """Todo el estado del juego en un solo lugar."""
    modo = 'menu'                 # menu | juego | pausa | fin
    panel = 'principal'           # principal | armas | config
    # opciones que se guardan en el disco
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


# ------------------------------------------------------------------ opciones guardadas
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


# ------------------------------------------------------------------ ventana y luces
app = Ursina(title='Frente de Batalla', borderless=False)
for nombre in ('fps_counter', 'exit_button', 'entity_counter', 'collider_counter'):
    obj = getattr(window, nombre, None)
    if obj is not None:
        obj.enabled = False
window.color = C('#8a5a40')

UI = {}   # opciones extra para los elementos de la interfaz
try:
    from ursina.shaders import lit_with_shadows_shader, unlit_shader
    Entity.default_shader = lit_with_shadows_shader
    UI = dict(shader=unlit_shader)
    sol = DirectionalLight(shadows=True)
    sol.look_at(Vec3(1, -1, -.6))
except Exception as e:
    print('Sin iluminación avanzada:', e)
try:
    scene.fog_color = C('#8a5a40')
    scene.fog_density = (40, 140)
except Exception:
    pass


# ------------------------------------------------------------------ mundo
mundo = Entity()      # todo lo que bloquea balas y enemigos cuelga de acá
ruinas = []
PUNTOS = []           # puntos donde aparecen los enemigos
LADRILLO = ['#6e4a3c', '#7a5442', '#5d3f33', '#8a6249']
CONCRETO = ['#6a6762', '#7c786f', '#5a5752']


def bloque(x, z, ancho, alto, largo, col, y=0.0, solido=True):
    return Entity(parent=mundo if solido else None, model='cube',
                  position=(x, y + alto / 2, z), scale=(ancho, alto, largo),
                  color=C(col), collider='box' if solido else None)


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
    for _ in range(9):     # escombros
        e = bloque(cx + random.uniform(-w / 2, w / 2), cz + random.uniform(-d / 2, d / 2),
                   random.uniform(.3, 1), random.uniform(.2, .6), random.uniform(.3, 1),
                   random.choice(LADRILLO + CONCRETO), solido=False)
        e.rotation = (random.uniform(-15, 15), random.uniform(0, 180), random.uniform(-15, 15))


def construir_mundo():
    # suelo y límites invisibles
    Entity(model='cube', scale=(130, 1, 130), y=-.5, color=C('#5a4631'), collider='box')
    for lado in (-1, 1):
        Entity(parent=mundo, model='cube', position=(60 * lado, 5, 0), scale=(1, 10, 124), collider='box', visible=False)
        Entity(parent=mundo, model='cube', position=(0, 5, 60 * lado), scale=(124, 10, 1), collider='box', visible=False)

    # edificios en ruinas
    intentos = 0
    while len(ruinas) < 11 and intentos < 300:
        intentos += 1
        p = Vec3(random.uniform(-50, 50), 0, random.uniform(-50, 50))
        if p.length() < 13 or cerca_de_ruina(p, 17):
            continue
        ruinas.append(p)
        ruina(p.x, p.z, random.uniform(7, 11), random.uniform(6, 10))

    # sacos de arena cerca del centro
    for i in range(7):
        a, r = i * .9 + random.uniform(0, .4), random.uniform(8, 14)
        p = Vec3(math.sin(a) * r, 0, math.cos(a) * r)
        if cerca_de_ruina(p, 8):
            continue
        ancho, largo = (.8, 4.5) if random.random() < .5 else (4.5, .8)
        bloque(p.x, p.z, ancho, .55, largo, '#8a7a55')
        bloque(p.x, p.z, ancho * .9, .5, largo * .9, '#8a7a55', y=.55)

    # cajas
    for _ in range(12):
        p = Vec3(random.uniform(-52, 52), 0, random.uniform(-52, 52))
        if p.length() < 6 or cerca_de_ruina(p, 8):
            continue
        bloque(p.x, p.z, 1.2, 1.2, 1.2, '#6a4a2a')
        if random.random() < .4:
            bloque(p.x, p.z, 1.2, 1.2, 1.2, '#6a4a2a', y=1.2)

    # tanques destruidos
    for x, z in ((-20, -12), (22, 18)):
        if cerca_de_ruina(Vec3(x, 0, z), 8):
            continue
        bloque(x, z, 5, 1.3, 2.6, '#3a3f35')
        bloque(x, z, 2, .8, 2, '#3a3f35', y=1.3)
        bloque(x + 2.2, z, 3.5, .2, .2, '#3a3f35', y=1.9)

    # barriles
    puestos = 0
    for _ in range(100):
        if puestos >= 4:
            break
        p = Vec3(random.uniform(-35, 35), 0, random.uniform(-35, 35))
        if p.length() < 8 or cerca_de_ruina(p, 9):
            continue
        puestos += 1
        bloque(p.x, p.z, .8, 1.1, .8, '#6a2a1a')
        bloque(p.x, p.z, .6, .1, .6, '#ff7a2a', y=1.1, solido=False)

    # skyline lejano
    for i in range(40):
        ang, rad, h = i / 40 * math.tau, random.uniform(95, 130), random.uniform(15, 45)
        Entity(model='cube', color=C('#1e1618'), position=(math.sin(ang) * rad, h / 2, math.cos(ang) * rad),
               scale=(random.uniform(8, 20), h, random.uniform(8, 20)))

    # puntos de aparición enemiga
    for _ in range(40):
        ang, rad = random.uniform(0, math.tau), random.uniform(38, 56)
        p = Vec3(max(-56, min(56, math.sin(ang) * rad)), 0, max(-56, min(56, math.cos(ang) * rad)))
        if not cerca_de_ruina(p, 9):
            PUNTOS.append(p)


# ------------------------------------------------------------------ jugador y arma
jugador = FirstPersonController(position=(0, .1, 0))
jugador.jump_height = 1.2
if hasattr(jugador, 'cursor'):
    jugador.cursor.alpha = 0      # la mira propia es el '+'; el controlador necesita que este objeto exista
camera.clip_plane_near = .05
camera.fov = S.fov

arma = Entity(parent=camera, model='cube', position=(.25, -.25, .7))
fogonazo = Entity(parent=arma, model='cube', color=C('#ffd070'), scale=(2, 2, .25), z=.55, enabled=False, **UI)


def cambiar_arma(i):
    S.arma, S.recargando, S.enfriamiento = i, False, .3
    a = ARMAS[i]
    arma.scale = (.07, .09, a['largo'])
    arma.color = C(a['col'])


# ------------------------------------------------------------------ interfaz
ORO, CREMA = '#d9a441', '#f1e7d0'
hud = Entity(parent=camera.ui)
menu = Entity(parent=camera.ui)


def texto(padre, t, pos, esc=1.0, col=CREMA, origen=(0, 0)):
    return Text(t, parent=padre, position=pos, scale=esc, color=C(col), origin=origen)


def poner(t, txt):
    """Cambia el texto solo si cambió (evita regenerarlo en cada frame)."""
    if getattr(t, '_ult', None) != txt:
        t._ult = txt
        t.text = txt


sangre = Entity(parent=hud, model='quad', scale=(2, 1.2), z=1, color=C('#c80000'), **UI)
sangre.alpha = 0
t_ola = texto(hud, '', (0, .46), 2, ORO)
t_rest = texto(hud, '', (0, .41), 1.1)
t_msg = texto(hud, '', (0, .32), 2, ORO)
t_mun = texto(hud, '', (.85, -.40), 2.5, origen=(.5, 0))
t_gran = texto(hud, '', (.85, -.46), 1.1, origen=(.5, 0))
t_armas = texto(hud, '', (0, -.46), 1, '#b9ab8c')
texto(hud, 'Salud', (-.85, -.40), 1.1, origen=(-.5, 0))
Entity(parent=hud, model='quad', color=C('#2a2420'), scale=(.3, .03), position=(-.85, -.44), origin=(-.5, 0), **UI)
barra = Entity(parent=hud, model='quad', color=C('#c4452d'), scale=(.3, .03), position=(-.85, -.44), origin=(-.5, 0), z=-.1, **UI)
texto(hud, '+', (0, 0), 2)
marca = texto(hud, 'x', (0, 0), 2, '#c4452d')

fondo = Entity(parent=menu, model='quad', scale=(2, 1.2), z=1, color=C('#0d0a07'), **UI)
fondo.alpha = .85

DESC = ['Automático. Equilibrado.', 'Semiautomática. Rápida y precisa.',
        '9 perdigones. Letal de cerca.', 'Un tiro, una baja. Clic derecho: zoom.']
DIFICULTADES = [('Fácil', .6), ('Normal', 1.0), ('Difícil', 1.5)]   # (nombre, daño que te hacen)


def boton(padre, txt, pos, accion, ancho=.42, alto=.075):
    return Button(parent=padre, text=txt, position=pos, scale=(ancho, alto), color=C('#3a2f22'),
                  highlight_color=C('#6a4f2a'), pressed_color=C('#8a6a30'), on_click=accion, **UI)


def mensaje(txt):
    poner(t_msg, txt)
    S.t_msg = 1.8


def limpiar():
    for e in S.enemigos + S.recogibles:
        destroy(e)
    S.enemigos.clear()
    S.recogibles.clear()


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


TEXTOS_INICIO = ('Frente de Batalla', 'Un soldado, una línea, sin refuerzos.\nResistí las oleadas.', 'JUGAR', 'SALIR')

# --- panel principal
p_principal = Entity(parent=menu)
p_armas = Entity(parent=menu)
p_config = Entity(parent=menu)
paneles = {'principal': p_principal, 'armas': p_armas, 'config': p_config}


def mostrar_panel(nombre):
    S.panel = nombre
    for n, pn in paneles.items():
        pn.enabled = (n == nombre)


m_titulo = texto(p_principal, '', (0, .32), 4, ORO)
m_sub = texto(p_principal, '', (0, .2), 1.4)
b_jugar = boton(p_principal, '', (0, .06), accion_jugar)
boton(p_principal, 'ELEGIR ARMA', (0, -.04), lambda: mostrar_panel('armas'))
boton(p_principal, 'CONFIGURACIÓN', (0, -.14), lambda: mostrar_panel('config'))
b_salir = boton(p_principal, '', (0, -.24), accion_salir)
m_record = texto(p_principal, '', (0, -.33), 1.1, ORO)
texto(p_principal, 'W A S D mover   Mouse apuntar   Clic disparar   Clic derecho zoom\n'
                   '1 a 4 o rueda: arma   R recargar   G granada   Shift correr   Espacio saltar   Esc pausa',
      (0, -.42), .9, '#b9ab8c')

# --- panel de armas
texto(p_armas, 'Elegí tu arma', (0, .32), 3, ORO)
b_armas = []


def elegir_arma(i):
    S.arma_inicial = i
    if S.modo == 'pausa':
        cambiar_arma(i)
    refrescar_armas()
    guardar()


def refrescar_armas():
    for i, b in enumerate(b_armas):
        b.text = f'[ {ARMAS[i]["n"]} ]' if i == S.arma_inicial else ARMAS[i]['n']
    w = ARMAS[S.arma_inicial]
    poner(m_stats, f'{w["n"]}\n{DESC[S.arma_inicial]}\n\n'
                   f'Daño {w["dano"]}   Cargador {w["cargador"]}   Munición de reserva {w["reserva"]}   Recarga {w["recarga"]} s')


for i, w in enumerate(ARMAS):
    b_armas.append(boton(p_armas, w['n'], (-.57 + i * .38, .15), lambda i=i: elegir_arma(i), .35, .12))
m_stats = texto(p_armas, '', (0, -.05), 1.3)
boton(p_armas, 'VOLVER', (0, -.3), lambda: mostrar_panel('principal'))

# --- panel de configuración
texto(p_config, 'Configuración', (0, .32), 3, ORO)


def fila(y, nombre, menos, mas):
    texto(p_config, nombre, (-.5, y), 1.4, origen=(-.5, 0))
    boton(p_config, '-', (.15, y), menos, .07, .07)
    valor = texto(p_config, '', (.35, y), 1.4)
    boton(p_config, '+', (.55, y), mas, .07, .07)
    return valor


def cambiar(campo, paso):
    if campo == 'sens':
        S.sens = max(10, min(100, S.sens + paso))
    elif campo == 'fov':
        S.fov = max(70, min(110, S.fov + paso))
        camera.fov = S.fov
    else:
        S.dif = max(0, min(2, S.dif + paso))
    refrescar_config()
    guardar()


def borrar_record():
    S.record_ola = S.record_bajas = 0
    guardar()
    poner(m_record, '')


def refrescar_config():
    poner(v_sens, str(S.sens))
    poner(v_fov, str(S.fov))
    poner(v_dif, DIFICULTADES[S.dif][0])


v_sens = fila(.15, 'Sensibilidad del mouse', lambda: cambiar('sens', -5), lambda: cambiar('sens', 5))
v_fov = fila(.03, 'Campo de visión', lambda: cambiar('fov', -5), lambda: cambiar('fov', 5))
v_dif = fila(-.09, 'Dificultad', lambda: cambiar('dif', -1), lambda: cambiar('dif', 1))
boton(p_config, 'BORRAR RÉCORD', (0, -.2), borrar_record, .42, .06)
boton(p_config, 'VOLVER', (0, -.3), lambda: mostrar_panel('principal'))


def abrir_menu(titulo, sub, jugar, salir):
    poner(m_titulo, titulo)
    poner(m_sub, sub)
    b_jugar.text = jugar
    b_salir.text = salir
    poner(m_record, f'Récord: oleada {S.record_ola}  ·  {S.record_bajas} bajas' if S.record_ola else '')
    refrescar_armas()
    refrescar_config()
    mostrar_panel('principal')
    menu.enabled = True
    hud.enabled = False
    mouse.locked = False
    jugador.enabled = False
    camera.fov = S.fov


def entrar_al_juego():
    S.modo = 'juego'
    S.enfriamiento = .3
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
        uniforme = random.choice(('#4a5238', '#3f4638', '#56563f'))
        self.cuerpo = Entity(parent=self, model='cube', color=C(uniforme), position=(0, 1.1, 0), scale=(.55, .9, .35), collider='box')
        self.cabeza = Entity(parent=self, model='cube', color=C('#c9a07a'), position=(0, 1.75, 0), scale=(.32, .32, .32), collider='box')
        Entity(parent=self, model='cube', color=C('#2f3328'), position=(0, .35, 0), scale=(.4, .7, .28))
        Entity(parent=self, model='cube', color=C('#1c1e1f'), position=(.2, 1.2, .4), scale=(.08, .1, .7))
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
        if raycast(self.position + Vec3(0, 1, 0), mv.normalized(), distance=1.5, traverse_target=mundo).hit:
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
        if cabeza:
            mensaje('Disparo a la cabeza')
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
        self_salud = random.random() < .5
        super().__init__(model='cube', position=pos + Vec3(0, .4, 0), scale=(.5, .35, .4),
                         color=C('#eeeeee' if self_salud else '#4d5a2e'))
        self.salud = self_salud
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
    for i, a in enumerate(ARMAS):
        S.reserva[i] += a['cargador'] * (2 if i == S.arma else 1)


def dano_jugador(n):
    S.hp -= n
    S.sangre = 1.0
    if S.hp <= 0 and S.modo == 'juego':
        S.modo = 'fin'
        sub = f'Llegaste a la oleada {S.ola} con {S.bajas} bajas.'
        if (S.ola, S.bajas) > (S.record_ola, S.record_bajas):
            S.record_ola, S.record_bajas = S.ola, S.bajas
            guardar()
            sub += '\n¡Nuevo récord!'
        abrir_menu('Caíste en combate', sub, 'JUGAR DE NUEVO', 'SALIR AL MENÚ')


def siguiente_ola():
    S.ola += 1
    S.por_aparecer = 4 + S.ola * 3
    S.restantes = S.por_aparecer
    if S.ola > 1:
        dar_municion()
        curar(15)
        S.granadas = min(4, S.granadas + 1)
    mensaje(f'Oleada {S.ola}')


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
    cambiar_arma(S.arma_inicial)
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
    arma.z = .6
    arma.animate_z(.7, .1)
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
                enemigo.golpe(min(100, a['dano'] * 3) if cabeza else a['dano'], cabeza, fin)
            else:
                chispas(fin, '#ffc060', 5, 5, .04, .35)
        trazador(boca, fin, '#ffd28a')


def recargar():
    a = ARMAS[S.arma]
    if S.recargando or S.municion[S.arma] >= a['cargador'] or S.reserva[S.arma] <= 0:
        return
    S.recargando = True
    S.t_recarga = a['recarga']
    arma.animate_y(-.5, a['recarga'] / 2, curve=curve.out_quad)
    arma.animate_y(-.25, a['recarga'] / 2, delay=a['recarga'] / 2, curve=curve.in_quad)


def lanzar_granada():
    if S.granadas <= 0 or S.t_granada > 0:
        return
    S.granadas -= 1
    S.t_granada = .8
    Granada()


def pausar():
    S.modo = 'pausa'
    abrir_menu('Pausa', 'Tu partida te espera.', 'CONTINUAR', 'SALIR AL MENÚ')


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
    if S.modo != 'juego':
        return
    dt = time.dt
    a = ARMAS[S.arma]

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
    arma.visible = not (S.arma == 3 and zoom and camera.fov < 45)

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

    # interfaz
    S.sangre = max(0, S.sangre - dt * .9)
    S.marcador = max(0, S.marcador - dt * 5)
    S.t_msg -= dt
    if S.t_msg <= 0:
        poner(t_msg, '')
    sangre.alpha = min(1, S.sangre + (.35 if S.hp < 30 else 0))
    marca.enabled = S.marcador > 0
    barra.scale_x = .3 * max(0, S.hp) / 100
    poner(t_ola, f'Oleada {S.ola}')
    poner(t_rest, f'Enemigos restantes: {S.restantes}' if S.restantes > 0 else 'Oleada despejada')
    poner(t_mun, ('Recargando' if S.recargando else str(S.municion[S.arma])) + f' / {S.reserva[S.arma]}')
    poner(t_gran, f'Granadas {S.granadas}')
    poner(t_armas, '   '.join(
        ('[{} {} {}/{}]' if i == S.arma else '{} {} {}/{}').format(i + 1, w['n'], S.municion[i], S.reserva[i])
        for i, w in enumerate(ARMAS)))


# ------------------------------------------------------------------ arranque
construir_mundo()
S.municion = [a['cargador'] for a in ARMAS]
S.reserva = [a['reserva'] for a in ARMAS]
cambiar_arma(S.arma_inicial)
abrir_menu(*TEXTOS_INICIO)
app.run()
