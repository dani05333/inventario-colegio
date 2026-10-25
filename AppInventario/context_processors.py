from django.conf import settings

from . import impresora, secciones, seguridad


def sistema(request):
    """Versión, modo (instalado o desarrollo), clave de administrador y sección actual, para todas las plantillas."""
    seccion = secciones.actual(request)
    return {
        'APP_VERSION': settings.APP_VERSION,
        'INSTALADO': settings.INSTALADO,
        'TIENE_CLAVE': seguridad.tiene_clave,   # se evalúa solo si la plantilla lo usa
        'ACCESO_ADMIN': lambda: seguridad.acceso_admin(request),   # puede ver lo protegido con la clave
        'BOLETA_ANCHO': impresora.ancho,
        'SECCION': seccion,
        'OTRAS_SECCIONES': [s for s in secciones.SECCIONES if s is not seccion],
    }
