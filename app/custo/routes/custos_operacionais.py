"""
Blueprint para rotas de custos operacionais
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.custo.services.custo_service import (
    criar_custo_operacional,
    atualizar_custo_operacional,
    excluir_custo_operacional as excluir_custo_operacional_service,
    obter_custo_operacional_por_id,
    listar_custos_operacionais,
    listar_despesas_distintas,
    renomear_despesa_operacional,
)
from app.custo.utils.formatters import obter_data_atual_iso

# Despesas padrão para custos operacionais
DESPESAS_PADRAO = ["TINTA", "COLA", "MÃO DE OBRA ALÇA", "ALÇA NATURAL", "ALÇA BRANCA", "VERNIZ"]

bp = Blueprint("custos_operacionais", __name__)


@bp.route("/configurar_custo_operacional", methods=["GET", "POST"])
def configurar_custo_operacional():
    """Lista e permite cadastrar novos custos operacionais"""
    # Migra o nome antigo "ALÇA" para "ALÇA NATURAL"
    renomear_despesa_operacional("ALÇA", "ALÇA NATURAL")

    if request.method == "POST":
        despesa = request.form.get("despesa")
        custo_unidade = request.form.get("custo_unidade")
        data_registro = obter_data_atual_iso()

        if despesa and custo_unidade:
            try:
                if criar_custo_operacional(despesa, custo_unidade, data_registro):
                    flash("Custo operacional cadastrado com sucesso.", "alert-success")
                else:
                    flash("Custo unitário inválido.", "alert-danger")
            except ValueError:
                flash("Custo unitário inválido.", "alert-danger")
            return redirect(url_for('custos_operacionais.configurar_custo_operacional'))

    existentes = listar_despesas_distintas()
    todas_despesas = sorted(list(set(existentes + DESPESAS_PADRAO)))
    hist = listar_custos_operacionais()

    return render_template("custos_operacionais/listar.html",
                         todas_despesas=todas_despesas,
                         hist=hist)


@bp.route("/custos/operacional/editar/<int:id>", methods=["GET", "POST"])
def editar_custo_operacional(id):
    """Edita um custo operacional existente"""
    if request.method == "POST":
        despesa = request.form.get("despesa")
        custo_unidade = request.form.get("custo_unidade")
        data_registro = request.form.get("data_registro")

        if despesa and custo_unidade and data_registro:
            if atualizar_custo_operacional(id, despesa, custo_unidade, data_registro):
                flash("Custo operacional atualizado com sucesso.", "alert-success")
                return redirect(url_for('custos_operacionais.configurar_custo_operacional'))
            else:
                flash("Erro ao atualizar custo operacional.", "alert-danger")
        else:
            flash("Preencha todos os campos.", "alert-warning")

    custo = obter_custo_operacional_por_id(id)

    if not custo:
        flash("Registro não encontrado.", "alert-danger")
        return redirect(url_for('custos_operacionais.configurar_custo_operacional'))

    return render_template("custos_operacionais/editar.html", custo=custo)


@bp.route("/custos/operacional/excluir/<int:id>", methods=["POST"])
def excluir_custo_operacional(id):
    """Exclui um custo operacional"""
    if excluir_custo_operacional_service(id):
        flash("Registro de custo operacional excluído com sucesso.", "alert-danger")
    else:
        flash("Erro ao excluir registro.", "alert-danger")

    return redirect(url_for('custos_operacionais.configurar_custo_operacional'))
