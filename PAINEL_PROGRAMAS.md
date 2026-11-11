# Painel dos programas NPD

No computador em que os dois programas rodam, abra `abrir_painel.bat`.
O painel é independente: pode ligar os servidores mesmo quando ambos estão desligados.
Fechar o painel não desliga os programas.

- Produção: executa `iniciar_servidor.bat` nesta pasta; porta 8082.
- CRM NPD: executa `run_local.bat` na pasta `CRM NPD`, ao lado desta pasta; porta 8089.
- Ligar, Desligar e Reiniciar atuam somente no programa escolhido.
- Abrir programa abre o endereço local no navegador.
- Ver log abre a saída do script iniciado pelo painel, em `logs/painel/`.

O status Rodando indica que o processo Python reconhecido do projeto está escutando na porta esperada.
Durante a preparação do ambiente, a indicação é Iniciando.
Uma porta ocupada por outro processo é sinalizada e seu processo não é encerrado.
O painel também reconhece servidores iniciados fora dele usando o Python do ambiente virtual do projeto.

Desligar encerra o processo do servidor e seus filhos. Finalize operações em andamento antes de usar.
Servidores instalados como serviço Windows devem ser controlados pelo serviço, pois podem reiniciar automaticamente.
O painel controla programas neste computador, não em outro servidor da rede.

Para outra estrutura de pastas ou portas, ajuste `PROGRAMAS` em `painel_programas.py`.
O painel não precisa de pacotes adicionais; utiliza Python com Tkinter e PowerShell do Windows.
