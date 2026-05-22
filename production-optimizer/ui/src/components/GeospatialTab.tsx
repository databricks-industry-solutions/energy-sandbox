import { useRef, useEffect, useState, useCallback } from 'react';
import AgentPanel from './AgentPanel';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface GeoJSONFeature {
  type: 'Feature';
  geometry: {
    type: string;
    coordinates: number[] | number[][] | number[][][];
  };
  properties: Record<string, unknown>;
}

interface GeoJSONFC {
  type: 'FeatureCollection';
  features: GeoJSONFeature[];
}

interface GeoJSONAssets {
  wells?: GeoJSONFC;
  facilities?: GeoJSONFC;
  pipelines?: GeoJSONFC;
  co2Sources?: GeoJSONFC;
  monitoringPoints?: GeoJSONFC;
  fleet?: GeoJSONFC;
  flares?: GeoJSONFC;
}

interface LayerDef {
  key: keyof GeoJSONAssets;
  label: string;
  color: string;
}

/* ------------------------------------------------------------------ */
/*  Layer Definitions                                                   */
/* ------------------------------------------------------------------ */

const LAYERS: LayerDef[] = [
  { key: 'wells', label: 'Wells', color: '#00d4aa' },
  { key: 'facilities', label: 'Facilities', color: '#3b82f6' },
  { key: 'pipelines', label: 'Pipelines', color: '#06b6d4' },
  { key: 'co2Sources', label: 'CO\u2082 Sources', color: '#a855f7' },
  { key: 'monitoringPoints', label: 'Monitoring', color: '#f59e0b' },
  { key: 'fleet', label: 'Fleet', color: '#8b5cf6' },
  { key: 'flares', label: 'Flares', color: '#f97316' },
];

/* ------------------------------------------------------------------ */
/*  Map math helpers                                                   */
/* ------------------------------------------------------------------ */

interface ViewState {
  centerLon: number;
  centerLat: number;
  zoom: number;
}

function lonLatToPixel(
  lon: number,
  lat: number,
  view: ViewState,
  w: number,
  h: number,
): [number, number] {
  const scale = Math.pow(2, view.zoom) * 80;
  const x = w / 2 + (lon - view.centerLon) * scale;
  const y = h / 2 - (lat - view.centerLat) * scale;
  return [x, y];
}

function pixelToLonLat(
  px: number,
  py: number,
  view: ViewState,
  w: number,
  h: number,
): [number, number] {
  const scale = Math.pow(2, view.zoom) * 80;
  const lon = view.centerLon + (px - w / 2) / scale;
  const lat = view.centerLat - (py - h / 2) / scale;
  return [lon, lat];
}

/* ------------------------------------------------------------------ */
/*  Canvas Map Renderer                                                */
/* ------------------------------------------------------------------ */

