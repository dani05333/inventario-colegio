from django.urls import path

from . import views

app_name = 'egresos'

urlpatterns = [
    path('', views.resumen, name='resumen'),
    path('gastos/', views.gastos, name='gastos'),
    path('gastos/editar/<int:pk>', views.gasto_editar, name='gasto_editar'),
    path('proveedores/', views.proveedores, name='proveedores'),
    path('proveedores/nuevo/', views.proveedor_form, name='proveedor_nuevo'),
    path('proveedores/<int:pk>/', views.proveedor, name='proveedor'),
    path('proveedores/<int:pk>/editar/', views.proveedor_form, name='proveedor_editar'),
    path('empleados/', views.empleados, name='empleados'),
    path('empleados/nuevo/', views.empleado_form, name='empleado_nuevo'),
    path('empleados/<int:pk>/', views.empleado, name='empleado'),
    path('empleados/<int:pk>/editar/', views.empleado_form, name='empleado_editar'),
    path('categorias/', views.categorias, name='categorias'),
    path('categorias/nueva/', views.CategoriaCreateView.as_view(), name='categoria_nueva'),
    path('categorias/editar/<int:pk>', views.CategoriaUpdateView.as_view(), name='categoria_editar'),
    path('categorias/eliminar/<int:pk>', views.CategoriaDeleteView.as_view(), name='categoria_eliminar'),

    path('api/gastos/<int:pk>/eliminar/', views.gasto_eliminar, name='gasto_eliminar'),
    path('api/horas/<int:pk>/eliminar/', views.horas_eliminar, name='horas_eliminar'),
    path('api/proveedores/<int:pk>/eliminar/', views.proveedor_eliminar, name='proveedor_eliminar'),
    path('api/pagos/<int:pk>/eliminar/', views.pago_eliminar, name='pago_eliminar'),
    path('api/categorias/', views.categorias_json, name='categorias_json'),
]
