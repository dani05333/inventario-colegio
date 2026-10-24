"""Clave de administrador: se pide para anular o borrar ventas, para eliminar registros y para ver
cuánto se ha vendido y las cantidades (totales del historial, análisis e inventario)."""
import threading
import time

from django.contrib.auth.hashers import check_password, make_password

from .models import Configuracion

CLAVE_CONFIG = 'clave_admin'
LARGO_MINIMO = 4
MAX_INTENTOS = 5
BLOQUEO_SEGUNDOS = 5 * 60

_fallos = []            # momentos de los intentos fallidos recientes
_lock = threading.Lock()


class ClaveError(Exception):
    """Clave faltante, incorrecta o bloqueada por demasiados intentos."""


def tiene_clave():
    return Configuracion.objects.filter(clave=CLAVE_CONFIG).exclude(valor='').exists()


def _bloqueo_restante():
    ahora = time.time()
    with _lock:
        _fallos[:] = [t for t in _fallos if ahora - t < BLOQUEO_SEGUNDOS]
        if len(_fallos) >= MAX_INTENTOS:
            return int(BLOQUEO_SEGUNDOS - (ahora - _fallos[0])) + 1
    return 0


def verificar(clave):
    """Lanza ClaveError si la clave no es válida; no hace nada si es correcta."""
    if not tiene_clave():
        raise ClaveError('Aún no hay una clave de administrador. Créala en Sistema → Clave de administrador.')
    restante = _bloqueo_restante()
    if restante:
        raise ClaveError(f'Demasiados intentos fallidos. Espera {max(1, restante // 60)} minuto(s) e intenta de nuevo.')
    guardada = Configuracion.objects.get(clave=CLAVE_CONFIG).valor
    if not clave or not check_password(str(clave), guardada):
        with _lock:
            _fallos.append(time.time())
        raise ClaveError('Clave de administrador incorrecta.')
    with _lock:
        _fallos.clear()


def cambiar(nueva, actual=None):
    """Crea la clave (si no existe) o la cambia (exige la actual)."""
    if tiene_clave():
        verificar(actual)
    nueva = str(nueva or '')
    if len(nueva) < LARGO_MINIMO:
        raise ClaveError(f'La clave debe tener al menos {LARGO_MINIMO} caracteres.')
    Configuracion.objects.update_or_create(clave=CLAVE_CONFIG, defaults={'valor': make_password(nueva)})


# ---------------------------------------------------------------------------
# Acceso a las secciones con montos de venta o cantidades: al ingresar la clave quedan abiertas en este
# navegador hasta que se va a otra sección (middleware.CerrarAccesoAlSalir), se presiona
# «Bloquear» o pasan MINUTOS_ACCESO sin usarlas.
# ---------------------------------------------------------------------------

SESION_ACCESO = 'admin_acceso_hasta'
MINUTOS_ACCESO = 10


def acceso_admin(request):
    """True si se pueden ver los montos y cantidades protegidos (también si aún no se crea la clave)."""
    if not tiene_clave():
        return True
    return request.session.get(SESION_ACCESO, 0) > time.time()


def renovar_acceso(request):
    if tiene_clave():
        request.session[SESION_ACCESO] = time.time() + MINUTOS_ACCESO * 60


def abrir_acceso(request, clave):
    """Lanza ClaveError si la clave no es válida."""
    verificar(clave)
    request.session.cycle_key()
    renovar_acceso(request)


def cerrar_acceso(request):
    request.session.pop(SESION_ACCESO, None)


def restablecer():
    """Borra la clave (para cuando se olvida). Solo se usa desde el equipo con el lanzador."""
    Configuracion.objects.filter(clave=CLAVE_CONFIG).delete()
