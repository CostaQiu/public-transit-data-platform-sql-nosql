/* global L, Chart */

function fmt2(x) {
  if (x === null || x === undefined || isNaN(x)) return '0.00';
  return Number(x).toFixed(2);
}

function serviceLabel(serviceId) {
  const sid = String(serviceId);
  if (sid === '1') return 'Weekday';
  if (sid === '2') return 'Sat';
  if (sid === '3') return 'Sun';
  return 'Whole week';
}

function getFormParams(formEl) {
  const formData = new FormData(formEl);
  return {
    service_id: formData.get('service_id'),
    limit: formData.get('limit'),
  };
}

function getColor(value, min, max) {
  // Green (low) -> Red (high) within current query range
  if (max <= min) return 'rgb(0,200,0)';
  const t = (value - min) / (max - min + 1e-12);
  const r = Math.round(255 * t);
  const g = Math.round(200 * (1 - t));
  return `rgb(${r},${g},0)`;
}

function createMap(divId) {
  const map = L.map(divId);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);
  const layer = L.layerGroup().addTo(map);
  // Default GTA view (Toronto area)
  map.setView([43.6532, -79.3832], 11);
  return { map, layer };
}

// Q1 - Busiest Stops
const q1 = (function() {
  const { map, layer } = createMap('map-q1');
  let lastBounds = null;

  async function load() {
    const params = getFormParams(document.getElementById('form-q1'));
    const url = new URL('/api/q1', window.location.origin);
    url.searchParams.set('service_id', params.service_id);
    url.searchParams.set('limit', params.limit);
    const res = await fetch(url);
    const data = await res.json();
    render(data.items || []);
  }

  function render(items) {
    layer.clearLayers();
    const lats = [];
    const lons = [];
    const values = items.map(d => d.total_trip_events);
    const vmin = Math.min(...values, 0);
    const vmax = Math.max(...values, 1);
    items.forEach(d => {
      if (typeof d.stop_lat !== 'number' || typeof d.stop_lon !== 'number') return;
      lats.push(d.stop_lat);
      lons.push(d.stop_lon);
      const color = getColor(d.total_trip_events, vmin, vmax);
      const radius = 6;
      const marker = L.circleMarker([d.stop_lat, d.stop_lon], {
        radius,
        color,
        fillColor: color,
        fillOpacity: 0.8,
        weight: 1
      });
      marker.bindTooltip(`<b>${d.stop_name}</b><br/>Stop code: ${d.stop_code ?? ''}<br/>Trip events: ${d.total_trip_events}<br/>Unique routes: ${d.num_unique_routes}`, {sticky: true, direction: 'top'});
      layer.addLayer(marker);
    });
    if (lats.length) {
      lastBounds = L.latLngBounds(lats.map((lat, i) => [lat, lons[i]]));
      map.fitBounds(lastBounds.pad(0.1));
    }
    // table
    const tbody = document.querySelector('#table-q1 tbody');
    tbody.innerHTML = '';
    items.forEach(d => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${d.stop_name}</td><td>${d.stop_code ?? ''}</td><td>${d.total_trip_events}</td><td>${d.num_unique_routes}</td>`;
      tbody.appendChild(tr);
    });
  }

  document.getElementById('form-q1').addEventListener('submit', (e) => { e.preventDefault(); load(); });
  function invalidate() {
    setTimeout(() => {
      map.invalidateSize();
      if (lastBounds) map.fitBounds(lastBounds.pad(0.1));
    }, 0);
  }
  return { load, invalidate };
})();

// Q3 - Transfer Points
const q3 = (function() {
  const { map, layer } = createMap('map-q3');
  let lastBounds = null;

  async function load() {
    const params = getFormParams(document.getElementById('form-q3'));
    const url = new URL('/api/q3', window.location.origin);
    url.searchParams.set('service_id', params.service_id);
    url.searchParams.set('limit', params.limit);
    const res = await fetch(url);
    const data = await res.json();
    render(data.items || []);
  }

  function render(items) {
    layer.clearLayers();
    const lats = [];
    const lons = [];
    const values = items.map(d => d.num_unique_routes);
    const vmin = Math.min(...values, 0);
    const vmax = Math.max(...values, 1);
    items.forEach(d => {
      if (typeof d.stop_lat !== 'number' || typeof d.stop_lon !== 'number') return;
      lats.push(d.stop_lat);
      lons.push(d.stop_lon);
      const color = getColor(d.num_unique_routes, vmin, vmax);
      const radius = 6;
      const marker = L.circleMarker([d.stop_lat, d.stop_lon], {
        radius,
        color,
        fillColor: color,
        fillOpacity: 0.8,
        weight: 1
      });
      marker.bindTooltip(`<b>${d.stop_name}</b><br/>Stop code: ${d.stop_code ?? ''}<br/>Unique routes: ${d.num_unique_routes}`, {sticky: true, direction: 'top'});
      layer.addLayer(marker);
    });
    if (lats.length) {
      lastBounds = L.latLngBounds(lats.map((lat, i) => [lat, lons[i]]));
      map.fitBounds(lastBounds.pad(0.1));
    }
    // table
    const tbody = document.querySelector('#table-q3 tbody');
    tbody.innerHTML = '';
    items.forEach(d => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${d.stop_name}</td><td>${d.stop_code ?? ''}</td><td>${d.num_unique_routes}</td>`;
      tbody.appendChild(tr);
    });
  }

  document.getElementById('form-q3').addEventListener('submit', (e) => { e.preventDefault(); load(); });
  function invalidate() {
    setTimeout(() => {
      map.invalidateSize();
      if (lastBounds) map.fitBounds(lastBounds.pad(0.1));
    }, 0);
  }
  return { load, invalidate };
})();

