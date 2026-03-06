import {
  TwinState, Well, InjectionPattern, Pad, Facility, Pipeline,
  CO2Source, MonitoringPoint, FlarePoint, FleetAsset, Alert,
  ShiftLog, AgentState, ProductionKPI, EconomicsKPI, EnvironmentalKPI,
} from '../twin/types';

// ------------------------------------------------------------------
// Helper – Delaware Basin centre ~31.80 N, -103.50 W
// Offsets in decimal degrees (~1 mi ≈ 0.0145° lat, 0.0170° lon)
// ------------------------------------------------------------------
const BASE_LAT = 31.80;
const BASE_LON = -103.50;
const dLat = (mi: number) => mi * 0.0145;
const dLon = (mi: number) => mi * 0.0170;

// ------------------------------------------------------------------
// Wells – 24 total across 4 patterns, 6 pads
// ------------------------------------------------------------------
function createWells(): Well[] {
  const wells: Well[] = [];
  const today = '2026-03-04';

  // Pattern A – 5-spot centred ~1 mi N of base (Pad A1, A2)
  const paCentre = { lat: BASE_LAT + dLat(1), lon: BASE_LON + dLon(0) };
  const paProducers: Partial<Well>[] = [
    { id: 'W-A01', name: 'Apache 1-A Producer', lat: paCentre.lat + dLat(0.25), lon: paCentre.lon - dLon(0.25), padId: 'PAD-A1', oilRate: 185, gasRate: 480, waterRate: 620, waterCut: 0.77 },
    { id: 'W-A02', name: 'Apache 2-A Producer', lat: paCentre.lat + dLat(0.25), lon: paCentre.lon + dLon(0.25), padId: 'PAD-A1', oilRate: 210, gasRate: 560, waterRate: 540, waterCut: 0.72 },
    { id: 'W-A03', name: 'Apache 3-A Producer', lat: paCentre.lat - dLat(0.25), lon: paCentre.lon - dLon(0.25), padId: 'PAD-A2', oilRate: 145, gasRate: 390, waterRate: 710, waterCut: 0.83 },
    { id: 'W-A04', name: 'Apache 4-A Producer', lat: paCentre.lat - dLat(0.25), lon: paCentre.lon + dLon(0.25), padId: 'PAD-A2', oilRate: 165, gasRate: 420, waterRate: 680, waterCut: 0.80 },
  ];
  paProducers.forEach((p) => {
    wells.push({
      ...p as any,
      type: 'producer', status: 'active', patternId: 'PAT-A',
      co2InjRate: 0, waterInjRate: 0, chokePercent: 72,
      tubingPressure: 380, casingPressure: 120, bottomholePressure: 2850,
      co2Concentration: 42, gor: 2600, lastTestDate: today,
      reservoirZone: 'Wolfcamp A', perforationTop: 7200, perforationBottom: 7650,
    });
  });
  // Pattern A injector (centre)
  wells.push({
    id: 'W-A05', name: 'Apache 5-A Injector', lat: paCentre.lat, lon: paCentre.lon,
    type: 'injector', status: 'active', patternId: 'PAT-A', padId: 'PAD-A1',
    oilRate: 0, gasRate: 0, waterRate: 0, co2InjRate: 2200, waterInjRate: 0,
    chokePercent: 85, tubingPressure: 2800, casingPressure: 500, bottomholePressure: 3600,
    co2Concentration: 99.5, gor: 0, waterCut: 0, lastTestDate: today,
    reservoirZone: 'Wolfcamp A', perforationTop: 7180, perforationBottom: 7700,
  });
  // Pattern A monitor
  wells.push({
    id: 'W-A06', name: 'Apache OBS-A Monitor', lat: paCentre.lat + dLat(0.12), lon: paCentre.lon + dLon(0.12),
    type: 'monitor', status: 'active', patternId: 'PAT-A', padId: 'PAD-A1',
    oilRate: 0, gasRate: 0, waterRate: 0, co2InjRate: 0, waterInjRate: 0,
    chokePercent: 0, tubingPressure: 0, casingPressure: 0, bottomholePressure: 3050,
    co2Concentration: 0, gor: 0, waterCut: 0, lastTestDate: today,
    reservoirZone: 'Wolfcamp A', perforationTop: 7200, perforationBottom: 7650,
  });

  // Pattern B – inverted 5-spot, ~1 mi E (Pad B1, B2)
  const pbCentre = { lat: BASE_LAT + dLat(1), lon: BASE_LON + dLon(2) };
  const pbProducers: Partial<Well>[] = [
    { id: 'W-B01', name: 'Bravo 1-B Producer', lat: pbCentre.lat + dLat(0.25), lon: pbCentre.lon - dLon(0.25), padId: 'PAD-B1', oilRate: 220, gasRate: 610, waterRate: 480, waterCut: 0.69 },
    { id: 'W-B02', name: 'Bravo 2-B Producer', lat: pbCentre.lat + dLat(0.25), lon: pbCentre.lon + dLon(0.25), padId: 'PAD-B1', oilRate: 195, gasRate: 530, waterRate: 560, waterCut: 0.74 },
    { id: 'W-B03', name: 'Bravo 3-B Producer', lat: pbCentre.lat - dLat(0.25), lon: pbCentre.lon - dLon(0.25), padId: 'PAD-B2', oilRate: 175, gasRate: 470, waterRate: 600, waterCut: 0.77 },
    { id: 'W-B04', name: 'Bravo 4-B Producer', lat: pbCentre.lat - dLat(0.25), lon: pbCentre.lon + dLon(0.25), padId: 'PAD-B2', oilRate: 250, gasRate: 680, waterRate: 430, waterCut: 0.63 },
  ];
  pbProducers.forEach((p) => {
    wells.push({
      ...p as any,
      type: 'producer', status: 'active', patternId: 'PAT-B',
      co2InjRate: 0, waterInjRate: 0, chokePercent: 68,
      tubingPressure: 400, casingPressure: 135, bottomholePressure: 2920,
      co2Concentration: 38, gor: 2750, lastTestDate: today,
      reservoirZone: 'Wolfcamp B', perforationTop: 7800, perforationBottom: 8250,
    });
  });
  // Pattern B – 2 WAG injectors at corners
  wells.push({
    id: 'W-B05', name: 'Bravo 5-B WAG Injector', lat: pbCentre.lat, lon: pbCentre.lon - dLon(0.25),
    type: 'WAG', status: 'active', patternId: 'PAT-B', padId: 'PAD-B1',
    oilRate: 0, gasRate: 0, waterRate: 0, co2InjRate: 1800, waterInjRate: 1200,
    chokePercent: 80, tubingPressure: 2650, casingPressure: 480, bottomholePressure: 3500,
    co2Concentration: 99.2, gor: 0, waterCut: 0, lastTestDate: today,
    reservoirZone: 'Wolfcamp B', perforationTop: 7780, perforationBottom: 8300,
  });
  wells.push({
    id: 'W-B06', name: 'Bravo 6-B WAG Injector', lat: pbCentre.lat, lon: pbCentre.lon + dLon(0.25),
    type: 'WAG', status: 'active', patternId: 'PAT-B', padId: 'PAD-B2',
    oilRate: 0, gasRate: 0, waterRate: 0, co2InjRate: 1650, waterInjRate: 1100,
    chokePercent: 78, tubingPressure: 2700, casingPressure: 490, bottomholePressure: 3480,
    co2Concentration: 99.1, gor: 0, waterCut: 0, lastTestDate: today,
    reservoirZone: 'Wolfcamp B', perforationTop: 7800, perforationBottom: 8280,
  });

  // Pattern C – 5-spot, ~2 mi S (Pad C1)
  const pcCentre = { lat: BASE_LAT - dLat(1), lon: BASE_LON - dLon(0.5) };
  const pcProducers: Partial<Well>[] = [
    { id: 'W-C01', name: 'Charlie 1-C Producer', lat: pcCentre.lat + dLat(0.25), lon: pcCentre.lon - dLon(0.25), padId: 'PAD-C1', oilRate: 130, gasRate: 350, waterRate: 780, waterCut: 0.86 },
    { id: 'W-C02', name: 'Charlie 2-C Producer', lat: pcCentre.lat + dLat(0.25), lon: pcCentre.lon + dLon(0.25), padId: 'PAD-C1', oilRate: 155, gasRate: 410, waterRate: 720, waterCut: 0.82 },
    { id: 'W-C03', name: 'Charlie 3-C Producer', lat: pcCentre.lat - dLat(0.25), lon: pcCentre.lon - dLon(0.25), padId: 'PAD-C1', oilRate: 115, gasRate: 310, waterRate: 830, waterCut: 0.88 },
    { id: 'W-C04', name: 'Charlie 4-C Producer', lat: pcCentre.lat - dLat(0.25), lon: pcCentre.lon + dLon(0.25), padId: 'PAD-C1', oilRate: 140, gasRate: 380, waterRate: 750, waterCut: 0.84 },
  ];
  pcProducers.forEach((p) => {
    wells.push({
      ...p as any,
      type: 'producer', status: 'active', patternId: 'PAT-C',
      co2InjRate: 0, waterInjRate: 0, chokePercent: 65,
      tubingPressure: 340, casingPressure: 105, bottomholePressure: 2700,
      co2Concentration: 55, gor: 2400, lastTestDate: today,
      reservoirZone: '2nd Bone Spring', perforationTop: 6900, perforationBottom: 7350,
    });
  });
  wells.push({
    id: 'W-C05', name: 'Charlie 5-C Injector', lat: pcCentre.lat, lon: pcCentre.lon,
    type: 'injector', status: 'active', patternId: 'PAT-C', padId: 'PAD-C1',
    oilRate: 0, gasRate: 0, waterRate: 0, co2InjRate: 1900, waterInjRate: 0,
    chokePercent: 90, tubingPressure: 2900, casingPressure: 520, bottomholePressure: 3700,
    co2Concentration: 99.6, gor: 0, waterCut: 0, lastTestDate: today,
    reservoirZone: '2nd Bone Spring', perforationTop: 6880, perforationBottom: 7380,
  });

  // Pattern D – inverted 5-spot, ~2 mi SE (Pad D1)
  const pdCentre = { lat: BASE_LAT - dLat(1), lon: BASE_LON + dLon(1.5) };
  const pdProducers: Partial<Well>[] = [
    { id: 'W-D01', name: 'Delta 1-D Producer', lat: pdCentre.lat + dLat(0.25), lon: pdCentre.lon - dLon(0.25), padId: 'PAD-D1', oilRate: 280, gasRate: 760, waterRate: 380, waterCut: 0.58 },
    { id: 'W-D02', name: 'Delta 2-D Producer', lat: pdCentre.lat + dLat(0.25), lon: pdCentre.lon + dLon(0.25), padId: 'PAD-D1', oilRate: 260, gasRate: 720, waterRate: 410, waterCut: 0.61 },
    { id: 'W-D03', name: 'Delta 3-D Producer', lat: pdCentre.lat - dLat(0.25), lon: pdCentre.lon - dLon(0.25), padId: 'PAD-D1', oilRate: 235, gasRate: 640, waterRate: 460, waterCut: 0.66 },
    { id: 'W-D04', name: 'Delta 4-D Producer', lat: pdCentre.lat - dLat(0.25), lon: pdCentre.lon + dLon(0.25), padId: 'PAD-D1', oilRate: 300, gasRate: 810, waterRate: 350, waterCut: 0.54 },
  ];
  pdProducers.forEach((p) => {
    wells.push({
      ...p as any,
      type: 'producer', status: 'active', patternId: 'PAT-D',
      co2InjRate: 0, waterInjRate: 0, chokePercent: 75,
      tubingPressure: 420, casingPressure: 150, bottomholePressure: 3000,
      co2Concentration: 30, gor: 2800, lastTestDate: today,
      reservoirZone: 'Wolfcamp A', perforationTop: 7100, perforationBottom: 7550,
    });
  });
  wells.push({
    id: 'W-D05', name: 'Delta 5-D Injector', lat: pdCentre.lat, lon: pdCentre.lon,
    type: 'injector', status: 'active', patternId: 'PAT-D', padId: 'PAD-D1',
    oilRate: 0, gasRate: 0, waterRate: 0, co2InjRate: 2400, waterInjRate: 0,
    chokePercent: 88, tubingPressure: 2750, casingPressure: 510, bottomholePressure: 3650,
    co2Concentration: 99.4, gor: 0, waterCut: 0, lastTestDate: today,
    reservoirZone: 'Wolfcamp A', perforationTop: 7080, perforationBottom: 7580,
  });
  // Disposal well
  wells.push({
    id: 'W-SWD01', name: 'SWD-1 Disposal', lat: BASE_LAT - dLat(0.5), lon: BASE_LON + dLon(3),
    type: 'disposal', status: 'active', patternId: '', padId: 'PAD-D1',
    oilRate: 0, gasRate: 0, waterRate: 0, co2InjRate: 0, waterInjRate: 8500,
    chokePercent: 95, tubingPressure: 1200, casingPressure: 300, bottomholePressure: 2200,
    co2Concentration: 0, gor: 0, waterCut: 1.0, lastTestDate: today,
    reservoirZone: 'Ellenburger', perforationTop: 12500, perforationBottom: 13200,
  });

  return wells;
}

