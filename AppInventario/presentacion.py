"""Presentación de imágenes en la pantalla del cliente mientras no hay una venta en curso."""
import re
import shutil
import time
from pathlib import Path

from django.conf import settings

from .models import Configuracion

EXTENSIONES = {'.jpg', '.jpeg', '.png', '.webp'}
MAX_MB = 10
SEGUNDOS_OPCIONES = (3, 5, 8, 10, 15, 20)
INICIALES = Path(__file__).resolve().parent / 'presentacion_inicial'

# Firmas de archivo: evita que se suba algo que no sea realmente una imagen
FIRMAS = (b'\xff\xd8\xff', b'\x89PNG\r\n\x1a\n', b'RIFF')


def carpeta():
    """Carpeta de las imágenes. La primera vez se llena con las imágenes de fábrica."""
    destino = Path(settings.PRESENTACION_DIR)
    if not destino.exists():
        destino.mkdir(parents=True, exist_ok=True)
        if INICIALES.exists():
            for f in sorted(INICIALES.iterdir()):
                if f.suffix.lower() in EXTENSIONES:
                    shutil.copy2(f, destino / f.name)
    return destino


def imagenes():
    return sorted(f.name for f in carpeta().iterdir() if f.is_file() and f.suffix.lower() in EXTENSIONES)


def _config(clave, defecto):
    fila = Configuracion.objects.filter(clave=clave).first()
    return fila.valor if fila else defecto


def ajustes():
    try:
        segundos = int(_config('presentacion_segundos', '5'))
    except ValueError:
        segundos = 5
    return {
        'activa': _config('presentacion_activa', '1') == '1',
        'segundos': segundos if segundos in SEGUNDOS_OPCIONES else 5,
    }


def guardar_ajustes(activa, segundos):
    segundos = int(segundos)
    if segundos not in SEGUNDOS_OPCIONES:
        raise ValueError('Tiempo no válido.')
    Configuracion.objects.update_or_create(clave='presentacion_activa', defaults={'valor': '1' if activa else '0'})
    Configuracion.objects.update_or_create(clave='presentacion_segundos', defaults={'valor': str(segundos)})


def ruta_segura(nombre):
    """Ruta de una imagen solo si es un nombre válido dentro de la carpeta (nada de '../')."""
    if not nombre or '/' in nombre or '\\' in nombre or nombre.startswith('.'):
        return None
    ruta = carpeta() / nombre
    if ruta.suffix.lower() not in EXTENSIONES or not ruta.is_file():
        return None
    return ruta


def guardar_subida(archivo):
    """Guarda una imagen subida (UploadedFile). Devuelve el nombre o lanza ValueError."""
    ext = Path(archivo.name).suffix.lower()
    if ext not in EXTENSIONES:
        raise ValueError(f'«{archivo.name}» no es una imagen JPG, PNG o WEBP.')
    if archivo.size > MAX_MB * 1024 * 1024:
        raise ValueError(f'«{archivo.name}» pesa más de {MAX_MB} MB.')
    inicio = archivo.read(12)
    archivo.seek(0)
    if not inicio.startswith(FIRMAS):
        raise ValueError(f'«{archivo.name}» no parece ser una imagen válida.')
    base = re.sub(r'[^a-zA-Z0-9_-]+', '-', Path(archivo.name).stem).strip('-').lower()[:40] or 'imagen'
    nombre = f"{int(time.time())}-{base}{'.jpg' if ext == '.jpeg' else ext}"
    with open(carpeta() / nombre, 'wb') as f:
        for trozo in archivo.chunks():
            f.write(trozo)
    return nombre


def eliminar(nombre):
    ruta = ruta_segura(nombre)
    if ruta is None:
        raise ValueError('La imagen no existe.')
    ruta.unlink()
