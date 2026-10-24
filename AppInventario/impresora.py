"""Impresoras térmicas de rollo (boletas de 58 mm, etiquetas en la de 80 mm): ancho de la boleta y drivers."""
import json
import os
import re
import subprocess

from django.conf import settings

from .models import Configuracion

ANCHOS = (58, 80)   # ancho del rollo de papel, en mm
ANCHO_DEFECTO = 58

# Drivers que vienen con el programa (los descarga instalador/construir.py), uno por ancho de rollo
DRIVERS = {58: 'driver-boletas-58mm.exe', 80: 'driver-boletas-80mm.exe'}

# Identificadores USB de las impresoras térmicas del local: la de 58 mm ("Receipt Printer Co.,Ltd.")
# y la de 80 mm ("Printer POS-80"). Sirven para reconocerlas aunque su driver les ponga otro nombre.
USB_VIDS = ('6868', '1FC9')
# Nombres típicos de impresoras/drivers térmicos, para reconocerlas aunque sean de otra marca
PATRON_TERMICA = re.compile(r'receipt|pos[- ]?\d|thermal|t[eé]rmica|(?<!\d)(58|80)(?!\d)', re.I)
PATRON_ANCHO = re.compile(r'(?<!\d)(58|80)(?!\d)')

CREATE_NO_WINDOW = 0x08000000

# Lista las impresoras de Windows y las impresoras USB enchufadas (con su puerto USB001, USB002… y
# el dispositivo USB del que cuelgan), para reconocer las térmicas y ver si a alguna le falta el driver
_PS_ESTADO = r'''
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$impresoras = @(Get-CimInstance Win32_Printer | ForEach-Object { @{ nombre = $_.Name; driver = $_.DriverName; puerto = $_.PortName } })
$usb = @(Get-CimInstance Win32_PnPEntity -Filter "DeviceID LIKE 'USBPRINT\\%'" | ForEach-Object {
  @{ puerto = ($_.DeviceID -split '&')[-1]; padre = [string](Get-PnpDeviceProperty -InstanceId $_.DeviceID -KeyName DEVPKEY_Device_Parent -ErrorAction SilentlyContinue).Data }
})
@{ impresoras = $impresoras; usb = $usb } | ConvertTo-Json -Compress -Depth 3
'''


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


def ruta_driver(ancho_rollo=None):
    """Instalador del driver para el ancho de rollo pedido (o el de la boleta), o None si no viene con el programa."""
    ruta = settings.DRIVERS_DIR / DRIVERS[ancho_rollo or ancho()]
    return ruta if ruta.is_file() else None


def _lista(valor):
    if not valor:
        return []
    return [valor] if isinstance(valor, dict) else valor   # PowerShell entrega un objeto suelto cuando hay uno solo


def estado():
    """Qué impresoras tiene Windows y cuáles son térmicas de rollo.

    {'conectada': bool,        # hay una impresora térmica enchufada por USB
     'sin_driver': bool,       # hay una térmica enchufada a la que le falta el driver
     'boletas': [{nombre, driver, puerto, ancho}],   # impresoras térmicas instaladas (ancho 58/80 o None)
     'otras': [nombres],
     'driver_disponible': bool}   # el programa trae los drivers para instalarlos
    """
    datos = {}
    if os.name == 'nt':
        try:
            r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', _PS_ESTADO],
                               capture_output=True, timeout=30, creationflags=CREATE_NO_WINDOW)
            datos = json.loads(r.stdout.decode('utf-8', 'replace').strip() or '{}') or {}
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
    impresoras = _lista(datos.get('impresoras'))
    puertos_termicas = {d.get('puerto') for d in _lista(datos.get('usb'))
                        if any(f'VID_{v}' in (d.get('padre') or '').upper() for v in USB_VIDS)}
    boletas, otras = [], []
    for imp in impresoras:
        texto = f"{imp.get('nombre')} {imp.get('driver')}"
        if imp.get('puerto') in puertos_termicas or PATRON_TERMICA.search(texto):
            m = PATRON_ANCHO.search(texto)
            boletas.append({**imp, 'ancho': int(m.group(1)) if m else None})
        else:
            otras.append(imp)
    puertos_con_impresora = {i.get('puerto') for i in impresoras}
    return {
        'conectada': bool(puertos_termicas),
        'sin_driver': bool(puertos_termicas - puertos_con_impresora),
        'boletas': boletas,
        'otras': [i.get('nombre') for i in otras],
        'driver_disponible': ruta_driver() is not None,
    }


def instalar_driver(ancho_rollo=None):
    """Abre el instalador del driver del ancho pedido (Windows pide permiso de administrador)."""
    if ancho_rollo is not None and ancho_rollo not in ANCHOS:
        raise ValueError('Ancho de rollo no válido.')
    ruta = ruta_driver(ancho_rollo)
    if ruta is None:
        raise ValueError('El driver viene solo con el programa instalado.')
    os.startfile(ruta)
