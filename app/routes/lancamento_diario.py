"""Lançamento Diário: quantidades e ocorrências por equipamento, gravadas na
tabela isolada `lancamento_diario` (não entra em nenhum cálculo de produção)."""
import calendar
from datetime import date, datetime, timedelta

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from ..models import get_db_connection
from . import main_bp

# (prefixo do campo no formulário, valor gravado em `equipamento`, título na tela, tem quantidade de alças)
EQUIPAMENTOS_DIARIO = [
    ('sos1', 'SOS 1', 'SOS 1', False),
    ('sos2', 'SOS 2', 'SOS 2', False),
    ('sos3', 'SOS 3', 'SOS 3', False),
    ('sos4', 'SOS 4', 'SOS 4', False),
    ('impressora', 'IMPRESSORA', 'Impressora', False),
    ('robo', 'ROBO', 'Robô', True),
    ('resmadeira', 'RESMADEIRA', 'Resmadeira', False),
    ('guilhotina', 'GUILHOTINA', 'Guilhotina', False),
]

# Grupos do bloco "Meta do Mês" (Display Diário): (grupo gravado em
# metas_lancamento_diario, título na tabela, nome do setor no painel da TV,
# equipamentos somados). No ROBO, `quantidade` são as sacolas.
# Resmadeira e Guilhotina ainda não têm meta.
GRUPOS_META_DIARIO = [
    ('SOS', 'Quantidade SOS', 'SOS', ['SOS 1', 'SOS 2', 'SOS 3', 'SOS 4']),
    ('IMPRESSORA', 'Quantidade Impressora', 'Impressora', ['IMPRESSORA']),
    ('ROBO', 'Quantidade Robô', 'Robô', ['ROBO']),
]

MESES_NOME = (
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
)

REGISTROS_POR_PAGINA = 50


class _ErroValidacao(ValueError):
    pass


def _parse_data(valor, titulo):
    valor = (valor or '').strip()
    if not valor:
        raise _ErroValidacao(f'{titulo}: informe a data.')
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(valor, fmt).date().isoformat()
        except ValueError:
            continue
    raise _ErroValidacao(f'{titulo}: data inválida ({valor}). Use dd/mm/aaaa.')


def _parse_inteiro(valor, titulo, rotulo):
    valor = (valor or '').strip()
    if not valor:
        return 0
    try:
        numero = int(valor)
    except ValueError:
        raise _ErroValidacao(f'{titulo}: {rotulo} deve ser um número inteiro.')
    if numero < 0:
        raise _ErroValidacao(f'{titulo}: {rotulo} não pode ser menor que zero.')
    return numero


def _parse_inteiro_opcional(valor, titulo, rotulo):
    """Como `_parse_inteiro`, mas campo vazio vira None (não informado)."""
    if not (valor or '').strip():
        return None
    return _parse_inteiro(valor, titulo, rotulo)


def _montar_registros(form):
    """Converte o formulário em linhas para `lancamento_diario`, ignorando blocos vazios."""
    registros = []
    for prefixo, equipamento, titulo, tem_alcas in EQUIPAMENTOS_DIARIO:
        qtd_bruta = form.get(f'{prefixo}_quantidade', '')
        alcas_bruta = form.get(f'{prefixo}_quantidade_alcas', '') if tem_alcas else ''
        problemas = form.get(f'{prefixo}_problemas', '').strip()
        solucoes = form.get(f'{prefixo}_solucoes', '').strip()
        observacao = form.get(f'{prefixo}_observacao', '').strip()

        rotulo_qtd = 'Quantidade Sacolas' if tem_alcas else 'Quantidade'
        quantidade = _parse_inteiro(qtd_bruta, titulo, rotulo_qtd)
        quantidade_alcas = _parse_inteiro(alcas_bruta, titulo, 'Quantidade Alças') if tem_alcas else None
        meta_diaria = _parse_inteiro_opcional(form.get(f'{prefixo}_meta_diaria'), titulo, 'Meta Diária')
        refugo_diario = _parse_inteiro_opcional(form.get(f'{prefixo}_refugo_diario'), titulo, 'Refugo Diário')

        preenchido = (
            quantidade > 0 or (quantidade_alcas or 0) > 0 or meta_diaria is not None
            or refugo_diario is not None or problemas or solucoes or observacao
        )
        if not preenchido:
            continue

        registros.append({
            'data': _parse_data(form.get(f'{prefixo}_data'), titulo),
            'equipamento': equipamento,
            'quantidade': quantidade,
            'quantidade_alcas': quantidade_alcas,
            'meta_diaria': meta_diaria,
            'refugo_diario': refugo_diario,
            'problemas': problemas or None,
            'solucoes': solucoes or None,
            'observacao': observacao or None,
        })
    return registros


