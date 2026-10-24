"""Ajustes de la impresora de boletas (impresora térmica de rollo) y su driver."""
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

# La impresora de boletas actual se identifica por USB como "Receipt Printer Co.,Ltd." (VID 6868)
USB_VID = '6868'
# Nombres típicos de impresoras/drivers de boletas, para reconocerlas aunque sean de otra marca
PATRON_BOLETAS = re.compile(r'receipt|pos[- ]?\d|thermal|t[eé]rmica|\b(58|80)\b', re.I)

CREATE_NO_WINDOW = 0x08000000

# Lista las impresoras de Windows, si la impresora de boletas está conectada por USB
# y en qué puerto USB (USB001, USB002…) está, para reconocer su impresora aunque tenga otro nombre
_PS_ESTADO = rf'''
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$impresoras = @(Get-CimInstance Win32_Printer | ForEach-Object {{ @{{ nombre = $_.Name; driver = $_.DriverName; puerto = $_.PortName }} }})
$usb = @(Get-CimInstance Win32_PnPEntity -Filter "DeviceID LIKE 'USB\\VID_{USB_VID}%' OR DeviceID LIKE 'USBPRINT\\%'")
$conectada = @($usb | Where-Object {{ $_.DeviceID -like 'USB\VID_{USB_VID}*' }}).Count -gt 0
$puertos = @($usb | Where-Object {{ $_.DeviceID -like 'USBPRINT\*' }} | Where-Object {{
  (Get-PnpDeviceProperty -InstanceId $_.DeviceID -KeyName DEVPKEY_Device_Parent -ErrorAction SilentlyContinue).Data -like 'USB\VID_{USB_VID}*'
}} | ForEach-Object {{ ($_.DeviceID -split '&')[-1] }})
@{{ impresoras = $impresoras; conectada = $conectada; puertos = $puertos }} | ConvertTo-Json -Compress -Depth 3
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
    """Instalador del driver para el ancho de rollo elegido, o None si no viene con el programa."""
    ruta = settings.DRIVERS_DIR / DRIVERS[ancho_rollo or ancho()]
    return ruta if ruta.is_file() else None


def estado():
    """Qué impresoras tiene Windows y cuál parece ser la de boletas.

    {'conectada': bool,          # la impresora de boletas está enchufada por USB
     'boletas': [{nombre, driver, puerto}],   # impresoras de Windows que son de boletas
     'otras': [nombres],
     'driver_disponible': bool}  # el programa trae el driver para instalarlo
    """
    datos = {'impresoras': [], 'conectada': False, 'puertos': []}
    if os.name == 'nt':
        try:
            r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', _PS_ESTADO],
                               capture_output=True, timeout=20, creationflags=CREATE_NO_WINDOW)
            datos = json.loads(r.stdout.decode('utf-8', 'replace').strip() or '{}') or datos
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
    impresoras = datos.get('impresoras') or []
    if isinstance(impresoras, dict):   # PowerShell entrega un objeto suelto cuando hay una sola
        impresoras = [impresoras]
    puertos = set(datos.get('puertos') or [])
    boletas, otras = [], []
    for imp in impresoras:
        es_boletas = imp.get('puerto') in puertos or PATRON_BOLETAS.search(f"{imp.get('nombre')} {imp.get('driver')}")
        (boletas if es_boletas else otras).append(imp)
    return {
        'conectada': bool(datos.get('conectada')),
        'boletas': boletas,
        'otras': [i.get('nombre') for i in otras],
        'driver_disponible': ruta_driver() is not None,
    }


def instalar_driver():
    """Abre el instalador del driver (Windows pide permiso de administrador)."""
    ruta = ruta_driver()
    if ruta is None:
        raise ValueError('El driver viene solo con el programa instalado.')
    os.startfile(ruta)
