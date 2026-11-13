"""Lançamento Diário: quantidades e ocorrências por equipamento, gravadas na
tabela isolada `lancamento_diario` (não entra em nenhum cálculo de produção)."""
import calendar
import math
import re
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone

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
EQUIPAMENTOS_SOS = {'SOS 1', 'SOS 2', 'SOS 3', 'SOS 4'}


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


def _parse_peso_diario(valor, titulo, rotulo='Peso Diário (kg)'):
    texto = str(valor).strip() if valor is not None else ''
    if not texto:
        return None
    if not re.fullmatch(r'[0-9]+(?:[,.][0-9]+)?', texto):
        raise _ErroValidacao(f'{titulo}: {rotulo} deve ser um número não negativo, como 1250,75.')
    peso = float(texto.replace(',', '.'))
    if not math.isfinite(peso):
        raise _ErroValidacao(f'{titulo}: {rotulo} inválido.')
    return peso


def _refugos_form(form, equipamento, titulo, prefixo='', atual=None):
    campos = ('refugo_impressora', 'refugo_sos')
    partes = {c: None for c in campos}
    if equipamento in EQUIPAMENTOS_SOS and any(prefixo + c in form for c in campos):
        for campo, rotulo in zip(campos, ('Refugo Impressora', 'Refugo SOS')):
            partes[campo] = _parse_inteiro_opcional(form.get(prefixo + campo), titulo, rotulo)
        valores = [v for v in partes.values() if v is not None]
        total = sum(valores) if valores else None
        # Um lançamento antigo tem só o total: não inventar a divisão nem perder o valor.
        if not valores and atual and all(atual[c] is None for c in campos):
            total = atual['refugo_diario']
    else:
        total = _parse_inteiro_opcional(form.get(prefixo + 'refugo_diario'), titulo, 'Refugo Diário')
    return {**partes, 'refugo_diario': total}


def _montar_registros(form):
    """Converte o formulário em linhas para `lancamento_diario`, ignorando blocos vazios."""
    registros = []
    for prefixo, equipamento, titulo, tem_alcas in EQUIPAMENTOS_DIARIO:
        if form.get(prefixo + '_usa_producoes') == '1':
            registro = _registro_por_producoes(form, prefixo, equipamento, titulo, tem_alcas)
            if registro:
                registros.append(registro)
            continue
        qtd_bruta = form.get(f'{prefixo}_quantidade', '')
        alcas_bruta = form.get(f'{prefixo}_quantidade_alcas', '') if tem_alcas else ''
        problemas = form.get(f'{prefixo}_problemas', '').strip()
        solucoes = form.get(f'{prefixo}_solucoes', '').strip()
        observacao = form.get(f'{prefixo}_observacao', '').strip()

        rotulo_qtd = 'Quantidade Sacolas' if tem_alcas else 'Quantidade'
        quantidade = _parse_inteiro(qtd_bruta, titulo, rotulo_qtd)
        quantidade_alcas = _parse_inteiro(alcas_bruta, titulo, 'Quantidade Alças') if tem_alcas else None
        meta_diaria = _parse_inteiro_opcional(form.get(f'{prefixo}_meta_diaria'), titulo, 'Meta Diária')
        refugos = _refugos_form(form, equipamento, titulo, prefixo + '_')
        peso_diario = _parse_peso_diario(form.get(f'{prefixo}_peso_diario'), titulo) if equipamento in EQUIPAMENTOS_SOS else None
        refugo_diario = refugos['refugo_diario']

        preenchido = (
            quantidade > 0 or (quantidade_alcas or 0) > 0 or meta_diaria is not None
            or refugo_diario is not None or peso_diario is not None or problemas or solucoes or observacao
        )
        if not preenchido:
            continue

        registros.append({
            'data': _parse_data(form.get(f'{prefixo}_data'), titulo),
            'equipamento': equipamento,
            'quantidade': quantidade,
            'quantidade_alcas': quantidade_alcas,
            'meta_diaria': meta_diaria,
            **refugos,
            'peso_diario': peso_diario,
            'problemas': problemas or None,
            'solucoes': solucoes or None,
            'observacao': observacao or None,
        })
    return registros


