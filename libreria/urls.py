from django.urls import path

from . import views

app_name = 'libreria'

urlpatterns = [
    path('', views.pos, name='pos'),
    path('historial/', views.historial, name='historial'),
    path('inventario/', views.inventario, name='inventario'),
    path('inventario/nuevo/', views.producto_form, name='producto_nuevo'),
    path('inventario/editar/<int:pk>', views.producto_form, name='producto_editar'),
    path('inventario/ingreso/', views.ingreso, name='ingreso'),
    path('categorias/', views.categorias, name='categorias'),
    path('categorias/nueva/', views.CategoriaCreateView.as_view(), name='categoria_nueva'),
    path('categorias/editar/<int:pk>', views.CategoriaUpdateView.as_view(), name='categoria_editar'),
    path('categorias/eliminar/<int:pk>', views.CategoriaDeleteView.as_view(), name='categoria_eliminar'),

    path('api/productos/', views.productos_json, name='productos_json'),
    path('api/productos/<int:pk>/eliminar/', views.producto_eliminar, name='producto_eliminar'),
    path('api/buscar-internet/', views.buscar_internet, name='buscar_internet'),
    path('api/generar-codigo/', views.generar_codigo, name='generar_codigo'),
    path('api/registrar-venta/', views.registrar_venta, name='registrar_venta'),
    path('api/ventas/<int:pk>/anular/', views.anular_venta, name='anular_venta'),
    path('api/ingreso/', views.ingreso_guardar, name='ingreso_guardar'),
    path('api/categorias/', views.categorias_json, name='categorias_json'),
]
