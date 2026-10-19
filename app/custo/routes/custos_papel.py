"""
Blueprint para rotas de custos de papel
"""
from flask import Blueprint, render_template, request, redirect, url_for, Response, flash
from app.custo.services.custo_service import (
    criar_custo_papel,
    atualizar_custo_papel,
    excluir_custo_papel as excluir_custo_papel_service,
    obter_custo_papel_por_id,
    listar_custos_papel,
    listar_papeis_distintos,
    exportar_custos_config_csv
)
from app.custo.utils.formatters import obter_data_atual_iso

bp = Blueprint("custos_papel", __name__)


@bp.route("/configurar_custos", methods=["GET", "POST"])
def configurar_custos():
    """Lista e permite cadastrar novos custos de papel"""
    if request.method == "POST":
        papel = request.form.get("papel")
        custo_kg = request.form.get("custo_kg")
        data_registro = request.form.get("data_registro") or obter_data_atual_iso()

        if papel and custo_kg:
            if criar_custo_papel(papel, custo_kg, data_registro):
                flash("Custo de papel cadastrado com sucesso.", "alert-success")
            else:
                flash("Erro ao cadastrar custo de papel.", "alert-danger")
            return redirect(url_for('custos_papel.configurar_custos'))

    papeis = listar_papeis_distintos()
    hist = listar_custos_papel()
    data_atual = obter_data_atual_iso()

    return render_template("custos_papel/listar.html",
                         papeis=papeis,
                         hist=hist,
                         data_atual=data_atual)


@bp.route("/custos/papel/editar/<int:id>", methods=["GET", "POST"])
def editar_custo_papel(id):
    """Edita um custo de papel existente"""
    if request.method == "POST":
        papel = request.form.get("papel")
        custo_kg = request.form.get("custo_kg")
        data_registro = request.form.get("data_registro")

        if papel and custo_kg and data_registro:
            if atualizar_custo_papel(id, papel, custo_kg, data_registro):
                flash("Custo do papel atualizado com sucesso.", "alert-success")
                return redirect(url_for('custos_papel.configurar_custos'))
            else:
                flash("Erro ao atualizar custo de papel.", "alert-danger")
        else:
            flash("Preencha todos os campos.", "alert-warning")

    custo = obter_custo_papel_por_id(id)

    if not custo:
        flash("Registro não encontrado.", "alert-danger")
        return redirect(url_for('custos_papel.configurar_custos'))

    papeis = listar_papeis_distintos()
    return render_template("custos_papel/editar.html", custo=custo, papeis=papeis)


@bp.route("/custos/papel/excluir/<int:id>", methods=["POST"])
def excluir_custo_papel(id):
    """Exclui um custo de papel"""
    if excluir_custo_papel_service(id):
        flash("Registro de custo do papel excluído com sucesso.", "alert-danger")
    else:
        flash("Erro ao excluir registro.", "alert-danger")

    return redirect(url_for('custos_papel.configurar_custos'))


@bp.route("/exportar_custos_config")
def exportar_custos_config():
    """Exporta histórico de custos de papel para CSV"""
    csv_content = exportar_custos_config_csv()
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=historico_papel.csv"}
    )