CAMPOS_PRODUCAO_DIARIA = ('quantidade', 'quantidade_alcas', 'peso_diario', 'refugo_diario', 'refugo_impressora', 'refugo_sos')


def _registro_por_producoes(form, prefixo, equipamento, titulo, tem_alcas, anteriores=()):
    producoes = []
    for chave in form:
        match = re.fullmatch(re.escape(prefixo) + r'_p(\d+)_\w+', chave)
        if match and not 1 <= int(match[1]) <= 10 and str(form.get(chave, '')).strip():
            raise _ErroValidacao(f'{titulo}: informe no máximo 10 produções.')
    for ordem in range(1, 11):
        p = f'{prefixo}_p{ordem}_'
        eh_sos = equipamento in EQUIPAMENTOS_SOS
        campos = ['quantidade']
        if eh_sos:
            campos.append('milheiro')
        elif equipamento not in ('IMPRESSORA', 'ROBO'):
            campos.append('peso_diario')
        campos += ['refugo_impressora', 'refugo_sos'] if equipamento in EQUIPAMENTOS_SOS else ['refugo_diario']
        if not any(str(form.get(p + campo, '')).strip() for campo in campos):
            continue
        linha = {campo: None for campo in CAMPOS_PRODUCAO_DIARIA}
        linha['milheiro'] = None
        linha['ordem'] = ordem
        antigo = next((p for p in anteriores if p['ordem'] == ordem), None)
        if antigo and equipamento in ('IMPRESSORA', 'ROBO'):
            linha['peso_diario'] = antigo['peso_diario']  # Preserva dados históricos, sem novo input.
        if antigo and tem_alcas:
            linha['quantidade_alcas'] = antigo['quantidade_alcas']
        for campo in campos:
            rotulo = f'Produção {ordem} · {campo.replace("_", " ")}'
            if campo in ('quantidade', 'quantidade_alcas'):
                linha[campo] = _parse_inteiro(form.get(p + campo), titulo, rotulo)
            else:
                # Peso e refugo por produção aceitam decimais com vírgula.
                linha[campo] = _parse_peso_diario(form.get(p + campo), titulo, rotulo)
        if equipamento in EQUIPAMENTOS_SOS:
            if linha['milheiro'] is not None:
                peso = Decimal(linha['quantidade']) / Decimal(1000) * Decimal(str(linha['milheiro']))
                linha['peso_diario'] = float(peso)
                if not math.isfinite(linha['peso_diario']):
                    raise _ErroValidacao(f'{titulo}: peso calculado inválido na produção {ordem}.')
            else:
                antigo = next((p for p in anteriores if p['ordem'] == ordem), None)
                if antigo and antigo['milheiro'] is None and antigo['peso_diario'] is not None:
                    if linha['quantidade'] != antigo['quantidade']:
                        raise _ErroValidacao(f'{titulo}: informe o Milheiro da produção {ordem} para alterar sua quantidade.')
                    linha['peso_diario'] = antigo['peso_diario']
            valores = [linha[c] for c in ('refugo_impressora', 'refugo_sos') if linha[c] is not None]
            linha['refugo_diario'] = float(sum(Decimal(str(v)) for v in valores)) if valores else None
        producoes.append(linha)

    textos = {campo: form.get(f'{prefixo}_{campo}', '').strip() or None for campo in ('problemas', 'solucoes', 'observacao')}
    meta = _parse_inteiro_opcional(form.get(prefixo + '_meta_diaria'), titulo, 'Meta Diária')
    alcas_dia = _parse_inteiro_opcional(form.get(prefixo + '_quantidade_alcas'), titulo, 'Quantidade Alças') if tem_alcas else None
    if not producoes and meta is None and alcas_dia is None and not any(textos.values()):
        return None
    registro = {
        'data': _parse_data(form.get(prefixo + '_data'), titulo), 'equipamento': equipamento,
        'meta_diaria': meta, **textos, 'producoes': producoes,
    }
    for campo in CAMPOS_PRODUCAO_DIARIA:
        valores = [p[campo] for p in producoes if p[campo] is not None]
        if campo == 'quantidade' or (campo == 'quantidade_alcas' and tem_alcas):
            registro[campo] = sum(valores)
        else:
            registro[campo] = float(sum(Decimal(str(v)) for v in valores)) if valores else None
    if tem_alcas:
        registro['quantidade_alcas'] = alcas_dia or 0
    return registro


