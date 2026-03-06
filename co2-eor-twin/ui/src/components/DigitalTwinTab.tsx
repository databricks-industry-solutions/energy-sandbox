import { useState, useEffect, useCallback } from 'react';

/* ================================================================
   Digital Twin Schematic — P&ID-style interactive SVG
   BOP Guardian HMI visual style: realistic equipment shapes,
   health-colored borders, status dots, live readouts.
   ================================================================ */

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface Well {
  id: string; name: string; type: string; status: string;
  patternId: string; padId: string;
  oilRate: number; gasRate: number; waterRate: number;
  co2InjRate: number; waterInjRate: number;
  chokePercent: number; tubingPressure: number; casingPressure: number;
  bottomholePressure: number; co2Concentration: number;
  gor: number; waterCut: number; reservoirZone: string;
}

interface InjectionPattern {
  id: string; name: string; type: string;
  producerIds: string[]; injectorIds: string[]; monitorIds: string[];
  currentPhase: string; cycleNumber: number;
  targetPressure: number; currentPressure: number;
  co2Slug: number; waterSlug: number; estimatedBreakthrough: string;
}

interface Pad {
  id: string; name: string; facilityId: string; wellIds: string[];
}

interface Facility {
  id: string; name: string; type: string;
  oilCapacity: number; gasCapacity: number; waterCapacity: number; co2Capacity: number;
  currentOilRate: number; currentGasRate: number; currentWaterRate: number; currentCO2Rate: number;
  utilization: number; emissions: number;
}

interface Pipeline {
  id: string; name: string; fromId: string; toId: string;
  capacity: number; currentFlow: number; product: string;
  pressure: number; diameter: number;
}

interface CO2Source {
  id: string; name: string; type: string;
  deliveryRate: number; contractedRate: number; purity: number; cost: number;
}

interface FlarePoint {
  id: string; facilityId: string;
  currentRate: number; maxRate: number; status: string;
}

interface MonitoringPoint {
  id: string; name: string; type: string;
  value: number; threshold: number; status: string;
}

interface TwinData {
  wells: Well[]; patterns: InjectionPattern[]; pads: Pad[];
  facilities: Facility[]; pipelines: Pipeline[];
  co2Sources: CO2Source[]; flares: FlarePoint[];
  monitoringPoints: MonitoringPoint[];
}

type Selected =
  | { kind: 'well'; data: Well }
  | { kind: 'pattern'; data: InjectionPattern }
  | { kind: 'facility'; data: Facility }
  | { kind: 'pipeline'; data: Pipeline }
  | { kind: 'co2source'; data: CO2Source }
  | { kind: 'flare'; data: FlarePoint }
  | { kind: 'monitor'; data: MonitoringPoint }
  | null;

/* ------------------------------------------------------------------ */
/*  Colors                                                             */
/* ------------------------------------------------------------------ */

const C = {
  bg: '#0d1117',
  panel: '#161b22',
  border: '#30363d',
  text: '#e6edf3',
  muted: '#6e7681',
  cyan: '#06b6d4',
  green: '#10b981',
  red: '#ef4444',
  yellow: '#f59e0b',
  orange: '#f97316',
  blue: '#3b82f6',
  purple: '#a855f7',
  // Equipment
  steel: '#475569',
  steelDark: '#334155',
  pipe: '#64748b',
};

function healthColor(util: number): string {
  if (util >= 0.85) return C.yellow;
  if (util >= 0.60) return C.green;
  return C.green;
}

function wellColor(type: string): string {
  switch (type) {
    case 'producer': return C.green;
    case 'injector': return C.cyan;
    case 'WAG': return C.purple;
    case 'monitor': return C.muted;
    case 'disposal': return C.orange;
    default: return C.muted;
  }
}

/* ------------------------------------------------------------------ */
/*  SVG Equipment Drawing Functions                                    */
/* ------------------------------------------------------------------ */

/** Christmas-tree wellhead with master valve, wing valves, and choke */
function WellheadSVG({
  x, y, well, isSelected, onClick,
}: {
  x: number; y: number; well: Well; isSelected: boolean;
  onClick: () => void;
}) {
  const c = wellColor(well.type);
  const sw = isSelected ? 2.5 : 1.5;
  const fo = isSelected ? 0.15 : 0.06;

  // Dimensions
  const casingW = 24;
  const casingH = 36;
  const tubingW = 10;
  const masterValveH = 8;
  const wingLen = 16;

  return (
    <g onClick={onClick} style={{ cursor: 'pointer' }}>
      {/* Selection glow */}
      {isSelected && (
        <rect x={x - casingW/2 - 6} y={y - 4} width={casingW + 12} height={casingH + 40}
          rx={4} fill={c} fillOpacity={0.08} stroke={c} strokeWidth={0.5} />
      )}

      {/* Casing head — wide base */}
      <rect x={x - casingW/2} y={y + 20} width={casingW} height={casingH}
        rx={2} fill={c} fillOpacity={fo} stroke={c} strokeWidth={sw} />

      {/* Bore wall lines inside casing */}
      <line x1={x - tubingW/2} y1={y + 22} x2={x - tubingW/2} y2={y + 20 + casingH - 2}
        stroke={C.steel} strokeWidth={1} opacity={0.4} />
      <line x1={x + tubingW/2} y1={y + 22} x2={x + tubingW/2} y2={y + 20 + casingH - 2}
        stroke={C.steel} strokeWidth={1} opacity={0.4} />

      {/* Master valve (bowtie at top of casing) */}
      <polygon
        points={`${x-8},${y+14} ${x},${y+14+masterValveH/2} ${x-8},${y+14+masterValveH}
                 ${x+8},${y+14} ${x},${y+14+masterValveH/2} ${x+8},${y+14+masterValveH}`}
        fill={c} fillOpacity={0.3} stroke={c} strokeWidth={1} />

      {/* Wing valves (horizontal stubs) */}
      <line x1={x - casingW/2} y1={y + 30} x2={x - casingW/2 - wingLen} y2={y + 30}
        stroke={c} strokeWidth={2.5} />
      <polygon
        points={`${x - casingW/2 - wingLen/2 - 3},${y+27} ${x - casingW/2 - wingLen/2},${y+30}
                 ${x - casingW/2 - wingLen/2 - 3},${y+33} ${x - casingW/2 - wingLen/2 + 3},${y+27}
                 ${x - casingW/2 - wingLen/2},${y+30} ${x - casingW/2 - wingLen/2 + 3},${y+33}`}
        fill={c} fillOpacity={0.3} stroke={c} strokeWidth={0.6} />

      <line x1={x + casingW/2} y1={y + 30} x2={x + casingW/2 + wingLen} y2={y + 30}
        stroke={c} strokeWidth={2.5} />
      <polygon
        points={`${x + casingW/2 + wingLen/2 - 3},${y+27} ${x + casingW/2 + wingLen/2},${y+30}
                 ${x + casingW/2 + wingLen/2 - 3},${y+33} ${x + casingW/2 + wingLen/2 + 3},${y+27}
                 ${x + casingW/2 + wingLen/2},${y+30} ${x + casingW/2 + wingLen/2 + 3},${y+33}`}
        fill={c} fillOpacity={0.3} stroke={c} strokeWidth={0.6} />

      {/* Tubing above master valve */}
      <rect x={x - tubingW/2} y={y} width={tubingW} height={14}
        fill={c} fillOpacity={fo} stroke={c} strokeWidth={1} />

      {/* Choke valve at very top */}
      <circle cx={x} cy={y - 3} r={4} fill={c} fillOpacity={0.25}
        stroke={c} strokeWidth={1.2} />

      {/* Flange at bottom */}
      <rect x={x - casingW/2 - 3} y={y + 20 + casingH} width={casingW + 6} height={4}
        rx={1} fill={C.bg} stroke={C.steelDark} strokeWidth={0.8} />
      {/* Bolt circles on flange */}
      <circle cx={x - casingW/2} cy={y + 20 + casingH + 2} r={1.5} fill={C.steel} />
      <circle cx={x + casingW/2} cy={y + 20 + casingH + 2} r={1.5} fill={C.steel} />

      {/* Status dot */}
      {well.status === 'alarm' && (
        <circle cx={x + casingW/2 + 2} cy={y} r={4} fill={C.red} opacity={0.9}>
          <animate attributeName="opacity" values="1;0.3;1" dur="0.8s" repeatCount="indefinite" />
        </circle>
      )}

      {/* Well ID label */}
      <text x={x} y={y + 20 + casingH + 18} textAnchor="middle"
        fill={isSelected ? C.text : C.muted} fontSize="7" fontWeight="600"
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
        {well.id}
      </text>

      {/* Rate readout */}
      {well.type === 'producer' && (
        <text x={x} y={y + 20 + casingH + 28} textAnchor="middle"
          fill={C.green} fontSize="7" fontWeight="700"
          style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
          {well.oilRate}b/d
        </text>
      )}
      {(well.type === 'injector' || well.type === 'WAG') && (
        <text x={x} y={y + 20 + casingH + 28} textAnchor="middle"
          fill={C.cyan} fontSize="7" fontWeight="700"
          style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
          {well.co2InjRate}M/d
        </text>
      )}
      {well.type === 'disposal' && (
        <text x={x} y={y + 20 + casingH + 28} textAnchor="middle"
          fill={C.orange} fontSize="7" fontWeight="700"
          style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
          {well.waterInjRate}b/d
        </text>
      )}
      {well.type === 'monitor' && (
        <text x={x} y={y + 20 + casingH + 28} textAnchor="middle"
          fill={C.muted} fontSize="7" fontWeight="700"
          style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
          {well.bottomholePressure}psi
        </text>
      )}

      {/* Pressure readout (right side) */}
      <text x={x + casingW/2 + wingLen + 4} y={y + 18} textAnchor="start"
        fill={C.cyan} fontSize="7" fontWeight="700"
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
        {well.tubingPressure}psi
      </text>
    </g>
  );
}

