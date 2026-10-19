"""
Blueprint para rotas de relatórios de custo
"""
from flask import Blueprint, render_template, request, Response, jsonify
from app.custo.services.relatorio_service import obter_dados_relatorio, exportar_custo_csv
from app.custo.services.custo_service import (
    obter_custos_papeis,
    obter_custo_operacional_por_despesa,
    obter_custo_alca_natural,
    obter_custo_alca_branca,
    renomear_despesa_operacional,
)

bp = Blueprint("relatorio", __name__)


@bp.route("/custo", methods=["GET"])
def lancamento_custo():
    """Tela de lançamento/simulação de custo por OF."""
    renomear_despesa_operacional("ALÇA", "ALÇA NATURAL")
    custos_papel = obter_custos_papeis()
    papeis = sorted(custos_papel.keys())
    custos_op = {
        "cola": obter_custo_operacional_por_despesa("COLA"),
        "alca_natural": obter_custo_alca_natural(),
        "alca_branca": obter_custo_alca_branca(),
        "alca": obter_custo_alca_natural(),  # compatibilidade / valor inicial
        "mdo_alca": obter_custo_operacional_por_despesa("MÃO DE OBRA ALÇA"),
        "tinta": obter_custo_operacional_por_despesa("TINTA"),
    }
    return render_template(
        "relatorio/lancamento_custo.html",
        papeis=papeis,
        custos_papel=custos_papel,
        custos_op=custos_op,
    )


@bp.route("/custo/buscar_pedidos")
def buscar_pedidos_custo():
    """Busca pedidos pelo número para lançamento de custo."""
    from app.pedidos import buscar_pedidos_por_numero

    pedido = request.args.get('pedido', '').strip()
    if not pedido:
        return jsonify({'erro': 'Informe o número do pedido.'}), 400
    return jsonify(buscar_pedidos_por_numero(pedido))


@bp.route("/custo/lancar", methods=["POST"])
def lancar_custo_movimento():
    """Grava custo manual em uma linha de pedido."""
    from app.pedidos import lancar_custo_pedido

    data = request.get_json(silent=True) or request.form
    pedido_id = data.get('pedido_id')
    custo = data.get('custo')

    if not pedido_id:
        return jsonify({'ok': False, 'mensagem': 'Pedido inválido.'}), 400
    if custo is None or str(custo).strip() == '':
        return jsonify({'ok': False, 'mensagem': 'Informe o valor do custo.'}), 400

    if lancar_custo_pedido(pedido_id, custo):
        return jsonify({'ok': True, 'mensagem': 'Custo lançado com sucesso.'})

    return jsonify({'ok': False, 'mensagem': 'Não foi possível lançar o custo.'}), 400


@bp.route("/custo/historico_custos", methods=["GET"])
def historico_custos():
    """Relatório histórico de custos de produção."""
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    servico = request.args.get("servico")
    num_of = request.args.get("num_of")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    dados, custo_op_un = obter_dados_relatorio(data_inicio, data_fim, servico, num_of, start_date, end_date)

    return render_template("relatorio/index.html",
                         dados=dados,
                         custo_op_un=custo_op_un,
                         ini=(data_inicio or ''),
                         fim=(data_fim or ''))


@bp.route("/exportar_custo")
def exportar_custo():
    """Exporta relatório de custos para CSV"""
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    servico = request.args.get("servico")
    num_of = request.args.get("num_of")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    csv_content = exportar_custo_csv(data_inicio, data_fim, servico, num_of, start_date, end_date)

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=custo_producao.csv"}
    )