def _salvar_producoes(conn, registro_id, producoes):
    conn.execute('DELETE FROM lancamento_diario_producoes WHERE lancamento_id = ?', (registro_id,))
    conn.executemany(
        '''INSERT INTO lancamento_diario_producoes
           (lancamento_id, ordem, quantidade, quantidade_alcas, peso_diario, refugo_diario, refugo_impressora, refugo_sos, milheiro)
           VALUES (:lancamento_id, :ordem, :quantidade, :quantidade_alcas, :peso_diario, :refugo_diario, :refugo_impressora, :refugo_sos, :milheiro)''',
        [{**p, 'lancamento_id': registro_id} for p in producoes],
    )


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
                **_contexto_formulario(valores=request.form),
            )

        if not registros:
            flash('Nenhum equipamento preenchido. Informe ao menos uma quantidade ou texto.', 'warning')
            return render_template(
                'lancamento_diario.html',
                **_contexto_formulario(valores=request.form),
            )

        usuario = getattr(current_user, 'nome', None) or getattr(current_user, 'username', None)
        conn = get_db_connection()
        try:
            for r in registros:
                cursor = conn.execute(
                    """
                INSERT INTO lancamento_diario
                    (data, equipamento, quantidade, quantidade_alcas, meta_diaria, refugo_diario, refugo_impressora, refugo_sos,
                     peso_diario, problemas, solucoes, observacao, usuario)
                VALUES (:data, :equipamento, :quantidade, :quantidade_alcas, :meta_diaria, :refugo_diario, :refugo_impressora, :refugo_sos,
                        :peso_diario, :problemas, :solucoes, :observacao, :usuario)
                    """,
                    {**r, 'usuario': usuario},
                )
                _salvar_producoes(conn, cursor.lastrowid, r.get('producoes', []))
            _bump_versao_painel(conn)
            conn.commit()
            flash(f'Lançamento diário salvo ({len(registros)} equipamento(s)).', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Erro ao salvar lançamento diário: {e}', 'danger')
        finally:
            conn.close()
        return redirect(url_for('main.lancamento_diario'))

    return render_template('lancamento_diario.html', **_contexto_formulario())


@main_bp.route('/historico-diario')
def historico_diario():
    return render_template('historico_diario.html', **_contexto_listagem())


def _url_retorno_listagem():
    """Volta para a mesma página/filtro do Histórico Diário; só aceita caminhos desta tela."""
    destino = request.form.get('voltar_para', '')
    if destino.startswith('/historico-diario') and not destino.startswith('//'):
        return destino
    return url_for('main.historico_diario')


@main_bp.route('/lancamento-diario/excluir/<int:id>', methods=['POST'])
def excluir_lancamento_diario(id):
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM lancamento_diario_producoes WHERE lancamento_id = ?', (id,))
        conn.execute('DELETE FROM lancamento_diario WHERE id = ?', (id,))
        _bump_versao_painel(conn)
        conn.commit()
        flash('Lançamento diário excluído.', 'success')
    except Exception as e:
        flash(f'Erro ao excluir lançamento diário: {e}', 'danger')
    finally:
        conn.close()
    return redirect(_url_retorno_listagem())


@main_bp.route('/lancamento-diario/editar/<int:id>', methods=['GET', 'POST'])
def editar_lancamento_diario(id):
    conn = get_db_connection()
    try:
        atual = conn.execute('SELECT * FROM lancamento_diario WHERE id = ?', (id,)).fetchone()
        if atual is None:
            flash('Lançamento diário não encontrado.', 'warning')
            return redirect(_url_retorno_listagem())

        titulos = {equip: (titulo, tem_alcas) for _, equip, titulo, tem_alcas in EQUIPAMENTOS_DIARIO}
        titulo, tem_alcas = titulos.get(atual['equipamento'], (atual['equipamento'], False))
        producoes = conn.execute('SELECT * FROM lancamento_diario_producoes WHERE lancamento_id = ? ORDER BY ordem', (id,)).fetchall()
        if request.method == 'GET':
            if not producoes:
                return redirect(url_for('main.historico_diario'))
            equipamento = next(e for e in EQUIPAMENTOS_DIARIO if e[1] == atual['equipamento'])
            prefixo = equipamento[0]
            valores = {prefixo + '_' + campo: atual[campo] if atual[campo] is not None else ''
                       for campo in ('data', 'meta_diaria', 'quantidade_alcas', 'problemas', 'solucoes', 'observacao')}
            for producao in producoes:
                for campo in (*CAMPOS_PRODUCAO_DIARIA, 'milheiro'):
                    valores[f'{prefixo}_p{producao["ordem"]}_{campo}'] = producao[campo] if producao[campo] is not None else ''
            contexto = _contexto_formulario(valores)
            contexto.update(equipamentos=[equipamento], editando=id)
            return render_template('lancamento_diario.html', **contexto)
        form = request.form
        prefixo = next(e[0] for e in EQUIPAMENTOS_DIARIO if e[1] == atual['equipamento'])
        modo_producoes = form.get(prefixo + '_usa_producoes') == '1'
        if producoes and not modo_producoes:
            flash('Edite as produções para recalcular os totais deste lançamento.', 'warning')
            return redirect(url_for('main.editar_lancamento_diario', id=id))
        try:
            if modo_producoes:
                dados = _registro_por_producoes(form, prefixo, atual['equipamento'], titulo, tem_alcas, anteriores=producoes)
                if not dados:
                    raise _ErroValidacao('Informe uma produção ou os dados do dia.')
                dados['id'] = id
            else:
                dados = {
                    'data': _parse_data(form.get('data'), titulo),
                    'quantidade': _parse_inteiro(form.get('quantidade'), titulo, 'Quantidade Sacolas' if tem_alcas else 'Quantidade'),
                    'quantidade_alcas': _parse_inteiro(form.get('quantidade_alcas'), titulo, 'Quantidade Alças') if tem_alcas else None,
                    'meta_diaria': _parse_inteiro_opcional(form.get('meta_diaria'), titulo, 'Meta Diária'),
                    **_refugos_form(form, atual['equipamento'], titulo, atual=atual),
                    'peso_diario': _parse_peso_diario(form.get('peso_diario', atual['peso_diario']), titulo) if atual['equipamento'] in EQUIPAMENTOS_SOS else None,
                    'problemas': form.get('problemas', '').strip() or None,
                    'solucoes': form.get('solucoes', '').strip() or None,
                    'observacao': form.get('observacao', '').strip() or None,
                    'id': id,
                }
        except _ErroValidacao as e:
            flash(str(e), 'danger')
            if modo_producoes:
                contexto = _contexto_formulario(form)
                contexto.update(equipamentos=[e for e in EQUIPAMENTOS_DIARIO if e[1] == atual['equipamento']], editando=id)
                return render_template('lancamento_diario.html', **contexto)
            return redirect(_url_retorno_listagem())

        conn.execute(
            """
            UPDATE lancamento_diario
            SET data = :data, quantidade = :quantidade, quantidade_alcas = :quantidade_alcas,
                meta_diaria = :meta_diaria, refugo_diario = :refugo_diario,
                refugo_impressora = :refugo_impressora, refugo_sos = :refugo_sos,
                peso_diario = :peso_diario,
                problemas = :problemas, solucoes = :solucoes, observacao = :observacao
            WHERE id = :id
            """,
            dados,
        )
        if modo_producoes:
            _salvar_producoes(conn, id, dados['producoes'])
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


def _quadro_sos_semana(hoje=None):
    # O quadro da TV sempre acompanha a semana atual de São Paulo, independente dos filtros.
    hoje = hoje or datetime.now(timezone(timedelta(hours=-3))).date()
    segunda = hoje - timedelta(days=hoje.weekday())
    sexta = segunda + timedelta(days=4)
    conn = get_db_connection()
    try:
        registros = conn.execute(
            """SELECT * FROM lancamento_diario WHERE data >= ? AND data < ?
               AND equipamento IN ('SOS 1', 'SOS 2', 'SOS 3', 'SOS 4')
               ORDER BY data, equipamento, id""",
            (segunda.isoformat(), (sexta + timedelta(days=1)).isoformat())
        ).fetchall()
        configuracao = conn.execute(
            'SELECT meta_refugo_pct FROM configuracao_quadro_sos WHERE id = 1'
        ).fetchone()
        meta_refugo = configuracao['meta_refugo_pct'] if configuracao else None
    finally:
        conn.close()
    grupos = {}
    for r in registros:
        grupos.setdefault((r['data'], r['equipamento']), []).append(dict(r))

    def percentual(valor, denominador):
        return valor / denominador * 100 if valor is not None and denominador is not None and denominador > 0 else None

    def fmt_pct(valor):
        return f'{valor:.2f}'.replace('.', ',') + '%' if valor is not None else '—'

    def soma_completa(linhas, campo):
        return sum(r[campo] for r in linhas) if linhas and all(r[campo] is not None for r in linhas) else None

    def indicadores(linhas):
        producao = sum(r['quantidade'] or 0 for r in linhas)
        meta = soma_completa(linhas, 'meta_diaria')
        peso = soma_completa(linhas, 'peso_diario')
        totais, pis, sos = [], [], []
        for r in linhas:
            if r['refugo_impressora'] is not None or r['refugo_sos'] is not None:
                pis.append(r['refugo_impressora'] or 0)
                sos.append(r['refugo_sos'] or 0)
                totais.append(pis[-1] + sos[-1])
            elif r['refugo_diario'] is not None:
                totais.append(r['refugo_diario'])
        total = sum(totais) if linhas and len(totais) == len(linhas) else None
        pi = sum(pis) if linhas and len(pis) == len(linhas) else None
        rsos = sum(sos) if linhas and len(sos) == len(linhas) else None
        atingimento = percentual(producao, meta)
        def pct_refugo(valor):
            return percentual(valor, peso + valor) if peso is not None and valor is not None else None
        refugo_pct = pct_refugo(total)
        cor_producao = ('verde' if atingimento >= 100 else 'vermelho') if atingimento is not None else ''
        cor_refugo = ('verde' if refugo_pct < meta_refugo else 'vermelho') if refugo_pct is not None and meta_refugo is not None else ''
        return {
            'tem_dados': bool(linhas), 'producao': _fmt_int(producao) if linhas else '—',
            'meta': _fmt_int(meta) if meta is not None else '—',
            'produtividade': fmt_pct(atingimento), 'barra': min(100, max(0, atingimento or 0)),
            'atingida': atingimento is not None and atingimento >= 100,
            'cor_producao': cor_producao, 'cor_refugo': cor_refugo,
            'refugo': f'{total:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.') if total is not None else '—',
            'refugo_pi_pct': fmt_pct(pct_refugo(pi)), 'refugo_sos_pct': fmt_pct(pct_refugo(rsos)),
            'refugo_total_pct': fmt_pct(refugo_pct),
        }
    dias = []
    for i, nome in enumerate(('Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta')):
        dia = segunda + timedelta(days=i)
        maquinas = []
        todas = []
        for numero in range(1, 5):
            linhas = grupos.get((dia.isoformat(), f'SOS {numero}'), [])
            todas.extend(linhas)
            maquinas.append({'sos': f'SOS {numero}', **indicadores(linhas)})
        dias.append({
            'nome': nome, 'data': dia.strftime('%d/%m'), 'iso': dia.isoformat(),
            'hoje': dia == hoje, 'futuro': dia > hoje,
            'maquinas': maquinas, 'resumo': indicadores(todas),
        })
    return {
        'inicio': segunda.strftime('%d/%m/%Y'), 'fim': sexta.strftime('%d/%m/%Y'), 'dias': dias,
        'meta_refugo': format(Decimal(str(meta_refugo)), 'f').rstrip('0').rstrip('.').replace('.', ',') if meta_refugo is not None else '',
    }


