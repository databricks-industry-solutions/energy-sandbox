// === Core CO2-EOR Types ===

export type WellType = 'producer' | 'injector' | 'WAG' | 'monitor' | 'disposal';
export type WellStatus = 'active' | 'shut_in' | 'drilling' | 'completing' | 'workover' | 'P&A';
export type FluidType = 'oil' | 'gas' | 'water' | 'CO2' | 'NGL';
export type FacilityType = 'CPF' | 'satellite' | 'CO2_recycle' | 'compression' | 'SWD' | 'gas_plant';
export type PipelineProduct = 'oil' | 'gas' | 'water' | 'CO2' | 'NGL' | 'mixed';
export type FleetType = 'truck' | 'frac_fleet' | 'rig' | 'workover' | 'pump_truck' | 'wireline' | 'coiled_tubing';
export type AgentRole = 'monitoring' | 'optimization' | 'maintenance' | 'commercial' | 'orchestrator';
export type AutonomyLevel = 'advisory' | 'supervised' | 'autonomous';
export type ShiftType = 'day' | 'night';
export type AlertSeverity = 'info' | 'warning' | 'critical' | 'emergency';

export interface GeoPoint {
  lat: number;
  lon: number;
}

export interface Well extends GeoPoint {
  id: string;
  name: string;
  type: WellType;
  status: WellStatus;
  patternId: string;        // injection pattern group
  padId: string;
  oilRate: number;          // bbl/d
  gasRate: number;          // mcf/d
  waterRate: number;        // bbl/d
  co2InjRate: number;       // mcf/d (for injectors)
  waterInjRate: number;     // bbl/d (for WAG/injectors)
  chokePercent: number;     // 0-100
  tubingPressure: number;   // psi
  casingPressure: number;   // psi
  bottomholePressure: number; // psi
  co2Concentration: number; // mol% in produced gas
  gor: number;              // gas-oil ratio scf/bbl
  waterCut: number;         // fraction 0-1
  lastTestDate: string;     // ISO date
  // Reservoir
  reservoirZone: string;
  perforationTop: number;   // ft
  perforationBottom: number; // ft
}

export interface InjectionPattern {
  id: string;
  name: string;
  type: '5-spot' | '9-spot' | 'line_drive' | 'inverted_5spot';
  producerIds: string[];
  injectorIds: string[];
  monitorIds: string[];
  currentPhase: 'CO2_injection' | 'water_injection' | 'soak' | 'production';
  cycleNumber: number;
  targetPressure: number;   // psi
  currentPressure: number;  // psi
  co2Slug: number;          // MCF cumulative
  waterSlug: number;        // BBL cumulative
  estimatedBreakthrough: string; // ISO date
}

export interface Pad extends GeoPoint {
  id: string;
  name: string;
  facilityId: string;
  wellIds: string[];
}

export interface Facility extends GeoPoint {
  id: string;
  name: string;
  type: FacilityType;
  oilCapacity: number;      // bbl/d
  gasCapacity: number;      // mcf/d
  waterCapacity: number;    // bbl/d
  co2Capacity: number;      // mcf/d (for recycle plants)
  currentOilRate: number;
  currentGasRate: number;
  currentWaterRate: number;
  currentCO2Rate: number;
  utilization: number;      // fraction 0-1
  emissions: number;        // tCO2e/d
}

export interface Pipeline {
  id: string;
  name: string;
  fromId: string;           // facility or well
  toId: string;
  coordinates: [number, number][]; // [lon, lat] pairs for GeoJSON
  capacity: number;
  currentFlow: number;
  product: PipelineProduct;
  pressure: number;         // psi
  diameter: number;         // inches
}

export interface CO2Source {
  id: string;
  name: string;
  type: 'anthropogenic' | 'natural' | 'DAC';
  lat: number;
  lon: number;
  deliveryRate: number;     // mcf/d
  contractedRate: number;   // mcf/d
  purity: number;           // fraction
  cost: number;             // $/mcf
}

