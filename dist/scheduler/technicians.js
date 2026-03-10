"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getTechnicians = getTechnicians;
exports.getTechnicianById = getTechnicianById;
exports.getTechnicianSchedule = getTechnicianSchedule;
exports.updateTechnicianSchedule = updateTechnicianSchedule;

const TECHNICIANS = [
    {
        id: 'TECH-001', name: 'J. Martinez', role: 'Senior Mechanic',
        skills: ['compressor', 'pump', 'separator', 'valve', 'mechanical'],
        homeBase: 'Pecos, TX', zone: 'Delaware Basin North',
        maxDailyHours: 10, certifications: ['API-510', 'API-570', 'OSHA-30'],
        phone: '+1-432-555-0101', shift: 'day',
    },
    {
        id: 'TECH-002', name: 'R. Thompson', role: 'Electrician / I&E',
        skills: ['electrical', 'instrumentation', 'meter', 'vsd', 'motor'],
        homeBase: 'Midland, TX', zone: 'Delaware Basin South',
        maxDailyHours: 10, certifications: ['NCCER-Electrical', 'ISA-CCST'],
        phone: '+1-432-555-0102', shift: 'day',
    },
    {
        id: 'TECH-003', name: 'A. Singh', role: 'Process Technician',
        skills: ['separator', 'dehydrator', 'membrane', 'heater', 'chemical'],
        homeBase: 'Pecos, TX', zone: 'Delaware Basin North',
        maxDailyHours: 10, certifications: ['API-RP-14C', 'H2S-Alive'],
        phone: '+1-432-555-0103', shift: 'day',
    },
    {
        id: 'TECH-004', name: 'D. Patel', role: 'Rotating Equipment Specialist',
        skills: ['compressor', 'pump', 'bearing', 'alignment', 'vibration_analysis'],
        homeBase: 'Odessa, TX', zone: 'Delaware Basin Central',
        maxDailyHours: 10, certifications: ['Vibration-Cat-II', 'API-617'],
        phone: '+1-432-555-0104', shift: 'day',
    },
    {
        id: 'TECH-005', name: 'K. Williams', role: 'Wellhead / Completions Tech',
        skills: ['wellhead', 'valve', 'tubing', 'workover', 'pressure_test'],
        homeBase: 'Carlsbad, NM', zone: 'Delaware Basin West',
        maxDailyHours: 10, certifications: ['WellCAP', 'API-6A'],
        phone: '+1-575-555-0105', shift: 'day',
    },
    {
        id: 'TECH-006', name: 'M. Garcia', role: 'Corrosion / Chemical Tech',
        skills: ['chemical', 'filter', 'corrosion', 'scale', 'pipeline_inspection'],
        homeBase: 'Pecos, TX', zone: 'Delaware Basin North',
        maxDailyHours: 10, certifications: ['NACE-CIP-1', 'NACE-CP-2'],
        phone: '+1-432-555-0106', shift: 'night',
    },
    {
        id: 'TECH-007', name: 'B. Jackson', role: 'General Operator',
        skills: ['pump', 'valve', 'filter', 'mechanical', 'separator'],
        homeBase: 'Midland, TX', zone: 'Delaware Basin South',
        maxDailyHours: 10, certifications: ['OSHA-10', 'H2S-Alive'],
        phone: '+1-432-555-0107', shift: 'night',
    },
    {
        id: 'TECH-008', name: 'C. Nguyen', role: 'Automation / Controls',
        skills: ['instrumentation', 'meter', 'electrical', 'scada', 'plc'],
        homeBase: 'Odessa, TX', zone: 'Delaware Basin Central',
        maxDailyHours: 10, certifications: ['ISA-CAP', 'NCCER-I&E'],
        phone: '+1-432-555-0108', shift: 'day',
    },
];

// In-memory daily schedules keyed by techId -> date
const _schedules = {};

function getTechnicians() {
    return TECHNICIANS.map(t => ({
        ...t,
        availableToday: true,
        bookedHours: _getBookedHours(t.id),
        remainingHours: t.maxDailyHours - _getBookedHours(t.id),
    }));
}

function getTechnicianById(id) {
    const t = TECHNICIANS.find(t => t.id === id);
    if (!t) return null;
    return {
        ...t,
        availableToday: true,
        bookedHours: _getBookedHours(t.id),
        remainingHours: t.maxDailyHours - _getBookedHours(t.id),
    };
}

function _getBookedHours(techId) {
    const today = new Date().toISOString().split('T')[0];
    const key = `${techId}:${today}`;
    const sched = _schedules[key];
    if (!sched) return 0;
    return sched.jobs.reduce((s, j) => s + j.estimatedHours, 0);
}

function getTechnicianSchedule(techId, date) {
    const d = date || new Date().toISOString().split('T')[0];
    const key = `${techId}:${d}`;
    const tech = TECHNICIANS.find(t => t.id === techId);
    if (!tech) return null;
    return {
        techId,
        techName: tech.name,
        date: d,
        locked: true,
        lockedAt: `${d}T05:00:00Z`,
        jobs: _schedules[key]?.jobs || [],
        totalHours: _getBookedHours(techId),
        maxHours: tech.maxDailyHours,
    };
}

function updateTechnicianSchedule(techId, date, jobs) {
    const d = date || new Date().toISOString().split('T')[0];
    const key = `${techId}:${d}`;
    _schedules[key] = { jobs, updatedAt: new Date().toISOString() };
    return { success: true, key };
}