@main_bp.route('/display-diario/meta-refugo-sos', methods=['POST'])
def salvar_meta_refugo_sos():
    try:
        meta = _parse_peso_diario(request.form.get('meta_refugo'), 'Semana das SOS', 'Meta de Refugo (%)')
        if meta is not None and meta > 100:
            raise _ErroValidacao('Meta de Refugo (%): informe um valor de 0 a 100.')
    except _ErroValidacao as e:
        flash(str(e), 'danger')
    else:
        conn = get_db_connection()
        try:
            conn.execute(
                '''INSERT INTO configuracao_quadro_sos (id, meta_refugo_pct) VALUES (1, ?)
                   ON CONFLICT(id) DO UPDATE SET meta_refugo_pct = excluded.meta_refugo_pct''',
                (meta,),
            )
            _bump_versao_painel(conn)
            conn.commit()
            flash('Meta de refugo das SOS salva.' if meta is not None else 'Meta de refugo das SOS removida.', 'success')
        except Exception:
            conn.rollback()
            flash('Erro ao salvar a meta de refugo. Tente novamente.', 'danger')
        finally:
            conn.close()
    ano, mes = _parse_mes(request.form.get('mes'))
    try:
        data = _parse_data(request.form.get('data'), 'Data')
    except _ErroValidacao:
        data = None
    return redirect(url_for('main.display_diario', mes=f'{ano:04d}-{mes:02d}', data=data, _anchor='indicadores-sos'))


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
        semana_sos=_quadro_sos_semana(),
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


