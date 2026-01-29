-- Patient Census Views for Grafana Dashboards

-- Current Census by Location
CREATE OR REPLACE VIEW metrics.v_census_current AS
SELECT
    l.facility_name,
    l.unit,
    l.location_type,
    c.midnight_census as current_census,
    l.operational_beds,
    ROUND(c.midnight_census::NUMERIC / NULLIF(l.operational_beds, 0) * 100, 1) as occupancy_pct,
    c.admissions as today_admissions,
    c.discharges as today_discharges,
    c.admissions - c.discharges as net_change
FROM metrics.metric_patient_census c
JOIN dim.dim_location l ON c.facility = l.facility_name AND c.unit = l.unit
WHERE c.census_date = CURRENT_DATE;

-- Census Trend (Last 30 Days)
CREATE OR REPLACE VIEW metrics.v_census_trend AS
SELECT
    census_date,
    facility,
    SUM(midnight_census) as total_census,
    SUM(operational_beds) as total_beds,
    ROUND(SUM(midnight_census)::NUMERIC / NULLIF(SUM(operational_beds), 0) * 100, 1) as occupancy_pct,
    SUM(admissions) as total_admissions,
    SUM(discharges) as total_discharges
FROM metrics.metric_patient_census
WHERE census_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY census_date, facility
ORDER BY census_date;

-- Census by Day of Week (for capacity planning)
CREATE OR REPLACE VIEW metrics.v_census_by_day_of_week AS
SELECT
    EXTRACT(DOW FROM census_date) as day_of_week,
    TO_CHAR(census_date, 'Day') as day_name,
    ROUND(AVG(midnight_census), 0) as avg_census,
    MAX(midnight_census) as max_census,
    MIN(midnight_census) as min_census,
    ROUND(AVG(occupancy_rate), 1) as avg_occupancy_pct
FROM metrics.metric_patient_census
WHERE census_date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY EXTRACT(DOW FROM census_date), TO_CHAR(census_date, 'Day')
ORDER BY EXTRACT(DOW FROM census_date);

-- Hourly Census Pattern (requires timestamp data in encounters)
CREATE OR REPLACE VIEW dim.v_inpatient_by_unit AS
SELECT
    l.unit,
    l.location_type,
    l.service_line,
    COUNT(DISTINCT fe.encounter_key) as active_encounters,
    l.operational_beds,
    ROUND(COUNT(DISTINCT fe.encounter_key)::NUMERIC / NULLIF(l.operational_beds, 0) * 100, 1) as occupancy_pct
FROM dim.fact_encounter fe
JOIN dim.dim_location l ON fe.location_key = l.location_key
WHERE fe.discharge_datetime IS NULL
   OR fe.discharge_datetime > CURRENT_TIMESTAMP
GROUP BY l.unit, l.location_type, l.service_line, l.operational_beds
ORDER BY l.unit;
