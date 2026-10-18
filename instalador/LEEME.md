# Instalador y actualizaciones de Chloe POS

## Qué hay en esta carpeta

| Archivo | Para qué sirve |
|---|---|
| `construir.py` | Arma el instalador completo (`salida/ChloePOS-Setup-X.Y.Z.exe`) |
| `chloe-pos.iss` | Configuración de Inno Setup (no se toca normalmente) |
| `lanzador.py` | Lo que se ejecuta al abrir el ícono en el POS |
| `requisitos.txt` | Paquetes de Python que van dentro del programa |
| `chloe.ico` | Ícono del programa |

Requisito en tu computador (una sola vez): **Inno Setup 6** — `winget install JRSoftware.InnoSetup`.

## Generar el instalador

```
venv\Scripts\activate
python instalador/construir.py
```

Quedan dos archivos en `instalador/salida/`:
- `ChloePOS-Setup-X.Y.Z.exe` → el instalador
- `ChloePOS-Setup-X.Y.Z.exe.sha256` → su verificación

Para probar sin compilar el instalador: `python instalador/construir.py --sin-instalador`.

## Primera instalación en el POS

1. Copia `ChloePOS-Setup-X.Y.Z.exe` a un pendrive.
2. En el POS, doble clic → Siguiente → Instalar → Finalizar.
3. Queda el ícono **Chloe POS** en el escritorio.

No pide permisos de administrador ni instala nada más (trae su propio Python).

## Publicar una actualización

1. Haz y prueba los cambios. Si cambiaste modelos, crea la migración (`python manage.py makemigrations`).
2. Sube el número en el archivo `VERSION` (por ejemplo `1.0.0` → `1.1.0`).
3. Genera el instalador: `python instalador/construir.py`.
4. Haz commit y push de los cambios.
5. En GitHub: **Releases → Draft a new release**
   - **Tag:** `v1.1.0` (el mismo número de `VERSION`, con una `v` delante)
   - **Título:** `Chloe POS 1.1.0`
   - **Descripción:** las novedades, en palabras simples (el cliente las ve antes de actualizar)
   - **Target:** la rama donde está el código de esa versión (hoy `rediseno-pos`)
   - **Adjunta los dos archivos** de `instalador/salida/` (el `.exe` y el `.sha256`)
   - **Release label: Latest** ← importante: con "None" GitHub no la marca como la más reciente y el POS no la ve
   - **Publish release**

En el POS, la próxima vez que abran el programa aparece un aviso, y en **Sistema → Buscar actualizaciones → Actualizar ahora** se instala sola (hace un respaldo antes).

> El número de versión siempre debe subir. Si publicas una versión con un número menor o igual al instalado, el POS no la ofrece.

## Dónde quedan las cosas en el POS

| Qué | Dónde |
|---|---|
| Programa | `%LOCALAPPDATA%\Programs\Chloe POS` |
| Base de datos | `%LOCALAPPDATA%\Chloe POS\chloe-pos.sqlite3` |
| Respaldos | `Documentos\Chloe POS - Respaldos` (uno diario, 30 días) |
| Registro de errores | `%LOCALAPPDATA%\Chloe POS\logs\` |

Desinstalar el programa **no borra** la base de datos ni los respaldos.

## Si se olvida la clave de administrador

En el POS, presiona **Windows + R**, pega esto y presiona Enter:

```
"%LOCALAPPDATA%\Programs\Chloe POS\python\pythonw.exe" "%LOCALAPPDATA%\Programs\Chloe POS\lanzador.py" --restablecer-clave
```

Confirma con **Sí**. Luego abre Chloe POS y crea una clave nueva en **Sistema → Clave de administrador**.
(No hay botón visible a propósito: así solo lo puede hacer quien conoce este paso.)

## Restaurar un respaldo

1. Cierra la ventana de Chloe POS y, en el menú Inicio, ejecuta **Chloe POS → Detener Chloe POS**.
2. Copia el respaldo elegido a `%LOCALAPPDATA%\Chloe POS\` y renómbralo como `chloe-pos.sqlite3` (reemplazando el actual).
3. Abre Chloe POS desde el ícono.
