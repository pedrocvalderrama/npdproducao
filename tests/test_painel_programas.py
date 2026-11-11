from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import painel_programas as painel


def processo(pid, pai=0, pasta=r'D:\dev npd\CRM NPD', entrada='app.py'):
    return dict(ProcessId=pid, ParentProcessId=pai, CreationDate='hoje',
                ExecutablePath=pasta + r'\.venv\Scripts\python.exe',
                CommandLine=f'"{pasta}\\.venv\\Scripts\\python.exe" {entrada}')


def test_status_reconhece_python_filho_do_venv_e_preserva_outra_porta():
    programa = painel.Programa('CRM', Path(r'D:\dev npd\CRM NPD'), 'run_local.bat', 8089, 'app.py')
    pai = processo(10)
    filho = processo(20, 10, r'C:\Python312')
    dados = dict(processos=[pai, filho], portas=[dict(LocalPort=8089, OwningProcess=20)])
    assert painel.status_programa(programa, dados) == ('Rodando', '20')
    dados['portas'][0]['OwningProcess'] = 99
    assert painel.status_programa(programa, dados)[0] == 'Porta ocupada por outro processo'
    dados['portas'] = []
    assert painel.status_programa(programa, dados)[0] == 'Iniciando / sem porta aberta'
    dados['processos'] = []
    assert painel.status_programa(programa, dados)[0] == 'Desligado'


def test_desligar_nao_mata_porta_de_outro_projeto():
    programa = painel.PROGRAMAS[1]
    dados = dict(processos=[], portas=[dict(LocalPort=8089, OwningProcess=999)])
    with patch.object(painel, 'inventario', return_value=dados), patch.object(painel.subprocess, 'run') as run:
        with pytest.raises(RuntimeError, match='outro processo'):
            painel.Controle().desligar(programa)
        run.assert_not_called()


def test_reiniciar_respeita_ordem_e_falha_ao_parar():
    controle = painel.Controle()
    controle.desligar = Mock(side_effect=RuntimeError('Sem permissão'))
    controle.iniciar = Mock()
    with pytest.raises(RuntimeError):
        controle.reiniciar(painel.PROGRAMAS[0])
    controle.iniciar.assert_not_called()


def test_rejeita_script_errado_e_caminho_com_prefixo_parecido():
    programa = painel.Programa('CRM', Path(r'D:\dev npd\CRM NPD'), 'run_local.bat', 8089, 'app.py')
    assert not painel.processo_do_programa(programa, processo(1, entrada='outra_tarefa.py'))
    assert not painel.processo_do_programa(programa, processo(1, pasta=r'D:\dev npd\CRM NPD copia'))


def test_iniciar_usa_bat_e_pasta_corretos_sem_duplicar(tmp_path):
    pasta = tmp_path / 'Projeto com espacos'
    pasta.mkdir()
    (pasta / 'run_local.bat').write_text('@echo off')
    programa = painel.Programa('CRM', pasta, 'run_local.bat', 8089, 'app.py')
    controle = painel.Controle()
    with patch.object(painel, 'inventario', return_value=dict(processos=[], portas=[])), \
            patch.object(painel, 'LOGS', tmp_path / 'logs'), \
            patch.object(painel.subprocess, 'Popen') as popen:
        popen.return_value.poll.return_value = None
        controle.iniciar(programa)
        assert popen.call_args.args[0] == f'cmd.exe /d /s /c ""{pasta / "run_local.bat"}""'
        assert popen.call_args.kwargs['cwd'] == pasta
        with pytest.raises(RuntimeError, match='ativo'):
            controle.iniciar(programa)
        popen.assert_called_once()