// ------------------------------------------------------------------
// Injection Patterns
// ------------------------------------------------------------------
function createPatterns(): InjectionPattern[] {
  return [
    {
      id: 'PAT-A', name: 'Apache 5-Spot', type: '5-spot',
      producerIds: ['W-A01', 'W-A02', 'W-A03', 'W-A04'],
      injectorIds: ['W-A05'], monitorIds: ['W-A06'],
      currentPhase: 'CO2_injection', cycleNumber: 5,
      targetPressure: 3200, currentPressure: 2950,
      co2Slug: 185000, waterSlug: 420000,
      estimatedBreakthrough: '2026-09-15',
    },
    {
      id: 'PAT-B', name: 'Bravo Inverted 5-Spot', type: 'inverted_5spot',
      producerIds: ['W-B01', 'W-B02', 'W-B03', 'W-B04'],
      injectorIds: ['W-B05', 'W-B06'], monitorIds: [],
      currentPhase: 'water_injection', cycleNumber: 4,
      targetPressure: 3300, currentPressure: 3100,
      co2Slug: 162000, waterSlug: 380000,
      estimatedBreakthrough: '2026-12-01',
    },
    {
      id: 'PAT-C', name: 'Charlie 5-Spot', type: '5-spot',
      producerIds: ['W-C01', 'W-C02', 'W-C03', 'W-C04'],
      injectorIds: ['W-C05'], monitorIds: [],
      currentPhase: 'CO2_injection', cycleNumber: 8,
      targetPressure: 3100, currentPressure: 3050,
      co2Slug: 310000, waterSlug: 620000,
      estimatedBreakthrough: '2026-06-20',
    },
    {
      id: 'PAT-D', name: 'Delta Inverted 5-Spot', type: 'inverted_5spot',
      producerIds: ['W-D01', 'W-D02', 'W-D03', 'W-D04'],
      injectorIds: ['W-D05'], monitorIds: [],
      currentPhase: 'CO2_injection', cycleNumber: 2,
      targetPressure: 3400, currentPressure: 3050,
      co2Slug: 95000, waterSlug: 180000,
      estimatedBreakthrough: '2027-04-10',
    },
  ];
}

