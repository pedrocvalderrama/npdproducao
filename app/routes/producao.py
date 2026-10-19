"""Rotas de lançamento de produção: formulário, criar, editar, excluir."""
from flask import render_template, request, flash, redirect, url_for, session, jsonify
from datetime import datetime
from ..models import get_db_connection
from ..business import enrich_lancamento_observacoes
from ..config import OPERADORES_SOS, OPERADORES_IMPRESSORA, OPERADORES_ROBO, PAPEIS, TIPOS
from ..services.formato_service import (
    obter_formatos,
    obter_ideal_speed_rates,
    obter_weight_tolerances,
)
from ..services.producao_service import (
    atualizar_producao,
    montar_campos_producao,
    salvar_producao,
    validar_form_producao,
)
from . import main_bp


def _contexto_lancamento(**extra):
    ctx = {
        'formatos': obter_formatos(),
        'papeis': PAPEIS,
        'tipos': TIPOS,
        'operadores_sos': OPERADORES_SOS,
        'operadores_impressora': OPERADORES_IMPRESSORA,
        'operadores_robo': OPERADORES_ROBO,
        'ideal_speed_rates': obter_ideal_speed_rates(),
        'weight_tolerances': obter_weight_tolerances(),
    }
    ctx.update(extra)
    return ctx


def _form_como_lancamento(form):
    """Converte o POST em dict para reexibir o formulário após erro de validação."""
    return form.to_dict()


# Rota principal: formulário de lançamento de produção
@main_bp.route("/")
def index():
    # Não passa valores padrão - formulário começa vazio para novo lançamento
    return render_template(
        'index.html',
        **_contexto_lancamento(
            page_title="Lançamento de Produção",
            action_url=url_for('main.lancar'),
            lancamento=None,
        ),
    )

# Rota para buscar dados por Nº OF (AJAX)
@main_bp.route("/buscar_por_of")
def buscar_por_of():
    """Busca um registro pelo Nº OF e retorna os dados em JSON."""
    num_of = request.args.get('num_of', '')
    if not num_of:
        return jsonify({}), 400
    conn = get_db_connection()
    lancamento = conn.execute("SELECT * FROM producao WHERE num_of = ?", (num_of,)).fetchone()
    conn.close()
    if lancamento:
        return jsonify(enrich_lancamento_observacoes(lancamento))
    return jsonify({}), 404

# Rota para duplicar um lançamento existente
@main_bp.route("/duplicar/<int:id>")
def duplicar(id):
    conn = get_db_connection()
    lancamento_original = conn.execute("SELECT * FROM producao WHERE id = ?", (id,)).fetchone()
    conn.close()
    if lancamento_original is None:
        flash("Registro original não encontrado.", "warning")
        return redirect(url_for('main.historico'))
    lancamento = enrich_lancamento_observacoes(dict(lancamento_original))
    lancamento['data'] = datetime.today().strftime('%Y-%m-%d')
    lancamento['id'] = None
    return render_template(
        'index.html',
        **_contexto_lancamento(
            page_title="Duplicar Lançamento",
            action_url=url_for('main.lancar'),
            lancamento=lancamento,
        ),
    )

# Rota para lançar um novo registro de produção
@main_bp.route("/lancar", methods=["POST"])
def lancar():
    erro = validar_form_producao(request.form)
    if erro:
        flash(erro, "danger")
        return render_template(
            'index.html',
            **_contexto_lancamento(
                page_title="Lançamento de Produção",
                action_url=url_for('main.lancar'),
                lancamento=_form_como_lancamento(request.form),
            ),
        )

    conn = None
    try:
        # Salva últimas seleções na sessão
        session['last_operador'] = request.form.get('operador')
        session['last_sos'] = request.form.get('sos')
        session['last_tipo'] = request.form.get('tipo')
        session['last_formato'] = request.form.get('formato')
        session['last_papel'] = request.form.get('papel')
        session['last_tipo_impressao'] = request.form.get('tipo_impressao')

        conn = get_db_connection()
        foi_update = salvar_producao(conn, request.form)
        conn.commit()
        flash("Dados atualizados com sucesso." if foi_update else "Dados lançados com sucesso.", "success")
    except Exception as e:
        flash(f"Erro ao salvar no banco: {e}", "danger")
    finally:
        if conn is not None:
            conn.close()
    return redirect(url_for('main.historico'))

# Rota para editar um registro existente
@main_bp.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    conn = get_db_connection()
    if request.method == "POST":
        erro = validar_form_producao(request.form)
        if erro:
            conn.close()
            flash(erro, "danger")
            return render_template(
                'index.html',
                **_contexto_lancamento(
                    page_title="Editar Lançamento",
                    action_url=url_for('main.editar', id=id),
                    lancamento=_form_como_lancamento(request.form),
                ),
            )
        try:
            campos = montar_campos_producao(request.form)
            atualizar_producao(conn, campos, id)
            conn.commit()
            flash("Registro atualizado com sucesso.", "success")
        except Exception as e:
            flash(f"Erro ao atualizar registro: {e}", "danger")
        finally:
            conn.close()
        return redirect(url_for('main.historico'))
    # Busca o registro para edição
    lancamento = conn.execute("SELECT * FROM producao WHERE id = ?", (id,)).fetchone()
    conn.close()
    if lancamento is None:
        flash("Registro não encontrado.", "warning")
        return redirect(url_for('main.historico'))
    return render_template(
        'index.html',
        **_contexto_lancamento(
            page_title="Editar Lançamento",
            action_url=url_for('main.editar', id=id),
            lancamento=enrich_lancamento_observacoes(lancamento),
        ),
    )

# Rota para excluir um registro
@main_bp.route("/excluir/<int:id>", methods=["POST"])
def excluir(id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM producao WHERE id = ?", (id,))
        conn.commit()
        flash("Registro excluído com sucesso.", "success")
    except Exception as e:
        flash(f"Erro ao excluir registro: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for('main.historico'))
