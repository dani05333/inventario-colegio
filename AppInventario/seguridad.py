"""Clave de administrador: se pide para anular o borrar ventas y para eliminar registros."""
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


def restablecer():
    """Borra la clave (para cuando se olvida). Solo se usa desde el equipo con el lanzador."""
    Configuracion.objects.filter(clave=CLAVE_CONFIG).delete()
