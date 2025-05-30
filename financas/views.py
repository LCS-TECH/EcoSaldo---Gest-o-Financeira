# financas/views.py
from django.shortcuts import render, redirect, get_object_or_404
from .models import Transacao, Categoria
from .forms import TransacaoForm, CategoriaForm, RegistroForm # Certifique-se que RegistroForm está definido em forms.py
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import calendar
import json # Importado para serializar dados para JavaScript
from django.contrib import messages
from django.db.models.functions import ExtractMonth, ExtractYear
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm # Para a view de login padrão, se usada
from decimal import Decimal # <-- NOVO IMPORT: Para lidar com valores monetários com precisão

# Imports para gráficos (Matplotlib)
import io
import base64
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np # Importar numpy para lidar com arrays de dados

# Configurações para Matplotlib (para evitar erros de backend e melhorar visualização)
plt.switch_backend('Agg') # Usar backend não interativo para geração de imagens
plt.rcParams['figure.autolayout'] = True # Ajusta automaticamente o layout para evitar cortes
plt.style.use('seaborn-v0_8-darkgrid') # Estilo mais moderno para os gráficos

# --- Funções Auxiliares para o Dashboard ---

def get_period_dates(period_str, today=None):
    """Retorna as datas de início e fim para um dado período."""
    if today is None:
        today = timezone.now().date()

    if period_str == 'month':
        start_date = today.replace(day=1)
        end_date = today # Até o dia atual
    elif period_str == 'quarter':
        current_quarter = (today.month - 1) // 3 + 1
        start_month = 3 * (current_quarter - 1) + 1
        start_date = today.replace(month=start_month, day=1)
        end_date = today
    elif period_str == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today
    else: # Padrão para 'month' se o período não for reconhecido
        start_date = today.replace(day=1)
        end_date = today
    
    return start_date, end_date

def get_transaction_summary(user, start_date, end_date):
    """Calcula o resumo de receitas e despesas para um dado período."""
    transactions = Transacao.objects.filter(
        usuario=user,
        data__gte=start_date,
        data__lte=end_date
    )
    
    # Certifique-se de que os agregados são tratados como Decimal desde o início
    receitas = transactions.filter(tipo='Receita').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    despesas = transactions.filter(tipo='Despesa').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    
    receitas_count = transactions.filter(tipo='Receita').count()
    despesas_count = transactions.filter(tipo='Despesa').count()
    
    saldo = receitas - despesas

    return {
        'receitas': receitas,
        'despesas': despesas,
        'saldo': saldo,
        'receitas_count': receitas_count,
        'despesas_count': despesas_count,
    }

def get_monthly_flow_data(user, num_months=12, today=None):
    """Gera dados para o gráfico de fluxo mensal (últimos N meses)."""
    if today is None:
        today = timezone.now().date()

    labels = []
    receitas_data = []
    despesas_data = []

    for i in range(num_months - 1, -1, -1): # Começa do mês mais antigo para o mais recente
        month_date = today - relativedelta(months=i)
        
        # Obter o nome abreviado do mês e o ano, como "Jan/24"
        labels.append(month_date.strftime('%b/%y'))

        # Calcular receitas para o mês
        monthly_receitas = Transacao.objects.filter(
            usuario=user,
            tipo='Receita',
            data__year=month_date.year,
            data__month=month_date.month
        ).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        receitas_data.append(float(monthly_receitas)) # Convertendo para float aqui para Chart.js

        # Calcular despesas para o mês
        monthly_despesas = Transacao.objects.filter(
            usuario=user,
            tipo='Despesa',
            data__year=month_date.year,
            data__month=month_date.month
        ).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        despesas_data.append(float(monthly_despesas)) # Convertendo para float aqui para Chart.js

    return {
        'labels': labels,
        'receitas_data': receitas_data,
        'despesas_data': despesas_data,
    }

