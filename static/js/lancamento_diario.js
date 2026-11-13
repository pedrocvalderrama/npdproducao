document.addEventListener('DOMContentLoaded', () => {
  const formato = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 6 });
  document.querySelectorAll('.maquina-diario').forEach(maquina => {
    const linhas = Array.from(maquina.querySelectorAll('.producao-diario'));
    const adicionar = maquina.querySelector('.adicionar-producao');
    adicionar.addEventListener('click', () => {
      const proxima = linhas.find(linha => linha.hidden);
      if (proxima) proxima.hidden = false;
      const visiveis = linhas.filter(linha => !linha.hidden).length;
      maquina.querySelector('.contador-producoes').textContent = `${visiveis} de 10 espaços`;
      adicionar.disabled = visiveis >= 10;
    });
    function atualizarTotais() {
      const totais = { quantidade: 0, quantidade_alcas: 0, peso_diario: 0, refugo_diario: 0 };
      const alcasDia = maquina.querySelector('[data-alcas-dia]');
      if (alcasDia) {
        const valor = Number(alcasDia.value);
        if (Number.isFinite(valor) && valor >= 0) totais.quantidade_alcas = valor;
      }
      maquina.querySelectorAll('[data-campo]').forEach(campo => {
        const valor = Number(campo.value.trim().replace(',', '.'));
        if (!Number.isFinite(valor) || valor < 0) return;
        const nome = campo.dataset.campo;
        if (nome === 'milheiro') return;
        const destino = nome === 'refugo_sos' || nome === 'refugo_impressora' ? 'refugo_diario' : nome;
        totais[destino] += valor;
      });
      linhas.forEach(linha => {
        const milheiro = linha.querySelector('[data-campo="milheiro"]');
        if (!milheiro) return;
        const quantidade = Number(linha.querySelector('[data-campo="quantidade"]').value || 0);
        const valor = Number(milheiro.value.trim().replace(',', '.'));
        const saida = linha.querySelector('[data-peso-producao]');
        let peso = null;
        if (milheiro.value.trim() && Number.isFinite(valor) && valor >= 0 && Number.isFinite(quantidade) && quantidade >= 0) {
          peso = quantidade / 1000 * valor;
        } else if (!milheiro.value.trim() && saida.dataset.pesoLegado !== '') {
          peso = Number(saida.dataset.pesoLegado);
        }
        saida.textContent = peso !== null && Number.isFinite(peso) ? formato.format(peso) : '—';
        if (peso !== null && Number.isFinite(peso)) totais.peso_diario += peso;
      });
      maquina.querySelectorAll('[data-total]').forEach(saida => {
        saida.textContent = formato.format(totais[saida.dataset.total]);
      });
    }
    maquina.addEventListener('input', atualizarTotais);
    atualizarTotais();
  });
  document.getElementById('form-diario').addEventListener('invalid', evento => {
    const maquina = evento.target.closest('.maquina-diario');
    if (maquina) maquina.open = true;
  }, true);
});