export interface MonitoringPoint extends GeoPoint {
  id: string;
  name: string;
  type: 'seismic' | 'pressure' | 'soil_gas' | 'groundwater' | 'tiltmeter';
  value: number;
  unit: string;
  threshold: number;
  status: 'normal' | 'warning' | 'alarm';
}

export interface FlarePoint extends GeoPoint {
  id: string;
  facilityId: string;
  currentRate: number;      // mcf/d
  maxRate: number;
  status: 'active' | 'standby' | 'offline';
}

export interface FleetAsset extends GeoPoint {
  id: string;
  type: FleetType;
  status: 'available' | 'en_route' | 'on_site' | 'maintenance';
  assignedTo: string | null;
  eta: string | null;       // ISO datetime
}

export interface Alert {
  id: string;
  timestamp: string;
  severity: AlertSeverity;
  source: string;           // entity ID
  sourceType: 'well' | 'facility' | 'pipeline' | 'pattern' | 'monitor' | 'agent';
  message: string;
  acknowledged: boolean;
  acknowledgedBy: string | null;
}

export interface ShiftLog {
  id: string;
  shift: ShiftType;
  date: string;
  operator: string;
  entries: ShiftLogEntry[];
}

export interface ShiftLogEntry {
  timestamp: string;
  category: 'operations' | 'safety' | 'maintenance' | 'agent_action' | 'handoff';
  message: string;
  entityId: string | null;
  agentId: string | null;
}

// KPI types
export interface ProductionKPI {
  totalOil: number;         // bbl/d
  totalGas: number;         // mcf/d
  totalWater: number;       // bbl/d
  co2Injected: number;      // mcf/d
  co2Recycled: number;      // mcf/d
  co2Purchased: number;     // mcf/d
  co2Utilization: number;   // fraction recycled/total
  incrementalOil: number;   // bbl/d above baseline
  gor: number;              // field average
  waterCut: number;         // field average
  uptime: number;           // fraction
}

export interface EconomicsKPI {
  revenue: number;          // $/d
  opex: number;             // $/d
  co2Cost: number;          // $/d
  netback: number;          // $/boe
  incrementalNetback: number; // $/boe for EOR increment
  co2CostPerBoe: number;
  breakeven: number;        // $/bbl WTI
}

export interface EnvironmentalKPI {
  co2Stored: number;        // tCO2/d net stored
  co2Emitted: number;       // tCO2e/d
  flaring: number;          // mcf/d
  carbonIntensity: number;  // kgCO2e/boe
  methaneLeaks: number;     // detected count
  complianceScore: number;  // 0-100
}

// Agent types
export interface AgentState {
  id: string;
  role: AgentRole;
  status: 'idle' | 'thinking' | 'proposing' | 'executing' | 'error';
  autonomyLevel: AutonomyLevel;
  lastAction: string;
  lastActionTime: string;
  pendingProposals: AgentProposal[];
  actionHistory: AgentAction[];
}

export interface AgentProposal {
  id: string;
  agentId: string;
  timestamp: string;
  title: string;
  description: string;
  impact: string;
  risk: 'low' | 'medium' | 'high';
  affectedEntities: string[];
  status: 'pending' | 'approved' | 'rejected' | 'executed';
  approvedBy: string | null;
}

export interface AgentAction {
  id: string;
  agentId: string;
  timestamp: string;
  action: string;
  result: string;
  entities: string[];
}

// Top-level state
export interface TwinState {
  wells: Well[];
  patterns: InjectionPattern[];
  pads: Pad[];
  facilities: Facility[];
  pipelines: Pipeline[];
  co2Sources: CO2Source[];
  monitoringPoints: MonitoringPoint[];
  flares: FlarePoint[];
  fleet: FleetAsset[];
  alerts: Alert[];
  shiftLog: ShiftLog;
  agents: AgentState[];
  kpis: {
    production: ProductionKPI;
    economics: EconomicsKPI;
    environmental: EnvironmentalKPI;
  };
}
