"""Presentación de imágenes y videos en la pantalla del cliente mientras no hay una venta en curso.

Se muestran en el orden en que se agregaron: cada imagen por los segundos elegidos y cada video
completo, sin sonido."""
import re
import shutil
import time
from pathlib import Path

from django.conf import settings

from .models import Configuracion

IMAGENES = {'.jpg', '.jpeg', '.png', '.webp'}
VIDEOS = {'.mp4', '.webm'}
EXTENSIONES = IMAGENES | VIDEOS
MAX_MB = 10
MAX_MB_VIDEO = 300
SEGUNDOS_OPCIONES = (3, 5, 8, 10, 15, 20)
INICIALES = Path(__file__).resolve().parent / 'presentacion_inicial'

# Firmas de archivo: evita que se suba algo que no sea realmente una imagen o un video
FIRMAS = (b'\xff\xd8\xff', b'\x89PNG\r\n\x1a\n', b'RIFF')
FIRMA_WEBM = b'\x1a\x45\xdf\xa3'


def es_video(nombre):
    return Path(nombre).suffix.lower() in VIDEOS


def _firma_valida(inicio, ext):
    if ext == '.mp4':
        return inicio[4:8] == b'ftyp'
    if ext == '.webm':
        return inicio.startswith(FIRMA_WEBM)
    return inicio.startswith(FIRMAS)


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


def archivos():
    """Imágenes y videos, en el orden en que se agregaron (el nombre empieza con la hora de subida)."""
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
    """Guarda una imagen o video subido (UploadedFile). Devuelve el nombre o lanza ValueError."""
    ext = Path(archivo.name).suffix.lower()
    if ext not in EXTENSIONES:
        raise ValueError(f'«{archivo.name}» no es una imagen JPG, PNG o WEBP ni un video MP4 o WEBM.')
    video = ext in VIDEOS
    limite = MAX_MB_VIDEO if video else MAX_MB
    if archivo.size > limite * 1024 * 1024:
        raise ValueError(f'«{archivo.name}» pesa más de {limite} MB.')
    inicio = archivo.read(12)
    archivo.seek(0)
    if not _firma_valida(inicio, ext):
        raise ValueError(f'«{archivo.name}» no parece ser {"un video" if video else "una imagen"} válido.')
    base = re.sub(r'[^a-zA-Z0-9_-]+', '-', Path(archivo.name).stem).strip('-').lower()[:40] or ('video' if video else 'imagen')
    # El nombre empieza con la hora de subida en microsegundos: así varios archivos subidos juntos
    # quedan en el orden en que se eligieron (con segundos quedaban en orden alfabético)
    nombre = f"{time.time_ns() // 1000}-{base}{'.jpg' if ext == '.jpeg' else ext}"
    with open(carpeta() / nombre, 'wb') as f:
        for trozo in archivo.chunks():
            f.write(trozo)
    return nombre


def eliminar(nombre):
    ruta = ruta_segura(nombre)
    if ruta is None:
        raise ValueError('El archivo no existe.')
    ruta.unlink()
