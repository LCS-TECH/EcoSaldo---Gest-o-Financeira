# financas/views.py
from django.shortcuts import render, redirect, get_object_or_404
from .models import Transacao, Categoria
from .forms import TransacaoForm, CategoriaForm, RegistroForm
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum, Q
from datetime import date, timedelta
from django.utils import timezone
from dateutil.relativedelta import relativedelta
import calendar
from django.contrib import messages
from django.db.models.functions import ExtractMonth, ExtractYear
from django.contrib.auth import login
import io
import base64
import matplotlib.pyplot as plt
import pandas as pd


@login_required
def dashboard(request):
    user = request.user
    hoje = timezone.now().date()
    primeiro_dia_mes_atual = hoje.replace(day=1)
    primeiro_dia_mes_anterior = (primeiro_dia_mes_atual - timedelta(days=1)).replace(day=1)
    ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)

    # Agregar receitas e despesas mês atual
    dados_mes_atual = Transacao.objects.filter(
        usuario=user,
        data__gte=primeiro_dia_mes_atual,
        data__lte=hoje
    ).values('tipo').annotate(total=Sum('valor'))

    # Agregar receitas e despesas mês anterior
    dados_mes_anterior = Transacao.objects.filter(
        usuario=user,
        data__gte=primeiro_dia_mes_anterior,
        data__lte=ultimo_dia_mes_anterior
    ).values('tipo').annotate(total=Sum('valor'))

    def extrair_valor(dados, tipo):
        for item in dados:
            if item['tipo'] == tipo:
                return float(item['total']) if item['total'] else 0
        return 0

    receita_atual = extrair_valor(dados_mes_atual, 'Receita')
    despesa_atual = extrair_valor(dados_mes_atual, 'Despesa')
    receita_anterior = extrair_valor(dados_mes_anterior, 'Receita')
    despesa_anterior = extrair_valor(dados_mes_anterior, 'Despesa')

    # Dados para resumo e gráficos adicionais (exemplo)
    periodo = request.GET.get('period', 'month')

    # Exemplo: calcular saldo, receitas, despesas e contagem para o período selecionado
    hoje = timezone.now().date()
    if periodo == 'month':
        inicio_periodo = hoje.replace(day=1)
    elif periodo == 'quarter':
        mes_atual = hoje.month
        trimestre = (mes_atual - 1) // 3 + 1
        mes_inicio = 3 * (trimestre - 1) + 1
        inicio_periodo = hoje.replace(month=mes_inicio, day=1)
    elif periodo == 'year':
        inicio_periodo = hoje.replace(month=1, day=1)
    else:
        inicio_periodo = hoje.replace(day=1)

    transacoes_periodo = Transacao.objects.filter(usuario=user, data__gte=inicio_periodo, data__lte=hoje)

    receitas = transacoes_periodo.filter(tipo='Receita').aggregate(total=Sum('valor'))['total'] or 0
    despesas = transacoes_periodo.filter(tipo='Despesa').aggregate(total=Sum('valor'))['total'] or 0
    saldo = receitas - despesas

    receitas_count = transacoes_periodo.filter(tipo='Receita').count()
    despesas_count = transacoes_periodo.filter(tipo='Despesa').count()

    # Dados para gráfico fluxo mensal últimos 12 meses
    labels = []
    receitas_mensais = []
    despesas_mensais = []
    for i in range(11, -1, -1):
        mes = hoje - relativedelta(months=i)
        labels.append(mes.strftime('%b/%Y'))
        receitas_mes = Transacao.objects.filter(
            usuario=user,
            tipo='Receita',
            data__year=mes.year,
            data__month=mes.month
        ).aggregate(total=Sum('valor'))['total'] or 0
        despesas_mes = Transacao.objects.filter(
            usuario=user,
            tipo='Despesa',
            data__year=mes.year,
            data__month=mes.month
        ).aggregate(total=Sum('valor'))['total'] or 0
        receitas_mensais.append(float(receitas_mes))
        despesas_mensais.append(float(despesas_mes))

    # Despesas por categoria no período
    despesas_categoria = transacoes_periodo.filter(tipo='Despesa').values('categoria__nome').annotate(total=Sum('valor')).order_by('-total')
    total_despesas = sum(item['total'] for item in despesas_categoria) or 1  # evitar divisão por zero
    despesas_por_categoria = []
    for item in despesas_categoria:
        percentual = (item['total'] / total_despesas) * 100
        despesas_por_categoria.append({
            'categoria': item['categoria__nome'] or 'Sem Categoria',
            'total': item['total'],
            'percentual': percentual,
        })

    # Dados para gráfico de distribuição de despesas por categoria
    chart_despesas_categoria_labels = [item['categoria'] for item in despesas_por_categoria]
    chart_despesas_categoria_data = [item['total'] for item in despesas_por_categoria]

    # Últimas transações
    ultimas_transacoes = Transacao.objects.filter(usuario=user).order_by('-data')[:10]

    contexto = {
        'receita_atual': receita_atual,
        'despesa_atual': despesa_atual,
        'receita_anterior': receita_anterior,
        'despesa_anterior': despesa_anterior,
        'saldo': saldo,
        'receitas': receitas,
        'despesas': despesas,
        'receitas_count': receitas_count,
        'despesas_count': despesas_count,
        'period': periodo,
        'chart_flow_labels': labels,
        'chart_flow_receitas_data': receitas_mensais,
        'chart_flow_despesas_data': despesas_mensais,
        'despesas_por_categoria': despesas_por_categoria,
        'chart_despesas_categoria_labels': chart_despesas_categoria_labels,
        'chart_despesas_categoria_data': chart_despesas_categoria_data,
        'ultimas_transacoes': ultimas_transacoes,
    }
    return render(request, 'financas/dashboard.html', contexto)