// Q2 - Duration & Speed
const q2 = (function() {
  let charts = [];

  function clearCharts() {
    charts.forEach(ch => ch.destroy());
    charts = [];
  }

  async function load() {
    const params = getFormParams(document.getElementById('form-q2'));
    const url = new URL('/api/q2', window.location.origin);
    url.searchParams.set('service_id', params.service_id);
    url.searchParams.set('limit', params.limit);
    const res = await fetch(url);
    const data = await res.json();
    render(data, params.service_id);
  }

  function render(data, serviceId) {
    clearCharts();
    const tableBody = document.querySelector('#table-q2 tbody');
    tableBody.innerHTML = '';
    const chartsDiv = document.getElementById('q2-charts');
    chartsDiv.innerHTML = '';
    const overallDiv = document.getElementById('q2-overall');
    overallDiv.innerHTML = '';
    const params = getFormParams(document.getElementById('form-q2'));

    // Overall metrics display
    if (data.overall) {
      const info = document.createElement('div');
      info.className = 'alert alert-info';
      info.innerText = `Overall averages — Duration: ${fmt2(data.overall.avg_duration_min)} min, Speed: ${fmt2(data.overall.avg_speed_kmh)} km/h`;
      overallDiv.appendChild(info);
    }

    if (data.mode === 'whole_week') {
      // List only for whole week: use global stats; sort by duration desc
      const rows = [...(data.routes || [])].sort((a, b) => (b.global?.avg_duration_min || 0) - (a.global?.avg_duration_min || 0));
      rows.forEach(routeObj => {
        const tr = document.createElement('tr');
        const name = routeObj.route_short_name ? `${routeObj.route_short_name} — ${routeObj.route_long_name}` : routeObj.route_long_name;
        tr.innerHTML = `<td>${name}</td><td>${serviceLabel('4')}</td><td data-v="${routeObj.global?.total_trips ?? 0}">${routeObj.global?.total_trips ?? ''}</td><td data-v="${routeObj.global?.avg_duration_min ?? 0}">${fmt2(routeObj.global?.avg_duration_min)}</td><td data-v="${routeObj.global?.avg_speed_kmh ?? 0}">${fmt2(routeObj.global?.avg_speed_kmh)}</td>`;
        tableBody.appendChild(tr);
      });
    } else if (String(params.limit) === 'all') {
      // Single service + All limit: list only from per-route stats; sort by duration desc
      const rows = [...(data.routes || [])].sort((a, b) => (b.avg_duration_min || 0) - (a.avg_duration_min || 0));
      rows.forEach(r => {
        const tr = document.createElement('tr');
        const name = r.route_short_name ? `${r.route_short_name} — ${r.route_long_name}` : r.route_long_name;
        tr.innerHTML = `<td>${name}</td><td>${serviceLabel(r.service_id)}</td><td data-v="${r.total_trips}">${r.total_trips}</td><td data-v="${r.avg_duration_min ?? 0}">${fmt2(r.avg_duration_min)}</td><td data-v="${r.avg_speed_kmh ?? 0}">${fmt2(r.avg_speed_kmh)}</td>`;
        tableBody.appendChild(tr);
      });
    } else {
      // Single service: two separate bar charts stacked vertically with names on x-axis
      const labels = (data.routes || []).map(r => (r.route_short_name ? `${r.route_short_name} — ${r.route_long_name}` : r.route_long_name));
      const durData = (data.routes || []).map(r => r.avg_duration_min ?? 0);
      const spdData = (data.routes || []).map(r => r.avg_speed_kmh ?? 0);

      // Ensure full width stacking
      chartsDiv.classList.remove('small-multiples');

      // Duration chart
      const cardDur = document.createElement('div');
      cardDur.className = 'card-chart';
      cardDur.innerHTML = `<h6>Average Duration (min)</h6><canvas></canvas>`;
      chartsDiv.appendChild(cardDur);
      const canvasDur = cardDur.querySelector('canvas');
      canvasDur.height = 320;
      // lock width and disable responsive resizing to prevent height growth; widen for many labels
      const baseWidth = Math.max(chartsDiv.getBoundingClientRect().width - 32, labels.length * 18);
      canvasDur.width = Math.max(600, baseWidth);
      const ctxDur = canvasDur.getContext('2d');
      charts.push(new Chart(ctxDur, {
        type: 'bar',
        data: { labels, datasets: [{ label: 'Duration (min)', data: durData, backgroundColor: 'rgba(54, 162, 235, 0.75)' }] },
        options: {
          responsive: false,
          animation: false,
          maintainAspectRatio: false,
          scales: {
            y: { beginAtZero: true, title: { display: true, text: 'Minutes' } },
            x: { ticks: { autoSkip: false, maxRotation: 70, minRotation: 45, font: { size: 9 } } }
          },
          plugins: {
            legend: { display: true, labels: { boxWidth: 12 } },
            datalabels: { anchor: 'center', align: 'center', color: '#222', formatter: v => fmt2(v), font: { size: 9 } }
          }
        }
      , plugins: (typeof window.ChartDataLabels !== 'undefined') ? [window.ChartDataLabels] : [] }));

      // Speed chart
      const cardSpd = document.createElement('div');
      cardSpd.className = 'card-chart mt-3';
      cardSpd.innerHTML = `<h6>Average Speed (km/h)</h6><canvas></canvas>`;
      chartsDiv.appendChild(cardSpd);
      const canvasSpd = cardSpd.querySelector('canvas');
      canvasSpd.height = 320;
      canvasSpd.width = Math.max(600, baseWidth);
      const ctxSpd = canvasSpd.getContext('2d');
      charts.push(new Chart(ctxSpd, {
        type: 'bar',
        data: { labels, datasets: [{ label: 'Speed (km/h)', data: spdData, backgroundColor: 'rgba(255, 99, 132, 0.65)' }] },
        options: {
          responsive: false,
          animation: false,
          maintainAspectRatio: false,
          scales: {
            y: { beginAtZero: true, title: { display: true, text: 'km/h' } },
            x: { ticks: { autoSkip: false, maxRotation: 70, minRotation: 45, font: { size: 9 } } }
          },
          plugins: {
            legend: { display: true, labels: { boxWidth: 12 } },
            datalabels: { anchor: 'center', align: 'center', color: '#222', formatter: v => fmt2(v), font: { size: 9 } }
          }
        }
      , plugins: (typeof window.ChartDataLabels !== 'undefined') ? [window.ChartDataLabels] : [] }));

      const rows = [...(data.routes || [])].sort((a, b) => (b.avg_duration_min || 0) - (a.avg_duration_min || 0));
      rows.forEach(r => {
        const tr = document.createElement('tr');
        const name = r.route_short_name ? `${r.route_short_name} — ${r.route_long_name}` : r.route_long_name;
        tr.innerHTML = `<td>${name}</td><td>${serviceLabel(r.service_id)}</td><td data-v="${r.total_trips}">${r.total_trips}</td><td data-v="${r.avg_duration_min ?? 0}">${fmt2(r.avg_duration_min)}</td><td data-v="${r.avg_speed_kmh ?? 0}">${fmt2(r.avg_speed_kmh)}</td>`;
        tableBody.appendChild(tr);
      });

      // Sorting handlers
      const headers = document.querySelectorAll('#table-q2 th.sortable');
      headers.forEach(th => {
        th.style.cursor = 'pointer';
        th.addEventListener('click', () => {
          const key = th.dataset.key; // trips | duration | speed
          const idx = key === 'trips' ? 2 : key === 'duration' ? 3 : 4; // td index with data-v
          const rows = Array.from(tableBody.querySelectorAll('tr'));
          rows.sort((a, b) => {
            const av = parseFloat(a.children[idx].dataset.v || '0');
            const bv = parseFloat(b.children[idx].dataset.v || '0');
            return bv - av; // desc
          });
          tableBody.innerHTML = '';
          rows.forEach(r => tableBody.appendChild(r));
        });
      });
    }
  }

  document.getElementById('form-q2').addEventListener('submit', (e) => { e.preventDefault(); load(); });
  return { load };
})();

