"""Ajustes de la impresora de boletas (impresora térmica de rollo)."""
from .models import Configuracion

ANCHOS = (58, 80)   # ancho del rollo de papel, en mm
ANCHO_DEFECTO = 58


def ancho():
    fila = Configuracion.objects.filter(clave='boleta_ancho').first()
    try:
        valor = int(fila.valor) if fila else ANCHO_DEFECTO
    except ValueError:
        valor = ANCHO_DEFECTO
    return valor if valor in ANCHOS else ANCHO_DEFECTO


def guardar_ancho(valor):
    valor = int(valor)
    if valor not in ANCHOS:
        raise ValueError('Ancho de rollo no válido.')
    Configuracion.objects.update_or_create(clave='boleta_ancho', defaults={'valor': str(valor)})
