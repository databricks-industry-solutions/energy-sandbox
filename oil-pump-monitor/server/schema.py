"""Database schema initialization for oil pump monitoring."""

CREATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pumps (
    id SERIAL PRIMARY KEY,
    pump_id VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    field_section VARCHAR(50),
    installation_date DATE,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vibration_readings (
    id BIGSERIAL PRIMARY KEY,
    pump_id VARCHAR(20) NOT NULL REFERENCES pumps(pump_id),
    timestamp TIMESTAMP NOT NULL,
    frequency_hz DOUBLE PRECISION NOT NULL,
    amplitude_mm_s DOUBLE PRECISION NOT NULL,
    rpm INTEGER NOT NULL,
    temperature_f DOUBLE PRECISION NOT NULL,
    pressure_psi DOUBLE PRECISION NOT NULL,
    is_anomaly BOOLEAN DEFAULT FALSE,
    alert_level VARCHAR(10) DEFAULT 'normal',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS spectrum_readings (
    id BIGSERIAL PRIMARY KEY,
    pump_id VARCHAR(20) NOT NULL REFERENCES pumps(pump_id),
    timestamp TIMESTAMP NOT NULL,
    frequencies DOUBLE PRECISION[] NOT NULL,
    amplitudes DOUBLE PRECISION[] NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vibration_pump_time ON vibration_readings(pump_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_vibration_time ON vibration_readings(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_spectrum_pump_time ON spectrum_readings(pump_id, timestamp DESC);
"""

INSERT_DEMO_PUMPS_SQL = """
INSERT INTO pumps (pump_id, name, latitude, longitude, field_section, installation_date, status)
VALUES
    ('PUMP-ND-001', 'Bakken Unit 1 - Williston', 48.1470, -103.6179, 'Section A', '2019-03-15', 'active'),
    ('PUMP-ND-002', 'Bakken Unit 2 - Tioga', 48.3977, -102.9394, 'Section B', '2019-06-22', 'active'),
    ('PUMP-ND-003', 'Bakken Unit 3 - Stanley', 48.3175, -102.3894, 'Section C', '2020-01-10', 'active'),
    ('PUMP-ND-004', 'Bakken Unit 4 - Watford City', 47.8011, -103.2875, 'Section A', '2020-04-18', 'active'),
    ('PUMP-ND-005', 'Bakken Unit 5 - Parshall', 47.9531, -102.1353, 'Section D', '2020-09-05', 'active'),
    ('PUMP-ND-006', 'Bakken Unit 6 - New Town', 47.9742, -102.4939, 'Section D', '2021-02-28', 'active')
ON CONFLICT (pump_id) DO NOTHING;
"""
