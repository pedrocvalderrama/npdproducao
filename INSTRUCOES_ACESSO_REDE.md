# Acesso à aplicação por outros computadores na rede

## 1. URL para outros PCs

Ao iniciar o servidor com `iniciar_servidor_dev.bat` ou `iniciar_servidor.bat`, o próprio script mostra o endereço para outros PCs, por exemplo:

- **http://192.168.1.100:8082**

(Substitua pelo IP que aparecer na tela. O IP desta máquina também pode ser visto com `ipconfig` no Prompt de Comando.)

## 2. Se outros computadores não conseguirem acessar: liberar no Firewall

O Windows pode estar bloqueando a porta **8082**. Libere assim:

1. Pressione **Win + R**, digite `wf.msc` e Enter (abre o Firewall do Windows com Segurança Avançada).
2. No menu à esquerda, clique em **Regras de Entrada**.
3. No menu à direita, clique em **Nova Regra...**.
4. Escolha **Porta** e Avançar.
5. Marque **TCP**, em "Portas locais específicas" digite **8082** e Avançar.
6. Marque **Permitir a conexão** e Avançar.
7. Deixe marcadas as três opções (Domínio, Particular, Público) e Avançar.
8. Nome: por exemplo **NPD Servidor porta 8082** e Concluir.

Depois disso, outros PCs na mesma rede devem conseguir acessar usando **http://[IP_DESTA_MAQUINA]:8082**.

## 3. Conferir se está na mesma rede

Os outros computadores precisam estar na **mesma rede** (mesmo Wi‑Fi ou mesma rede cabeada). Em redes diferentes ou com VPN, o acesso pode não funcionar.
