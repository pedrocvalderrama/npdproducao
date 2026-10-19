"""Cadastro de formatos — fonte única no banco (formatos_cadastro / formato_tolerancias)."""
import re

from ..config import PAPEIS
from ..models import get_db_connection


def normalizar_descricao(descricao):
    """Normaliza string canônica: maiúsculas, X como separador, vírgula decimal."""
    s = (descricao or '').strip().upper().replace('.', ',')
    s = re.sub(r'\s+', '', s)
    s = s.replace('*', 'X').replace('×', 'X')
    return s


def _rows_cadastro(conn=None):
    close = False
    if conn is None:
        conn = get_db_connection()
        close = True
    try:
        return conn.execute(
            "SELECT id, descricao, largura_bobina, velocidade_ideal, criado_em "
            "FROM formatos_cadastro ORDER BY descricao"
        ).fetchall()
    finally:
        if close:
            conn.close()


def _tolerancias_por_formato(conn, formato_id):
    rows = conn.execute(
        "SELECT papel, min_kg, max_kg FROM formato_tolerancias WHERE formato_id = ? ORDER BY papel",
        (formato_id,),
    ).fetchall()
    return [
        {'papel': r['papel'], 'min_kg': r['min_kg'], 'max_kg': r['max_kg']}
        for r in rows
    ]


def listar_formatos_cadastro():
    conn = get_db_connection()
    try:
        itens = []
        for row in _rows_cadastro(conn):
            itens.append({
                'id': row['id'],
                'descricao': row['descricao'],
                'largura_bobina': row['largura_bobina'],
                'velocidade_ideal': row['velocidade_ideal'],
                'criado_em': row['criado_em'],
                'tolerancias': _tolerancias_por_formato(conn, row['id']),
            })
        return itens
    finally:
        conn.close()


def descricao_ja_existe(descricao, excluir_id=None):
    desc = normalizar_descricao(descricao)
    conn = get_db_connection()
    try:
        if excluir_id is not None:
            row = conn.execute(
                "SELECT 1 FROM formatos_cadastro WHERE descricao = ? AND id != ?",
                (desc, excluir_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT 1 FROM formatos_cadastro WHERE descricao = ?", (desc,)
            ).fetchone()
        return row is not None
    finally:
        conn.close()


def obter_formato_por_id(formato_id):
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id, descricao, largura_bobina, velocidade_ideal, criado_em "
            "FROM formatos_cadastro WHERE id = ?",
            (formato_id,),
        ).fetchone()
        if not row:
            return None
        return {
            'id': row['id'],
            'descricao': row['descricao'],
            'largura_bobina': row['largura_bobina'],
            'velocidade_ideal': row['velocidade_ideal'],
            'criado_em': row['criado_em'],
            'tolerancias': _tolerancias_por_formato(conn, row['id']),
        }
    finally:
        conn.close()


def _validar_campos_formato(descricao, largura_bobina, velocidade_ideal, tolerancias, excluir_id=None):
    """Retorna (ok, mensagem, desc, largura, velocidade, tol_validas)."""
    desc = normalizar_descricao(descricao)
    if not desc:
        return False, "Descrição do formato é obrigatória.", None, None, None, None
    try:
        largura = float(largura_bobina)
        velocidade = float(velocidade_ideal)
    except (TypeError, ValueError):
        return False, "Largura da bobina e velocidade ideal devem ser números.", None, None, None, None
    if largura <= 0:
        return False, "Largura da bobina deve ser maior que zero.", None, None, None, None
    if velocidade <= 0:
        return False, "Velocidade ideal deve ser maior que zero.", None, None, None, None
    if descricao_ja_existe(desc, excluir_id=excluir_id):
        return False, f"O formato '{desc}' já existe.", None, None, None, None

    tol_validas = []
    for t in tolerancias or []:
        papel = (t.get('papel') or '').strip()
        if papel not in PAPEIS:
            return False, f"Papel inválido: {papel}.", None, None, None, None
        min_raw = t.get('min_kg')
        max_raw = t.get('max_kg')
        min_vazio = min_raw is None or str(min_raw).strip() == ''
        max_vazio = max_raw is None or str(max_raw).strip() == ''
        if min_vazio and max_vazio:
            continue
        if min_vazio or max_vazio:
            return False, f"Para {papel}, preencha mínimo e máximo (ou deixe ambos em branco).", None, None, None, None
        try:
            min_kg = float(str(min_raw).replace(',', '.'))
            max_kg = float(str(max_raw).replace(',', '.'))
        except (TypeError, ValueError):
            return False, f"Tolerância inválida para {papel}.", None, None, None, None
        if min_kg > max_kg:
            return False, f"Para {papel}, o mínimo não pode ser maior que o máximo.", None, None, None, None
        tol_validas.append({'papel': papel, 'min_kg': min_kg, 'max_kg': max_kg})
    return True, '', desc, largura, velocidade, tol_validas


