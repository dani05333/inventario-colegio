from . import seguridad

# Secciones que piden la clave de administrador (enteras o, en el historial, sus totales)
PROTEGIDAS = {
    'historial_ventas', 'boleta', 'dashboard_ventas',
    'ver_inventario', 'crear_inventario', 'editar_inventario', 'eliminar_inventario', 'carga_rapida',
}
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
        nombre = request.resolver_match.url_name if request.resolver_match else None
        if (request.method == 'GET' and request.headers.get('Sec-Fetch-Mode') == 'navigate'
                and nombre not in NO_CIERRAN and seguridad.SESION_ACCESO in request.session):
            seguridad.cerrar_acceso(request)
        return None
