"""Painel Windows independente dos servidores; usa somente a biblioteca padrão."""
import json
import ntpath
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk
import webbrowser
from dataclasses import dataclass


BASE = Path(__file__).resolve().parent
LOGS = BASE / 'logs' / 'painel'


@dataclass(frozen=True)
class Programa:
    nome: str
    pasta: Path
    script: str
    porta: int
    entrada: str


PROGRAMAS = (
    Programa('Produção NPD', BASE, 'iniciar_servidor.bat', 8082, 'wsgi.py'),
    Programa('CRM NPD', BASE.parent / 'CRM NPD', 'run_local.bat', 8089, 'app.py'),
)


def powershell(comando):
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', comando],
        capture_output=True, encoding='utf-8', errors='replace', timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Falha ao consultar processos do Windows.')
    return result.stdout


def inventario():
    # Não lê arquivos .env nem expõe linhas de comando na interface ou nos logs.
    return json.loads(powershell('''
        $ErrorActionPreference = 'Stop'
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        $processos = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId, ExecutablePath, CommandLine, CreationDate)
        $portas = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Select-Object LocalPort, OwningProcess)
        @{processos=$processos; portas=$portas} | ConvertTo-Json -Depth 4 -Compress
    '''))


def processo_do_programa(programa, processo):
    """Exige Python do projeto e o arquivo de entrada correto para reconhecer um servidor."""
    comando = (processo.get('CommandLine') or '').replace('/', '\\').lower()
    executavel = (processo.get('ExecutablePath') or '').replace('/', '\\').lower()
    if ntpath.basename(executavel) not in ('python.exe', 'pythonw.exe'):
        return False
    pasta = str(programa.pasta).replace('/', '\\').lower().rstrip('\\') + '\\'
    entrada = programa.entrada.lower()
    arquivo = re.search(r'(?:^|[\s"\\])' + re.escape(entrada) + r'(?=$|[\s"])', comando)
    return bool(arquivo and (executavel.startswith(pasta) or pasta + entrada in comando))


def servidores(programa, dados):
    return [p for p in dados['processos'] if processo_do_programa(programa, p)]


def status_programa(programa, dados):
    processos = servidores(programa, dados)
    pids = {p['ProcessId'] for p in processos}
    # O Python do venv no Windows pode delegar ao executável Python global.
    while True:
        filhos = {p['ProcessId'] for p in dados['processos'] if p['ParentProcessId'] in pids}
        if filhos.issubset(pids):
            break
        pids.update(filhos)
    donos = {p['OwningProcess'] for p in dados['portas'] if p['LocalPort'] == programa.porta}
    if donos & pids:
        return 'Rodando', ', '.join(map(str, sorted(donos & pids)))
    if donos:
        return 'Porta ocupada por outro processo', ''
    if processos:
        return 'Iniciando / sem porta aberta', ', '.join(map(str, sorted(pids)))
    return 'Desligado', ''


