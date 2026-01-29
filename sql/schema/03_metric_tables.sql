-- Healthcare Analytics Starter Kit
-- Pre-aggregated Metric Tables
-- Optimized for dashboard queries and reporting

-- ============================================================================
-- METRIC TABLES
-- ============================================================================

-- Metric: Patient Census
CREATE TABLE IF NOT EXISTS metric_patient_census (
    id SERIAL PRIMARY KEY,
    census_date DATE NOT NULL,

    facility VARCHAR(200),
    department VARCHAR(200),
    unit VARCHAR(100),
    location_key INTEGER REFERENCES dim_location(location_key),

    -- Census counts
    midnight_census INTEGER,
    admissions INTEGER,
    discharges INTEGER,
    transfers_in INTEGER,
    transfers_out INTEGER,
    deaths INTEGER,

    -- Capacity
    licensed_beds INTEGER,
    operational_beds INTEGER,
    occupancy_rate NUMERIC(5,2),

    -- Patient type
    inpatient_count INTEGER,
    observation_count INTEGER,
    icu_count INTEGER,
    pediatric_count INTEGER,

    avg_acuity_score NUMERIC(4,2),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(census_date, location_key)
);

CREATE INDEX IF NOT EXISTS ix_metric_census_date ON metric_patient_census(census_date);
CREATE INDEX IF NOT EXISTS ix_metric_census_facility ON metric_patient_census(facility);

-- Metric: ED Throughput
CREATE TABLE IF NOT EXISTS metric_ed_throughput (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,
    metric_hour INTEGER NOT NULL,  -- 0-23

    facility VARCHAR(200),
    ed_location VARCHAR(100),

    -- Volume
    arrivals INTEGER,
    departures INTEGER,
    patients_in_ed INTEGER,
    patients_waiting INTEGER,
    patients_in_treatment INTEGER,

    -- Disposition
    admitted INTEGER,
    discharged INTEGER,
    transferred INTEGER,
    left_without_seen INTEGER,
    left_ama INTEGER,

    -- Time metrics (minutes)
    avg_door_to_provider NUMERIC(8,2),
    avg_door_to_bed NUMERIC(8,2),
    avg_length_of_stay NUMERIC(8,2),
    avg_boarding_time NUMERIC(8,2),
    median_los NUMERIC(8,2),
    p90_los NUMERIC(8,2),

    -- Acuity (ESI levels)
    esi_1_count INTEGER,
    esi_2_count INTEGER,
    esi_3_count INTEGER,
    esi_4_count INTEGER,
    esi_5_count INTEGER,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(metric_date, metric_hour, facility)
);

CREATE INDEX IF NOT EXISTS ix_metric_ed_date ON metric_ed_throughput(metric_date);
CREATE INDEX IF NOT EXISTS ix_metric_ed_facility ON metric_ed_throughput(facility);