// ------------------------------------------------------------------
// Pads
// ------------------------------------------------------------------
function createPads(): Pad[] {
  return [
    { id: 'PAD-A1', name: 'Apache Pad North', lat: BASE_LAT + dLat(1.15), lon: BASE_LON - dLon(0.15), facilityId: 'FAC-CPF', wellIds: ['W-A01', 'W-A02', 'W-A05', 'W-A06'] },
    { id: 'PAD-A2', name: 'Apache Pad South', lat: BASE_LAT + dLat(0.85), lon: BASE_LON - dLon(0.15), facilityId: 'FAC-CPF', wellIds: ['W-A03', 'W-A04'] },
    { id: 'PAD-B1', name: 'Bravo Pad West', lat: BASE_LAT + dLat(1.15), lon: BASE_LON + dLon(1.75), facilityId: 'FAC-CPF', wellIds: ['W-B01', 'W-B02', 'W-B05'] },
    { id: 'PAD-B2', name: 'Bravo Pad East', lat: BASE_LAT + dLat(0.85), lon: BASE_LON + dLon(2.25), facilityId: 'FAC-CPF', wellIds: ['W-B03', 'W-B04', 'W-B06'] },
    { id: 'PAD-C1', name: 'Charlie Pad', lat: BASE_LAT - dLat(1), lon: BASE_LON - dLon(0.5), facilityId: 'FAC-CPF', wellIds: ['W-C01', 'W-C02', 'W-C03', 'W-C04', 'W-C05'] },
    { id: 'PAD-D1', name: 'Delta Pad', lat: BASE_LAT - dLat(1), lon: BASE_LON + dLon(1.5), facilityId: 'FAC-CPF', wellIds: ['W-D01', 'W-D02', 'W-D03', 'W-D04', 'W-D05'] },
  ];
}

