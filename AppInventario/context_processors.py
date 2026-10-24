from django.conf import settings

from . import impresora, seguridad


def sistema(request):
    """Versión, modo (instalado o desarrollo) y si existe clave de administrador, para todas las plantillas."""
    return {
        'APP_VERSION': settings.APP_VERSION,
        'INSTALADO': settings.INSTALADO,
        'TIENE_CLAVE': seguridad.tiene_clave,   # se evalúa solo si la plantilla lo usa
        'ACCESO_ADMIN': lambda: seguridad.acceso_admin(request),   # puede ver totales de venta, análisis e inventario
        'BOLETA_ANCHO': impresora.ancho,
    }
