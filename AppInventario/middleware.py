from . import seguridad

# Páginas que piden la clave de administrador (enteras o, en los historiales, sus totales).
# Se nombran como 'nombre' (uniformes) o 'seccion:nombre' (librería); la sección de egresos entera pide la clave.
PROTEGIDAS = {
    'historial_ventas', 'boleta', 'dashboard_ventas',
    'ver_inventario', 'crear_inventario', 'editar_inventario', 'eliminar_inventario', 'carga_rapida',
    'libreria:historial', 'libreria:inventario', 'libreria:producto_nuevo', 'libreria:producto_editar',
    'libreria:producto_eliminar', 'libreria:ingreso',
    'arriendos:inventario', 'arriendos:pieza_nueva', 'arriendos:pieza_editar', 'arriendos:traje_nuevo', 'arriendos:traje_editar',
}
SECCIONES_PROTEGIDAS = {'egresos'}
# Páginas que se abren aparte sin que la persona deje la sección protegida
NO_CIERRAN = PROTEGIDAS | {'pantalla_cliente'}


class CerrarAccesoAlSalir:
    """Al ir a cualquier otra sección, se cierra el acceso con clave: así no queda abierto por olvido.

    Solo cuenta cuando se abre una página (no las consultas internas ni las imágenes), lo que el
    navegador indica con Sec-Fetch-Mode: navigate.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        rm = request.resolver_match
        nombre = rm.view_name if rm else None
        sigue_protegido = nombre in NO_CIERRAN or (rm is not None and rm.namespace in SECCIONES_PROTEGIDAS)
        if (request.method == 'GET' and request.headers.get('Sec-Fetch-Mode') == 'navigate'
                and not sigue_protegido and seguridad.SESION_ACCESO in request.session):
            seguridad.cerrar_acceso(request)
        return None
