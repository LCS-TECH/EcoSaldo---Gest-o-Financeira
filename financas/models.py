# financas/models.py
from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal

class Categoria(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.nome

class Transacao(models.Model):
    TIPO_CHOICES = (
        ('Receita', 'Receita'),
        ('Despesa', 'Despesa'),
    )
    METODO_PAGAMENTO_CHOICES = (
        ('Cartão de Crédito', 'Cartão de Crédito'),
        ('Dinheiro', 'Dinheiro'),
        ('Transferência', 'Transferência'),
    )

    data = models.DateField()
    descricao = models.CharField(max_length=255)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    metodo_pagamento = models.CharField(max_length=20, choices=METODO_PAGAMENTO_CHOICES)
    parcelado = models.BooleanField(default=False)
    num_parcelas = models.IntegerField(blank=True, null=True)
    parcela_atual = models.IntegerField(blank=True, null=True)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        # Usando f-string com formatação de data
        return f"{self.descricao} - R${self.valor} - {self.data.strftime('%d/%m/%Y')}"

    def valor_parcela(self):
        if self.parcelado and self.num_parcelas and self.num_parcelas > 0: # Adicionado check para > 0
            return self.valor / Decimal(self.num_parcelas)
        return self.valor