function drawMap(
  ctx: CanvasRenderingContext2D,
  w: number,
  h: number,
  assets: GeoJSONAssets,
  view: ViewState,
  visibility: Record<string, boolean>,
  flarePhase: number,
) {
  // Background — dark terrain
  ctx.fillStyle = '#0c1018';
  ctx.fillRect(0, 0, w, h);

  // Subtle grid
  ctx.strokeStyle = 'rgba(48, 54, 61, 0.4)';
  ctx.lineWidth = 0.5;
  const scale = Math.pow(2, view.zoom) * 80;
  const gridStep = 0.01; // ~1km
  const [leftLon, topLat] = pixelToLonLat(0, 0, view, w, h);
  const [rightLon, botLat] = pixelToLonLat(w, h, view, w, h);

  const lonStart = Math.floor(leftLon / gridStep) * gridStep;
  const latStart = Math.floor(botLat / gridStep) * gridStep;

  for (let lon = lonStart; lon <= rightLon; lon += gridStep) {
    const [x] = lonLatToPixel(lon, 0, view, w, h);
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  for (let lat = latStart; lat <= topLat; lat += gridStep) {
    const [, y] = lonLatToPixel(0, lat, view, w, h);
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  // Coordinate labels
  ctx.font = '9px monospace';
  ctx.fillStyle = 'rgba(110, 118, 129, 0.6)';
  const labelStep = 0.05;
  const lonLabelStart = Math.floor(leftLon / labelStep) * labelStep;
  const latLabelStart = Math.floor(botLat / labelStep) * labelStep;
  for (let lon = lonLabelStart; lon <= rightLon; lon += labelStep) {
    const [x] = lonLatToPixel(lon, view.centerLat, view, w, h);
    if (x > 30 && x < w - 30) {
      ctx.fillText(lon.toFixed(2) + '°', x + 2, h - 4);
    }
  }
  for (let lat = latLabelStart; lat <= topLat; lat += labelStep) {
    const [, y] = lonLatToPixel(view.centerLon, lat, view, w, h);
    if (y > 15 && y < h - 15) {
      ctx.fillText(lat.toFixed(2) + '°', 4, y - 2);
    }
  }

  const toXY = (lon: number, lat: number) => lonLatToPixel(lon, lat, view, w, h);

  // --- Pipelines ---
  if (visibility.pipelines && assets.pipelines) {
    for (const f of assets.pipelines.features) {
      const coords = f.geometry.coordinates as number[][];
      if (!coords || coords.length < 2) continue;
      const color = (f.properties.color as string) || '#06b6d4';
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.globalAlpha = 0.7;
      ctx.setLineDash([8, 5]);
      ctx.beginPath();
      const [x0, y0] = toXY(coords[0][0], coords[0][1]);
      ctx.moveTo(x0, y0);
      for (let i = 1; i < coords.length; i++) {
        const [x, y] = toXY(coords[i][0], coords[i][1]);
        ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;

      // Pipeline label
      if (coords.length >= 2) {
        const midIdx = Math.floor(coords.length / 2);
        const [mx, my] = toXY(coords[midIdx][0], coords[midIdx][1]);
        ctx.font = '9px sans-serif';
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.7;
        ctx.fillText(String(f.properties.name || ''), mx + 4, my - 4);
        ctx.globalAlpha = 1;
      }
    }
  }

  // --- Monitoring Points ---
  if (visibility.monitoringPoints && assets.monitoringPoints) {
    for (const f of assets.monitoringPoints.features) {
      const [lon, lat] = f.geometry.coordinates as number[];
      const [x, y] = toXY(lon, lat);
      // Triangle marker
      ctx.fillStyle = '#f59e0b';
      ctx.globalAlpha = 0.8;
      ctx.beginPath();
      ctx.moveTo(x, y - 5);
      ctx.lineTo(x - 4, y + 3);
      ctx.lineTo(x + 4, y + 3);
      ctx.closePath();
      ctx.fill();
      ctx.globalAlpha = 1;
    }
  }

  // --- CO2 Sources ---
  if (visibility.co2Sources && assets.co2Sources) {
    for (const f of assets.co2Sources.features) {
      const [lon, lat] = f.geometry.coordinates as number[];
      const [x, y] = toXY(lon, lat);
      // Diamond marker
      ctx.fillStyle = '#a855f7';
      ctx.strokeStyle = '#c084fc';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x, y - 8);
      ctx.lineTo(x + 6, y);
      ctx.lineTo(x, y + 8);
      ctx.lineTo(x - 6, y);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      // Label
      ctx.font = '10px sans-serif';
      ctx.fillStyle = '#c084fc';
      ctx.fillText(String(f.properties.name || ''), x + 10, y + 4);
    }
  }

  // --- Fleet ---
  if (visibility.fleet && assets.fleet) {
    for (const f of assets.fleet.features) {
      const [lon, lat] = f.geometry.coordinates as number[];
      const [x, y] = toXY(lon, lat);
      ctx.fillStyle = '#8b5cf6';
      ctx.strokeStyle = '#a78bfa';
      ctx.lineWidth = 1.5;
      // Square marker
      ctx.beginPath();
      ctx.rect(x - 4, y - 4, 8, 8);
      ctx.fill();
      ctx.stroke();
    }
  }

  // --- Flares ---
  if (visibility.flares && assets.flares) {
    for (const f of assets.flares.features) {
      const [lon, lat] = f.geometry.coordinates as number[];
      const [x, y] = toXY(lon, lat);
      // Pulsing outer ring
      const pulseR = 12 + Math.sin(flarePhase) * 6;
      const pulseAlpha = 0.3 - Math.sin(flarePhase) * 0.15;
      ctx.fillStyle = `rgba(249, 115, 22, ${Math.max(0, pulseAlpha)})`;
      ctx.beginPath();
      ctx.arc(x, y, pulseR, 0, Math.PI * 2);
      ctx.fill();
      // Inner circle
      ctx.fillStyle = '#f97316';
      ctx.beginPath();
      ctx.arc(x, y, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#fb923c';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  }

  // --- Facilities ---
  if (visibility.facilities && assets.facilities) {
    for (const f of assets.facilities.features) {
      const [lon, lat] = f.geometry.coordinates as number[];
      const [x, y] = toXY(lon, lat);
      const color = (f.properties.color as string) || '#3b82f6';
      // Outer ring
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(x, y, 13, 0, Math.PI * 2);
      ctx.stroke();
      // Fill
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.85;
      ctx.beginPath();
      ctx.arc(x, y, 10, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;
      // Label
      ctx.font = 'bold 10px sans-serif';
      ctx.fillStyle = '#e6edf3';
      ctx.fillText(String(f.properties.name || ''), x + 16, y + 4);
    }
  }

  // --- Wells ---
  if (visibility.wells && assets.wells) {
    for (const f of assets.wells.features) {
      const [lon, lat] = f.geometry.coordinates as number[];
      const [x, y] = toXY(lon, lat);
      const color = (f.properties.color as string) || '#00d4aa';
      const wellType = f.properties.type as string;
      const r = wellType === 'producer' ? 6 : wellType === 'injector' ? 5 : 4;
      // Circle
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.25)';
      ctx.lineWidth = 1;
      ctx.stroke();
      // Label for producers
      if (scale > 500) {
        ctx.font = '8px sans-serif';
        ctx.fillStyle = 'rgba(230,237,243,0.6)';
        ctx.fillText(String(f.properties.name || ''), x + r + 3, y + 3);
      }
    }
  }

  // Scale bar
  ctx.fillStyle = 'rgba(230,237,243,0.5)';
  ctx.font = '10px monospace';
  const kmPerPx = (1 / scale) * 111.32;
  const scaleBarKm = kmPerPx * 100 < 1 ? 0.5 : Math.round(kmPerPx * 100);
  const scaleBarPx = scaleBarKm / kmPerPx;
  const sbX = w - scaleBarPx - 20;
  const sbY = h - 16;
  ctx.strokeStyle = 'rgba(230,237,243,0.5)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(sbX, sbY);
  ctx.lineTo(sbX + scaleBarPx, sbY);
  ctx.stroke();
  ctx.fillText(`${scaleBarKm} km`, sbX + scaleBarPx / 2 - 12, sbY - 4);
}

/* ------------------------------------------------------------------ */
/*  Hit-test                                                           */
/* ------------------------------------------------------------------ */

function hitTest(
  px: number,
  py: number,
  assets: GeoJSONAssets,
  view: ViewState,
  w: number,
  h: number,
  visibility: Record<string, boolean>,
): { feature: Record<string, unknown>; type: string } | null {
  const toXY = (lon: number, lat: number) => lonLatToPixel(lon, lat, view, w, h);
  const dist = (x1: number, y1: number, x2: number, y2: number) =>
    Math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2);

  // Check point layers (wells first, then facilities, etc.)
  const pointLayers: { key: keyof GeoJSONAssets; type: string; radius: number }[] = [
    { key: 'wells', type: 'well', radius: 10 },
    { key: 'facilities', type: 'facility', radius: 16 },
    { key: 'co2Sources', type: 'source', radius: 12 },
    { key: 'monitoringPoints', type: 'monitor', radius: 8 },
    { key: 'fleet', type: 'fleet', radius: 10 },
    { key: 'flares', type: 'flare', radius: 10 },
  ];

  for (const layer of pointLayers) {
    if (!visibility[layer.key]) continue;
    const fc = assets[layer.key];
    if (!fc) continue;
    for (const f of fc.features) {
      const [lon, lat] = f.geometry.coordinates as number[];
      const [x, y] = toXY(lon, lat);
      if (dist(px, py, x, y) <= layer.radius) {
        return { feature: f.properties, type: layer.type };
      }
    }
  }

  // Check pipelines
  if (visibility.pipelines && assets.pipelines) {
    for (const f of assets.pipelines.features) {
      const coords = f.geometry.coordinates as number[][];
      if (!coords || coords.length < 2) continue;
      for (let i = 0; i < coords.length - 1; i++) {
        const [x1, y1] = toXY(coords[i][0], coords[i][1]);
        const [x2, y2] = toXY(coords[i + 1][0], coords[i + 1][1]);
        // Point-to-segment distance
        const dx = x2 - x1;
        const dy = y2 - y1;
        const len2 = dx * dx + dy * dy;
        if (len2 === 0) continue;
        let t = ((px - x1) * dx + (py - y1) * dy) / len2;
        t = Math.max(0, Math.min(1, t));
        const nearX = x1 + t * dx;
        const nearY = y1 + t * dy;
        if (dist(px, py, nearX, nearY) <= 8) {
          return { feature: f.properties, type: 'pipeline' };
        }
      }
    }
  }

  return null;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function GeospatialTab() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const assetsRef = useRef<GeoJSONAssets>({});
  const viewRef = useRef<ViewState>({
    centerLon: -103.5,
    centerLat: 31.8,
    zoom: 5,
  });
  const flarePhaseRef = useRef(0);
  const rafRef = useRef<number>(0);

  const [panelOpen, setPanelOpen] = useState(true);
  const [layerPanelOpen, setLayerPanelOpen] = useState(true);
  const [layerVisibility, setLayerVisibility] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(LAYERS.map((l) => [l.key, true]))
  );
  const layerVisRef = useRef(layerVisibility);
  const [layerCounts, setLayerCounts] = useState<Record<string, number>>({});
  const [selectedFeature, setSelectedFeature] = useState<Record<string, unknown> | null>(null);
  const [featureType, setFeatureType] = useState<string>('');
  const [, setAssetsLoaded] = useState(false);

  // Keep ref in sync
  useEffect(() => {
    layerVisRef.current = layerVisibility;
  }, [layerVisibility]);

  const toggleLayer = useCallback((key: string) => {
    setLayerVisibility((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  /* ---------------------------------------------------------------- */
  /*  Animation loop                                                   */
  /* ---------------------------------------------------------------- */
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const w = rect.width;
    const h = rect.height;

    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    flarePhaseRef.current += 0.05;
    drawMap(ctx, w, h, assetsRef.current, viewRef.current, layerVisRef.current, flarePhaseRef.current);

    rafRef.current = requestAnimationFrame(render);
  }, []);

  /* ---------------------------------------------------------------- */
  /*  Fetch assets                                                     */
  /* ---------------------------------------------------------------- */
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/map/geospatial/assets');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: GeoJSONAssets = await res.json();
        assetsRef.current = data;

        const counts: Record<string, number> = {};
        for (const l of LAYERS) {
          counts[l.key] = data[l.key]?.features?.length ?? 0;
        }
        setLayerCounts(counts);
        setAssetsLoaded(true);
      } catch {
        console.warn('Could not fetch geospatial assets');
      }
    })();
  }, []);

  /* ---------------------------------------------------------------- */
  /*  Canvas setup + interaction                                       */
  /* ---------------------------------------------------------------- */
  useEffect(() => {
    rafRef.current = requestAnimationFrame(render);

    const canvas = canvasRef.current;
    if (!canvas) return;

    // Pan
    let dragging = false;
    let lastX = 0;
    let lastY = 0;

    const onMouseDown = (e: MouseEvent) => {
      dragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
      canvas.style.cursor = 'grabbing';
    };

    const onMouseMove = (e: MouseEvent) => {
      if (!dragging) return;
      const dx = e.clientX - lastX;
      const dy = e.clientY - lastY;
      lastX = e.clientX;
      lastY = e.clientY;
      const scale = Math.pow(2, viewRef.current.zoom) * 80;
      viewRef.current.centerLon -= dx / scale;
      viewRef.current.centerLat += dy / scale;
    };

    const onMouseUp = () => {
      dragging = false;
      canvas.style.cursor = 'crosshair';
    };

    // Zoom
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const delta = -e.deltaY * 0.002;
      viewRef.current.zoom = Math.max(1, Math.min(14, viewRef.current.zoom + delta));
    };

    // Click
    const onClick = (e: MouseEvent) => {
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const px = e.clientX - rect.left;
      const py = e.clientY - rect.top;
      const w = rect.width;
      const h = rect.height;

      const hit = hitTest(px, py, assetsRef.current, viewRef.current, w, h, layerVisRef.current);
      if (hit) {
        setSelectedFeature(hit.feature);
        setFeatureType(hit.type);
        if (!panelOpen) setPanelOpen(true);
      } else {
        setSelectedFeature(null);
        setFeatureType('');
      }
    };

    canvas.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    canvas.addEventListener('wheel', onWheel, { passive: false });
    canvas.addEventListener('click', onClick);
    canvas.style.cursor = 'crosshair';

    return () => {
      cancelAnimationFrame(rafRef.current);
      canvas.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      canvas.removeEventListener('wheel', onWheel);
      canvas.removeEventListener('click', onClick);
    };
  }, [render, panelOpen]);

  /* ---------------------------------------------------------------- */
  /*  Render                                                           */
  /* ---------------------------------------------------------------- */
  return (
    <div className="geo-layout">
      {/* --- Map --- */}
      <div className="map-container" ref={containerRef}>
        <canvas
          ref={canvasRef}
          style={{ width: '100%', height: '100%', display: 'block' }}
        />

        {/* Layer toggle */}
        <div className="layer-toggle-panel">
          <div
            className="layer-toggle-header"
            onClick={() => setLayerPanelOpen((v) => !v)}
          >
            <span>Layers</span>
            <span className={`chevron ${layerPanelOpen ? '' : 'collapsed'}`}>&#9660;</span>
          </div>
          <div className={`layer-toggle-body ${layerPanelOpen ? '' : 'collapsed'}`}>
            {LAYERS.map((l) => (
              <label key={l.key} className="layer-toggle-item">
                <input
                  type="checkbox"
                  checked={layerVisibility[l.key]}
                  onChange={() => toggleLayer(l.key)}
                />
                <span className="layer-color-dot" style={{ background: l.color }} />
                <span>{l.label}</span>
                <span className="layer-count">{layerCounts[l.key] ?? 0}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Panel toggle button */}
        <button
          className={`panel-toggle-btn ${panelOpen ? '' : 'panel-collapsed'}`}
          onClick={() => setPanelOpen((v) => !v)}
          title={panelOpen ? 'Close panel' : 'Open panel'}
        >
          {panelOpen ? '\u25B6' : '\u25C0'}
        </button>
      </div>

      {/* --- Right Panel --- */}
      <div className={`right-panel ${panelOpen ? '' : 'collapsed'}`}>
        <AgentPanel selectedFeature={selectedFeature} featureType={featureType} />
      </div>
    </div>
  );
}