-- Metric: Readmissions
CREATE TABLE IF NOT EXISTS metric_readmission (
    id SERIAL PRIMARY KEY,
    discharge_date DATE NOT NULL,

    facility VARCHAR(200),
    department VARCHAR(200),
    discharge_diagnosis_category VARCHAR(100),
    payer_type VARCHAR(50),
    age_group VARCHAR(20),

    -- Index encounters
    index_discharges INTEGER,

    -- Readmission counts
    readmissions_7_day INTEGER,
    readmissions_14_day INTEGER,
    readmissions_30_day INTEGER,

    -- Rates
    readmission_rate_7_day NUMERIC(6,4),
    readmission_rate_14_day NUMERIC(6,4),
    readmission_rate_30_day NUMERIC(6,4),

    -- Potentially preventable
    potentially_preventable_30_day INTEGER,
    ppr_rate NUMERIC(6,4),

    -- CMS comparison
    cms_expected_rate NUMERIC(6,4),
    excess_readmission_ratio NUMERIC(6,4),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_metric_readmission_date ON metric_readmission(discharge_date);
CREATE INDEX IF NOT EXISTS ix_metric_readmission_facility ON metric_readmission(facility);
CREATE INDEX IF NOT EXISTS ix_metric_readmission_diagnosis ON metric_readmission(discharge_diagnosis_category);

-- Metric: Length of Stay
CREATE TABLE IF NOT EXISTS metric_length_of_stay (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,

    facility VARCHAR(200),
    department VARCHAR(200),
    service_line VARCHAR(100),
    drg_code VARCHAR(10),
    drg_description VARCHAR(200),
    payer_type VARCHAR(50),

    -- Volume
    discharge_count INTEGER,

    -- LOS statistics (days)
    avg_los NUMERIC(8,2),
    median_los NUMERIC(8,2),
    min_los NUMERIC(8,2),
    max_los NUMERIC(8,2),
    std_dev_los NUMERIC(8,2),
    p25_los NUMERIC(8,2),
    p75_los NUMERIC(8,2),
    p90_los NUMERIC(8,2),

    -- Comparison
    expected_los NUMERIC(8,2),
    los_index NUMERIC(6,4),

    -- Long stay
    long_stay_count_7_plus INTEGER,
    long_stay_count_14_plus INTEGER,
    long_stay_count_30_plus INTEGER,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_metric_los_date ON metric_length_of_stay(metric_date);
CREATE INDEX IF NOT EXISTS ix_metric_los_facility ON metric_length_of_stay(facility);
CREATE INDEX IF NOT EXISTS ix_metric_los_drg ON metric_length_of_stay(drg_code);

-- Metric: Quality Indicators
CREATE TABLE IF NOT EXISTS metric_quality_indicator (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,
    metric_period VARCHAR(20) NOT NULL,  -- daily, weekly, monthly

    facility VARCHAR(200),
    department VARCHAR(200),
    unit VARCHAR(100),

    indicator_code VARCHAR(50) NOT NULL,
    indicator_name VARCHAR(200) NOT NULL,
    indicator_category VARCHAR(100),

    -- Values
    numerator INTEGER,
    denominator INTEGER,
    rate NUMERIC(10,6),
    rate_per_1000 NUMERIC(10,4),

    -- Benchmarks
    target_rate NUMERIC(10,6),
    benchmark_rate NUMERIC(10,6),
    national_benchmark NUMERIC(10,6),

    -- Performance
    meets_target BOOLEAN,
    variance_from_target NUMERIC(10,6),
    percentile_rank NUMERIC(5,2),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_metric_quality_date ON metric_quality_indicator(metric_date);
CREATE INDEX IF NOT EXISTS ix_metric_quality_indicator ON metric_quality_indicator(indicator_code);
CREATE INDEX IF NOT EXISTS ix_metric_quality_facility ON metric_quality_indicator(facility);

-- Metric: Operational KPIs
CREATE TABLE IF NOT EXISTS metric_operational_kpi (
    id SERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,

    facility VARCHAR(200),
    department VARCHAR(200),

    kpi_code VARCHAR(50) NOT NULL,
    kpi_name VARCHAR(200) NOT NULL,
    kpi_category VARCHAR(100),

    kpi_value NUMERIC(14,4),
    kpi_unit VARCHAR(50),

    prior_period_value NUMERIC(14,4),
    change_pct NUMERIC(8,4),
    trend_direction VARCHAR(20),  -- up, down, flat

    target_value NUMERIC(14,4),
    variance_from_target NUMERIC(14,4),
    status VARCHAR(20),  -- green, yellow, red

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_metric_kpi_date ON metric_operational_kpi(metric_date);
CREATE INDEX IF NOT EXISTS ix_metric_kpi_code ON metric_operational_kpi(kpi_code);
CREATE INDEX IF NOT EXISTS ix_metric_kpi_facility ON metric_operational_kpi(facility);

-- ============================================================================
-- VIEWS FOR DASHBOARDS
-- ============================================================================

-- View: Current Census Summary
CREATE OR REPLACE VIEW v_current_census AS
SELECT
    facility,
    department,
    SUM(midnight_census) as total_patients,
    SUM(licensed_beds) as total_licensed_beds,
    SUM(operational_beds) as total_operational_beds,
    ROUND(AVG(occupancy_rate), 1) as avg_occupancy_pct,
    SUM(admissions) as todays_admissions,
    SUM(discharges) as todays_discharges
FROM metric_patient_census
WHERE census_date = CURRENT_DATE
GROUP BY facility, department;

-- View: 30-Day Readmission Summary
CREATE OR REPLACE VIEW v_readmission_summary AS
SELECT
    facility,
    discharge_diagnosis_category,
    SUM(index_discharges) as total_discharges,
    SUM(readmissions_30_day) as total_readmissions,
    ROUND(AVG(readmission_rate_30_day) * 100, 1) as avg_readmission_rate_pct
FROM metric_readmission
WHERE discharge_date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY facility, discharge_diagnosis_category
ORDER BY avg_readmission_rate_pct DESC;

-- View: ED Performance Today
CREATE OR REPLACE VIEW v_ed_performance_today AS
SELECT
    facility,
    SUM(arrivals) as total_arrivals,
    MAX(patients_in_ed) as current_census,
    ROUND(AVG(avg_door_to_provider), 0) as avg_wait_minutes,
    ROUND(AVG(avg_length_of_stay) / 60, 1) as avg_los_hours,
    SUM(left_without_seen) as lwbs_count
FROM metric_ed_throughput
WHERE metric_date = CURRENT_DATE
GROUP BY facility;

-- View: Quality Dashboard
CREATE OR REPLACE VIEW v_quality_dashboard AS
SELECT
    indicator_category,
    indicator_code,
    indicator_name,
    SUM(numerator) as total_events,
    SUM(denominator) as total_population,
    ROUND(AVG(rate) * 1000, 2) as rate_per_1000,
    ROUND(AVG(target_rate) * 1000, 2) as target_per_1000,
    SUM(CASE WHEN meets_target THEN 1 ELSE 0 END) as periods_meeting_target
FROM metric_quality_indicator
WHERE metric_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY indicator_category, indicator_code, indicator_name
ORDER BY indicator_category, indicator_code;
