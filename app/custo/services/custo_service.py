"""
Serviços relacionados a custos (papel e operacional)
"""
import sqlite3
import sys
import os

# Garantir que o diretório raiz do projeto esteja no path
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # NPD
if _root not in sys.path:
    sys.path.insert(0, _root)

from database.connection import get_db


def obter_custos_papeis():
    """Obtém um dicionário com os custos mais recentes de cada papel."""
    conn = get_db()
    custos = {}
    try:
        rows = conn.execute("""
            SELECT cp.papel, cp.custo_kg FROM custo_papel cp
            INNER JOIN (
                SELECT papel, MAX(data_registro) as max_data
                FROM custo_papel GROUP BY papel
            ) AS latest ON cp.papel = latest.papel AND cp.data_registro = latest.max_data
        """).fetchall()
        custos = {row["papel"]: row["custo_kg"] for row in rows}
    except Exception:
        pass
    finally:
        conn.close()
    return custos


def obter_custo_operacional_por_despesa(despesa):
    """Obtém o custo unitário mais recente para uma despesa específica."""
    conn = get_db()
    custo = 0.0
    try:
        row = conn.execute("""
            SELECT t1.custo_unidade FROM custo_operacional t1
            INNER JOIN (
                SELECT despesa, MAX(data_registro) as max_data
                FROM custo_operacional WHERE despesa = ? GROUP BY despesa
            ) t2 ON t1.despesa = t2.despesa AND t1.data_registro = t2.max_data
        """, (despesa,)).fetchone()
        if row:
            custo = float(row['custo_unidade'] or 0)
    except Exception as e:
        print(f"Erro ao obter custo da despesa {despesa}: {e}")
    finally:
        conn.close()
    return custo


def obter_custo_operacional_atual():
    """Soma o custo unitário mais recente de todas as despesas cadastradas."""
    conn = get_db()
    total = 0.0
    try:
        rows = conn.execute("""
            SELECT t1.custo_unidade FROM custo_operacional t1
            INNER JOIN (
                SELECT despesa, MAX(data_registro) as max_data
                FROM custo_operacional GROUP BY despesa
            ) t2 ON t1.despesa = t2.despesa AND t1.data_registro = t2.max_data
        """).fetchall()
        for r in rows:
            total += float(r['custo_unidade'] or 0)
    except Exception:
        pass
    finally:
        conn.close()
    return total


def criar_custo_papel(papel, custo_kg, data_registro):
    """Cria um novo registro de custo de papel."""
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO custo_papel (papel, custo_kg, data_registro) VALUES (?, ?, ?)",
            (papel, float(custo_kg), data_registro)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao criar custo de papel: {e}")
        return False
    finally:
        conn.close()


def atualizar_custo_papel(id, papel, custo_kg, data_registro):
    """Atualiza um registro de custo de papel."""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE custo_papel SET papel=?, custo_kg=?, data_registro=? WHERE id=?",
            (papel, float(custo_kg), data_registro, id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao atualizar custo de papel: {e}")
        return False
    finally:
        conn.close()


def excluir_custo_papel(id):
    """Exclui um registro de custo de papel."""
    conn = get_db()
    try:
        conn.execute("DELETE FROM custo_papel WHERE id=?", (id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao excluir custo de papel: {e}")
        return False
    finally:
        conn.close()


def obter_custo_papel_por_id(id):
    """Obtém um registro de custo de papel por ID."""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM custo_papel WHERE id=?", (id,)).fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()


def listar_custos_papel():
    """Lista todos os registros de custo de papel ordenados."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, papel, custo_kg, data_registro FROM custo_papel ORDER BY papel, data_registro DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def listar_papeis_distintos():
    """Lista todos os tipos de papel distintos (cadastro oficial + produção + custo_papel)."""
    from ...config import PAPEIS

    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT DISTINCT papel FROM (
                SELECT papel FROM producao WHERE papel IS NOT NULL AND papel != ''
                UNION
                SELECT papel FROM custo_papel WHERE papel IS NOT NULL AND papel != ''
            ) ORDER BY papel
        """).fetchall()
        papeis_db = {row["papel"] for row in rows}
    except sqlite3.OperationalError:
        papeis_db = set()
    finally:
        conn.close()

    return [{"papel": p} for p in sorted(set(PAPEIS) | papeis_db)]


def criar_custo_operacional(despesa, custo_unidade, data_registro):
    """Cria um novo registro de custo operacional."""
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO custo_operacional (despesa, custo_unidade, data_registro) VALUES (?, ?, ?)",
            (despesa, float(custo_unidade), data_registro)
        )
        conn.commit()
        return True
    except ValueError:
        return False
    except Exception as e:
        print(f"Erro ao criar custo operacional: {e}")
        return False
    finally:
        conn.close()


def atualizar_custo_operacional(id, despesa, custo_unidade, data_registro):
    """Atualiza um registro de custo operacional."""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE custo_operacional SET despesa=?, custo_unidade=?, data_registro=? WHERE id=?",
            (despesa, float(custo_unidade), data_registro, id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao atualizar custo operacional: {e}")
        return False
    finally:
        conn.close()


def excluir_custo_operacional(id):
    """Exclui um registro de custo operacional."""
    conn = get_db()
    try:
        conn.execute("DELETE FROM custo_operacional WHERE id=?", (id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao excluir custo operacional: {e}")
        return False
    finally:
        conn.close()


def obter_custo_operacional_por_id(id):
    """Obtém um registro de custo operacional por ID."""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM custo_operacional WHERE id=?", (id,)).fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()


def listar_custos_operacionais():
    """Lista todos os registros de custo operacional ordenados."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, despesa, custo_unidade, data_registro FROM custo_operacional ORDER BY data_registro DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def listar_despesas_distintas():
    """Lista todas as despesas distintas cadastradas."""
    conn = get_db()
    try:
        rows = conn.execute("SELECT DISTINCT despesa FROM custo_operacional").fetchall()
        return [row['despesa'] for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def renomear_despesa_operacional(antiga, nova):
    """Renomeia todos os registros de uma despesa para o novo nome."""
    if not antiga or not nova or antiga == nova:
        return False
    conn = get_db()
    try:
        conn.execute(
            "UPDATE custo_operacional SET despesa=? WHERE despesa=?",
            (nova, antiga)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Erro ao renomear despesa operacional {antiga} -> {nova}: {e}")
        return False
    finally:
        conn.close()


def obter_custo_alca_natural():
    """Custo unitário da alça natural (com fallback do nome legado ALÇA)."""
    custo = obter_custo_operacional_por_despesa("ALÇA NATURAL")
    if custo:
        return custo
    return obter_custo_operacional_por_despesa("ALÇA")


def obter_custo_alca_branca():
    """Custo unitário da alça branca."""
    return obter_custo_operacional_por_despesa("ALÇA BRANCA")


def is_papel_branco(papel):
    """Indica se o papel usa alça branca (sacolas brancas)."""
    p = (papel or "").strip().upper()
    return p in ("BRANCO 110G", "BRANCO 110GRS", "BRANCO 90GRS", "BRANCO 80GRS")


def exportar_custos_config_csv():
    """Exporta histórico de custos de papel para CSV."""
    import csv
    import io
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT papel, custo_kg, data_registro FROM custo_papel ORDER BY papel, data_registro DESC"
        ).fetchall()
        out = io.StringIO()
        w = csv.writer(out, delimiter=';')
        w.writerow(['Papel', 'Custo_Kg', 'Vigencia'])
        for r in rows:
            w.writerow([r[0], f"{r[1]:.2f}", r[2]])
        return out.getvalue()
    finally:
        conn.close()