def _formatar_data_br(valor):
    try:
        return datetime.strptime(valor, '%Y-%m-%d').strftime('%d/%m/%Y')
    except (TypeError, ValueError):
        return valor or ''


def _garantir_sinal_painel(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS painel_diario_sinal (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            versao INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        'INSERT OR IGNORE INTO painel_diario_sinal (id, versao) VALUES (1, 0)'
    )


def _bump_versao_painel(conn):
    """Sinaliza ao Display Diário (TV) que há dados novos para o painel."""
    _garantir_sinal_painel(conn)
    conn.execute(
        'UPDATE painel_diario_sinal SET versao = versao + 1 WHERE id = 1'
    )


def _ler_versao_painel():
    conn = get_db_connection()
    try:
        _garantir_sinal_painel(conn)
        conn.commit()
        row = conn.execute(
            'SELECT versao FROM painel_diario_sinal WHERE id = 1'
        ).fetchone()
        return int(row['versao'] if row else 0)
    finally:
        conn.close()


@main_bp.route('/lancamento-diario', methods=['GET', 'POST'])
def lancamento_diario():
    if request.method == 'POST':
        try:
            registros = _montar_registros(request.form)
        except _ErroValidacao as e:
            flash(str(e), 'danger')
            return render_template(
                'lancamento_diario.html',
                **_contexto_tela(valores=request.form),
            )

        if not registros:
            flash('Nenhum equipamento preenchido. Informe ao menos uma quantidade ou texto.', 'warning')
            return render_template(
                'lancamento_diario.html',
                **_contexto_tela(valores=request.form),
            )

        usuario = getattr(current_user, 'nome', None) or getattr(current_user, 'username', None)
        conn = get_db_connection()
        try:
            conn.executemany(
                """
                INSERT INTO lancamento_diario
                    (data, equipamento, quantidade, quantidade_alcas, meta_diaria, refugo_diario,
                     problemas, solucoes, observacao, usuario)
                VALUES (:data, :equipamento, :quantidade, :quantidade_alcas, :meta_diaria, :refugo_diario,
                        :problemas, :solucoes, :observacao, :usuario)
                """,
                [{**r, 'usuario': usuario} for r in registros],
            )
            _bump_versao_painel(conn)
            conn.commit()
            flash(f'Lançamento diário salvo ({len(registros)} equipamento(s)).', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Erro ao salvar lançamento diário: {e}', 'danger')
        finally:
            conn.close()
        return redirect(url_for('main.lancamento_diario'))

    return render_template('lancamento_diario.html', **_contexto_tela())


def _url_retorno_listagem():
    """Volta para a mesma página/filtro da listagem; só aceita caminhos desta tela."""
    destino = request.form.get('voltar_para', '')
    if destino.startswith('/lancamento-diario') and not destino.startswith('//'):
        return destino
    return url_for('main.lancamento_diario')


@main_bp.route('/lancamento-diario/excluir/<int:id>', methods=['POST'])
def excluir_lancamento_diario(id):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM lancamento_diario WHERE id = ?', (id,))
        _bump_versao_painel(conn)
        conn.commit()
        flash('Lançamento diário excluído.', 'success')
    except Exception as e:
        flash(f'Erro ao excluir lançamento diário: {e}', 'danger')
    finally:
        conn.close()
    return redirect(_url_retorno_listagem())


@main_bp.route('/lancamento-diario/editar/<int:id>', methods=['POST'])
def editar_lancamento_diario(id):
    conn = get_db_connection()
    try:
        atual = conn.execute('SELECT equipamento FROM lancamento_diario WHERE id = ?', (id,)).fetchone()
        if atual is None:
            flash('Lançamento diário não encontrado.', 'warning')
            return redirect(_url_retorno_listagem())

        titulos = {equip: (titulo, tem_alcas) for _, equip, titulo, tem_alcas in EQUIPAMENTOS_DIARIO}
        titulo, tem_alcas = titulos.get(atual['equipamento'], (atual['equipamento'], False))
        form = request.form
        try:
            dados = {
                'data': _parse_data(form.get('data'), titulo),
                'quantidade': _parse_inteiro(form.get('quantidade'), titulo, 'Quantidade Sacolas' if tem_alcas else 'Quantidade'),
                'quantidade_alcas': _parse_inteiro(form.get('quantidade_alcas'), titulo, 'Quantidade Alças') if tem_alcas else None,
                'meta_diaria': _parse_inteiro_opcional(form.get('meta_diaria'), titulo, 'Meta Diária'),
                'refugo_diario': _parse_inteiro_opcional(form.get('refugo_diario'), titulo, 'Refugo Diário'),
                'problemas': form.get('problemas', '').strip() or None,
                'solucoes': form.get('solucoes', '').strip() or None,
                'observacao': form.get('observacao', '').strip() or None,
                'id': id,
            }
        except _ErroValidacao as e:
            flash(str(e), 'danger')
            return redirect(_url_retorno_listagem())

        conn.execute(
            """
            UPDATE lancamento_diario
            SET data = :data, quantidade = :quantidade, quantidade_alcas = :quantidade_alcas,
                meta_diaria = :meta_diaria, refugo_diario = :refugo_diario,
                problemas = :problemas, solucoes = :solucoes, observacao = :observacao
            WHERE id = :id
            """,
            dados,
        )
        _bump_versao_painel(conn)
        conn.commit()
        flash('Lançamento diário atualizado.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Erro ao atualizar lançamento diário: {e}', 'danger')
    finally:
        conn.close()
    return redirect(_url_retorno_listagem())


def _juntar_textos(valores):
    textos = [v.strip() for v in valores if v and v.strip()]
    return '\n'.join(textos) if textos else None


@main_bp.route('/display-diario')
def display_diario():
    try:
        data_sel = _parse_data(request.args.get('data'), 'Data')
    except _ErroValidacao:
        data_sel = date.today().isoformat()

    conn = get_db_connection()
    try:
        linhas = conn.execute(
            """
            SELECT equipamento, quantidade, meta_diaria, problemas, solucoes, observacao
            FROM lancamento_diario
            WHERE data = ?
            ORDER BY id
            """,
            (data_sel,),
        ).fetchall()
    finally:
        conn.close()

    por_equipamento = {}
    for linha in linhas:
        por_equipamento.setdefault(linha['equipamento'], []).append(linha)

    producao_dia = []
    for _, equipamento, titulo, _ in EQUIPAMENTOS_DIARIO:
        registros = por_equipamento.get(equipamento, [])
        quantidade = sum(r['quantidade'] or 0 for r in registros)
        metas = [r['meta_diaria'] for r in registros if r['meta_diaria'] is not None]
        producao_dia.append({
            'titulo': titulo,
            'tem_lancamento': bool(registros),
            'meta_diaria_fmt': _fmt_int(sum(metas)) if metas else None,
            'quantidade_fmt': f'{quantidade:,}'.replace(',', '.'),
            'problemas': _juntar_textos(r['problemas'] for r in registros),
            'solucoes': _juntar_textos(r['solucoes'] for r in registros),
            'observacao': _juntar_textos(r['observacao'] for r in registros),
        })

    ano, mes = _parse_mes(request.args.get('mes'))
    meta_mes = _montar_meta_mes(ano, mes)

    return render_template(
        'display_diario.html',
        data_selecionada=data_sel,
        data_selecionada_fmt=_formatar_data_br(data_sel),
        producao_dia=producao_dia,
        mes_selecionado=f'{ano:04d}-{mes:02d}',
        mes_selecionado_fmt=f'{MESES_NOME[mes - 1]}/{ano}',
        meta_mes=meta_mes,
    )


def _parse_mes(valor):
    try:
        d = datetime.strptime((valor or '').strip(), '%Y-%m')
        return d.year, d.month
    except ValueError:
        hoje = date.today()
        return hoje.year, hoje.month


def _fmt_int(valor):
    return f'{valor:,}'.replace(',', '.')


def _contar_dias_uteis(inicio, fim):
    """Conta dias úteis (segunda a sexta) no intervalo inclusivo [inicio, fim]."""
    if fim < inicio:
        return 0
    total = 0
    dia = inicio
    while dia <= fim:
        if dia.weekday() < 5:  # 0=segunda … 4=sexta
            total += 1
        dia += timedelta(days=1)
    return total


def _dias_uteis_projecao_mes(ano, mes, hoje=None):
    """Retorna (dias úteis do mês, dias úteis já decorridos) para a projeção.

    Mês passado: decorridos = total (projeção = produzido).
    Mês atual: decorridos = úteis de 1 até hoje (inclusive).
    Mês futuro: decorridos = 0 (sem projeção).
    Não desconta feriados — só sábados e domingos.
    """
    hoje = hoje or date.today()
    ultimo = date(ano, mes, calendar.monthrange(ano, mes)[1])
    primeiro = date(ano, mes, 1)
    total_uteis = _contar_dias_uteis(primeiro, ultimo)
    if (ano, mes) > (hoje.year, hoje.month):
        return total_uteis, 0
    if (ano, mes) < (hoje.year, hoje.month):
        return total_uteis, total_uteis
    return total_uteis, _contar_dias_uteis(primeiro, min(hoje, ultimo))


def _montar_meta_mes(ano, mes, hoje=None):
    inicio = f'{ano:04d}-{mes:02d}-01'
    fim = f'{ano + 1:04d}-01-01' if mes == 12 else f'{ano:04d}-{mes + 1:02d}-01'
    total_dias, dias_passados = _dias_uteis_projecao_mes(ano, mes, hoje)
    conn = get_db_connection()
    try:
        # Painel de Metas: ignora lançamentos de sábado (strftime %w: 0=dom … 6=sáb).
        soma_por_equip = {
            r['equipamento']: r['total'] or 0
            for r in conn.execute(
                """
                SELECT equipamento, SUM(quantidade) AS total
                FROM lancamento_diario
                WHERE data >= ? AND data < ?
                  AND CAST(strftime('%w', data) AS INTEGER) != 6
                GROUP BY equipamento
                """,
                (inicio, fim),
            ).fetchall()
        }
        metas = {
            r['grupo']: r['meta_quantidade']
            for r in conn.execute(
                'SELECT grupo, meta_quantidade FROM metas_lancamento_diario WHERE ano = ? AND mes = ?',
                (ano, mes),
            ).fetchall()
        }
    finally:
        conn.close()

    linhas = []
    for grupo, titulo, setor, equipamentos in GRUPOS_META_DIARIO:
        produzido = sum(soma_por_equip.get(e, 0) for e in equipamentos)
        meta = metas.get(grupo)
        if dias_passados > 0:
            projecao = round(produzido * total_dias / dias_passados)
            projecao_fmt = _fmt_int(projecao)
        else:
            projecao_fmt = '—'
        linha = {
            'grupo': grupo,
            'titulo': titulo,
            'setor': setor,
            'meta': meta,
            'produzido_fmt': _fmt_int(produzido),
            'meta_fmt': _fmt_int(meta) if meta else '—',
            'status_fmt': '—',
            'falta_fmt': '—',
            'projecao_fmt': projecao_fmt,
            'atingida': False,
        }
        if meta:
            pct = produzido / meta * 100
            linha['pct'] = pct
            linha['pct_grafico'] = min(pct, 100.0)
            linha['status_fmt'] = f'{pct:.2f}'.replace('.', ',') + '%'
            linha['falta_fmt'] = _fmt_int(max(meta - produzido, 0))
            linha['atingida'] = produzido >= meta
        linhas.append(linha)
    return linhas


@main_bp.route('/display-diario/metas', methods=['POST'])
def salvar_metas_display_diario():
    ano, mes = _parse_mes(request.form.get('mes'))
    try:
        valores = {}
        for grupo, titulo, _, _ in GRUPOS_META_DIARIO:
            valores[grupo] = _parse_inteiro(request.form.get(f'meta_{grupo}'), titulo, 'a meta')
    except _ErroValidacao as e:
        flash(str(e), 'danger')
    else:
        conn = get_db_connection()
        try:
            for grupo, meta in valores.items():
                if meta > 0:
                    conn.execute(
                        """
                        INSERT INTO metas_lancamento_diario (ano, mes, grupo, meta_quantidade)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(ano, mes, grupo) DO UPDATE SET meta_quantidade = excluded.meta_quantidade
                        """,
                        (ano, mes, grupo, meta),
                    )
                else:
                    conn.execute(
                        'DELETE FROM metas_lancamento_diario WHERE ano = ? AND mes = ? AND grupo = ?',
                        (ano, mes, grupo),
                    )
            _bump_versao_painel(conn)
            conn.commit()
            flash(f'Metas de {MESES_NOME[mes - 1]}/{ano} salvas.', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Erro ao salvar metas: {e}', 'danger')
        finally:
            conn.close()
    return redirect(url_for(
        'main.display_diario',
        mes=f'{ano:04d}-{mes:02d}',
        data=request.form.get('data') or None,
    ))


@main_bp.route('/display-diario/versao')
def versao_painel_display_diario():
    """Versão leve para o painel TV detectar novos lançamentos sem baixar a página."""
    return jsonify({'versao': _ler_versao_painel()})


def _filtros_listagem(args):
    """Filtros de data (YYYY-MM-DD) válidos da listagem; valores inválidos são ignorados."""
    filtros = {}
    for chave in ('filtro_inicio', 'filtro_fim'):
        try:
            filtros[chave] = _parse_data(args.get(chave), '')
        except _ErroValidacao:
            pass
    return filtros


def _contexto_tela(valores=None):
    filtros = _filtros_listagem(request.args)
    condicoes, params = [], []
    if 'filtro_inicio' in filtros:
        condicoes.append('data >= ?')
        params.append(filtros['filtro_inicio'])
    if 'filtro_fim' in filtros:
        condicoes.append('data <= ?')
        params.append(filtros['filtro_fim'])
    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ''

    conn = get_db_connection()
    try:
        total_registros = conn.execute(f'SELECT COUNT(*) FROM lancamento_diario {where}', params).fetchone()[0]
        total_paginas = max(1, -(-total_registros // REGISTROS_POR_PAGINA))
        page = min(max(request.args.get('page', 1, type=int) or 1, 1), total_paginas)
        linhas = conn.execute(
            f"""
            SELECT id, data, equipamento, quantidade, quantidade_alcas, meta_diaria, refugo_diario,
                   problemas, solucoes, observacao, usuario
            FROM lancamento_diario
            {where}
            ORDER BY data DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, REGISTROS_POR_PAGINA, (page - 1) * REGISTROS_POR_PAGINA),
        ).fetchall()
    finally:
        conn.close()

    rotulos = {equip: titulo for _, equip, titulo, _ in EQUIPAMENTOS_DIARIO}
    registros = []
    for linha in linhas:
        r = dict(linha)
        r['data_fmt'] = _formatar_data_br(r['data'])
        r['equipamento_fmt'] = rotulos.get(r['equipamento'], r['equipamento'])
        registros.append(r)

    return {
        'equipamentos': EQUIPAMENTOS_DIARIO,
        'valores': valores or {},
        'hoje': date.today().isoformat(),
        'registros': registros,
        'filtros': filtros,
        'page': page,
        'total_paginas': total_paginas,
        'total_registros': total_registros,
        'per_page': REGISTROS_POR_PAGINA,
        'voltar_para': url_for('main.lancamento_diario', page=page, **filtros),
    }