def get_category_expenses_data(user, start_date, end_date):
    """Gera dados para a tabela e gráfico de despesas por categoria."""
    despesas_por_categoria_query = Transacao.objects.filter(
        usuario=user,
        tipo='Despesa',
        data__gte=start_date,
        data__lte=end_date
    ).values('categoria__nome').annotate(total=Sum('valor')).order_by('-total')

    total_despesas_periodo = despesas_por_categoria_query.aggregate(total_sum=Sum('total'))['total_sum'] or Decimal('0.00')

    despesas_por_categoria_list = []
    chart_labels = []
    chart_data = []

    if total_despesas_periodo > Decimal('0.00'): # Comparar com Decimal
        for item in despesas_por_categoria_query:
            categoria_nome = item['categoria__nome'] or 'Sem Categoria'
            total_valor = item['total'] # Item['total'] já é Decimal do Sum
            
            # Garante que a divisão é entre Decimals
            percentual = (total_valor / total_despesas_periodo) * 100 
            
            despesas_por_categoria_list.append({
                'categoria': categoria_nome,
                'total': total_valor,
                'percentual': float(percentual), # Convertendo percentual para float para serialização se necessário
            })
            chart_labels.append(categoria_nome)
            chart_data.append(float(total_valor)) # Convertendo para float aqui para Chart.js
    
    return {
        'table_data': despesas_por_categoria_list,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
    }


# --- Views Principais ---

@login_required
def dashboard(request):
    user = request.user
    hoje = timezone.now().date()
    
    # 1. Obter dados de resumo para o período selecionado
    periodo = request.GET.get('period', 'month')
    start_date_period, end_date_period = get_period_dates(periodo, hoje)
    summary_data = get_transaction_summary(user, start_date_period, end_date_period)

    # 2. Dados para o comparativo Mês Atual vs Mês Anterior
    primeiro_dia_mes_atual = hoje.replace(day=1)
    # Garante que `ultimo_dia_mes_anterior` é o último dia do mês anterior para o cálculo correto
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1) 
    primeiro_dia_mes_anterior = ultimo_dia_mes_anterior.replace(day=1)

    summary_current_month = get_transaction_summary(user, primeiro_dia_mes_atual, hoje)
    summary_previous_month = get_transaction_summary(user, primeiro_dia_mes_anterior, ultimo_dia_mes_anterior)

    # 3. Dados para o gráfico de fluxo mensal (últimos 12 meses)
    monthly_flow = get_monthly_flow_data(user, num_months=12, today=hoje)

    # 4. Dados para despesas por categoria
    category_expenses = get_category_expenses_data(user, start_date_period, end_date_period)

    # 5. Últimas transações
    ultimas_transacoes = Transacao.objects.filter(usuario=user).order_by('-data')[:10]

    # 6. Preparar dados para JSON no template
    # Usamos json.dumps para garantir que listas e números sejam passados corretamente
    # o `|safe` é necessário porque o Django escaparia o HTML do JSON
    context = {
        'saldo': summary_data['saldo'],
        'receitas': summary_data['receitas'],
        'despesas': summary_data['despesas'],
        'receitas_count': summary_data['receitas_count'],
        'despesas_count': summary_data['despesas_count'],
        'period': periodo,
        
        'comparativo_mes_atual_receitas': summary_current_month['receitas'],
        'comparativo_mes_atual_despesas': summary_current_month['despesas'],
        'comparativo_mes_anterior_receitas': summary_previous_month['receitas'],
        'comparativo_mes_anterior_despesas': summary_previous_month['despesas'],

        'chart_flow_labels_json': json.dumps(monthly_flow['labels']),
        'chart_flow_receitas_data_json': json.dumps(monthly_flow['receitas_data']),
        'chart_flow_despesas_data_json': json.dumps(monthly_flow['despesas_data']),
        
        'despesas_por_categoria': category_expenses['table_data'], # Dados para a tabela
        'chart_despesas_categoria_labels_json': json.dumps(category_expenses['chart_labels']),
        'chart_despesas_categoria_data_json': json.dumps(category_expenses['chart_data']),

        'ultimas_transacoes': ultimas_transacoes,
        
        # Exemplo de alertas (você pode carregar isso de um modelo ou lógica real)
        'alerts': [
            {'type': 'warning', 'title': 'Limite de gastos', 'message': 'Você atingiu 85% do seu limite mensal.'},
            {'type': 'info', 'title': 'Assinatura renovando', 'message': 'Netflix em 3 dias - R$ 39,90'},
            {'type': 'success', 'title': 'Meta alcançada', 'message': 'Você economizou 100% da meta deste mês'},
        ],
    }
    return render(request, 'financas/dashboard.html', context)


@login_required
def lista_transacoes(request):
    # Filtro por tipo de transação
    tipo_filtro = request.GET.get('tipo')
    if tipo_filtro and tipo_filtro in ['Receita', 'Despesa']:
        transacoes_query = Transacao.objects.filter(usuario=request.user, tipo=tipo_filtro)
    else:
        transacoes_query = Transacao.objects.filter(usuario=request.user)

    transacoes_query = transacoes_query.order_by('-data', '-id') # Ordenar por data e id para consistência
    
    paginator = Paginator(transacoes_query, 10) # 10 transações por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'financas/lista_transacoes.html', {'page_obj': page_obj, 'tipo_filtro': tipo_filtro})


