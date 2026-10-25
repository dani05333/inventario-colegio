from django.urls import path

from . import views

app_name = 'arriendos'

urlpatterns = [
    path('', views.agenda, name='agenda'),
    path('calendario/', views.calendario, name='calendario'),
    path('disponibilidad/', views.disponibilidad, name='disponibilidad'),
    path('arriendos/', views.lista, name='lista'),
    path('arriendos/nuevo/', views.arriendo_form, name='nuevo'),
    path('arriendos/<int:pk>/', views.detalle, name='detalle'),
    path('arriendos/<int:pk>/editar/', views.arriendo_form, name='editar'),
    path('clientes/', views.clientes, name='clientes'),
    path('clientes/nuevo/', views.cliente_form, name='cliente_nuevo'),
    path('clientes/<int:pk>/', views.cliente, name='cliente'),
    path('clientes/<int:pk>/editar/', views.cliente_form, name='cliente_editar'),
    path('inventario/', views.inventario, name='inventario'),
    path('inventario/pieza/nueva/', views.pieza_form, name='pieza_nueva'),
    path('inventario/pieza/<int:pk>/', views.pieza_form, name='pieza_editar'),
    path('inventario/traje/nuevo/', views.traje_form, name='traje_nuevo'),
    path('inventario/traje/<int:pk>/', views.traje_form, name='traje_editar'),
    path('categorias/', views.categorias, name='categorias'),
    path('categorias/nueva/', views.CategoriaCreateView.as_view(), name='categoria_nueva'),
    path('categorias/editar/<int:pk>', views.CategoriaUpdateView.as_view(), name='categoria_editar'),
    path('categorias/eliminar/<int:pk>', views.CategoriaDeleteView.as_view(), name='categoria_eliminar'),

    path('api/disponibilidad/', views.api_disponibilidad, name='api_disponibilidad'),
    path('api/guardar/', views.api_guardar, name='api_guardar'),
    path('api/arriendos/<int:pk>/accion/', views.api_accion, name='api_accion'),
    path('api/<str:tipo>/<int:pk>/eliminar/', views.api_eliminar, name='api_eliminar'),
    path('api/categorias/', views.categorias_json, name='categorias_json'),
]
