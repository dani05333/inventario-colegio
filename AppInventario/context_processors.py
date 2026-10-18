from django.conf import settings


def sistema(request):
    """Versión y modo (instalado o desarrollo) disponibles en todas las plantillas."""
    return {
        'APP_VERSION': settings.APP_VERSION,
        'INSTALADO': settings.INSTALADO,
    }
