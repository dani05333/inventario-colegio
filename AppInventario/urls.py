from django.urls import path
from . import views

urlpatterns = [
    path('inicio/', views.inicio, name='inicio'),
    path('colegios/', views.ver_colegios, name='ver_colegios'),
    path('colegios/nuevo/', views.ColegioCreateView.as_view(), name='crear_colegio'),
    path('colegios/editar/<int:pk>',views.ColegioUpdateView.as_view(), name='editar_colegio'),
    path('colegios/eliminar/<int:pk>',views.ColegioDeleteView.as_view(), name='eliminar_colegio'),
    path('api/colegios/', views.colegios_json, name='colegios_json'),


    path('tallas/', views.ver_tallas, name='ver_tallas'),
    path('tallas/nuevo/', views.TallaCreateView.as_view(), name='crear_talla'),
    path('tallas/editar/<int:pk>',views.TallasUpdateView.as_view(), name='editar_tallas'),
    path('tallas/eliminar/<int:pk>',views.TallasDeleteView.as_view(), name='eliminar_tallas'),
    path('api/tallas/', views.tallas_json, name='tallas_json'),

    path('uniformes/', views.ver_uniformes, name='ver_uniformes'),
    path('uniformes/nuevo/', views.UniformeCreateView.as_view(), name='crear_uniforme'),
    path('uniformes/editar/<int:pk>', views.UniformeUpdateView.as_view(), name='editar_uniforme'),
    path('uniformes/eliminar/<int:pk>', views.UniformeDeleteView.as_view(), name='eliminar_uniforme'),
    path('api/uniformes/',views.uniformes_json, name='uniformes_json'),

    path('inventario/', views.ver_inventario, name='ver_inventario'),
    path('inventario/nuevo/', views.InventarioCreateView.as_view(), name='crear_inventario'),
    path('inventario/editar/<int:pk>', views.InventarioUpdateView.as_view(), name='editar_inventario'),
    path('inventario/eliminar/<int:pk>',views.InventarioDeleteView.as_view(), name='eliminar_inventario'),
    path('api/inventario/', views.inventario_json, name='inventario_json'),
    
    path('punto-de-venta/', views.punto_de_venta, name='punto_de_venta'),
    path('pantalla-cliente/', views.pantalla_cliente, name='pantalla_cliente'),
    path('buscar-producto/', views.buscar_producto, name='buscar_producto'),
    path('registrar-venta/', views.registrar_venta, name='registrar_venta'),
    path('historial-ventas/', views.historial_ventas, name='historial_ventas'),
    path('boleta/<int:pk>/', views.boleta, name='boleta'),
    path('api/ventas/<int:pk>/anular/', views.anular_venta, name='anular_venta'),
    path('api/sistema/borrar-ventas/', views.borrar_ventas, name='borrar_ventas'),
    path('api/sistema/clave/', views.sistema_clave, name='sistema_clave'),
    path('api/presentacion/', views.presentacion_datos, name='presentacion_datos'),
    path('api/presentacion/ajustes/', views.presentacion_config, name='presentacion_config'),
    path('api/presentacion/subir/', views.presentacion_subir, name='presentacion_subir'),
    path('api/presentacion/eliminar/', views.presentacion_eliminar, name='presentacion_eliminar'),
    path('presentacion/<str:nombre>', views.presentacion_imagen, name='presentacion_imagen'),
    path('etiquetas/', views.etiquetas, name='etiquetas'),
    path('sistema/', views.ver_sistema, name='sistema'),
    path('api/sistema/salud/', views.sistema_salud, name='sistema_salud'),
    path('api/sistema/buscar-actualizacion/', views.sistema_buscar_actualizacion, name='sistema_buscar_actualizacion'),
    path('api/sistema/actualizar/', views.sistema_actualizar, name='sistema_actualizar'),
    path('api/sistema/respaldar/', views.sistema_respaldar, name='sistema_respaldar'),
    path('api/generar-codigo/', views.generar_codigo, name='generar_codigo'),
    path('api/asignar-codigos/', views.asignar_codigos, name='asignar_codigos'),
    path('', views.dashboard_ventas, name='dashboard_ventas'),
    path('api/ventas-data/', views.ventas_data, name='ventas_data'),
    path('api/historial-ventas/', views.historial_ventas_json, name='historial_ventas_json'),
    path('api/stock_bajo/', views.stock_bajo, name='stock_bajo'),
    path('api/productos_tendencia/', views.productos_tendencia, name='productos_tendencia'),




    
]