class Controle:
    def __init__(self):
        self.lancadores = {}

    def iniciar(self, programa):
        dados = inventario()
        atual, _ = status_programa(programa, dados)
        launcher = self.lancadores.get(programa.nome)
        if atual != 'Desligado' or (launcher and launcher.poll() is None):
            raise RuntimeError('O programa já está ativo/iniciando ou a porta está ocupada.')
        script = programa.pasta / programa.script
        if not script.is_file():
            raise RuntimeError(f'Script não encontrado: {script}')
        LOGS.mkdir(parents=True, exist_ok=True)
        with (LOGS / f'{programa.porta}.log').open('ab') as log:
            # Executa o .bat solicitado com a pasta de trabalho correta e sem janela extra.
            launcher = subprocess.Popen(
                f'cmd.exe /d /s /c ""{script}""',
                cwd=programa.pasta, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        self.lancadores[programa.nome] = launcher

    def desligar(self, programa):
        dados = inventario()
        processos = servidores(programa, dados)
        # Mata apenas servidores reconhecidos deste projeto e seus filhos.
        # Nunca encerra um processo apenas porque ele ocupa a porta configurada.
        for processo in processos:
            atuais = inventario()['processos']
            if not any(
                p['ProcessId'] == processo['ProcessId']
                and p['CreationDate'] == processo['CreationDate']
                and processo_do_programa(programa, p) for p in atuais
            ):
                continue
            resultado = subprocess.run(
                ['taskkill.exe', '/PID', str(processo['ProcessId']), '/T', '/F'],
                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if resultado.returncode and servidores(programa, inventario()):
                raise RuntimeError('Não foi possível desligar. Verifique as permissões do Windows.')
        launcher = self.lancadores.get(programa.nome)
        if launcher and launcher.poll() is None:
            subprocess.run(
                ['taskkill.exe', '/PID', str(launcher.pid), '/T', '/F'],
                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, check=True,
            )
        self.lancadores.pop(programa.nome, None)
        limite = time.monotonic() + 15
        while True:
            atual, _ = status_programa(programa, inventario())
            if atual == 'Desligado':
                return
            if atual == 'Porta ocupada por outro processo':
                raise RuntimeError('A porta pertence a outro processo; ele foi preservado.')
            if time.monotonic() >= limite:
                raise RuntimeError('O servidor continua ativo. Pode estar sendo reiniciado por um serviço Windows.')
            time.sleep(0.5)

    def reiniciar(self, programa):
        self.desligar(programa)
        self.iniciar(programa)


class Painel:
    def __init__(self, root):
        self.root = root
        self.controle = Controle()
        self.consultando = False
        self.operando = set()
        self.linhas = {}
        root.title('NPD · Painel dos programas')
        root.geometry('850x570')
        root.minsize(800, 540)
        estilo = ttk.Style()
        estilo.theme_use('clam')
        estilo.configure('TFrame', background='#f2f5fa')
        estilo.configure('TLabel', background='#f2f5fa', foreground='#172b45', font=('Segoe UI', 10))
        estilo.configure('Title.TLabel', font=('Segoe UI', 22, 'bold'))
        estilo.configure('Name.TLabel', font=('Segoe UI', 15, 'bold'))
        estilo.configure('TButton', font=('Segoe UI', 10), padding=(12, 8))
        container = ttk.Frame(root, padding=25)
        container.pack(fill='both', expand=True)
        ttk.Label(container, text='Painel dos programas', style='Title.TLabel').pack(anchor='w')
        ttk.Label(container, text='Status neste computador · atualização automática a cada 5 segundos').pack(anchor='w', pady=(4, 18))
        for programa in PROGRAMAS:
            card = ttk.Frame(container, padding=15, relief='solid', borderwidth=1)
            card.pack(fill='x', pady=(0, 12))
            ttk.Label(card, text=programa.nome, style='Name.TLabel').pack(anchor='w')
            status = ttk.Label(card, text='Consultando…')
            status.pack(anchor='w', pady=6)
            ttk.Label(card, text=f'{programa.script} · porta {programa.porta}').pack(anchor='w')
            botoes = ttk.Frame(card)
            botoes.pack(anchor='w', pady=(10, 0))
            controles = []
            for nome, acao in [('Ligar', 'iniciar'), ('Desligar', 'desligar'), ('Reiniciar', 'reiniciar')]:
                botao = ttk.Button(botoes, text=nome, command=lambda p=programa, a=acao: self.acao(p, a))
                botao.pack(side='left', padx=(0, 8))
                controles.append(botao)
            ttk.Button(botoes, text='Abrir programa', command=lambda p=programa: webbrowser.open(f'http://127.0.0.1:{p.porta}')).pack(side='left', padx=(0, 8))
            ttk.Button(botoes, text='Ver log', command=lambda p=programa: self.ver_log(p)).pack(side='left')
            self.linhas[programa.nome] = (status, controles)
        self.mensagem = ttk.Label(container, text='Fechar o painel mantém os programas no estado atual.', wraplength=780)
        self.mensagem.pack(anchor='w', pady=5)
        self.atualizar()

    def ver_log(self, programa):
        arquivo = LOGS / f'{programa.porta}.log'
        if arquivo.exists():
            os.startfile(arquivo)
        else:
            self.mensagem.config(text='O log será criado quando este programa for ligado pelo painel.')

    def atualizar(self):
        if not self.consultando:
            self.consultando = True
            threading.Thread(target=self.consultar, daemon=True).start()
        self.root.after(5000, self.atualizar)

    def consultar(self):
        try:
            dados = inventario()
            resultados = {p.nome: status_programa(p, dados) for p in PROGRAMAS}
            self.root.after(0, lambda: self.mostrar_status(resultados))
        except Exception as exc:
            self.root.after(0, lambda erro=str(exc): self.mostrar_erro(erro))

    def mostrar_status(self, resultados):
        self.consultando = False
        for nome, (status, pid) in resultados.items():
            if nome not in self.operando:
                launcher = self.controle.lancadores.get(nome)
                if status == 'Desligado' and launcher and launcher.poll() is None:
                    status = 'Iniciando / preparando ambiente'
                self.linhas[nome][0].config(text=status + (f' · PID {pid}' if pid else ''))

    def mostrar_erro(self, erro):
        self.consultando = False
        for nome, (label, _) in self.linhas.items():
            if nome not in self.operando:
                label.config(text='Status indisponível')
        self.mensagem.config(text=erro)

    def acao(self, programa, acao):
        if programa.nome in self.operando:
            return
        self.operando.add(programa.nome)
        label, botoes = self.linhas[programa.nome]
        label.config(text={'iniciar': 'Ligando…', 'desligar': 'Desligando…', 'reiniciar': 'Reiniciando…'}[acao])
        for botao in botoes:
            botao.config(state='disabled')
        def executar():
            try:
                getattr(self.controle, acao)(programa)
                mensagem = f'{programa.nome}: comando concluído. Aguarde a atualização do status.'
            except Exception as exc:
                mensagem = f'{programa.nome}: {exc}'
            self.root.after(0, lambda: self.finalizar(programa, mensagem))
        threading.Thread(target=executar, daemon=True).start()

    def finalizar(self, programa, mensagem):
        self.operando.discard(programa.nome)
        self.mensagem.config(text=mensagem)
        for botao in self.linhas[programa.nome][1]:
            botao.config(state='normal')
        if not self.consultando:
            self.consultando = True
            threading.Thread(target=self.consultar, daemon=True).start()


if __name__ == '__main__':
    root = tk.Tk()
    Painel(root)
    root.mainloop()
