# financas/forms.py
# ... (conteúdo da resposta anterior com TransacaoForm e CategoriaForm) ...
# A definição de CategoriaForm adicionada na resposta anterior está correta aqui.
# Certifique-se que o conteúdo completo do forms.py da resposta anterior esteja neste arquivo.
from django import forms
from .models import Transacao, Categoria

class TransacaoForm(forms.ModelForm):
    # ... (seu código TransacaoForm com __init__ e Meta) ...
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['categoria'].queryset = Categoria.objects.filter(usuario=user)
        else:
             self.fields['categoria'].queryset = Categoria.objects.none() # fallback

    class Meta:
        model = Transacao
        fields = [
            'data', 'descricao', 'valor', 'categoria', 'tipo',
            'metodo_pagamento', 'parcelado', 'num_parcelas', 'parcela_atual',
        ]
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'descricao': forms.TextInput(attrs={'placeholder': 'Descrição da transação', 'class': 'form-control'}),
            'valor': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'metodo_pagamento': forms.Select(attrs={'class': 'form-select'}),
            'parcelado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'num_parcelas': forms.NumberInput(attrs={'min': '1', 'class': 'form-control'}),
            'parcela_atual': forms.NumberInput(attrs={'min': '1', 'class': 'form-control'}),
        }
        labels = {
            'data': 'Data', 'descricao': 'Descrição', 'valor': 'Valor (R$)', 'categoria': 'Categoria',
            'tipo': 'Tipo', 'metodo_pagamento': 'Método de Pagamento', 'parcelado': 'Parcelado',
            'num_parcelas': 'Nº de Parcelas', 'parcela_atual': 'Parcela Atual',
        }


    def clean(self):
        cleaned_data = super().clean()
        parcelado = cleaned_data.get('parcelado')
        num_parcelas = cleaned_data.get('num_parcelas')
        parcela_atual = cleaned_data.get('parcela_atual')

        if parcelado:
            if num_parcelas is None or num_parcelas < 1:
                self.add_error('num_parcelas', 'Informe o número total de parcelas.')
            if num_parcelas is not None and num_parcelas >= 1:
                if parcela_atual is None or parcela_atual < 1:
                    self.add_error('parcela_atual', 'Informe o número da parcela atual.')
                elif parcela_atual is not None and parcela_atual > num_parcelas: # check for None added
                    self.add_error('parcela_atual', 'Número da parcela atual não pode ser maior que o total de parcelas.')
        else:
            cleaned_data['num_parcelas'] = None
            cleaned_data['parcela_atual'] = None

        return cleaned_data


# --- DEFINIÇÃO DE CategoriaForm ---
class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nome', 'descricao']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'nome': 'Nome',
            'descricao': 'Descrição',
        }
        
        from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class RegistroForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='Obrigatório. Informe um email válido.')

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Este email já está em uso.")
        return email