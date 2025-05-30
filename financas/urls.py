# financas/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # URL da Dashboard (página inicial da app financas)
    path('', views.dashboard, name='dashboard'),

    # URLs para Transações
    path('transacoes/', views.lista_transacoes, name='lista_transacoes'),
    path('transacoes/adicionar/', views.adicionar_transacao, name='adicionar_transacao'),
    path('transacoes/editar/<int:pk>/', views.editar_transacao, name='editar_transacao'),
    # Note: A URL de deletar geralmente tem um nome diferente, mas 'deletar_transacao' está ok se você usar esse nome
    path('transacoes/deletar/<int:pk>/', views.deletar_transacao, name='deletar_transacao'),

    # URLs para Categorias
    path('categorias/', views.lista_categorias, name='lista_categorias'),
    path('categorias/adicionar/', views.adicionar_categoria, name='adicionar_categoria'),
    path('categorias/editar/<int:pk>/', views.editar_categoria, name='editar_categoria'),
     # Note: A URL de deletar geralmente tem um nome diferente, mas 'deletar_categoria' está ok se você usar esse nome
    path('categorias/deletar/<int:pk>/', views.deletar_categoria, name='deletar_categoria'),

    # URL para Relatórios
    path('relatorios/', views.relatorios, name='relatorios'),

    # Note: URLs para login/logout estão definidas no urls.py principal (ecosaldo/urls.py)
    path('registro/', views.registro, name='registro'),
    path('perfil/', views.perfil_usuario_view, name='perfil_usuario'),
    path('configuracoes/', views.configuracoes_view, name='configuracoes'),

]