"""
Arma el instalador de Chloe POS.

Uso (desde la carpeta del proyecto, con el entorno virtual activado):
    python instalador/construir.py

Resultado en instalador/salida/:
    ChloePOS-Setup-<versión>.exe          el instalador (para el pendrive o para publicar)
    ChloePOS-Setup-<versión>.exe.sha256   su verificación (se publica junto al .exe)

Requisitos en este computador: Inno Setup 6 (https://jrsoftware.org/isinfo.php) e internet
la primera vez (descarga Python portable y los paquetes; después quedan en caché en
%LOCALAPPDATA%\\ChloePOS-build, donde también se arma el programa).
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

PYTHON_VERSION = '3.13.16'
PY_TAG = '313'

INSTALADOR = Path(__file__).resolve().parent
RAIZ = INSTALADOR.parent
SALIDA = INSTALADOR / 'salida'
# El armado (miles de archivos) se hace en el disco interno del equipo: es más rápido,
# evita rutas largas y no depende de discos externos USB
TRABAJO = Path(os.environ.get('LOCALAPPDATA', tempfile.gettempdir())) / 'ChloePOS-build'
CACHE = TRABAJO / 'cache'
BUILD = TRABAJO / 'build' / 'programa'


def paso(texto):
    print(f'\n==> {texto}', flush=True)


def descargar_python():
    CACHE.mkdir(parents=True, exist_ok=True)
    zip_path = CACHE / f'python-{PYTHON_VERSION}-embed-amd64.zip'
    if not zip_path.exists():
        url = f'https://www.python.org/ftp/python/{PYTHON_VERSION}/{zip_path.name}'
        print(f'    descargando {url}')
        urllib.request.urlretrieve(url, zip_path)
    return zip_path


def preparar_python(zip_path):
    destino = BUILD / 'python'
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(destino)
    # Habilitar site-packages en el Python portable
    pth = destino / f'python{PY_TAG}._pth'
    pth.write_text(f'python{PY_TAG}.zip\n.\nLib\\site-packages\nimport site\n', encoding='utf-8')
    site_packages = destino / 'Lib' / 'site-packages'
    site_packages.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable, '-m', 'pip', 'install', '--quiet', '--disable-pip-version-check', '--no-compile',
        '--target', str(site_packages),
        '--platform', 'win_amd64', '--python-version', PYTHON_VERSION.rsplit('.', 1)[0],
        '--implementation', 'cp', '--only-binary=:all:',
        '--cache-dir', str(CACHE / 'pip'),
        '-r', str(INSTALADOR / 'requisitos.txt'),
    ], check=True)
    return destino / 'python.exe'


def copiar_programa():
    app = BUILD / 'app'
    ignorar = shutil.ignore_patterns('__pycache__', '*.pyc')
    for carpeta in ('AppInventario', 'ProyectoInventario'):
        shutil.copytree(RAIZ / carpeta, app / carpeta, ignore=ignorar)
    for archivo in ('VERSION', 'manage.py'):
        shutil.copy2(RAIZ / archivo, app / archivo)
    shutil.copy2(INSTALADOR / 'lanzador.py', BUILD / 'lanzador.py')
    shutil.copy2(INSTALADOR / 'chloe.ico', BUILD / 'chloe.ico')
    return app


def manage(python, app, *args):
    """Ejecuta un comando de Django con el Python portable, en modo instalado."""
    datos = Path(tempfile.mkdtemp(prefix='chloe-build-'))
    (datos / 'secret.key').write_text('solo-para-construir', encoding='utf-8')
    env = dict(os.environ, CHLOE_DATA_DIR=str(datos), DJANGO_SETTINGS_MODULE='ProyectoInventario.settings')
    codigo = (f'import sys; sys.path.insert(0, r"{app}"); '
              'from django.core.management import execute_from_command_line; '
              f'execute_from_command_line(["manage.py", *{list(args)!r}])')
    try:
        subprocess.run([str(python), '-c', codigo], check=True, env=env)
    finally:
        shutil.rmtree(datos, ignore_errors=True)


def buscar_iscc():
    candidatos = [
        Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Inno Setup 6' / 'ISCC.exe',
        Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Inno Setup 6' / 'ISCC.exe',
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Inno Setup 6' / 'ISCC.exe',
    ]
    for c in candidatos:
        if c.exists():
            return c
    encontrado = shutil.which('ISCC')
    if encontrado:
        return Path(encontrado)
    sys.exit('\nNo se encontró Inno Setup 6. Instálalo desde https://jrsoftware.org/isdl.php y vuelve a ejecutar.')


def main():
    version = (RAIZ / 'VERSION').read_text(encoding='utf-8').strip()
    sin_instalador = '--sin-instalador' in sys.argv   # solo arma la carpeta del programa (para probar)
    print(f'Construyendo Chloe POS {version}')
    iscc = None if sin_instalador else buscar_iscc()

    paso('Limpiando la carpeta de construcción')
    shutil.rmtree(BUILD.parent, ignore_errors=True)
    if BUILD.exists() and any(BUILD.iterdir()):
        sys.exit(f'\nNo se pudo limpiar {BUILD}. Cierra el programa de prueba o el explorador que tenga esa carpeta abierta.')
    BUILD.mkdir(parents=True, exist_ok=True)

    paso(f'Preparando Python {PYTHON_VERSION} portable y paquetes')
    python = preparar_python(descargar_python())

    paso('Copiando el programa')
    app = copiar_programa()

    paso('Verificando el proyecto y reuniendo archivos estáticos')
    manage(python, app, 'check')
    manage(python, app, 'collectstatic', '--noinput', '--verbosity', '0')

    if sin_instalador:
        print(f'\nPrograma armado en {BUILD} (sin instalador).')
        return

    paso('Compilando el instalador con Inno Setup')
    SALIDA.mkdir(exist_ok=True)
    subprocess.run([str(iscc), '/Q', f'/DAppVersion={version}', f'/DBuildDir={BUILD}', str(INSTALADOR / 'chloe-pos.iss')],
                   check=True, cwd=INSTALADOR)

    exe = SALIDA / f'ChloePOS-Setup-{version}.exe'
    suma = hashlib.sha256(exe.read_bytes()).hexdigest()
    (SALIDA / f'{exe.name}.sha256').write_text(f'{suma}  {exe.name}\n', encoding='utf-8')

    mb = exe.stat().st_size / 1_048_576
    print(f'\nListo: {exe} ({mb:.1f} MB)')
    print(f'       {exe.name}.sha256')


if __name__ == '__main__':
    main()
