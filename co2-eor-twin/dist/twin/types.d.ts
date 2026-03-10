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
    patternId: string;
    padId: string;
    oilRate: number;
    gasRate: number;
    waterRate: number;
    co2InjRate: number;
    waterInjRate: number;
    chokePercent: number;
    tubingPressure: number;
    casingPressure: number;
    bottomholePressure: number;
    co2Concentration: number;
    gor: number;
    waterCut: number;
    lastTestDate: string;
    reservoirZone: string;
    perforationTop: number;
    perforationBottom: number;
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
    targetPressure: number;
    currentPressure: number;
    co2Slug: number;
    waterSlug: number;
    estimatedBreakthrough: string;
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
    oilCapacity: number;
    gasCapacity: number;
    waterCapacity: number;
    co2Capacity: number;
    currentOilRate: number;
    currentGasRate: number;
    currentWaterRate: number;
    currentCO2Rate: number;
    utilization: number;
    emissions: number;
}
export interface Pipeline {
    id: string;
    name: string;
    fromId: string;
    toId: string;
    coordinates: [number, number][];
    capacity: number;
    currentFlow: number;
    product: PipelineProduct;
    pressure: number;
    diameter: number;
}
export interface CO2Source {
    id: string;
    name: string;
    type: 'anthropogenic' | 'natural' | 'DAC';
    lat: number;
    lon: number;
    deliveryRate: number;
    contractedRate: number;
    purity: number;
    cost: number;
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
    currentRate: number;
    maxRate: number;
    status: 'active' | 'standby' | 'offline';
}
export interface FleetAsset extends GeoPoint {
    id: string;
    type: FleetType;
    status: 'available' | 'en_route' | 'on_site' | 'maintenance';
    assignedTo: string | null;
    eta: string | null;
}
export interface Alert {
    id: string;
    timestamp: string;
    severity: AlertSeverity;
    source: string;
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
export interface ProductionKPI {
    totalOil: number;
    totalGas: number;
    totalWater: number;
    co2Injected: number;
    co2Recycled: number;
    co2Purchased: number;
    co2Utilization: number;
    incrementalOil: number;
    gor: number;
    waterCut: number;
    uptime: number;
}
export interface EconomicsKPI {
    revenue: number;
    opex: number;
    co2Cost: number;
    netback: number;
    incrementalNetback: number;
    co2CostPerBoe: number;
    breakeven: number;
}
export interface EnvironmentalKPI {
    co2Stored: number;
    co2Emitted: number;
    flaring: number;
    carbonIntensity: number;
    methaneLeaks: number;
    complianceScore: number;
}
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