// ------------------------------------------------------------------
// Facilities
// ------------------------------------------------------------------
function createFacilities(): Facility[] {
  return [
    {
      id: 'FAC-CPF', name: 'Delaware Basin CPF', type: 'CPF',
      lat: BASE_LAT, lon: BASE_LON + dLon(0.5),
      oilCapacity: 5000, gasCapacity: 15000, waterCapacity: 20000, co2Capacity: 0,
      currentOilRate: 3960, currentGasRate: 9520, currentWaterRate: 11190, currentCO2Rate: 0,
      utilization: 0.82, emissions: 45,
    },
    {
      id: 'FAC-CO2R', name: 'CO2 Recycle Plant', type: 'CO2_recycle',
      lat: BASE_LAT + dLat(0.3), lon: BASE_LON + dLon(1),
      oilCapacity: 0, gasCapacity: 12000, waterCapacity: 0, co2Capacity: 10000,
      currentOilRate: 0, currentGasRate: 8400, currentWaterRate: 0, currentCO2Rate: 6200,
      utilization: 0.70, emissions: 28,
    },
    {
      id: 'FAC-COMP', name: 'CO2 Compression Station', type: 'compression',
      lat: BASE_LAT + dLat(0.5), lon: BASE_LON + dLon(0.8),
      oilCapacity: 0, gasCapacity: 0, waterCapacity: 0, co2Capacity: 12000,
      currentOilRate: 0, currentGasRate: 0, currentWaterRate: 0, currentCO2Rate: 9950,
      utilization: 0.88, emissions: 18,
    },
    {
      id: 'FAC-SWD', name: 'Salt Water Disposal', type: 'SWD',
      lat: BASE_LAT - dLat(0.5), lon: BASE_LON + dLon(3),
      oilCapacity: 0, gasCapacity: 0, waterCapacity: 12000, co2Capacity: 0,
      currentOilRate: 0, currentGasRate: 0, currentWaterRate: 8500, currentCO2Rate: 0,
      utilization: 0.71, emissions: 5,
    },
  ];
}