/** Horizontal separator vessel (CPF) */
function SeparatorSVG({
  x, y, fac, isSelected, onClick,
}: {
  x: number; y: number; fac: Facility; isSelected: boolean;
  onClick: () => void;
}) {
  const hc = healthColor(fac.utilization);
  const sw = isSelected ? 2.5 : 1.5;
  const W = 280;
  const H = 90;
  const headR = 28;

  return (
    <g onClick={onClick} style={{ cursor: 'pointer' }}>
      {/* Vessel body */}
      <rect x={x + headR} y={y} width={W - headR * 2} height={H}
        fill={hc} fillOpacity={isSelected ? 0.12 : 0.05}
        stroke={hc} strokeWidth={sw} />
      {/* Left elliptical head */}
      <ellipse cx={x + headR} cy={y + H/2} rx={headR} ry={H/2}
        fill={hc} fillOpacity={isSelected ? 0.12 : 0.05}
        stroke={hc} strokeWidth={sw} />
      {/* Right elliptical head */}
      <ellipse cx={x + W - headR} cy={y + H/2} rx={headR} ry={H/2}
        fill={hc} fillOpacity={isSelected ? 0.12 : 0.05}
        stroke={hc} strokeWidth={sw} />

      {/* Internal weir plates */}
      <line x1={x + W * 0.35} y1={y + 12} x2={x + W * 0.35} y2={y + H - 5}
        stroke={hc} strokeWidth={0.8} opacity={0.3} strokeDasharray="4 2" />
      <line x1={x + W * 0.65} y1={y + 12} x2={x + W * 0.65} y2={y + H - 5}
        stroke={hc} strokeWidth={0.8} opacity={0.3} strokeDasharray="4 2" />

      {/* Zone labels inside */}
      <text x={x + W * 0.17} y={y + H/2 + 3} textAnchor="middle"
        fill={C.green} fontSize="9" fontWeight="600" opacity={0.6}
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>OIL</text>
      <text x={x + W * 0.5} y={y + H/2 + 3} textAnchor="middle"
        fill={C.blue} fontSize="9" fontWeight="600" opacity={0.6}
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>WATER</text>
      <text x={x + W * 0.83} y={y + H/2 + 3} textAnchor="middle"
        fill={C.red} fontSize="9" fontWeight="600" opacity={0.6}
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>GAS</text>

      {/* Level indicator (left side) — shows utilization */}
      <rect x={x + 6} y={y + 8} width={6} height={H - 16}
        fill="none" stroke={hc} strokeWidth={0.6} opacity={0.4} rx={1} />
      <rect x={x + 7} y={y + 8 + (H - 16) * (1 - fac.utilization)}
        width={4} height={(H - 16) * fac.utilization}
        fill={hc} opacity={0.5} rx={1} />

      {/* Inlet nozzle (top-left) */}
      <rect x={x + headR + 20} y={y - 12} width={12} height={14}
        fill={C.bg} stroke={C.steel} strokeWidth={1} />
      <rect x={x + headR + 17} y={y - 14} width={18} height={4}
        rx={1} fill={C.bg} stroke={C.steelDark} strokeWidth={0.8} />

      {/* Outlet nozzles (bottom) */}
      <rect x={x + W * 0.35 - 6} y={y + H} width={12} height={10}
        fill={C.bg} stroke={C.steel} strokeWidth={1} />
      <rect x={x + W * 0.65 - 6} y={y + H} width={12} height={10}
        fill={C.bg} stroke={C.steel} strokeWidth={1} />

      {/* Gas outlet (top-right) */}
      <rect x={x + W - headR - 30} y={y - 12} width={12} height={14}
        fill={C.bg} stroke={C.steel} strokeWidth={1} />

      {/* Name and data */}
      <text x={x + W/2} y={y - 20} textAnchor="middle"
        fill={C.text} fontSize="12" fontWeight="700"
        style={{ fontFamily: '-apple-system, sans-serif', pointerEvents: 'none' }}>
        {fac.name}
      </text>

      {/* Readouts below */}
      <text x={x + 4} y={y + H + 24} fill={C.green} fontSize="9" fontWeight="600"
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
        Oil:{fac.currentOilRate}/{fac.oilCapacity}
      </text>
      <text x={x + 110} y={y + H + 24} fill={C.red} fontSize="9" fontWeight="600"
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
        Gas:{fac.currentGasRate}/{fac.gasCapacity}
      </text>
      <text x={x + 4} y={y + H + 36} fill={C.blue} fontSize="9" fontWeight="600"
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
        Water:{fac.currentWaterRate}/{fac.waterCapacity}
      </text>
      <text x={x + 110} y={y + H + 36} fill={C.muted} fontSize="9"
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
        {Math.round(fac.utilization * 100)}% util | {fac.emissions}tCO&#x2082;e
      </text>
    </g>
  );
}

/** Compressor station — motor + cylinder */
function CompressorSVG({
  x, y, fac, isSelected, onClick,
}: {
  x: number; y: number; fac: Facility; isSelected: boolean;
  onClick: () => void;
}) {
  const hc = healthColor(fac.utilization);
  const sw = isSelected ? 2.5 : 1.5;

  return (
    <g onClick={onClick} style={{ cursor: 'pointer' }}>
      {/* Motor housing */}
      <rect x={x} y={y} width={90} height={60} rx={4}
        fill={hc} fillOpacity={isSelected ? 0.12 : 0.05}
        stroke={hc} strokeWidth={sw} />
      {/* Motor windings (decorative circles) */}
      <circle cx={x + 30} cy={y + 30} r={18} fill="none" stroke={hc}
        strokeWidth={0.6} opacity={0.3} />
      <circle cx={x + 30} cy={y + 30} r={10} fill="none" stroke={hc}
        strokeWidth={0.6} opacity={0.2} />
      <text x={x + 30} y={y + 34} textAnchor="middle" fill={hc}
        fontSize="10" fontWeight="700" opacity={0.5}
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>M</text>

      {/* Shaft coupling */}
      <rect x={x + 90} y={y + 22} width={16} height={16} rx={2}
        fill={C.steel} fillOpacity={0.3} stroke={C.steel} strokeWidth={1} />
      <line x1={x + 98} y1={y + 24} x2={x + 98} y2={y + 36}
        stroke={hc} strokeWidth={1} opacity={0.4} />

      {/* Cylinder */}
      <rect x={x + 106} y={y + 5} width={70} height={50} rx={6}
        fill={hc} fillOpacity={isSelected ? 0.12 : 0.05}
        stroke={hc} strokeWidth={sw} />
      {/* Cylinder head */}
      <rect x={x + 170} y={y + 10} width={10} height={40} rx={3}
        fill={hc} fillOpacity={0.15} stroke={hc} strokeWidth={1} />
      {/* Piston rod */}
      <line x1={x + 108} y1={y + 30} x2={x + 168} y2={y + 30}
        stroke={hc} strokeWidth={2} opacity={0.3} />
      {/* Suction / discharge nozzles */}
      <rect x={x + 120} y={y - 8} width={10} height={14}
        fill={C.bg} stroke={C.steel} strokeWidth={1} />
      <rect x={x + 150} y={y + 50} width={10} height={14}
        fill={C.bg} stroke={C.steel} strokeWidth={1} />

      {/* Cooling fins on cylinder */}
      {[0, 8, 16, 24, 32].map((dx) => (
        <line key={dx} x1={x + 115 + dx} y1={y + 7} x2={x + 115 + dx} y2={y + 53}
          stroke={hc} strokeWidth={0.4} opacity={0.2} />
      ))}

      {/* Name */}
      <text x={x + 90} y={y - 14} textAnchor="middle"
        fill={C.text} fontSize="12" fontWeight="700"
        style={{ fontFamily: '-apple-system, sans-serif', pointerEvents: 'none' }}>
        {fac.name}
      </text>

      {/* Readouts */}
      <text x={x} y={y + 76} fill={C.cyan} fontSize="9" fontWeight="600"
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
        CO&#x2082;:{fac.currentCO2Rate}/{fac.co2Capacity} Mcf/d
      </text>
      <text x={x} y={y + 88} fill={C.muted} fontSize="9"
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
        {Math.round(fac.utilization * 100)}% util | {fac.emissions}tCO&#x2082;e
      </text>
    </g>
  );
}

