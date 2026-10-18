"""Respaldos de la base de datos y actualizaciones del programa instalado."""
import hashlib
import json
import os
import socket
import sqlite3
import ssl
import subprocess
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings

DIAS_RESPALDO = 30          # los respaldos diarios se guardan este número de días
USER_AGENT = 'ChloePOS'


# ---------------------------------------------------------------------------
# Respaldos
# ---------------------------------------------------------------------------

def _ruta_db():
    db = settings.DATABASES['default']
    if db['ENGINE'] != 'django.db.backends.sqlite3':
        return None
    return Path(db['NAME'])


def crear_respaldo(motivo='manual'):
    """Copia segura de la base de datos (funciona aunque el programa esté en uso)."""
    origen = _ruta_db()
    if origen is None or not origen.exists():
        raise RuntimeError('No hay una base de datos local para respaldar.')
    destino_dir = Path(settings.RESPALDOS_DIR)
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / f"chloe-pos_{datetime.now():%Y-%m-%d_%H%M%S}_{motivo}.sqlite3"
    with sqlite3.connect(origen) as src, sqlite3.connect(destino) as dst:
        src.backup(dst)
    return destino


def respaldo_diario():
    """Un respaldo por día (al abrir el programa) y limpieza de los muy antiguos."""
    destino_dir = Path(settings.RESPALDOS_DIR)
    hoy = f"{datetime.now():%Y-%m-%d}"
    if not any(destino_dir.glob(f'chloe-pos_{hoy}_*.sqlite3')):
        crear_respaldo('diario')
    limite = datetime.now() - timedelta(days=DIAS_RESPALDO)
    for f in destino_dir.glob('chloe-pos_*_diario.sqlite3'):
        if datetime.fromtimestamp(f.stat().st_mtime) < limite:
            f.unlink(missing_ok=True)


def listar_respaldos(limite=15):
    destino_dir = Path(settings.RESPALDOS_DIR)
    if not destino_dir.exists():
        return []
    archivos = sorted(destino_dir.glob('chloe-pos_*.sqlite3'), key=lambda f: f.stat().st_mtime, reverse=True)
    return [{
        'nombre': f.name,
        'fecha': datetime.fromtimestamp(f.stat().st_mtime),
        'kb': max(1, f.stat().st_size // 1024),
        'motivo': f.stem.rsplit('_', 1)[-1],
    } for f in archivos[:limite]]


# ---------------------------------------------------------------------------
# Actualizaciones (Releases de GitHub)
# ---------------------------------------------------------------------------

def _version_tupla(v):
    partes = []
    for p in str(v).lstrip('vV').split('.'):
        num = ''.join(ch for ch in p if ch.isdigit())
        partes.append(int(num or 0))
    return tuple(partes + [0] * (3 - len(partes)))


def _contexto_ssl():
    """Certificados de Windows + los de certifi: un Windows recién instalado puede no tener
    aún el certificado raíz de GitHub (el navegador lo descarga solo; Python no)."""
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    return ctx


def _get(url, timeout=10):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/vnd.github+json'})
    return urllib.request.urlopen(req, timeout=timeout, context=_contexto_ssl())


def explicar_error(exc):
    """Mensaje entendible según la causa real del problema de conexión."""
    texto = str(exc)
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (403, 429):
            return 'GitHub limitó las consultas por un rato. Intenta nuevamente en una hora.'
        return f'GitHub respondió con un error ({exc.code}). Intenta más tarde.'
    if 'CERTIFICATE_VERIFY_FAILED' in texto or isinstance(getattr(exc, 'reason', None), ssl.SSLError) or isinstance(exc, ssl.SSLError):
        if 'not yet valid' in texto or 'expired' in texto:
            return 'La fecha u hora del equipo parece incorrecta. Corrígela en la configuración de Windows e intenta de nuevo.'
        return 'No se pudo verificar la conexión segura con GitHub (certificado). Revisa la fecha y hora del equipo.'
    if isinstance(exc, (TimeoutError, socket.timeout)) or 'timed out' in texto:
        return 'La conexión tardó demasiado. Revisa el internet e intenta de nuevo.'
    if isinstance(exc, urllib.error.URLError):
        return f'No hay conexión con GitHub ({getattr(exc, "reason", texto)}). Revisa el internet o el firewall.'
    return f'No se pudo revisar si hay actualizaciones ({type(exc).__name__}: {texto[:120]}).'


def buscar_actualizacion():
    """Consulta la última versión publicada. Devuelve un dict o lanza una excepción si no hay conexión."""
    try:
        with _get(f'https://api.github.com/repos/{settings.UPDATE_REPO}/releases/latest') as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        data = {}   # todavía no hay versiones publicadas: no hay nada que actualizar
    version = data.get('tag_name', '').lstrip('vV') or settings.APP_VERSION
    assets = data.get('assets', [])
    instalador = next((a for a in assets if a['name'].lower().endswith('.exe')), None)
    suma = next((a for a in assets if a['name'].lower().endswith('.sha256')), None)
    return {
        'version': version,
        'actual': settings.APP_VERSION,
        'nueva': bool(instalador) and _version_tupla(version) > _version_tupla(settings.APP_VERSION),
        'notas': data.get('body') or '',
        'fecha': data.get('published_at'),
        'url': instalador['browser_download_url'] if instalador else None,
        'sha256_url': suma['browser_download_url'] if suma else None,
        'mb': round(instalador['size'] / 1_048_576, 1) if instalador else None,
    }


def descargar_e_instalar():
    """Descarga el instalador de la última versión, lo verifica, respalda la base de datos,
    lanza la instalación silenciosa y cierra el servidor para que pueda reemplazar los archivos."""
    if not settings.INSTALADO:
        raise RuntimeError('Las actualizaciones solo funcionan en el programa instalado.')
    info = buscar_actualizacion()
    if not info['nueva']:
        raise RuntimeError('Ya tienes la última versión.')
    if not info['sha256_url']:
        raise RuntimeError('La versión publicada no trae su archivo de verificación (.sha256).')

    with _get(info['sha256_url']) as r:
        esperado = r.read().decode('utf-8', 'ignore').split()[0].strip().lower()

    carpeta = Path(settings.DATA_DIR) / 'actualizaciones'
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"ChloePOS-Setup-{info['version']}.exe"
    sha = hashlib.sha256()
    with _get(info['url'], timeout=60) as r, open(destino, 'wb') as f:
        while bloque := r.read(1 << 16):
            sha.update(bloque)
            f.write(bloque)
    if sha.hexdigest().lower() != esperado:
        destino.unlink(missing_ok=True)
        raise RuntimeError('El archivo descargado no pasó la verificación. Intenta nuevamente.')

    crear_respaldo(f"antes-de-{info['version']}")

    # Instalación silenciosa: el instalador cierra este programa, reemplaza los archivos
    # (los datos están en otra carpeta) y vuelve a levantar el servidor.
    flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(destino), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'],
                     creationflags=flags, close_fds=True)
    threading.Timer(1.5, lambda: os._exit(0)).start()
    return info