// ------------------------------------------------------------------
// Pipelines
// ------------------------------------------------------------------
function createPipelines(): Pipeline[] {
  const cpf = { lon: BASE_LON + dLon(0.5), lat: BASE_LAT };
  const co2r = { lon: BASE_LON + dLon(1), lat: BASE_LAT + dLat(0.3) };
  const comp = { lon: BASE_LON + dLon(0.8), lat: BASE_LAT + dLat(0.5) };
  const swd = { lon: BASE_LON + dLon(3), lat: BASE_LAT - dLat(0.5) };

  return [
    {
      id: 'PL-OIL-TRUNK', name: 'Oil Trunk Line', fromId: 'FAC-CPF', toId: 'EXPORT',
      coordinates: [[cpf.lon, cpf.lat], [cpf.lon + 0.05, cpf.lat - 0.02], [cpf.lon + 0.12, cpf.lat - 0.01]],
      capacity: 5000, currentFlow: 3960, product: 'oil', pressure: 650, diameter: 10,
    },
    {
      id: 'PL-GAS-SALES', name: 'Gas Sales Line', fromId: 'FAC-CPF', toId: 'EXPORT',
      coordinates: [[cpf.lon, cpf.lat], [cpf.lon - 0.03, cpf.lat + 0.04], [cpf.lon - 0.08, cpf.lat + 0.06]],
      capacity: 6000, currentFlow: 3320, product: 'gas', pressure: 900, diameter: 8,
    },
    {
      id: 'PL-CO2-RECYCLE', name: 'CO2 to Recycle Plant', fromId: 'FAC-CPF', toId: 'FAC-CO2R',
      coordinates: [[cpf.lon, cpf.lat], [co2r.lon, co2r.lat]],
      capacity: 12000, currentFlow: 8400, product: 'CO2', pressure: 1200, diameter: 12,
    },
    {
      id: 'PL-CO2-COMP', name: 'CO2 Recycle to Compressor', fromId: 'FAC-CO2R', toId: 'FAC-COMP',
      coordinates: [[co2r.lon, co2r.lat], [comp.lon, comp.lat]],
      capacity: 10000, currentFlow: 6200, product: 'CO2', pressure: 1800, diameter: 10,
    },
    {
      id: 'PL-CO2-INJ', name: 'CO2 Injection Trunk', fromId: 'FAC-COMP', toId: 'WELLS',
      coordinates: [[comp.lon, comp.lat], [comp.lon - 0.02, comp.lat + 0.01], [BASE_LON, BASE_LAT + dLat(1)]],
      capacity: 12000, currentFlow: 9950, product: 'CO2', pressure: 2200, diameter: 12,
    },
    {
      id: 'PL-WATER-SWD', name: 'Produced Water to SWD', fromId: 'FAC-CPF', toId: 'FAC-SWD',
      coordinates: [[cpf.lon, cpf.lat], [cpf.lon + 0.015, cpf.lat - 0.01], [swd.lon, swd.lat]],
      capacity: 12000, currentFlow: 8500, product: 'water', pressure: 250, diameter: 10,
    },
  ];
}

// ------------------------------------------------------------------
// CO2 Sources
// ------------------------------------------------------------------
function createCO2Sources(): CO2Source[] {
  return [
    {
      id: 'CO2-ANTHRO', name: 'Val Verde Gas Plant', type: 'anthropogenic',
      lat: 31.55, lon: -103.20,
      deliveryRate: 3800, contractedRate: 4000, purity: 0.96, cost: 1.25,
    },
    {
      id: 'CO2-NAT', name: 'Bravo Dome Supply', type: 'natural',
      lat: 36.35, lon: -104.00,
      deliveryRate: 5200, contractedRate: 6000, purity: 0.985, cost: 0.85,
    },
  ];
}

// ------------------------------------------------------------------
// Monitoring Points
// ------------------------------------------------------------------
function createMonitoringPoints(): MonitoringPoint[] {
  return [
    { id: 'MON-S01', name: 'Seismic Array North', type: 'seismic', lat: BASE_LAT + dLat(1.5), lon: BASE_LON, value: 0.12, unit: 'Richter', threshold: 2.0, status: 'normal' },
    { id: 'MON-S02', name: 'Seismic Array South', type: 'seismic', lat: BASE_LAT - dLat(1.5), lon: BASE_LON, value: 0.08, unit: 'Richter', threshold: 2.0, status: 'normal' },
    { id: 'MON-P01', name: 'Pressure Gauge Pattern A', type: 'pressure', lat: BASE_LAT + dLat(1), lon: BASE_LON + dLon(0.1), value: 2950, unit: 'psi', threshold: 3500, status: 'normal' },
    { id: 'MON-P02', name: 'Pressure Gauge Pattern D', type: 'pressure', lat: BASE_LAT - dLat(1), lon: BASE_LON + dLon(1.6), value: 3380, unit: 'psi', threshold: 3500, status: 'warning' },
    { id: 'MON-G01', name: 'Soil Gas Sensor NE', type: 'soil_gas', lat: BASE_LAT + dLat(0.5), lon: BASE_LON + dLon(1.5), value: 120, unit: 'ppm CO2', threshold: 500, status: 'normal' },
    { id: 'MON-G02', name: 'Soil Gas Sensor SW', type: 'soil_gas', lat: BASE_LAT - dLat(0.5), lon: BASE_LON - dLon(1), value: 85, unit: 'ppm CO2', threshold: 500, status: 'normal' },
    { id: 'MON-W01', name: 'Groundwater Monitor Alpha', type: 'groundwater', lat: BASE_LAT + dLat(2), lon: BASE_LON + dLon(0.5), value: 350, unit: 'ppm TDS', threshold: 1000, status: 'normal' },
    { id: 'MON-W02', name: 'Groundwater Monitor Beta', type: 'groundwater', lat: BASE_LAT - dLat(2), lon: BASE_LON - dLon(0.5), value: 410, unit: 'ppm TDS', threshold: 1000, status: 'normal' },
  ];
}

