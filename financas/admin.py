from django.contrib import admin
from .models import Categoria, Transacao

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'descricao', 'usuario')
    search_fields = ('nome',)
    list_filter = ('usuario',)

@admin.register(Transacao)
class TransacaoAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'tipo', 'valor', 'data', 'categoria', 'usuario')
    list_filter = ('tipo', 'categoria', 'data')
    search_fields = ('descricao',)
    date_hierarchy = 'data'
    ordering = ('-data',)
    list_editable = ('valor', 'categoria')