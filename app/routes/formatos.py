"""Rotas de cadastro de formatos (gerente e admin)."""
from flask import Blueprint, flash, redirect, request, url_for
from flask_login import login_required

from ..auth import ROLE_ADMIN, ROLE_GERENTE, role_required
from ..config import PAPEIS
from ..services.formato_service import atualizar_formato, criar_formato

bp = Blueprint('formatos', __name__)


def _tolerancias_do_form():
    tolerancias = []
    for papel in PAPEIS:
        tolerancias.append({
            'papel': papel,
            'min_kg': request.form.get(f'tol_min[{papel}]', ''),
            'max_kg': request.form.get(f'tol_max[{papel}]', ''),
        })
    return tolerancias


def _tolerancias_mapa(formato):
    """Mapa papel -> {min_kg, max_kg} para preencher o form."""
    if not formato:
        return {}
    return {
        t['papel']: {'min_kg': t['min_kg'], 'max_kg': t['max_kg']}
        for t in formato.get('tolerancias') or []
    }


@bp.route('/configuracoes/formatos', methods=['GET', 'POST'])
@login_required
@role_required(ROLE_GERENTE, ROLE_ADMIN)
def configurar_formatos():
    if request.method == 'POST':
        descricao = request.form.get('descricao', '')
        largura = request.form.get('largura_bobina', '')
        velocidade = request.form.get('velocidade_ideal', '')
        formato_id = request.form.get('formato_id', '').strip()
        tolerancias = _tolerancias_do_form()

        if formato_id:
            try:
                fid = int(formato_id)
            except ValueError:
                flash('ID de formato inválido.', 'alert-danger')
                return redirect(url_for('auth.configuracoes'))
            ok, mensagem = atualizar_formato(fid, descricao, largura, velocidade, tolerancias)
        else:
            ok, mensagem = criar_formato(descricao, largura, velocidade, tolerancias)

        flash(mensagem, 'alert-success' if ok else 'alert-danger')
        if ok:
            return redirect(url_for('auth.configuracoes') + '#formatos')
        if formato_id:
            return redirect(url_for('auth.configuracoes', editar=formato_id) + '#formatos')
        return redirect(url_for('auth.configuracoes') + '#formatos')

    # GET legado: a tela oficial de formatos fica em /configuracoes
    editar = request.args.get('editar')
    if editar:
        return redirect(url_for('auth.configuracoes', editar=editar) + '#formatos')
    return redirect(url_for('auth.configuracoes') + '#formatos')