/** CO₂ recycle — absorption column / tower */
function RecycleTowerSVG({
  x, y, fac, isSelected, onClick,
}: {
  x: number; y: number; fac: Facility; isSelected: boolean;
  onClick: () => void;
}) {
  const hc = healthColor(fac.utilization);
  const sw = isSelected ? 2.5 : 1.5;
  const W = 50;
  const H = 120;

  return (
    <g onClick={onClick} style={{ cursor: 'pointer' }}>
      {/* Tower body */}
      <rect x={x} y={y + 15} width={W} height={H} rx={6}
        fill={hc} fillOpacity={isSelected ? 0.12 : 0.05}
        stroke={hc} strokeWidth={sw} />
      {/* Dome top */}
      <ellipse cx={x + W/2} cy={y + 15} rx={W/2} ry={15}
        fill={hc} fillOpacity={isSelected ? 0.12 : 0.05}
        stroke={hc} strokeWidth={sw} />
      {/* Bottom dish */}
      <ellipse cx={x + W/2} cy={y + 15 + H} rx={W/2} ry={10}
        fill={hc} fillOpacity={isSelected ? 0.12 : 0.05}
        stroke={hc} strokeWidth={sw} />

      {/* Trays / packing (horizontal lines) */}
      {[0.2, 0.35, 0.5, 0.65, 0.8].map((frac) => (
        <line key={frac}
          x1={x + 6} y1={y + 15 + H * frac}
          x2={x + W - 6} y2={y + 15 + H * frac}
          stroke={hc} strokeWidth={0.8} opacity={0.25} />
      ))}

      {/* Inlet nozzle (middle-right) */}
      <rect x={x + W} y={y + 15 + H * 0.4} width={12} height={8}
        fill={C.bg} stroke={C.steel} strokeWidth={1} />
      {/* Outlet nozzle (top) */}
      <rect x={x + W/2 - 5} y={y - 5} width={10} height={10}
        fill={C.bg} stroke={C.steel} strokeWidth={1} />
      {/* Bottom outlet */}
      <rect x={x + W/2 - 5} y={y + 15 + H + 5} width={10} height={10}
        fill={C.bg} stroke={C.steel} strokeWidth={1} />

      {/* Vent line at top */}
      <line x1={x + W/2} y1={y - 5} x2={x + W/2} y2={y - 18}
        stroke={C.steel} strokeWidth={2} />
      <polygon points={`${x + W/2 - 4},${y - 18} ${x + W/2 + 4},${y - 18} ${x + W/2},${y - 24}`}
        fill={C.steel} opacity={0.5} />

      {/* Name */}
      <text x={x + W/2} y={y - 30} textAnchor="middle"
        fill={C.text} fontSize="11" fontWeight="700"
        style={{ fontFamily: '-apple-system, sans-serif', pointerEvents: 'none' }}>
        {fac.name}
      </text>

      {/* Readouts to the right */}
      <text x={x + W + 16} y={y + 40} fill={C.cyan} fontSize="9" fontWeight="600"
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
        {fac.currentCO2Rate}
      </text>
      <text x={x + W + 16} y={y + 52} fill={C.muted} fontSize="8"
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
        /{fac.co2Capacity}
      </text>
      <text x={x + W + 16} y={y + 64} fill={C.muted} fontSize="8"
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
        Mcf/d
      </text>
      <text x={x + W + 16} y={y + 82} fill={C.muted} fontSize="9"
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
        {Math.round(fac.utilization * 100)}%
      </text>
    </g>
  );
}

/** SWD — injection pump + wellhead */
function SWDSVG({
  x, y, fac, isSelected, onClick,
}: {
  x: number; y: number; fac: Facility; isSelected: boolean;
  onClick: () => void;
}) {
  const hc = healthColor(fac.utilization);
  const sw = isSelected ? 2.5 : 1.5;

  return (
    <g onClick={onClick} style={{ cursor: 'pointer' }}>
      {/* Pump body */}
      <rect x={x} y={y} width={80} height={50} rx={4}
        fill={hc} fillOpacity={isSelected ? 0.12 : 0.05}
        stroke={hc} strokeWidth={sw} />
      {/* Pump impeller symbol */}
      <circle cx={x + 40} cy={y + 25} r={16} fill="none"
        stroke={hc} strokeWidth={1} opacity={0.35} />
      <line x1={x + 40} y1={y + 9} x2={x + 40} y2={y + 41}
        stroke={hc} strokeWidth={1} opacity={0.2} />
      <line x1={x + 24} y1={y + 25} x2={x + 56} y2={y + 25}
        stroke={hc} strokeWidth={1} opacity={0.2} />
      <text x={x + 40} y={y + 29} textAnchor="middle" fill={hc}
        fontSize="10" fontWeight="700" opacity={0.5}
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>P</text>

      {/* Suction nozzle (left) */}
      <rect x={x - 10} y={y + 18} width={12} height={14}
        fill={C.bg} stroke={C.steel} strokeWidth={1} />

      {/* Discharge pipe → wellhead */}
      <line x1={x + 80} y1={y + 25} x2={x + 110} y2={y + 25}
        stroke={C.steel} strokeWidth={3} />

      {/* Wellhead (small Christmas tree) */}
      <rect x={x + 110} y={y + 10} width={18} height={30} rx={2}
        fill={hc} fillOpacity={isSelected ? 0.1 : 0.04}
        stroke={hc} strokeWidth={1.2} />
      {/* Master valve symbol */}
      <polygon
        points={`${x+114},${y+20} ${x+119},${y+25} ${x+114},${y+30}
                 ${x+124},${y+20} ${x+119},${y+25} ${x+124},${y+30}`}
        fill={hc} fillOpacity={0.3} stroke={hc} strokeWidth={0.6} />
      {/* Flange */}
      <rect x={x + 108} y={y + 40} width={22} height={4}
        rx={1} fill={C.bg} stroke={C.steelDark} strokeWidth={0.6} />
      {/* Down-hole pipe */}
      <rect x={x + 116} y={y + 44} width={6} height={16}
        fill={C.bg} stroke={C.steel} strokeWidth={0.8} />
      {/* Ground line */}
      <line x1={x + 100} y1={y + 44} x2={x + 138} y2={y + 44}
        stroke={C.muted} strokeWidth={1} strokeDasharray="3 2" />

      {/* Name */}
      <text x={x + 64} y={y - 10} textAnchor="middle"
        fill={C.text} fontSize="11" fontWeight="700"
        style={{ fontFamily: '-apple-system, sans-serif', pointerEvents: 'none' }}>
        {fac.name}
      </text>

      {/* Readouts */}
      <text x={x} y={y + 68} fill={C.blue} fontSize="9" fontWeight="600"
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
        Water:{fac.currentWaterRate}/{fac.waterCapacity} bbl/d
      </text>
      <text x={x} y={y + 80} fill={C.muted} fontSize="9"
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
        {Math.round(fac.utilization * 100)}% util
      </text>
    </g>
  );
}

/** Flare stack with animated flame */
function FlareStackSVG({
  x, y, flare, isSelected, onClick,
}: {
  x: number; y: number; flare: FlarePoint; isSelected: boolean;
  onClick: () => void;
}) {
  const isActive = flare.status === 'active';
  const c = isActive ? C.orange : C.muted;
  const sw = isSelected ? 2.5 : 1.5;

  return (
    <g onClick={onClick} style={{ cursor: 'pointer' }}>
      {/* Stack base */}
      <rect x={x - 4} y={y + 60} width={8} height={6} rx={1}
        fill={C.steelDark} stroke={C.steel} strokeWidth={0.8} />
      {/* Support legs */}
      <line x1={x - 8} y1={y + 66} x2={x} y2={y + 20}
        stroke={C.steel} strokeWidth={1.2} />
      <line x1={x + 8} y1={y + 66} x2={x} y2={y + 20}
        stroke={C.steel} strokeWidth={1.2} />
      {/* Main stack */}
      <rect x={x - 3} y={y + 8} width={6} height={52} rx={1}
        fill={c} fillOpacity={isSelected ? 0.15 : 0.08}
        stroke={c} strokeWidth={sw} />
      {/* Wind brace */}
      <line x1={x - 6} y1={y + 50} x2={x + 6} y2={y + 35}
        stroke={C.steel} strokeWidth={0.6} opacity={0.3} />

      {/* Flame tip */}
      {isActive && (
        <g>
          {/* Outer flame glow */}
          <ellipse cx={x} cy={y - 4} rx={12} ry={16} fill={C.orange} opacity={0.08}>
            <animate attributeName="ry" values="16;20;16" dur="1.5s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.08;0.15;0.08" dur="1.5s" repeatCount="indefinite" />
          </ellipse>
          {/* Inner flame */}
          <path
            d={`M${x-6},${y+8} Q${x-4},${y-8} ${x},${y-12} Q${x+4},${y-8} ${x+6},${y+8}`}
            fill={C.orange} fillOpacity={0.6} stroke={C.yellow} strokeWidth={0.8}>
            <animate attributeName="d"
              values={`M${x-6},${y+8} Q${x-4},${y-8} ${x},${y-12} Q${x+4},${y-8} ${x+6},${y+8};M${x-5},${y+8} Q${x-6},${y-10} ${x},${y-15} Q${x+6},${y-10} ${x+5},${y+8};M${x-6},${y+8} Q${x-4},${y-8} ${x},${y-12} Q${x+4},${y-8} ${x+6},${y+8}`}
              dur="2s" repeatCount="indefinite" />
          </path>
          {/* Core */}
          <ellipse cx={x} cy={y + 2} rx={3} ry={6} fill={C.yellow} opacity={0.5}>
            <animate attributeName="ry" values="6;8;6" dur="1s" repeatCount="indefinite" />
          </ellipse>
        </g>
      )}
      {!isActive && (
        <circle cx={x} cy={y + 5} r={3} fill={C.muted} opacity={0.3} />
      )}

      {/* Label */}
      <text x={x} y={y + 78} textAnchor="middle"
        fill={isSelected ? C.text : C.muted} fontSize="8" fontWeight="600"
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
        {flare.id}
      </text>
      {isActive && (
        <text x={x} y={y + 88} textAnchor="middle"
          fill={C.orange} fontSize="7" fontWeight="700"
          style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
          {flare.currentRate}Mcf/d
        </text>
      )}
    </g>
  );
}