// ------------------------------------------------------------------
// Flare Points
// ------------------------------------------------------------------
function createFlares(): FlarePoint[] {
  return [
    { id: 'FLR-01', facilityId: 'FAC-CPF', lat: BASE_LAT + dLat(0.05), lon: BASE_LON + dLon(0.55), currentRate: 120, maxRate: 5000, status: 'active' },
    { id: 'FLR-02', facilityId: 'FAC-CO2R', lat: BASE_LAT + dLat(0.35), lon: BASE_LON + dLon(1.05), currentRate: 0, maxRate: 3000, status: 'standby' },
  ];
}

// ------------------------------------------------------------------
// Fleet Assets
// ------------------------------------------------------------------
function createFleet(): FleetAsset[] {
  return [
    { id: 'FL-T01', type: 'truck', status: 'en_route', lat: BASE_LAT + dLat(0.8), lon: BASE_LON + dLon(0.3), assignedTo: 'W-A03', eta: '2026-03-05T08:30:00Z' },
    { id: 'FL-T02', type: 'truck', status: 'available', lat: BASE_LAT, lon: BASE_LON + dLon(0.5), assignedTo: null, eta: null },
    { id: 'FL-WO1', type: 'workover', status: 'on_site', lat: BASE_LAT - dLat(1), lon: BASE_LON - dLon(0.5), assignedTo: 'W-C03', eta: null },
    { id: 'FL-WL1', type: 'wireline', status: 'available', lat: BASE_LAT + dLat(0.1), lon: BASE_LON + dLon(0.6), assignedTo: null, eta: null },
    { id: 'FL-PT1', type: 'pump_truck', status: 'en_route', lat: BASE_LAT - dLat(0.3), lon: BASE_LON + dLon(2), assignedTo: 'FAC-SWD', eta: '2026-03-05T10:00:00Z' },
    { id: 'FL-CT1', type: 'coiled_tubing', status: 'maintenance', lat: 31.95, lon: -103.40, assignedTo: null, eta: null },
  ];
}

// ------------------------------------------------------------------
// Alerts
// ------------------------------------------------------------------
function createAlerts(): Alert[] {
  return [
    {
      id: 'ALT-001', timestamp: '2026-03-05T02:14:00Z', severity: 'warning',
      source: 'FAC-COMP', sourceType: 'facility',
      message: 'CO2 Compression Station utilization at 88% — approaching capacity limit',
      acknowledged: false, acknowledgedBy: null,
    },
    {
      id: 'ALT-002', timestamp: '2026-03-05T01:45:00Z', severity: 'critical',
      source: 'MON-P02', sourceType: 'monitor',
      message: 'Pattern D reservoir pressure 3380 psi nearing threshold 3500 psi — risk of fracture propagation',
      acknowledged: false, acknowledgedBy: null,
    },
    {
      id: 'ALT-003', timestamp: '2026-03-05T03:22:00Z', severity: 'info',
      source: 'W-C01', sourceType: 'well',
      message: 'CO2 concentration in Charlie 1-C produced gas rising (55 mol%) — possible early breakthrough',
      acknowledged: true, acknowledgedBy: 'demo-user',
    },
    {
      id: 'ALT-004', timestamp: '2026-03-05T00:58:00Z', severity: 'warning',
      source: 'PL-CO2-INJ', sourceType: 'pipeline',
      message: 'CO2 injection trunk pressure 2200 psi — verify downstream choke positions',
      acknowledged: false, acknowledgedBy: null,
    },
    {
      id: 'ALT-005', timestamp: '2026-03-04T23:30:00Z', severity: 'info',
      source: 'agent-optimization', sourceType: 'agent',
      message: 'Optimization agent proposes reducing Pattern A injection rate by 8% to improve CO2 utilization',
      acknowledged: false, acknowledgedBy: null,
    },
  ];
}