def _contexto_formulario(valores=None):
    valores = valores or {}
    visiveis, abertos = {}, {}
    for prefixo, *_ in EQUIPAMENTOS_DIARIO:
        preenchidos = [int(m[1]) for chave in valores
                       if (m := re.fullmatch(re.escape(prefixo) + r'_p(\d+)_\w+', chave))
                       and str(valores.get(chave, '')).strip()]
        visiveis[prefixo] = min(10, max([1, *preenchidos]))
        abertos[prefixo] = any(k.startswith(prefixo + '_') and k not in (prefixo + '_data', prefixo + '_usa_producoes')
                              and str(valores.get(k, '')).strip() for k in valores)
    return {
        'equipamentos': EQUIPAMENTOS_DIARIO, 'valores': valores,
        'hoje': date.today().isoformat(), 'visiveis': visiveis, 'abertos': abertos,
    }


def _contexto_listagem():
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
            SELECT id, data, equipamento, quantidade, quantidade_alcas, meta_diaria, refugo_diario, refugo_impressora, refugo_sos,
                   EXISTS(SELECT 1 FROM lancamento_diario_producoes p WHERE p.lancamento_id = lancamento_diario.id) AS tem_producoes,
                   peso_diario, problemas, solucoes, observacao, usuario
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
        'registros': registros,
        'filtros': filtros,
        'page': page,
        'total_paginas': total_paginas,
        'total_registros': total_registros,
        'per_page': REGISTROS_POR_PAGINA,
        'voltar_para': url_for('main.historico_diario', page=page, **filtros),
    }