/** CO₂ source — industrial stack / natural reservoir */
function CO2SourceSVG({
  x, y, src, isSelected, onClick,
}: {
  x: number; y: number; src: CO2Source; isSelected: boolean;
  onClick: () => void;
}) {
  const c = C.cyan;
  const sw = isSelected ? 2.5 : 1.5;
  const isNatural = src.type === 'natural';

  return (
    <g onClick={onClick} style={{ cursor: 'pointer' }}>
      {isNatural ? (
        /* Natural reservoir — dome/anticline shape */
        <g>
          <path
            d={`M${x},${y+60} L${x},${y+25} Q${x+50},${y-5} ${x+100},${y+25} L${x+100},${y+60} Z`}
            fill={c} fillOpacity={isSelected ? 0.12 : 0.05}
            stroke={c} strokeWidth={sw} />
          {/* Pore structure hints */}
          <circle cx={x + 30} cy={y + 35} r={3} fill="none" stroke={c}
            strokeWidth={0.5} opacity={0.2} />
          <circle cx={x + 55} cy={y + 28} r={4} fill="none" stroke={c}
            strokeWidth={0.5} opacity={0.2} />
          <circle cx={x + 72} cy={y + 40} r={3} fill="none" stroke={c}
            strokeWidth={0.5} opacity={0.2} />
          {/* Ground line */}
          <line x1={x - 5} y1={y + 60} x2={x + 105} y2={y + 60}
            stroke={C.muted} strokeWidth={1} strokeDasharray="3 2" />
        </g>
      ) : (
        /* Industrial / Anthropogenic — smokestack */
        <g>
          {/* Building base */}
          <rect x={x + 10} y={y + 30} width={80} height={30} rx={2}
            fill={c} fillOpacity={isSelected ? 0.12 : 0.05}
            stroke={c} strokeWidth={sw} />
          {/* Smokestack */}
          <rect x={x + 65} y={y} width={16} height={30} rx={1}
            fill={c} fillOpacity={isSelected ? 0.12 : 0.05}
            stroke={c} strokeWidth={sw} />
          {/* Stack rim */}
          <rect x={x + 62} y={y} width={22} height={4} rx={1}
            fill={C.bg} stroke={c} strokeWidth={1} />
          {/* Smoke puffs (CO₂) */}
          <circle cx={x + 73} cy={y - 8} r={5} fill={c} opacity={0.1}>
            <animate attributeName="cy" values={`${y - 8};${y - 20};${y - 8}`}
              dur="3s" repeatCount="indefinite" />
            <animate attributeName="opacity" values="0.1;0.03;0.1"
              dur="3s" repeatCount="indefinite" />
          </circle>
          {/* Windows */}
          <rect x={x + 20} y={y + 38} width={8} height={8} rx={1}
            fill={C.yellow} fillOpacity={0.15} stroke={C.yellow} strokeWidth={0.5} opacity={0.5} />
          <rect x={x + 40} y={y + 38} width={8} height={8} rx={1}
            fill={C.yellow} fillOpacity={0.15} stroke={C.yellow} strokeWidth={0.5} opacity={0.5} />
        </g>
      )}

      {/* Name */}
      <text x={x + 50} y={y + 76} textAnchor="middle"
        fill={C.text} fontSize="10" fontWeight="700"
        style={{ fontFamily: '-apple-system, sans-serif', pointerEvents: 'none' }}>
        {src.name}
      </text>
      <text x={x + 50} y={y + 88} textAnchor="middle"
        fill={c} fontSize="9" fontWeight="600"
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
        {src.deliveryRate.toLocaleString()} Mcf/d
      </text>
      <text x={x + 50} y={y + 100} textAnchor="middle"
        fill={C.muted} fontSize="8"
        style={{ fontFamily: 'monospace', pointerEvents: 'none' }}>
        ${src.cost}/Mcf | {(src.purity * 100).toFixed(0)}%
      </text>
    </g>
  );
}

/** Gate valve symbol on pipelines */
function GateValveSVG({ x, y, color }: { x: number; y: number; color: string }) {
  const s = 5;
  return (
    <g>
      <polygon
        points={`${x - s},${y - s} ${x + s},${y} ${x - s},${y + s}`}
        fill={color} fillOpacity={0.25} stroke={color} strokeWidth={0.8} />
      <polygon
        points={`${x + s},${y - s} ${x - s},${y} ${x + s},${y + s}`}
        fill={color} fillOpacity={0.25} stroke={color} strokeWidth={0.8} />
    </g>
  );
}

/** Pipeline color by product */
function pipeColor(product: string): string {
  switch (product) {
    case 'oil': return C.green;
    case 'gas': return C.red;
    case 'water': return C.blue;
    case 'CO2': return C.cyan;
    default: return C.muted;
  }
}

/* ------------------------------------------------------------------ */
/*  Layout constants                                                   */
/* ------------------------------------------------------------------ */