// ------------------------------------------------------------------
// Shift Log
// ------------------------------------------------------------------
function createShiftLog(): ShiftLog {
  return {
    id: 'SL-20260305-N',
    shift: 'night',
    date: '2026-03-05',
    operator: 'J. Martinez',
    entries: [
      {
        timestamp: '2026-03-05T00:15:00Z',
        category: 'operations',
        message: 'Night shift started. All patterns nominal. FAC-COMP running at 88% — monitoring closely.',
        entityId: null, agentId: null,
      },
      {
        timestamp: '2026-03-05T01:45:00Z',
        category: 'safety',
        message: 'Pressure alarm on MON-P02 (Pattern D). Contacted reservoir engineer on call.',
        entityId: 'MON-P02', agentId: null,
      },
      {
        timestamp: '2026-03-05T02:30:00Z',
        category: 'agent_action',
        message: 'Monitoring agent flagged rising CO2 concentration on W-C01 — early breakthrough risk. Recommended well test.',
        entityId: 'W-C01', agentId: 'agent-monitoring',
      },
      {
        timestamp: '2026-03-05T03:00:00Z',
        category: 'maintenance',
        message: 'Workover unit FL-WO1 on site at W-C03 for ESP replacement. ETA completion 12:00.',
        entityId: 'W-C03', agentId: null,
      },
    ],
  };
}

// ------------------------------------------------------------------
// Agent States
// ------------------------------------------------------------------
function createAgents(): AgentState[] {
  return [
    {
      id: 'agent-monitoring', role: 'monitoring',
      status: 'idle', autonomyLevel: 'autonomous',
      lastAction: 'Scanned all 24 wells — flagged W-C01 CO2 concentration trend',
      lastActionTime: '2026-03-05T02:28:00Z',
      pendingProposals: [],
      actionHistory: [
        { id: 'ACT-M01', agentId: 'agent-monitoring', timestamp: '2026-03-05T02:28:00Z', action: 'Well scan', result: 'Flagged W-C01 rising CO2', entities: ['W-C01'] },
        { id: 'ACT-M02', agentId: 'agent-monitoring', timestamp: '2026-03-05T01:00:00Z', action: 'Facility scan', result: 'All facilities within limits', entities: ['FAC-CPF', 'FAC-CO2R', 'FAC-COMP', 'FAC-SWD'] },
      ],
    },
    {
      id: 'agent-optimization', role: 'optimization',
      status: 'proposing', autonomyLevel: 'supervised',
      lastAction: 'Computed optimal choke settings for Pattern A',
      lastActionTime: '2026-03-04T23:30:00Z',
      pendingProposals: [
        {
          id: 'PROP-O01', agentId: 'agent-optimization',
          timestamp: '2026-03-04T23:30:00Z',
          title: 'Reduce Pattern A CO2 injection by 8%',
          description: 'Current CO2 utilization in Pattern A is 62%. Reducing injection rate from 2200 to 2024 mcf/d and adjusting producer chokes will improve utilization to ~70% and extend breakthrough by 3 weeks.',
          impact: '+$12,400/d in CO2 cost savings, +3 week breakthrough delay',
          risk: 'low',
          affectedEntities: ['W-A05', 'W-A01', 'W-A02', 'W-A03', 'W-A04'],
          status: 'pending', approvedBy: null,
        },
      ],
      actionHistory: [
        { id: 'ACT-O01', agentId: 'agent-optimization', timestamp: '2026-03-04T23:30:00Z', action: 'Pattern A optimization', result: 'Proposal PROP-O01 created', entities: ['PAT-A'] },
      ],
    },
    {
      id: 'agent-maintenance', role: 'maintenance',
      status: 'idle', autonomyLevel: 'advisory',
      lastAction: 'Predicted ESP failure on W-C03 — dispatched workover unit',
      lastActionTime: '2026-03-04T18:00:00Z',
      pendingProposals: [],
      actionHistory: [
        { id: 'ACT-X01', agentId: 'agent-maintenance', timestamp: '2026-03-04T18:00:00Z', action: 'ESP failure prediction', result: 'Dispatched FL-WO1 to W-C03', entities: ['W-C03', 'FL-WO1'] },
      ],
    },
    {
      id: 'agent-commercial', role: 'commercial',
      status: 'idle', autonomyLevel: 'advisory',
      lastAction: 'Updated daily netback calculations — $42.80/boe field average',
      lastActionTime: '2026-03-05T00:05:00Z',
      pendingProposals: [],
      actionHistory: [
        { id: 'ACT-C01', agentId: 'agent-commercial', timestamp: '2026-03-05T00:05:00Z', action: 'Daily economics update', result: 'Netback $42.80/boe, CO2 cost $8.20/boe', entities: [] },
      ],
    },
    {
      id: 'agent-orchestrator', role: 'orchestrator',
      status: 'idle', autonomyLevel: 'autonomous',
      lastAction: 'Coordinated night shift agent handoff — all agents reporting nominal',
      lastActionTime: '2026-03-05T00:00:00Z',
      pendingProposals: [],
      actionHistory: [
        { id: 'ACT-R01', agentId: 'agent-orchestrator', timestamp: '2026-03-05T00:00:00Z', action: 'Shift handoff', result: 'All 4 sub-agents synchronized', entities: [] },
      ],
    },
  ];
}