// Q4 - Hourly Frequency
const q4 = (function() {
  let charts = [];
  function clearCharts() { charts.forEach(c => c.destroy()); charts = []; }

  async function load() {
    const params = getFormParams(document.getElementById('form-q4'));
    const url = new URL('/api/q4', window.location.origin);
    url.searchParams.set('service_id', params.service_id);
    url.searchParams.set('limit', params.limit);
    const res = await fetch(url);
    const data = await res.json();
    render(data);
  }

  function render(data) {
    clearCharts();
    const root = document.getElementById('q4-charts');
    root.innerHTML = '';
    const tbody = document.querySelector('#table-q4 tbody');
    tbody.innerHTML = '';
    let routes = data.routes || [];
    // Sort by total trip count descending for charts and lists
    routes.sort((a, b) => (b.total_daily_trips || 0) - (a.total_daily_trips || 0));
    const params = getFormParams(document.getElementById('form-q4'));
    const isWhole = String(params.service_id) === '4';
    const isAllLimit = String(params.limit) === 'all';
    if (isWhole) {
      // Adjust header for whole-week per day totals
      const headRow = document.querySelector('#table-q4 thead tr');
      if (headRow) {
        headRow.innerHTML = '<th>Route name and number of trips</th><th>Weekday</th><th>Saturday</th><th>Sunday</th><th>Average</th>';
      }
      // List only: totals for weekday, saturday, sunday, and average per route
      routes.forEach(r => {
        const name = r.route_short_name ? `${r.route_short_name} — ${r.route_long_name}` : r.route_long_name;
        const t1 = r.totals_by_service ? (r.totals_by_service['1'] || 0) : 0;
        const t2 = r.totals_by_service ? (r.totals_by_service['2'] || 0) : 0;
        const t3 = r.totals_by_service ? (r.totals_by_service['3'] || 0) : 0;
        const avg = r.average_daily_trips != null ? Number(r.average_daily_trips).toFixed(2) : '0.00';
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${name} — Total: ${r.total_daily_trips ?? ''}</td><td>${t1}</td><td>${t2}</td><td>${t3}</td><td>${avg}</td>`;
        tbody.appendChild(tr);
      });
      return;
    }

    if (isAllLimit) {
      // No charts when limit is all; show compact hourly list
      const headRow = document.querySelector('#table-q4 thead tr');
      if (headRow) {
        headRow.innerHTML = '<th>Route name and number of trips</th><th>Hourly profile (h:count, …)</th>';
      }
      routes.forEach(r => {
        const name = r.route_short_name ? `${r.route_short_name} — ${r.route_long_name}` : r.route_long_name;
        const profile = (r.hourly || []).map(h => `${h.hour}:${h.trips}`).join(', ');
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${name} — Total: ${r.total_daily_trips ?? ''}</td><td>${profile}</td>`;
        tbody.appendChild(tr);
      });
      return;
    }

    // Plot charts (service-specific)
    routes.forEach(r => {
      const card = document.createElement('div');
      card.className = 'card-chart';
      const title = document.createElement('h6');
      const label = r.route_short_name ? `${r.route_short_name} — ${r.route_long_name}` : r.route_long_name;
      title.textContent = `${label} — Total: ${r.total_daily_trips}`;
      const canvas = document.createElement('canvas');
      card.appendChild(title);
      card.appendChild(canvas);
      root.appendChild(card);

      const labels = r.hourly.map(h => String(h.hour));
      const values = r.hourly.map(h => h.trips);
      const ctx = canvas.getContext('2d');
      const hasDatalabels = typeof window.ChartDataLabels !== 'undefined';
      charts.push(new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets: [{ label: 'Trips per hour', data: values, backgroundColor: 'rgba(99, 132, 255, 0.6)' }] },
        options: {
          responsive: true,
          scales: { y: { beginAtZero: true } },
          plugins: hasDatalabels ? { datalabels: { anchor: 'center', align: 'center', color: '#222', formatter: v => v, font: { size: 10 } } } : {}
        },
        plugins: hasDatalabels ? [window.ChartDataLabels] : []
      }));
    });
  }

  document.getElementById('form-q4').addEventListener('submit', (e) => { e.preventDefault(); load(); });
  return { load };
})();

// Initial loads when the page is ready
window.addEventListener('DOMContentLoaded', () => {
  q1.load();
  q2.load();
  q3.load();
  q4.load();
  // Ensure Leaflet maps created in hidden tabs render correctly
  document.querySelectorAll('button[data-bs-toggle="tab"]').forEach(btn => {
    btn.addEventListener('shown.bs.tab', (e) => {
      const target = e.target.getAttribute('data-bs-target');
      if (target === '#q1') q1.invalidate();
      if (target === '#q3') q3.invalidate();
    });
  });
});



