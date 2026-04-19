/**
 * AlgoTrader — Chart.js chart initialisation
 * Called from reports.html after inline data is injected.
 */

function initReportCharts(
  equityLabels, equityData,
  dailyLabels, dailyPnl,
  totalWins, totalLosses,
  strategyLabels, strategyPnl
) {

  // 1. Equity curve — Line chart
  const equityCtx = document.getElementById('equityChart');
  if (equityCtx) {
    new Chart(equityCtx, {
      type: 'line',
      data: {
        labels: equityLabels,
        datasets: [{
          label: 'Cumulative Net P&L (₹)',
          data: equityData,
          borderColor: '#0d6efd',
          backgroundColor: 'rgba(13,110,253,0.08)',
          fill: true,
          tension: 0.3,
          pointRadius: 3,
        }],
      },
      options: {
        responsive: true,
        plugins: {legend: {display: false}},
        scales: {
          x: {ticks: {maxTicksLimit: 10}},
          y: {
            ticks: {
              callback: v => `₹${v}`,
            },
          },
        },
      },
    });
  }

  // 2. Daily P&L — Bar chart (green positive, red negative)
  const dailyCtx = document.getElementById('dailyPnlChart');
  if (dailyCtx) {
    new Chart(dailyCtx, {
      type: 'bar',
      data: {
        labels: dailyLabels,
        datasets: [{
          label: 'Daily Net P&L (₹)',
          data: dailyPnl,
          backgroundColor: dailyPnl.map(v => v >= 0 ? 'rgba(25,135,84,0.75)' : 'rgba(220,53,69,0.75)'),
          borderColor: dailyPnl.map(v => v >= 0 ? '#198754' : '#dc3545'),
          borderWidth: 1,
        }],
      },
      options: {
        responsive: true,
        plugins: {legend: {display: false}},
        scales: {
          y: {ticks: {callback: v => `₹${v}`}},
          x: {ticks: {maxTicksLimit: 10}},
        },
      },
    });
  }

  // 3. Win rate — Doughnut
  const winCtx = document.getElementById('winRateChart');
  if (winCtx) {
    const total = totalWins + totalLosses;
    const winPct = total > 0 ? Math.round(totalWins / total * 100) : 0;
    new Chart(winCtx, {
      type: 'doughnut',
      data: {
        labels: [`Win (${totalWins})`, `Loss (${totalLosses})`],
        datasets: [{
          data: [totalWins || 0, totalLosses || 0],
          backgroundColor: ['#198754', '#dc3545'],
          borderWidth: 0,
        }],
      },
      options: {
        responsive: true,
        cutout: '65%',
        plugins: {
          legend: {position: 'bottom'},
          tooltip: {
            callbacks: {
              label: ctx => `${ctx.label}: ${ctx.raw} trades`,
            },
          },
        },
      },
      plugins: [{
        id: 'centerText',
        afterDraw(chart) {
          const {ctx, chartArea: {width, height, top}} = chart;
          ctx.save();
          ctx.font = 'bold 20px sans-serif';
          ctx.fillStyle = winPct >= 50 ? '#198754' : '#dc3545';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(`${winPct}%`, width / 2, top + height / 2);
          ctx.restore();
        },
      }],
    });
  }

  // 4. Strategy comparison — Grouped bar
  const strategyCtx = document.getElementById('strategyChart');
  if (strategyCtx) {
    new Chart(strategyCtx, {
      type: 'bar',
      data: {
        labels: strategyLabels,
        datasets: [{
          label: 'Net P&L (₹) — Last 30 Days',
          data: strategyPnl,
          backgroundColor: strategyPnl.map(v => v >= 0 ? 'rgba(25,135,84,0.75)' : 'rgba(220,53,69,0.75)'),
          borderColor: strategyPnl.map(v => v >= 0 ? '#198754' : '#dc3545'),
          borderWidth: 1,
        }],
      },
      options: {
        responsive: true,
        plugins: {legend: {display: false}},
        scales: {
          y: {ticks: {callback: v => `₹${v}`}},
        },
      },
    });
  }
}
