document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const uploadProgress = document.getElementById('uploadProgress');
  const progressFill = document.getElementById('progressFill');
  const uploadStatus = document.getElementById('uploadStatus');
  const filesList = document.getElementById('filesList');
  const summaryCard = document.getElementById('summaryCard');
  const fileCrsBadge = document.getElementById('fileCrsBadge');
  const statFeatures = document.getElementById('statFeatures');
  const statArea = document.getElementById('statArea');
  const statAreaSub = document.getElementById('statAreaSub');
  const statLength = document.getElementById('statLength');
  const statLengthSub = document.getElementById('statLengthSub');
  const statGeomBreakdown = document.getElementById('statGeomBreakdown');
  const tableBody = document.getElementById('tableBody');
  const geomFilter = document.getElementById('geomFilter');
  const btnResetMap = document.getElementById('btnResetMap');

  let currentFileId = null;
  let currentGeoJsonLayer = null;

  // Initialize Leaflet Map (dark/modern tiles)
  const map = L.map('map').setView([20.5937, 78.9629], 4);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
  }).addTo(map);

  // Setup Drag & Drop
  dropzone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFileUpload(e.target.files[0]);
    }
  });

  geomFilter.addEventListener('change', () => {
    if (currentFileId) {
      loadMeasurements(currentFileId, geomFilter.value);
    }
  });

  btnResetMap.addEventListener('click', () => {
    if (currentGeoJsonLayer && currentGeoJsonLayer.getLayers().length > 0) {
      map.fitBounds(currentGeoJsonLayer.getBounds(), { padding: [30, 30] });
    }
  });

  // Handle File Upload
  async function handleFileUpload(file) {
    const formData = new FormData();
    formData.append('file', file);

    uploadProgress.style.display = 'block';
    progressFill.style.width = '30%';
    uploadStatus.className = 'status-msg info';
    uploadStatus.textContent = `Uploading and processing '${file.name}'...`;

    try {
      progressFill.style.width = '70%';
      const response = await fetch('/api/files/', {
        method: 'POST',
        body: formData,
      });

      progressFill.style.width = '100%';

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Upload failed');
      }

      const fileInfo = await response.json();
      uploadStatus.className = 'status-msg success';
      uploadStatus.textContent = `✓ '${fileInfo.filename}' successfully processed! (${fileInfo.feature_count} features)`;
      
      setTimeout(() => {
        uploadProgress.style.display = 'none';
        progressFill.style.width = '0%';
      }, 1000);

      loadFilesList();
      selectFile(fileInfo.id);
    } catch (err) {
      uploadProgress.style.display = 'none';
      uploadStatus.className = 'status-msg error';
      uploadStatus.textContent = `✕ ${err.message}`;
    }
  }

  // Load Files List
  async function loadFilesList() {
    try {
      const res = await fetch('/api/files/');
      const files = await res.json();
      
      if (!files || files.length === 0) {
        filesList.innerHTML = '<p class="empty-state">No files uploaded yet.</p>';
        return;
      }

      filesList.innerHTML = files.map(f => `
        <div class="file-item ${f.id === currentFileId ? 'active' : ''}" data-id="${f.id}">
          <div class="file-info-main" onclick="window.selectFile('${f.id}')">
            <div class="file-info-title">${f.filename}</div>
            <div class="file-info-meta">${f.feature_count} features • ${f.crs} • ${f.status}</div>
          </div>
          <button class="btn-delete" title="Delete" onclick="window.deleteFile('${f.id}', event)">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          </button>
        </div>
      `).join('');
    } catch (err) {
      console.error("Failed to load files:", err);
    }
  }

  // Select File
  window.selectFile = async function(fileId) {
    currentFileId = fileId;
    loadFilesList();
    geomFilter.value = "";
    await Promise.all([
      loadMeasurements(fileId),
      loadMapFeatures(fileId)
    ]);
  };

  // Delete File
  window.deleteFile = async function(fileId, event) {
    event.stopPropagation();
    if (!confirm('Are you sure you want to delete this file?')) return;

    try {
      await fetch(`/api/files/${fileId}/`, { method: 'DELETE' });
      if (currentFileId === fileId) {
        currentFileId = null;
        summaryCard.style.display = 'none';
        tableBody.innerHTML = '<tr><td colspan="5" class="empty-state">Select or upload a file.</td></tr>';
        if (currentGeoJsonLayer) map.removeLayer(currentGeoJsonLayer);
      }
      loadFilesList();
    } catch (err) {
      alert("Failed to delete file: " + err.message);
    }
  };

  // Load Measurements
  async function loadMeasurements(fileId, geometryType = '') {
    try {
      let url = `/api/files/${fileId}/measurements/?limit=200`;
      if (geometryType) url += `&geometry_type=${encodeURIComponent(geometryType)}`;

      const res = await fetch(url);
      if (!res.ok) throw new Error("Measurements not found");
      const data = await res.json();

      // Update Summary Card
      summaryCard.style.display = 'block';
      fileCrsBadge.textContent = data.source_crs;
      statFeatures.textContent = data.summary.total_features;
      
      statArea.textContent = `${data.summary.total_area_sq_meters.toLocaleString()} m²`;
      statAreaSub.textContent = `${data.summary.total_area_hectares.toLocaleString()} ha (${data.summary.total_area_sq_km.toFixed(4)} km²)`;

      statLength.textContent = `${data.summary.total_length_meters.toLocaleString()} m`;
      statLengthSub.textContent = `${data.summary.total_length_km.toFixed(3)} km`;

      statGeomBreakdown.textContent = `Poly: ${data.summary.polygon_count} | Line: ${data.summary.linestring_count} | Pt: ${data.summary.point_count}`;

      // Populate Table
      if (!data.features || data.features.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5" class="empty-state">No matching features found.</td></tr>';
        return;
      }

      tableBody.innerHTML = data.features.map(f => {
        let measureHtml = '-';
        if (f.measurement.area) {
          measureHtml = `
            <span class="measure-pill measure-area">${f.measurement.area.sq_meters.toLocaleString()} m²</span>
            <span class="measure-sub">${f.measurement.area.hectares} ha | ${f.measurement.area.acres} acres</span>
          `;
        } else if (f.measurement.length) {
          measureHtml = `
            <span class="measure-pill measure-length">${f.measurement.length.meters.toLocaleString()} m</span>
            <span class="measure-sub">${f.measurement.length.kilometers} km | ${f.measurement.length.feet} ft</span>
          `;
        } else if (f.geometry_type === 'Point' || f.geometry_type === 'MultiPoint') {
          measureHtml = `<span class="measure-pill measure-point">Point Geometry</span><span class="measure-sub">${f.measurement.measurement_note || ''}</span>`;
        } else {
          measureHtml = `<span class="measure-sub">${f.measurement.measurement_note || 'N/A'}</span>`;
        }

        const propsStr = Object.keys(f.properties).length > 0 
          ? Object.entries(f.properties).map(([k, v]) => `<strong>${k}:</strong> ${v}`).join(', ')
          : '<em style="color:var(--text-muted)">None</em>';

        return `
          <tr>
            <td><strong>#${f.feature_id}</strong></td>
            <td><code>${f.geometry_type}</code></td>
            <td>${measureHtml}</td>
            <td>
              <div><code>${f.measurement.calculated_crs || f.crs}</code></div>
              <span class="measure-sub">${f.measurement.method}</span>
            </td>
            <td style="font-size: 0.8rem; max-width: 250px; overflow: hidden; text-overflow: ellipsis;">${propsStr}</td>
          </tr>
        `;
      }).join('');

    } catch (err) {
      console.error("Failed to load measurements:", err);
    }
  }

  // Load Map Features GeoJSON
  async function loadMapFeatures(fileId) {
    try {
      if (currentGeoJsonLayer) {
        map.removeLayer(currentGeoJsonLayer);
      }

      const res = await fetch(`/api/files/${fileId}/geojson/`);
      if (!res.ok) return;
      const geojson = await res.json();

      currentGeoJsonLayer = L.geoJSON(geojson, {
        style: (feature) => {
          const type = feature.geometry ? feature.geometry.type : '';
          if (type.includes('Polygon')) {
            return {
              color: '#10b981',
              weight: 2,
              fillColor: '#10b981',
              fillOpacity: 0.35,
            };
          } else if (type.includes('Line')) {
            return {
              color: '#06b6d4',
              weight: 3,
            };
          }
          return { color: '#8b5cf6' };
        },
        pointToLayer: (feature, latlng) => {
          return L.circleMarker(latlng, {
            radius: 6,
            fillColor: '#8b5cf6',
            color: '#fff',
            weight: 1.5,
            opacity: 1,
            fillOpacity: 0.8
          });
        },
        onEachFeature: (feature, layer) => {
          const m = feature.properties.measurement;
          let mText = '';
          if (m && m.area) {
            mText = `<b>Area:</b> ${m.area.sq_meters.toLocaleString()} m² (${m.area.hectares} ha)`;
          } else if (m && m.length) {
            mText = `<b>Length:</b> ${m.length.meters.toLocaleString()} m (${m.length.kilometers} km)`;
          }

          layer.bindPopup(`
            <div style="font-family: 'Inter', sans-serif; font-size: 13px;">
              <h4 style="margin: 0 0 5px 0;">Feature #${feature.properties.feature_id || feature.id} (${feature.geometry.type})</h4>
              ${mText ? `<p style="margin: 3px 0;">${mText}</p>` : ''}
              <p style="margin: 3px 0; font-size: 11px; color: #666;"><b>Projected CRS:</b> ${m?.calculated_crs || 'N/A'}</p>
            </div>
          `);
        }
      }).addTo(map);

      if (currentGeoJsonLayer.getLayers().length > 0) {
        map.fitBounds(currentGeoJsonLayer.getBounds(), { padding: [40, 40] });
      }
    } catch (err) {
      console.error("Failed to render GeoJSON on map:", err);
    }
  }

  // Initial files load
  loadFilesList();
});