@login_required
def adicionar_transacao(request):
    if request.method == 'POST':
        form = TransacaoForm(request.POST, user=request.user) # Passar o usuário para filtrar categorias
        if form.is_valid():
            transacao = form.save(commit=False)
            transacao.usuario = request.user
            transacao.save()
            messages.success(request, 'Transação adicionada com sucesso.')
            return redirect('lista_transacoes')
        else:
            messages.error(request, 'Erro ao adicionar transação. Por favor, corrija os erros no formulário.')
    else:
        form = TransacaoForm(user=request.user) # Passar o usuário ao instanciar o formulário vazio
    return render(request, 'financas/form_transacao.html', {'form': form, 'acao': 'Adicionar'})


@login_required
def editar_transacao(request, pk):
    transacao = get_object_or_404(Transacao, pk=pk, usuario=request.user)
    if request.method == 'POST':
        form = TransacaoForm(request.POST, instance=transacao, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Transação atualizada com sucesso.')
            return redirect('lista_transacoes')
        else:
            messages.error(request, 'Erro ao atualizar transação. Por favor, corrija os erros no formulário.')
    else:
        form = TransacaoForm(instance=transacao, user=request.user)
    return render(request, 'financas/form_transacao.html', {'form': form, 'acao': 'Editar'})


@login_required
def deletar_transacao(request, pk):
    transacao = get_object_or_404(Transacao, pk=pk, usuario=request.user)
    if request.method == 'POST':
        transacao.delete()
        messages.success(request, 'Transação deletada com sucesso.')
        return redirect('lista_transacoes')
    # Se for uma requisição GET, renderiza a página de confirmação
    return render(request, 'financas/confirma_exclusao.html', {'obj': transacao, 'tipo': 'Transação'})


@login_required
def lista_categorias(request):
    categorias = Categoria.objects.filter(usuario=request.user).order_by('nome')
    return render(request, 'financas/lista_categorias.html', {'categorias': categorias})


@login_required
def adicionar_categoria(request):
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            categoria = form.save(commit=False)
            categoria.usuario = request.user
            categoria.save()
            messages.success(request, 'Categoria adicionada com sucesso.')
            return redirect('lista_categorias')
        else:
            messages.error(request, 'Erro ao adicionar categoria. Por favor, corrija os erros no formulário.')
    else:
        form = CategoriaForm()
    return render(request, 'financas/form_categoria.html', {'form': form, 'acao': 'Adicionar'})


@login_required
def editar_categoria(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk, usuario=request.user)
    if request.method == 'POST':
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoria atualizada com sucesso.')
            return redirect('lista_categorias')
        else:
            messages.error(request, 'Erro ao atualizar categoria. Por favor, corrija os erros no formulário.')
    else:
        form = CategoriaForm(instance=categoria)
    return render(request, 'financas/form_categoria.html', {'form': form, 'acao': 'Editar'})


@login_required
def deletar_categoria(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk, usuario=request.user)
    if request.method == 'POST':
        # Verificar se existem transações associadas a esta categoria antes de deletar
        if Transacao.objects.filter(categoria=categoria).exists():
            messages.error(request, 'Não é possível deletar esta categoria, pois existem transações associadas a ela. Remova ou altere as transações primeiro.')
            return redirect('lista_categorias')
        categoria.delete()
        messages.success(request, 'Categoria deletada com sucesso.')
        return redirect('lista_categorias')
    return render(request, 'financas/confirma_exclusao.html', {'obj': categoria, 'tipo': 'Categoria'})


@login_required
def relatorios(request):
    categorias = Categoria.objects.filter(usuario=request.user)

    # Obtenção dos filtros da requisição
    categoria_id = request.GET.get('categoria')
    tipo = request.GET.get('tipo')
    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')

    filtro = Q(usuario=request.user)

    # Aplicando filtros
    if categoria_id and categoria_id.isdigit():
        filtro &= Q(categoria_id=int(categoria_id))
    if tipo in ['Receita', 'Despesa']:
        filtro &= Q(tipo=tipo)
    if data_inicio_str:
        try:
            data_inicio = date.fromisoformat(data_inicio_str)
            filtro &= Q(data__gte=data_inicio)
        except ValueError:
            messages.error(request, "Formato de data de início inválido.")
            data_inicio_str = None # Limpar para não preencher o formulário com data errada
    if data_fim_str:
        try:
            data_fim = date.fromisoformat(data_fim_str)
            filtro &= Q(data__lte=data_fim)
        except ValueError:
            messages.error(request, "Formato de data de fim inválido.")
            data_fim_str = None # Limpar para não preencher o formulário com data errada

    transacoes_filtradas = Transacao.objects.filter(filtro).order_by('-data')

    # Geração do gráfico de despesas por categoria (usando Matplotlib)
    grafico_despesas_categoria_base64 = None
    
    # Converter QuerySet para DataFrame para facilitar manipulação
    df = pd.DataFrame(list(transacoes_filtradas.values('categoria__nome', 'valor', 'tipo', 'data')))

    if not df.empty:
        # Filtrar despesas
        df_despesas = df[df['tipo'] == 'Despesa'].copy()
        
        if not df_despesas.empty:
            # Usar Decimal para soma para evitar imprecisões e converter para float apenas para o gráfico
            resumo_despesas = df_despesas.groupby('categoria__nome')['valor'].sum()

            # Criar o gráfico de barras
            fig, ax = plt.subplots(figsize=(10, 6)) # Aumentar o tamanho para melhor visualização
            
            # Convertendo os valores do resumo_despesas para float apenas para o plot, se necessário
            # plot() do pandas geralmente lida bem com Decimal, mas é bom ser explícito
            resumo_despesas.astype(float).plot(kind='bar', ax=ax, color='#28a745', edgecolor='black') # Usar primary-color
            
            ax.set_title('Distribuição de Despesas por Categoria', fontsize=16, fontweight='bold')
            ax.set_ylabel('Valor (R$)', fontsize=12)
            ax.set_xlabel('Categoria', fontsize=12)
            ax.tick_params(axis='x', rotation=45, ha='right', labelsize=10)
            ax.tick_params(axis='y', labelsize=10)
            # Ajuste para formatar Decimal corretamente para o matplotlib
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'R$ {x:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'))) # Formato moeda
            
            # Adicionar rótulos de valor nas barras (garantir que sejam floats para bar_label)
            for container in ax.containers:
                ax.bar_label(container, fmt='R$ %.2f', label_type='edge', fontsize=9, padding=3)

            fig.tight_layout() # Ajusta o layout para evitar sobreposição

            # Salvar o gráfico em um buffer e converter para base64
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150) # Aumentar DPI para melhor qualidade
            plt.close(fig) # Fechar a figura para liberar memória
            buf.seek(0)
            grafico_despesas_categoria_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    context = {
        'categorias': categorias,
        'transacoes': transacoes_filtradas,
        'grafico_despesas_categoria_base64': grafico_despesas_categoria_base64, # Alterar nome para ser mais específico
        'filtros': {
            'categoria_id': categoria_id,
            'tipo': tipo,
            'data_inicio': data_inicio_str, # Passar string original de volta
            'data_fim': data_fim_str, # Passar string original de volta
        }
    }
    return render(request, 'financas/relatorios.html', context)


