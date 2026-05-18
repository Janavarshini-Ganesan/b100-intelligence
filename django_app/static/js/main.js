// Active nav link highlight on page load
document.addEventListener('DOMContentLoaded', function () {
  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach(link => {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('active');
    }
  });
});

// Number formatter
function formatNumber(num, decimals = 0) {
  if (num === null || num === undefined || isNaN(num)) return '—';
  if (Math.abs(num) >= 1e12) return (num / 1e12).toFixed(2) + 'T';
  if (Math.abs(num) >= 1e9)  return (num / 1e9).toFixed(2) + 'B';
  if (Math.abs(num) >= 1e7)  return (num / 1e7).toFixed(2) + 'Cr';
  if (Math.abs(num) >= 1e5)  return (num / 1e5).toFixed(2) + 'L';
  return num.toFixed(decimals).toLocaleString();
}

// Health badge renderer
function healthBadge(label) {
  const map = {
    'EXCELLENT': 'badge-excellent',
    'GOOD':      'badge-good',
    'AVERAGE':   'badge-average',
    'WEAK':      'badge-weak',
    'POOR':      'badge-poor',
  };
  const cls = map[label] || 'badge-average';
  return `<span class="health-badge ${cls}">${label}</span>`;
}

// Positive/negative color
function colorVal(val, suffix = '%') {
  if (val === null || val === undefined || isNaN(val)) return '—';
  const cls = val >= 0 ? 'positive' : 'negative';
  const sign = val >= 0 ? '+' : '';
  return `<span class="${cls}">${sign}${val.toFixed(1)}${suffix}</span>`;
}

// Chart.js global defaults
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.color = '#6b7280';
Chart.defaults.plugins.legend.labels.boxWidth = 12;
Chart.defaults.plugins.legend.labels.padding = 16;
Chart.defaults.plugins.tooltip.backgroundColor = '#1f2937';
Chart.defaults.plugins.tooltip.titleColor = '#f9fafb';
Chart.defaults.plugins.tooltip.bodyColor = '#d1d5db';
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.plugins.tooltip.cornerRadius = 6;