def criar_formato(descricao, largura_bobina, velocidade_ideal, tolerancias):
    """
    Cria formato no banco.
    tolerancias: lista de dicts {papel, min_kg, max_kg} (só papéis preenchidos).
    Retorna (ok: bool, mensagem: str).
    """
    ok, mensagem, desc, largura, velocidade, tol_validas = _validar_campos_formato(
        descricao, largura_bobina, velocidade_ideal, tolerancias
    )
    if not ok:
        return False, mensagem

    conn = get_db_connection()
    try:
        cur = conn.execute(
            "INSERT INTO formatos_cadastro (descricao, largura_bobina, velocidade_ideal) VALUES (?, ?, ?)",
            (desc, largura, velocidade),
        )
        formato_id = cur.lastrowid
        for t in tol_validas:
            conn.execute(
                "INSERT INTO formato_tolerancias (formato_id, papel, min_kg, max_kg) VALUES (?, ?, ?, ?)",
                (formato_id, t['papel'], t['min_kg'], t['max_kg']),
            )
        conn.commit()
        return True, f"Formato '{desc}' cadastrado com sucesso."
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao cadastrar formato: {e}"
    finally:
        conn.close()


def atualizar_formato(formato_id, descricao, largura_bobina, velocidade_ideal, tolerancias):
    """Atualiza formato e substitui as tolerâncias. Retorna (ok, mensagem)."""
    existente = obter_formato_por_id(formato_id)
    if not existente:
        return False, "Formato não encontrado."

    ok, mensagem, desc, largura, velocidade, tol_validas = _validar_campos_formato(
        descricao, largura_bobina, velocidade_ideal, tolerancias, excluir_id=formato_id
    )
    if not ok:
        return False, mensagem

    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE formatos_cadastro SET descricao = ?, largura_bobina = ?, velocidade_ideal = ? WHERE id = ?",
            (desc, largura, velocidade, formato_id),
        )
        conn.execute("DELETE FROM formato_tolerancias WHERE formato_id = ?", (formato_id,))
        for t in tol_validas:
            conn.execute(
                "INSERT INTO formato_tolerancias (formato_id, papel, min_kg, max_kg) VALUES (?, ?, ?, ?)",
                (formato_id, t['papel'], t['min_kg'], t['max_kg']),
            )
        conn.commit()
        return True, f"Formato '{desc}' atualizado com sucesso."
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao atualizar formato: {e}"
    finally:
        conn.close()


def obter_formatos():
    """Lista de descrições cadastradas (fonte única: banco)."""
    return [row['descricao'] for row in _rows_cadastro()]


def obter_ideal_speed_rates():
    return {row['descricao']: float(row['velocidade_ideal']) for row in _rows_cadastro()}


def obter_formato_to_largura():
    """Mapa descricao canônica → largura_bobina (cm) do cadastro na tela de formatos."""
    return {
        normalizar_descricao(row['descricao']): float(row['largura_bobina'])
        for row in _rows_cadastro()
    }


def obter_weight_tolerances():
    """Tolerâncias do banco + aliases de papel."""
    resultado = {}
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT f.descricao, t.papel, t.min_kg, t.max_kg
            FROM formato_tolerancias t
            JOIN formatos_cadastro f ON f.id = t.formato_id
            """
        ).fetchall()
        for r in rows:
            papel = r['papel']
            if papel not in resultado:
                resultado[papel] = {}
            resultado[papel][r['descricao']] = {'min': float(r['min_kg']), 'max': float(r['max_kg'])}
    finally:
        conn.close()

    for alias, fonte in (
        ('COLLEY 100G', 'BAG 100GRS'),
        ('ECO 70GRS', 'BAG 70GRS'),
        ('MONOL 70GR', 'BAG 70GRS'),
        ('BRANCO 90GRS', 'BAG 80GRS'),
        ('BRANCO 80GRS', 'BAG 80GRS'),
    ):
        mesclado = dict(resultado.get(fonte, {}))
        mesclado.update(resultado.get(alias, {}))
        resultado[alias] = mesclado
    return resultado