# --- Views de Autenticação e Perfil ---

def registro(request):
    if request.user.is_authenticated: # Redireciona se o usuário já estiver logado
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Faz o login do usuário automaticamente após o registro
            messages.success(request, f'Sua conta foi criada com sucesso! Bem-vindo(a), {user.username}.')
            return redirect('dashboard')
        else:
            messages.error(request, 'Houve um erro ao registrar sua conta. Por favor, verifique os dados.')
    else:
        form = RegistroForm()
    return render(request, 'financas/registro.html', {'form': form})

# Placeholder para a view de perfil do usuário
@login_required
def perfil_usuario_view(request):
    messages.info(request, "Esta é a página de perfil do usuário. Em breve, você poderá editar suas informações aqui!")
    return render(request, 'financas/perfil_usuario.html', {})

# Placeholder para a view de configurações
@login_required
def configuracoes_view(request):
    messages.info(request, "Esta é a página de configurações. Funcionalidades de configuração serão adicionadas em breve!")
    return render(request, 'financas/configuracoes.html', {})

# --- Login/Logout (Se você estiver usando as views padrão do Django, você as mapearia no urls.py) ---
# Exemplo de como você as mapearia no seu urls.py principal se não tiver uma customização
# path('login/', auth_views.LoginView.as_view(template_name='financas/login.html'), name='login'),
# path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),