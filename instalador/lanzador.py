"""
Lanzador de Chloe POS (programa instalado).

Lo ejecuta el ícono del escritorio con el Python incluido en la instalación (pythonw.exe, sin consola):
  - prepara la carpeta de datos (base de datos, clave secreta, registros)
  - aplica las migraciones y hace el respaldo diario
  - levanta el servidor local (Waitress) en 127.0.0.1
  - abre la ventana del programa (Edge en modo aplicación)

Si el servidor ya está corriendo, solo abre la ventana.

Opciones:
  --servidor   solo levanta el servidor, sin abrir ventana (lo usa el instalador al actualizar)
  --respaldar  crea un respaldo de la base de datos y avisa dónde quedó
  --restablecer-clave  borra la clave de administrador (si se olvidó)
  --detener    detiene el servidor si está corriendo
"""
import ctypes
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from ctypes import wintypes
from pathlib import Path

PUERTO = 8765
URL = f'http://127.0.0.1:{PUERTO}/'
NOMBRE = 'Chloe POS'

INSTALACION = Path(__file__).resolve().parent
APP_DIR = INSTALACION / 'app'
# CHLOE_POS_DATOS permite usar otra carpeta de datos (solo para pruebas)
DATOS = Path(os.environ.get('CHLOE_POS_DATOS') or Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / NOMBRE)
PID_FILE = DATOS / 'servidor.pid'


def carpeta_documentos():
    """Carpeta Documentos real del usuario (aunque esté redirigida a OneDrive)."""
    try:
        class GUID(ctypes.Structure):
            _fields_ = [('a', wintypes.DWORD), ('b', wintypes.WORD), ('c', wintypes.WORD), ('d', ctypes.c_ubyte * 8)]
        documentos = GUID(0xFDD39AD0, 0x238F, 0x46AF, (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
        ruta = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(documentos), 0, None, ctypes.byref(ruta)) == 0:
            valor = ruta.value
            ctypes.windll.ole32.CoTaskMemFree(ruta)
            return Path(valor)
    except Exception:
        pass
    return Path.home() / 'Documents'


RESPALDOS = (DATOS / 'respaldos') if os.environ.get('CHLOE_POS_DATOS') else carpeta_documentos() / f'{NOMBRE} - Respaldos'


def mensaje(texto, titulo=NOMBRE, error=False):
    ctypes.windll.user32.MessageBoxW(None, texto, titulo, 0x10 if error else 0x40)


def registrar_error(contexto):
    try:
        (DATOS / 'logs').mkdir(parents=True, exist_ok=True)
        with open(DATOS / 'logs' / 'lanzador.log', 'a', encoding='utf-8') as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {contexto}\n{traceback.format_exc()}")
    except Exception:
        pass


def preparar_entorno():
    DATOS.mkdir(parents=True, exist_ok=True)
    RESPALDOS.mkdir(parents=True, exist_ok=True)
    clave = DATOS / 'secret.key'
    if not clave.exists():
        clave.write_text(secrets.token_urlsafe(50), encoding='utf-8')
    os.environ['CHLOE_DATA_DIR'] = str(DATOS)
    os.environ['CHLOE_BACKUP_DIR'] = str(RESPALDOS)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'ProyectoInventario.settings'
    sys.path.insert(0, str(APP_DIR))


def servidor_activo():
    try:
        with urllib.request.urlopen(URL + 'api/sistema/salud/', timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


def ruta_edge():
    for base in (os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'), os.environ.get('LOCALAPPDATA')):
        if base:
            exe = Path(base) / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe'
            if exe.exists():
                return exe
    return shutil.which('msedge')


def abrir_ventana():
    edge = ruta_edge()
    if edge:
        # Perfil propio: ventana tipo aplicación, sin pestañas ni barra de direcciones
        subprocess.Popen([
            str(edge), f'--app={URL}', f'--user-data-dir={DATOS / "navegador"}',
            '--no-first-run', '--no-default-browser-check', '--disable-features=Translate',
            '--start-maximized',
        ], close_fds=True)
    else:
        webbrowser.open(URL)


def iniciar_django():
    import django
    django.setup()
    from django.core.management import call_command
    call_command('migrate', interactive=False, verbosity=0)
    try:
        from AppInventario.sistema import respaldo_diario
        respaldo_diario()
    except Exception:
        registrar_error('Respaldo diario')


def correr_servidor(abrir):
    from waitress import serve
    from django.core.wsgi import get_wsgi_application
    app = get_wsgi_application()
    PID_FILE.write_text(str(os.getpid()), encoding='utf-8')
    if abrir:
        def esperar_y_abrir():
            for _ in range(60):
                if servidor_activo():
                    break
                time.sleep(0.25)
            abrir_ventana()
        threading.Thread(target=esperar_y_abrir, daemon=True).start()
    try:
        serve(app, host='127.0.0.1', port=PUERTO, threads=6, ident=NOMBRE)
    finally:
        PID_FILE.unlink(missing_ok=True)


def detener():
    try:
        pid = int(PID_FILE.read_text())
        handle = ctypes.windll.kernel32.OpenProcess(0x0001, False, pid)  # PROCESS_TERMINATE
        if handle:
            ctypes.windll.kernel32.TerminateProcess(handle, 0)
            ctypes.windll.kernel32.CloseHandle(handle)
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def main():
    args = sys.argv[1:]
    preparar_entorno()

    if '--detener' in args:
        detener()
        return

    if '--restablecer-clave' in args:
        # Para cuando se olvida la clave de administrador: la borra y se crea una nueva en Sistema
        if ctypes.windll.user32.MessageBoxW(
                None, '¿Borrar la clave de administrador de Chloe POS?\n\n'
                      'Después tendrás que crear una nueva en Sistema → Clave de administrador.',
                NOMBRE, 0x04 | 0x30) != 6:   # Sí/No + advertencia; 6 = Sí
            return
        import django
        django.setup()
        from django.core.management import call_command
        call_command('migrate', interactive=False, verbosity=0)
        from AppInventario.seguridad import restablecer
        restablecer()
        mensaje('La clave de administrador fue borrada.\n\nAbre Chloe POS y crea una nueva en Sistema.')
        return

    if '--respaldar' in args:
        import django
        django.setup()
        from AppInventario.sistema import crear_respaldo
        try:
            archivo = crear_respaldo('manual')
        except RuntimeError as e:
            mensaje(f'No se pudo crear el respaldo.\n\n{e}', error=True)
        else:
            mensaje(f'Respaldo creado:\n\n{archivo}')
        return

    solo_servidor = '--servidor' in args
    if servidor_activo():
        if not solo_servidor:
            abrir_ventana()
        return

    iniciar_django()
    try:
        correr_servidor(abrir=not solo_servidor)
    except OSError:
        # El puerto ya está ocupado (por ejemplo, dos clics seguidos): solo abrir la ventana
        if not solo_servidor:
            abrir_ventana()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        registrar_error('Error al iniciar')
        mensaje('No se pudo iniciar Chloe POS.\n\nEl detalle quedó en:\n'
                f'{DATOS / "logs" / "lanzador.log"}', error=True)
