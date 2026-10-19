// Gráfico Comparativo Mensal renderizado no navegador com Chart.js.
// Substitui a geração de imagem PNG no servidor via matplotlib (Fase 4 da
// auditoria de otimização): os dados vêm prontos em JSON (embutidos no HTML
// pelo backend) e todo o desenho acontece no cliente, sem custo de CPU/RAM
// no servidor a cada requisição.
(function () {
  var dataEl = document.getElementById('chart-data');
  var canvas = document.getElementById('comparativo-mensal-chart');
  if (!dataEl || !canvas || typeof Chart === 'undefined') {
    return;
  }

  var dados = JSON.parse(dataEl.textContent);

  Chart.defaults.color = '#ecf0f1';
  Chart.defaults.borderColor = 'rgba(236, 240, 241, 0.2)';

  new Chart(canvas.getContext('2d'), {
    data: {
      labels: dados.meses,
      datasets: [
        {
          type: 'bar',
          label: 'Quantidade Produzida',
          data: dados.quantidades,
          backgroundColor: 'rgba(52, 152, 219, 0.9)',
          borderColor: '#2980b9',
          borderWidth: 1,
          yAxisID: 'yQuantidade',
          order: 2,
        },
        {
          type: 'line',
          label: 'Média de PERCENTUAL REFUGO SOS',
          data: dados.pct_refugo_sos,
          borderColor: '#ff8c00',
          backgroundColor: '#ff8c00',
          pointBackgroundColor: '#ff8c00',
          pointBorderColor: '#fff',
          pointRadius: 4,
          borderWidth: 2.5,
          spanGaps: true,
          tension: 0,
          yAxisID: 'yPercentual',
          order: 1,
        },
        {
          type: 'line',
          label: "Média de % Refugo SOS + Refugo Flexográfica versus Produção das SOS's",
          data: dados.pct_refugo_sos_flexo,
          borderColor: '#bdc3c7',
          backgroundColor: '#bdc3c7',
          pointBackgroundColor: '#bdc3c7',
          pointBorderColor: '#fff',
          pointRadius: 4,
          borderWidth: 2.5,
          spanGaps: true,
          tension: 0,
          yAxisID: 'yPercentual',
          order: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        title: {
          display: true,
          text: 'Quantidade Produzida e Porcentagem de Refugo',
          color: '#fff',
          font: { size: 16, weight: 'bold' },
          padding: { bottom: 16 },
        },
        legend: {
          position: 'bottom',
          labels: { color: '#fff', font: { size: 11 } },
        },
        tooltip: {
          callbacks: {
            label: function (context) {
              var valor = context.raw;
              if (valor === null || valor === undefined) return null;
              if (context.dataset.yAxisID === 'yPercentual') {
                return context.dataset.label + ': ' + valor.toFixed(2) + '%';
              }
              return context.dataset.label + ': ' + Math.round(valor).toLocaleString('pt-BR');
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { color: '#fff' },
          grid: { color: 'rgba(236, 240, 241, 0.15)' },
        },
        yQuantidade: {
          type: 'linear',
          position: 'left',
          min: 0,
          max: 1500000,
          title: { display: true, text: 'QUANTIDADE PRODUZIDA', color: '#5dade2', font: { weight: 'bold' } },
          ticks: { color: '#5dade2' },
          grid: { color: 'rgba(236, 240, 241, 0.15)' },
        },
        yPercentual: {
          type: 'linear',
          position: 'right',
          min: 0,
          title: { display: true, text: '% DE REFUGO', color: '#bdc3c7', font: { weight: 'bold' } },
          ticks: { color: '#bdc3c7' },
          grid: { drawOnChartArea: false },
        },
      },
    },
  });
})();