@login_required
def lista_transacoes(request):
    transacoes = Transacao.objects.filter(usuario=request.user).order_by('-data')
    paginator = Paginator(transacoes, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'financas/lista_transacoes.html', {'page_obj': page_obj})


@login_required
def adicionar_transacao(request):
    if request.method == 'POST':
        form = TransacaoForm(request.POST, user=request.user)
        if form.is_valid():
            transacao = form.save(commit=False)
            transacao.usuario = request.user
            transacao.save()
            messages.success(request, 'Transação adicionada com sucesso.')
            return redirect('lista_transacoes')
    else:
        form = TransacaoForm(user=request.user)
    return render(request, 'financas/form_transacao.html', {'form': form})


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
        form = TransacaoForm(instance=transacao, user=request.user)
    return render(request, 'financas/form_transacao.html', {'form': form})


@login_required
def deletar_transacao(request, pk):
    transacao = get_object_or_404(Transacao, pk=pk, usuario=request.user)
    if request.method == 'POST':
        transacao.delete()
        messages.success(request, 'Transação deletada com sucesso.')
        return redirect('lista_transacoes')
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
        form = CategoriaForm()
    return render(request, 'financas/form_categoria.html', {'form': form})


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
        form = CategoriaForm(instance=categoria)
    return render(request, 'financas/form_categoria.html', {'form': form})


@login_required
def deletar_categoria(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk, usuario=request.user)
    if request.method == 'POST':
        categoria.delete()
        messages.success(request, 'Categoria deletada com sucesso.')
        return redirect('lista_categorias')
    return render(request, 'financas/confirma_exclusao.html', {'obj': categoria, 'tipo': 'Categoria'})


@login_required
def relatorios(request):
    categorias = Categoria.objects.filter(usuario=request.user)

    categoria_id = request.GET.get('categoria')
    tipo = request.GET.get('tipo')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    filtro = Q(usuario=request.user)
    if categoria_id and categoria_id.isdigit():
        filtro &= Q(categoria_id=int(categoria_id))
    if tipo in ['Receita', 'Despesa']:
        filtro &= Q(tipo=tipo)
    if data_inicio:
        filtro &= Q(data__gte=data_inicio)
    if data_fim:
        filtro &= Q(data__lte=data_fim)

    transacoes_filtradas = Transacao.objects.filter(filtro).order_by('-data')

    df = pd.DataFrame(list(transacoes_filtradas.values('categoria__nome', 'valor', 'tipo')))

    if not df.empty and 'tipo' in df.columns:
        df_despesas = df[df['tipo'] == 'Despesa'].copy()
    else:
        df_despesas = pd.DataFrame()

    grafico_url = None
    if not df_despesas.empty:
        resumo_despesas = df_despesas.groupby('categoria__nome')['valor'].sum()

        plt.figure(figsize=(8,4))
        resumo_despesas.plot(kind='bar', color='#28a745')
        plt.title('Despesas por Categoria')
        plt.ylabel('Valor (R$)')
        plt.xlabel('Categoria')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        buf.seek(0)
        grafico_url = base64.b64encode(buf.getvalue()).decode('utf-8')

    context = {
        'categorias': categorias,
        'transacoes': transacoes_filtradas,
        'grafico_url': grafico_url,
        'filtros': {
            'categoria_id': categoria_id,
            'tipo': tipo,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
        }
    }
    return render(request, 'financas/relatorios.html', context)


def registro(request):
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Conta criada com sucesso! Bem-vindo(a).')
            return redirect('dashboard')
    else:
        form = RegistroForm()
    return render(request, 'financas/registro.html', {'form': form})