// ------------------------------------------------------------------
// KPIs — calculated from well/facility data
// ------------------------------------------------------------------
function calculateKPIs(wells: Well[], facilities: Facility[], flares: FlarePoint[]): {
  production: ProductionKPI;
  economics: EconomicsKPI;
  environmental: EnvironmentalKPI;
} {
  const producers = wells.filter((w) => w.type === 'producer');
  const totalOil = producers.reduce((s, w) => s + w.oilRate, 0);
  const totalGas = producers.reduce((s, w) => s + w.gasRate, 0);
  const totalWater = producers.reduce((s, w) => s + w.waterRate, 0);
  const co2Injected = wells.filter((w) => w.type === 'injector' || w.type === 'WAG').reduce((s, w) => s + w.co2InjRate, 0);
  const co2Recycled = facilities.find((f) => f.type === 'CO2_recycle')?.currentCO2Rate ?? 0;
  const co2Purchased = co2Injected - co2Recycled;
  const avgGor = totalOil > 0 ? (totalGas * 1000) / totalOil : 0;  // scf/bbl
  const avgWaterCut = producers.length > 0 ? producers.reduce((s, w) => s + w.waterCut, 0) / producers.length : 0;
  const baselineOil = 2200; // bbl/d baseline without EOR
  const incrementalOil = totalOil - baselineOil;

  const oilPrice = 72; // $/bbl WTI
  const gasPrice = 3.2; // $/mcf
  const revenue = totalOil * oilPrice + totalGas * gasPrice;
  const opex = totalOil * 18 + totalWater * 0.8;
  const co2Cost = co2Purchased * 1.05;  // weighted avg
  const totalBoe = totalOil + totalGas / 6;
  const netback = totalBoe > 0 ? (revenue - opex - co2Cost) / totalBoe : 0;
  const incrementalBoe = incrementalOil + (incrementalOil * avgGor / 6000);
  const incrementalNetback = incrementalBoe > 0 ? ((incrementalOil * oilPrice) - (co2Cost * 0.6)) / incrementalBoe : 0;

  const flaringRate = flares.reduce((s, f) => s + f.currentRate, 0);
  const facilityEmissions = facilities.reduce((s, f) => s + f.emissions, 0);
  // Net CO2 stored: injected minus produced CO2 (approximation)
  const producedCO2approx = producers.reduce((s, w) => s + (w.gasRate * w.co2Concentration / 100), 0);
  const co2StoredMcf = co2Injected - producedCO2approx;
  const co2StoredTons = co2StoredMcf * 0.0541; // approx tonnes per mcf

  return {
    production: {
      totalOil,
      totalGas,
      totalWater,
      co2Injected,
      co2Recycled,
      co2Purchased: Math.max(0, co2Purchased),
      co2Utilization: co2Injected > 0 ? co2Recycled / co2Injected : 0,
      incrementalOil: Math.max(0, incrementalOil),
      gor: Math.round(avgGor),
      waterCut: Math.round(avgWaterCut * 100) / 100,
      uptime: 0.96,
    },
    economics: {
      revenue: Math.round(revenue),
      opex: Math.round(opex),
      co2Cost: Math.round(co2Cost),
      netback: Math.round(netback * 100) / 100,
      incrementalNetback: Math.round(incrementalNetback * 100) / 100,
      co2CostPerBoe: totalBoe > 0 ? Math.round((co2Cost / totalBoe) * 100) / 100 : 0,
      breakeven: 38,
    },
    environmental: {
      co2Stored: Math.round(co2StoredTons * 100) / 100,
      co2Emitted: facilityEmissions,
      flaring: flaringRate,
      carbonIntensity: totalBoe > 0 ? Math.round((facilityEmissions * 1000 / totalBoe) * 100) / 100 : 0,
      methaneLeaks: 0,
      complianceScore: 94,
    },
  };
}

// ==================================================================
// Main factory
// ==================================================================
export function createMockState(): TwinState {
  const wells = createWells();
  const facilities = createFacilities();
  const flares = createFlares();

  return {
    wells,
    patterns: createPatterns(),
    pads: createPads(),
    facilities,
    pipelines: createPipelines(),
    co2Sources: createCO2Sources(),
    monitoringPoints: createMonitoringPoints(),
    flares,
    fleet: createFleet(),
    alerts: createAlerts(),
    shiftLog: createShiftLog(),
    agents: createAgents(),
    kpis: calculateKPIs(wells, facilities, flares),
  };
}