const VW = 1900;
const VH = 900;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function DigitalTwinTab() {
  const [data, setData] = useState<TwinData | null>(null);
  const [selected, setSelected] = useState<Selected>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch('/api/twin/state');
      if (!res.ok) return;
      const json = await res.json();
      setData({
        wells: json.wells || [],
        patterns: json.patterns || [],
        pads: json.pads || [],
        facilities: json.facilities || [],
        pipelines: json.pipelines || [],
        co2Sources: json.co2Sources || [],
        flares: json.flares || [],
        monitoringPoints: json.monitoringPoints || [],
      });
    } catch {
      console.warn('DigitalTwinTab: failed to fetch /api/twin/state');
    }
  }, []);

  useEffect(() => {
    fetchData();
    const iv = setInterval(fetchData, 15_000);
    return () => clearInterval(iv);
  }, [fetchData]);

  if (!data) {
    return (
      <div className="tab-loading">
        <div className="loading-spinner" />
        Loading schematic...
      </div>
    );
  }

  // Build lookup maps
  const wellMap = new Map(data.wells.map((w) => [w.id, w]));
  const facMap = new Map(data.facilities.map((f) => [f.id, f]));
  const padMap = new Map(data.pads.map((p) => [p.id, p]));

  // Facility references
  const cpf = data.facilities.find((f) => f.type === 'CPF');
  const co2r = data.facilities.find((f) => f.type === 'CO2_recycle');
  const comp = data.facilities.find((f) => f.type === 'compression');
  const swd = data.facilities.find((f) => f.type === 'SWD');

  // ---------- Industrial P&ID Layout ----------

  // Pattern boxes — single horizontal row
  const patBoxes: Record<string, { x: number; y: number; w: number; h: number }> = {
    'PAT-A': { x: 375, y: 72, w: 318, h: 283 },
    'PAT-B': { x: 711, y: 72, w: 258, h: 283 },
    'PAT-C': { x: 987, y: 72, w: 238, h: 283 },
    'PAT-D': { x: 1243, y: 72, w: 238, h: 283 },
  };

  // Injector positions (y=100, connect UP to CO2 injection header at y=88)
  const injectorPos: Record<string, number> = {
    'W-A05': 420, 'W-A06': 466, 'W-B05': 750, 'W-B06': 878,
    'W-C05': 1100, 'W-D05': 1356,
  };

  // Producer positions (y=240, connect DOWN to gathering header at y=340)
  const producerPos: Record<string, number> = {
    'W-A01': 400, 'W-A02': 447, 'W-A03': 565, 'W-A04': 612,
    'W-B01': 727, 'W-B02': 773, 'W-B03': 855, 'W-B04': 902,
    'W-C01': 1003, 'W-C02': 1049, 'W-C03': 1151, 'W-C04': 1197,
    'W-D01': 1259, 'W-D02': 1305, 'W-D03': 1403, 'W-D04': 1449,
  };

  // Monitoring sensor positions (near equipment)
  const monitorPos: Record<string, { x: number; y: number }> = {
    'MON-P01': { x: 389, y: 48 },
    'MON-P02': { x: 1248, y: 48 },
    'MON-S01': { x: 700, y: 58 },
    'MON-S02': { x: 850, y: 58 },
    'MON-G01': { x: 1488, y: 355 },
    'MON-G02': { x: 389, y: 355 },
    'MON-W01': { x: 1500, y: 390 },
    'MON-W02': { x: 1680, y: 845 },
  };

  // W-SWD01 standalone (near SWD, NOT inside Pattern D)
  const swdWell = data.wells.find((w) => w.id === 'W-SWD01');

  // Style helpers
  const mono = { fontFamily: 'monospace', pointerEvents: 'none' as const };
  const sans = { fontFamily: '-apple-system, sans-serif', pointerEvents: 'none' as const };

  return (
    <div className="twin-tab-layout">
      <div className="twin-svg-container">
        <svg
          viewBox={`0 0 ${VW} ${VH}`}
          className="twin-svg"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <style>{`
              .twin-edge-track { fill: none; stroke-width: 2; opacity: 0.15; }
              .twin-edge-anim { fill: none; stroke-width: 2.5; stroke-dasharray: 10 6; animation: fd 2s linear infinite; opacity: 0.7; }
              @keyframes fd { to { stroke-dashoffset: -32; } }
            `}</style>
          </defs>

          {/* Background */}
          <rect x={0} y={0} width={VW} height={VH} fill={C.bg} />

          {/* Title */}
          <text x={VW / 2} y={28} textAnchor="middle" fill={C.text}
            fontSize="16" fontWeight="700" style={sans}>
            CO&#x2082;-EOR Field P&amp;ID — Digital Twin
          </text>
          <text x={VW / 2} y={44} textAnchor="middle" fill={C.muted}
            fontSize="10" style={mono}>
            Live SCADA telemetry — click any equipment for details
          </text>

          {/* === SECTION LABELS === */}
          <text x={20} y={68} fill={C.muted} fontSize="9" fontWeight="700"
            style={{ ...mono, textTransform: 'uppercase' as const, letterSpacing: '0.1em' }}>
            CO&#x2082; SUPPLY
          </text>
          <text x={375} y={68} fill={C.muted} fontSize="9" fontWeight="700"
            style={{ ...mono, textTransform: 'uppercase' as const, letterSpacing: '0.1em' }}>
            INJECTION PATTERNS
          </text>
          <text x={1510} y={68} fill={C.muted} fontSize="9" fontWeight="700"
            style={{ ...mono, textTransform: 'uppercase' as const, letterSpacing: '0.1em' }}>
            PROCESSING &amp; EXPORT
          </text>

          {/* ============================================================ */}
          {/*  CO₂ INJECTION HEADER — horizontal cyan pipe y=88            */}
          {/* ============================================================ */}
          <line x1={358} y1={88} x2={1460} y2={88}
            stroke={C.cyan} strokeWidth={4} opacity={0.15} />
          <line x1={358} y1={88} x2={1460} y2={88}
            className="twin-edge-anim" stroke={C.cyan} strokeWidth={4} />
          <text x={362} y={82} fill={C.cyan} fontSize="7" fontWeight="600" style={mono}>
            CO&#x2082; INJECTION HEADER
          </text>

          {/* ============================================================ */}
          {/*  PRODUCTION GATHERING HEADER — horizontal green pipe y=340    */}
          {/* ============================================================ */}
          <line x1={390} y1={340} x2={1460} y2={340}
            stroke={C.green} strokeWidth={4} opacity={0.15} />
          <line x1={390} y1={340} x2={1460} y2={340}
            className="twin-edge-anim" stroke={C.green} strokeWidth={4} />
          {/* Gathering header → CPF inlet */}
          <path d="M 1460 340 H 1564 V 366" className="twin-edge-track" stroke={C.green} />
          <path d="M 1460 340 H 1564 V 366" className="twin-edge-anim" stroke={C.green} />
          <text x={394} y={334} fill={C.green} fontSize="7" fontWeight="600" style={mono}>
            PRODUCTION GATHERING HEADER
          </text>

          {/* ============================================================ */}
          {/*  CO₂ SOURCES (bottom-left)                                   */}
          {/* ============================================================ */}
          {data.co2Sources.map((src, i) => (
            <CO2SourceSVG
              key={src.id}
              x={20}
              y={430 + i * 160}
              src={src}
              isSelected={selected?.kind === 'co2source' && selected.data.id === src.id}
              onClick={() => setSelected(
                selected?.kind === 'co2source' && selected.data.id === src.id
                  ? null : { kind: 'co2source', data: src }
              )}
            />
          ))}

          {/* ============================================================ */}
          {/*  COMPRESSOR STATION                                          */}
          {/* ============================================================ */}
          {comp && (
            <CompressorSVG
              x={175}
              y={460}
              fac={comp}
              isSelected={selected?.kind === 'facility' && selected.data.id === comp.id}
              onClick={() => setSelected(
                selected?.kind === 'facility' && selected.data.id === comp.id
                  ? null : { kind: 'facility', data: comp }
              )}
            />
          )}

          {/* CO₂ Sources → Compressor (orthogonal) */}
          {/* CO2-ANTHRO outlet ~(110,453) → compressor suction (300,452) */}
          <path d="M 110 453 H 300" className="twin-edge-track" stroke={C.cyan} />
          <path d="M 110 453 H 300" className="twin-edge-anim" stroke={C.cyan} />
          <GateValveSVG x={205} y={453} color={C.cyan} />

          {/* CO2-NAT outlet ~(120,632) → compressor suction (300,542) */}
          <path d="M 120 632 H 300 V 520" className="twin-edge-track" stroke={C.cyan} />
          <path d="M 120 632 H 300 V 520" className="twin-edge-anim" stroke={C.cyan} />
          <GateValveSVG x={300} y={576} color={C.cyan} />

          {/* Compressor discharge → CO₂ Injection Trunk (up to header) */}
          <path d="M 355 524 H 358 V 88" className="twin-edge-track" stroke={C.cyan} />
          <path d="M 355 524 H 358 V 88" className="twin-edge-anim" stroke={C.cyan} />
          <GateValveSVG x={358} y={306} color={C.cyan} />
          <text x={362} y={302} fill={C.cyan} fontSize="7" style={mono}>CO&#x2082; INJ TRUNK</text>

          {/* ============================================================ */}
          {/*  PATTERN BOXES — single horizontal row                       */}
          {/* ============================================================ */}
          {data.patterns.map((pat) => {
            const box = patBoxes[pat.id];
            if (!box) return null;
            const isSel = selected?.kind === 'pattern' && selected.data.id === pat.id;

            const phaseColors: Record<string, string> = {
              CO2_injection: C.cyan,
              water_injection: C.blue,
              soak: C.yellow,
              production: C.green,
            };
            const phaseColor = phaseColors[pat.currentPhase] || C.muted;

            return (
              <g key={pat.id}>
                {/* Pattern dashed box */}
                <rect
                  x={box.x} y={box.y} width={box.w} height={box.h} rx={6}
                  fill={isSel ? '#1c2129' : C.bg}
                  stroke={isSel ? '#00d4aa' : C.border}
                  strokeWidth={isSel ? 2 : 1}
                  strokeDasharray={isSel ? 'none' : '6 3'}
                  onClick={() => setSelected(isSel ? null : { kind: 'pattern', data: pat })}
                  style={{ cursor: 'pointer' }}
                />

                {/* Pattern header */}
                <text x={box.x + 8} y={box.y + 16} fill={C.text}
                  fontSize="10" fontWeight="700" style={sans}>
                  {pat.name}
                </text>
                <text x={box.x + 8} y={box.y + 28} fill={C.muted}
                  fontSize="7.5" style={mono}>
                  {pat.type} | Cycle {pat.cycleNumber} | P:{pat.currentPressure}/{pat.targetPressure}
                </text>

                {/* Phase badge */}
                <rect x={box.x + box.w - 100} y={box.y + 4} width={92} height={16} rx={4}
                  fill={phaseColor + '22'} stroke={phaseColor + '66'} strokeWidth={1} />
                <text x={box.x + box.w - 54} y={box.y + 16} textAnchor="middle"
                  fill={phaseColor} fontSize="7" fontWeight="600" style={mono}>
                  {pat.currentPhase.replace(/_/g, ' ')}
                </text>
              </g>
            );
          })}

          {/* ============================================================ */}
          {/*  INJECTOR WELLHEADS (y=100) — connect UP to header at y=88   */}
          {/* ============================================================ */}
          {Object.entries(injectorPos).map(([wid, wx]) => {
            const w = wellMap.get(wid);
            if (!w) return null;
            const isWellSel = selected?.kind === 'well' && selected.data.id === w.id;
            return (
              <g key={wid}>
                <WellheadSVG
                  x={wx} y={100} well={w} isSelected={isWellSel}
                  onClick={() => setSelected(isWellSel ? null : { kind: 'well', data: w })}
                />
                {/* Vertical riser UP to injection header */}
                <line x1={wx} y1={97} x2={wx} y2={88}
                  stroke={wellColor(w.type)} strokeWidth={2} opacity={0.5} />
              </g>
            );
          })}

          {/* ============================================================ */}
          {/*  PRODUCER WELLHEADS (y=240) — connect DOWN to header at y=340*/}
          {/* ============================================================ */}
          {Object.entries(producerPos).map(([wid, wx]) => {
            const w = wellMap.get(wid);
            if (!w) return null;
            const isWellSel = selected?.kind === 'well' && selected.data.id === w.id;
            return (
              <g key={wid}>
                <WellheadSVG
                  x={wx} y={240} well={w} isSelected={isWellSel}
                  onClick={() => setSelected(isWellSel ? null : { kind: 'well', data: w })}
                />
                {/* Vertical drop DOWN to gathering header */}
                <line x1={wx} y1={300} x2={wx} y2={340}
                  stroke={wellColor(w.type)} strokeWidth={1.5} opacity={0.4} />
              </g>
            );
          })}

          {/* ============================================================ */}
          {/*  CPF SEPARATOR                                               */}
          {/* ============================================================ */}
          {cpf && (
            <SeparatorSVG
              x={1510}
              y={380}
              fac={cpf}
              isSelected={selected?.kind === 'facility' && selected.data.id === cpf.id}
              onClick={() => setSelected(
                selected?.kind === 'facility' && selected.data.id === cpf.id
                  ? null : { kind: 'facility', data: cpf }
              )}
            />
          )}

          {/* ============================================================ */}
          {/*  FLARE STACKS — connected to parent facilities               */}
          {/* ============================================================ */}
          {/* FLR-01: connected to CPF gas nozzle */}
          {data.flares.filter((f) => f.id === 'FLR-01').map((flr) => (
            <g key={flr.id}>
              <path d="M 1738 366 H 1810 V 361" className="twin-edge-track" stroke={C.red} />
              <path d="M 1738 366 H 1810 V 361" className="twin-edge-anim" stroke={C.red} />
              <FlareStackSVG
                x={1810} y={295}
                flare={flr}
                isSelected={selected?.kind === 'flare' && selected.data.id === flr.id}
                onClick={() => setSelected(
                  selected?.kind === 'flare' && selected.data.id === flr.id
                    ? null : { kind: 'flare', data: flr }
                )}
              />
            </g>
          ))}
          {/* FLR-02: connected to CO2R vent */}
          {data.flares.filter((f) => f.id === 'FLR-02').map((flr) => (
            <g key={flr.id}>
              <path d="M 1605 515 H 1648 V 446" className="twin-edge-track" stroke={C.orange} />
              <path d="M 1605 515 H 1648 V 446" className="twin-edge-anim" stroke={C.orange} />
              <FlareStackSVG
                x={1648} y={380}
                flare={flr}
                isSelected={selected?.kind === 'flare' && selected.data.id === flr.id}
                onClick={() => setSelected(
                  selected?.kind === 'flare' && selected.data.id === flr.id
                    ? null : { kind: 'flare', data: flr }
                )}
              />
            </g>
          ))}

          {/* ============================================================ */}
          {/*  CO₂ RECYCLE TOWER                                           */}
          {/* ============================================================ */}
          {co2r && (
            <RecycleTowerSVG
              x={1580}
              y={520}
              fac={co2r}
              isSelected={selected?.kind === 'facility' && selected.data.id === co2r.id}
              onClick={() => setSelected(
                selected?.kind === 'facility' && selected.data.id === co2r.id
                  ? null : { kind: 'facility', data: co2r }
              )}
            />
          )}

          {/* CPF → CO₂ Recycle Tower (orthogonal: gas nozzle → tower inlet) */}
          <path d="M 1738 366 V 430 H 1642 V 583" className="twin-edge-track" stroke={C.cyan} />
          <path d="M 1738 366 V 430 H 1642 V 583" className="twin-edge-anim" stroke={C.cyan} />
          <GateValveSVG x={1690} y={430} color={C.cyan} />
          <text x={1694} y={426} fill={C.cyan} fontSize="7" style={mono}>TO CO&#x2082; RECYCLE</text>

          {/* CO₂ Recycle → Compressor (recycle loop along bottom) */}
          <path d="M 1605 665 V 700 H 358 V 520"
            className="twin-edge-track" stroke={C.cyan} strokeDasharray="6 3" />
          <path d="M 1605 665 V 700 H 358 V 520"
            className="twin-edge-anim" stroke={C.cyan} />
          <GateValveSVG x={952} y={700} color={C.cyan} />
          <text x={780} y={692} fill={C.cyan} fontSize="9" fontWeight="600" opacity={0.7} style={mono}>
            CO&#x2082; RECYCLE LOOP
          </text>

          {/* ============================================================ */}
          {/*  SWD FACILITY                                                */}
          {/* ============================================================ */}
          {swd && (
            <SWDSVG
              x={1680}
              y={690}
              fac={swd}
              isSelected={selected?.kind === 'facility' && selected.data.id === swd.id}
              onClick={() => setSelected(
                selected?.kind === 'facility' && selected.data.id === swd.id
                  ? null : { kind: 'facility', data: swd }
              )}
            />
          )}

          {/* CPF → SWD water line (orthogonal) */}
          <path d="M 1608 480 V 715 H 1670" className="twin-edge-track" stroke={C.blue} />
          <path d="M 1608 480 V 715 H 1670" className="twin-edge-anim" stroke={C.blue} />
          <GateValveSVG x={1608} y={597} color={C.blue} />
          <text x={1612} y={593} fill={C.blue} fontSize="7" style={mono}>WATER TO SWD</text>

          {/* W-SWD01 — standalone disposal wellhead near SWD */}
          {swdWell && (() => {
            const isWellSel = selected?.kind === 'well' && selected.data.id === swdWell.id;
            return (
              <WellheadSVG
                x={1846} y={668} well={swdWell} isSelected={isWellSel}
                onClick={() => setSelected(isWellSel ? null : { kind: 'well', data: swdWell })}
              />
            );
          })()}

          {/* ============================================================ */}
          {/*  EXPORT PIPELINES                                            */}
          {/* ============================================================ */}
          {/* Oil Export */}
          {data.pipelines.filter((p) => p.product === 'oil' && p.toId === 'EXPORT').map((pl) => {
            const isSel = selected?.kind === 'pipeline' && selected.data.id === pl.id;
            return (
              <g key={pl.id} onClick={() => setSelected(isSel ? null : { kind: 'pipeline', data: pl })}
                style={{ cursor: 'pointer' }}>
                <path d="M 1692 480 H 1890" className="twin-edge-track" stroke={C.green}
                  strokeWidth={isSel ? 3 : 2} opacity={isSel ? 0.4 : 0.15} />
                <path d="M 1692 480 H 1890" className="twin-edge-anim" stroke={C.green}
                  strokeWidth={isSel ? 3.5 : 2.5} opacity={isSel ? 1 : 0.7} />
                <GateValveSVG x={1791} y={480} color={C.green} />
                <polygon points="1882,475 1890,480 1882,485" fill={C.green} opacity={0.6} />
                <text x={1780} y={474} textAnchor="middle" fill={C.green} fontSize="7" fontWeight="600" style={mono}>
                  OIL {pl.currentFlow.toLocaleString()}/{pl.capacity.toLocaleString()}
                </text>
              </g>
            );
          })}

          {/* Gas Export */}
          {data.pipelines.filter((p) => p.product === 'gas' && p.toId === 'EXPORT').map((pl) => {
            const isSel = selected?.kind === 'pipeline' && selected.data.id === pl.id;
            return (
              <g key={pl.id} onClick={() => setSelected(isSel ? null : { kind: 'pipeline', data: pl })}
                style={{ cursor: 'pointer' }}>
                <path d="M 1738 366 V 340 H 1890" className="twin-edge-track" stroke={C.red}
                  strokeWidth={isSel ? 3 : 2} opacity={isSel ? 0.4 : 0.15} />
                <path d="M 1738 366 V 340 H 1890" className="twin-edge-anim" stroke={C.red}
                  strokeWidth={isSel ? 3.5 : 2.5} opacity={isSel ? 1 : 0.7} />
                <GateValveSVG x={1814} y={340} color={C.red} />
                <polygon points="1882,335 1890,340 1882,345" fill={C.red} opacity={0.6} />
                <text x={1800} y={334} textAnchor="middle" fill={C.red} fontSize="7" fontWeight="600" style={mono}>
                  GAS {pl.currentFlow.toLocaleString()}/{pl.capacity.toLocaleString()}
                </text>
              </g>
            );
          })}

          {/* ============================================================ */}
          {/*  MONITORING SENSORS — positioned near relevant equipment     */}
          {/* ============================================================ */}
          {data.monitoringPoints.map((mp) => {
            const pos = monitorPos[mp.id];
            if (!pos) return null;
            const statusColor = mp.status === 'alarm' ? C.red : mp.status === 'warning' ? C.yellow : C.green;
            const isSel = selected?.kind === 'monitor' && selected.data.id === mp.id;

            return (
              <g key={mp.id}
                onClick={() => setSelected(isSel ? null : { kind: 'monitor', data: mp })}
                style={{ cursor: 'pointer' }}>
                <rect x={pos.x} y={pos.y} width={80} height={28} rx={4}
                  fill={isSel ? statusColor + '15' : C.panel}
                  stroke={statusColor} strokeWidth={isSel ? 2 : 1} />
                <circle cx={pos.x + 10} cy={pos.y + 10} r={3.5} fill={statusColor} opacity={0.9}>
                  {mp.status === 'alarm' && (
                    <animate attributeName="opacity" values="1;0.3;1" dur="0.8s" repeatCount="indefinite" />
                  )}
                </circle>
                <text x={pos.x + 18} y={pos.y + 13} fill={C.text} fontSize="7" fontWeight="600" style={mono}>
                  {mp.id}
                </text>
                <text x={pos.x + 6} y={pos.y + 24} fill={statusColor} fontSize="8" fontWeight="700" style={mono}>
                  {mp.value}/{mp.threshold}
                </text>
              </g>
            );
          })}

          {/* ============================================================ */}
          {/*  LEGEND                                                       */}
          {/* ============================================================ */}
          <g transform={`translate(20, 820)`}>
            <rect x={0} y={0} width={1860} height={64} rx={6}
              fill={C.panel} stroke={C.border} strokeWidth={0.8} />
            <text x={12} y={16} fill={C.muted} fontSize="8" fontWeight="700" style={mono}>
              WELL TYPES
            </text>

            {/* Producer */}
            <rect x={12} y={24} width={8} height={16} rx={1} fill="none" stroke={C.green} strokeWidth={1} />
            <line x1={6} y1={32} x2={26} y2={32} stroke={C.green} strokeWidth={1} />
            <text x={30} y={36} fill={C.muted} fontSize="8" style={mono}>Producer</text>

            {/* Injector */}
            <rect x={100} y={24} width={8} height={16} rx={1} fill="none" stroke={C.cyan} strokeWidth={1} />
            <line x1={94} y1={32} x2={114} y2={32} stroke={C.cyan} strokeWidth={1} />
            <text x={118} y={36} fill={C.muted} fontSize="8" style={mono}>Injector</text>

            {/* WAG */}
            <rect x={186} y={24} width={8} height={16} rx={1} fill="none" stroke={C.purple} strokeWidth={1} />
            <line x1={180} y1={32} x2={200} y2={32} stroke={C.purple} strokeWidth={1} />
            <text x={204} y={36} fill={C.muted} fontSize="8" style={mono}>WAG</text>

            {/* Monitor */}
            <rect x={250} y={24} width={8} height={16} rx={1} fill="none" stroke={C.muted} strokeWidth={1} />
            <text x={264} y={36} fill={C.muted} fontSize="8" style={mono}>Monitor</text>

            {/* Disposal */}
            <rect x={326} y={24} width={8} height={16} rx={1} fill="none" stroke={C.orange} strokeWidth={1} />
            <text x={340} y={36} fill={C.muted} fontSize="8" style={mono}>Disposal</text>

            {/* Pipeline legend */}
            <text x={440} y={16} fill={C.muted} fontSize="8" fontWeight="700" style={mono}>PIPELINES</text>
            <line x1={440} y1={32} x2={470} y2={32} stroke={C.cyan} strokeWidth={2.5} />
            <text x={476} y={36} fill={C.muted} fontSize="8" style={mono}>CO&#x2082;</text>
            <line x1={510} y1={32} x2={540} y2={32} stroke={C.green} strokeWidth={2.5} />
            <text x={546} y={36} fill={C.muted} fontSize="8" style={mono}>Oil</text>
            <line x1={572} y1={32} x2={602} y2={32} stroke={C.red} strokeWidth={2.5} />
            <text x={608} y={36} fill={C.muted} fontSize="8" style={mono}>Gas</text>
            <line x1={638} y1={32} x2={668} y2={32} stroke={C.blue} strokeWidth={2.5} />
            <text x={674} y={36} fill={C.muted} fontSize="8" style={mono}>Water</text>

            {/* Header legend */}
            <text x={750} y={16} fill={C.muted} fontSize="8" fontWeight="700" style={mono}>HEADERS</text>
            <line x1={750} y1={32} x2={810} y2={32} stroke={C.cyan} strokeWidth={4} opacity={0.4} />
            <text x={816} y={36} fill={C.muted} fontSize="8" style={mono}>CO&#x2082; Injection</text>
            <line x1={920} y1={32} x2={980} y2={32} stroke={C.green} strokeWidth={4} opacity={0.4} />
            <text x={986} y={36} fill={C.muted} fontSize="8" style={mono}>Gathering</text>

            {/* Sensor legend */}
            <text x={1080} y={16} fill={C.muted} fontSize="8" fontWeight="700" style={mono}>SENSORS</text>
            <circle cx={1086} cy={32} r={3.5} fill={C.green} />
            <text x={1094} y={36} fill={C.muted} fontSize="8" style={mono}>Normal</text>
            <circle cx={1150} cy={32} r={3.5} fill={C.yellow} />
            <text x={1158} y={36} fill={C.muted} fontSize="8" style={mono}>Warning</text>
            <circle cx={1216} cy={32} r={3.5} fill={C.red} />
            <text x={1224} y={36} fill={C.muted} fontSize="8" style={mono}>Alarm</text>

            {/* Dashed line = recycle */}
            <text x={1300} y={16} fill={C.muted} fontSize="8" fontWeight="700" style={mono}>OTHER</text>
            <line x1={1300} y1={32} x2={1340} y2={32} stroke={C.cyan} strokeWidth={2} strokeDasharray="6 3" />
            <text x={1346} y={36} fill={C.muted} fontSize="8" style={mono}>CO&#x2082; Recycle</text>
          </g>
        </svg>
      </div>

      {/* === Detail Panel === */}
      <div className="twin-detail-panel">
        {selected ? (
          <DetailView selected={selected} wellMap={wellMap} facMap={facMap} padMap={padMap} />
        ) : (
          <div className="flow-how-it-works">
            <div className="flow-how-header">P&amp;ID Schematic — Click any equipment</div>
            <div className="flow-how-cards">
              <HowCard icon={'\u2B21'} title="CO\u2082 Supply" text="Anthropogenic &amp; natural CO\u2082 sources feed the compressor station via metered pipelines with gate valves." color={C.cyan} />
              <HowCard icon={'\u26CF'} title="Wellheads" text="24 Christmas-tree wellheads across 4 injection patterns. Each shows live pressure &amp; rate readouts." color="#00d4aa" />
              <HowCard icon={'\u2699'} title="Separator &amp; Processing" text="3-phase separator (CPF), CO\u2082 recycle tower, compressor station, and SWD — all with utilization gauges." color={C.blue} />
              <HowCard icon={'\uD83D\uDD25'} title="Flares &amp; Sensors" text="Flare stacks animate when active. Monitoring sensors show status dots with alarm pulsing." color={C.red} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Detail View                                                        */
/* ------------------------------------------------------------------ */

function DetailView({
  selected,
  wellMap,
  facMap,
  padMap,
}: {
  selected: NonNullable<Selected>;
  wellMap: Map<string, Well>;
  facMap: Map<string, Facility>;
  padMap: Map<string, Pad>;
}) {
  const badgeColors: Record<string, string> = {
    well: '#00d4aa', pattern: '#f59e0b', facility: '#3b82f6',
    pipeline: '#06b6d4', co2source: '#a855f7', flare: '#ef4444', monitor: '#f59e0b',
  };
  const bc = badgeColors[selected.kind] || '#8b949e';

  function PropRow({ label, value }: { label: string; value: string | number }) {
    return (
      <div className="feature-prop-row">
        <span className="feature-prop-key">{label}</span>
        <span className="feature-prop-value">{value}</span>
      </div>
    );
  }

  switch (selected.kind) {
    case 'well': {
      const w = selected.data;
      const pad = padMap.get(w.padId);
      const fac = pad ? facMap.get(pad.facilityId) : null;
      return (
        <div className="flow-detail-card">
          <div className="flow-detail-header">
            <span className="flow-detail-title">{w.name}</span>
            <span className="flow-detail-badge" style={{ background: bc + '22', color: bc, borderColor: bc + '44' }}>
              {w.type} well
            </span>
            <span className="inline-badge green">{w.status}</span>
          </div>
          <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
            <div className="feature-props" style={{ minWidth: 200 }}>
              <PropRow label="ID" value={w.id} />
              <PropRow label="Pattern" value={w.patternId} />
              <PropRow label="Pad" value={`${w.padId} (${pad?.name || ''})`} />
              {fac && <PropRow label="Facility" value={fac.name} />}
              <PropRow label="Reservoir" value={w.reservoirZone} />
              <PropRow label="Choke" value={`${w.chokePercent}%`} />
            </div>
            <div className="feature-props" style={{ minWidth: 200 }}>
              {w.oilRate > 0 && <PropRow label="Oil Rate" value={`${w.oilRate} bbl/d`} />}
              {w.gasRate > 0 && <PropRow label="Gas Rate" value={`${w.gasRate} Mcf/d`} />}
              {w.waterRate > 0 && <PropRow label="Water Rate" value={`${w.waterRate} bbl/d`} />}
              {w.co2InjRate > 0 && <PropRow label="CO\u2082 Inj Rate" value={`${w.co2InjRate} Mcf/d`} />}
              {w.waterInjRate > 0 && <PropRow label="Water Inj" value={`${w.waterInjRate} bbl/d`} />}
              {w.co2Concentration > 0 && <PropRow label="CO\u2082 Conc" value={`${w.co2Concentration} mol%`} />}
            </div>
            <div className="feature-props" style={{ minWidth: 200 }}>
              <PropRow label="Tubing P" value={`${w.tubingPressure} psi`} />
              <PropRow label="Casing P" value={`${w.casingPressure} psi`} />
              <PropRow label="BHP" value={`${w.bottomholePressure} psi`} />
              {w.gor > 0 && <PropRow label="GOR" value={`${w.gor} scf/bbl`} />}
              {w.waterCut > 0 && <PropRow label="Water Cut" value={`${Math.round(w.waterCut * 100)}%`} />}
            </div>
          </div>
        </div>
      );
    }
    case 'pattern': {
      const p = selected.data;
      const producers = p.producerIds.map((id) => wellMap.get(id)).filter(Boolean) as Well[];
      const totalOil = producers.reduce((s, w) => s + w.oilRate, 0);
      return (
        <div className="flow-detail-card">
          <div className="flow-detail-header">
            <span className="flow-detail-title">{p.name}</span>
            <span className="flow-detail-badge" style={{ background: bc + '22', color: bc, borderColor: bc + '44' }}>
              {p.type}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
            <div className="feature-props" style={{ minWidth: 200 }}>
              <PropRow label="ID" value={p.id} />
              <PropRow label="Phase" value={p.currentPhase.replace(/_/g, ' ')} />
              <PropRow label="Cycle" value={p.cycleNumber} />
              <PropRow label="Producers" value={p.producerIds.join(', ')} />
              <PropRow label="Injectors" value={p.injectorIds.join(', ')} />
              {p.monitorIds.length > 0 && <PropRow label="Monitors" value={p.monitorIds.join(', ')} />}
            </div>
            <div className="feature-props" style={{ minWidth: 200 }}>
              <PropRow label="Current P" value={`${p.currentPressure} psi`} />
              <PropRow label="Target P" value={`${p.targetPressure} psi`} />
              <PropRow label="CO\u2082 Slug" value={`${p.co2Slug.toLocaleString()} Mcf`} />
              <PropRow label="Water Slug" value={`${p.waterSlug.toLocaleString()} bbl`} />
              <PropRow label="Total Oil" value={`${totalOil} bbl/d`} />
              <PropRow label="Breakthrough" value={p.estimatedBreakthrough} />
            </div>
          </div>
        </div>
      );
    }
    case 'facility': {
      const f = selected.data;
      return (
        <div className="flow-detail-card">
          <div className="flow-detail-header">
            <span className="flow-detail-title">{f.name}</span>
            <span className="flow-detail-badge" style={{ background: bc + '22', color: bc, borderColor: bc + '44' }}>
              {f.type}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
            <div className="feature-props" style={{ minWidth: 200 }}>
              <PropRow label="ID" value={f.id} />
              <PropRow label="Utilization" value={`${Math.round(f.utilization * 100)}%`} />
              <PropRow label="Emissions" value={`${f.emissions} tCO\u2082e/d`} />
            </div>
            <div className="feature-props" style={{ minWidth: 200 }}>
              {f.oilCapacity > 0 && <PropRow label="Oil" value={`${f.currentOilRate}/${f.oilCapacity} bbl/d`} />}
              {f.gasCapacity > 0 && <PropRow label="Gas" value={`${f.currentGasRate}/${f.gasCapacity} Mcf/d`} />}
              {f.waterCapacity > 0 && <PropRow label="Water" value={`${f.currentWaterRate}/${f.waterCapacity} bbl/d`} />}
              {f.co2Capacity > 0 && <PropRow label="CO\u2082" value={`${f.currentCO2Rate}/${f.co2Capacity} Mcf/d`} />}
            </div>
          </div>
        </div>
      );
    }
    case 'pipeline': {
      const pl = selected.data;
      return (
        <div className="flow-detail-card">
          <div className="flow-detail-header">
            <span className="flow-detail-title">{pl.name}</span>
            <span className="flow-detail-badge" style={{ background: bc + '22', color: bc, borderColor: bc + '44' }}>
              {pl.product} pipeline
            </span>
          </div>
          <div className="feature-props">
            <PropRow label="ID" value={pl.id} />
            <PropRow label="From" value={pl.fromId} />
            <PropRow label="To" value={pl.toId} />
            <PropRow label="Flow" value={`${pl.currentFlow.toLocaleString()}/${pl.capacity.toLocaleString()}`} />
            <PropRow label="Pressure" value={`${pl.pressure} psi`} />
            <PropRow label="Diameter" value={`${pl.diameter}"`} />
          </div>
        </div>
      );
    }
    case 'co2source': {
      const s = selected.data;
      return (
        <div className="flow-detail-card">
          <div className="flow-detail-header">
            <span className="flow-detail-title">{s.name}</span>
            <span className="flow-detail-badge" style={{ background: bc + '22', color: bc, borderColor: bc + '44' }}>
              {s.type} CO&#x2082;
            </span>
          </div>
          <div className="feature-props">
            <PropRow label="ID" value={s.id} />
            <PropRow label="Delivery" value={`${s.deliveryRate.toLocaleString()} Mcf/d`} />
            <PropRow label="Contracted" value={`${s.contractedRate.toLocaleString()} Mcf/d`} />
            <PropRow label="Purity" value={`${(s.purity * 100).toFixed(1)}%`} />
            <PropRow label="Cost" value={`$${s.cost}/Mcf`} />
          </div>
        </div>
      );
    }
    case 'flare': {
      const fl = selected.data;
      const fac = facMap.get(fl.facilityId);
      return (
        <div className="flow-detail-card">
          <div className="flow-detail-header">
            <span className="flow-detail-title">Flare {fl.id}</span>
            <span className="flow-detail-badge" style={{ background: bc + '22', color: bc, borderColor: bc + '44' }}>
              {fl.status}
            </span>
          </div>
          <div className="feature-props">
            <PropRow label="Facility" value={fac?.name || fl.facilityId} />
            <PropRow label="Current Rate" value={`${fl.currentRate} Mcf/d`} />
            <PropRow label="Max Rate" value={`${fl.maxRate} Mcf/d`} />
          </div>
        </div>
      );
    }
    case 'monitor': {
      const mp = selected.data;
      return (
        <div className="flow-detail-card">
          <div className="flow-detail-header">
            <span className="flow-detail-title">{mp.name}</span>
            <span className="flow-detail-badge" style={{
              background: (mp.status === 'alarm' ? C.red : mp.status === 'warning' ? C.yellow : C.green) + '22',
              color: mp.status === 'alarm' ? C.red : mp.status === 'warning' ? C.yellow : C.green,
              borderColor: (mp.status === 'alarm' ? C.red : mp.status === 'warning' ? C.yellow : C.green) + '44',
            }}>
              {mp.status}
            </span>
          </div>
          <div className="feature-props">
            <PropRow label="ID" value={mp.id} />
            <PropRow label="Type" value={mp.type} />
            <PropRow label="Value" value={mp.value} />
            <PropRow label="Threshold" value={mp.threshold} />
          </div>
        </div>
      );
    }
  }
}

/* ------------------------------------------------------------------ */
/*  How-it-works cards                                                 */
/* ------------------------------------------------------------------ */

function HowCard({ icon, title, text, color }: { icon: string; title: string; text: string; color: string }) {
  return (
    <div className="flow-how-card" style={{ borderTopColor: color }}>
      <div className="flow-how-card-icon">{icon}</div>
      <div className="flow-how-card-title">{title}</div>
      <div className="flow-how-card-text">{text}</div>
    </div>
  );
}
