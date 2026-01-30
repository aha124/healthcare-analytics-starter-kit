-- Length of Stay Views for Grafana Dashboards

-- LOS Trend by Service Line
CREATE OR REPLACE VIEW metrics.v_los_trend AS
SELECT
    metric_date,
    service_line,
    SUM(discharge_count) as discharges,
    ROUND(AVG(avg_los)::NUMERIC, 1) as avg_los_days,
    ROUND(AVG(median_los)::NUMERIC, 1) as median_los_days,
    ROUND(AVG(expected_los)::NUMERIC, 1) as expected_los_days,
    ROUND(AVG(los_index)::NUMERIC, 2) as los_index
FROM metrics.metric_length_of_stay
WHERE metric_date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY metric_date, service_line
ORDER BY metric_date, service_line;

-- LOS by DRG (Top 20 by Volume)
CREATE OR REPLACE VIEW metrics.v_los_by_drg AS
SELECT
    drg_code,
    drg_description,
    SUM(discharge_count) as total_discharges,
    ROUND(AVG(avg_los)::NUMERIC, 1) as avg_los_days,
    ROUND(AVG(expected_los)::NUMERIC, 1) as expected_los_days,
    ROUND(AVG(los_index)::NUMERIC, 2) as los_index,
    CASE
        WHEN AVG(los_index) > 1.1 THEN 'Above Expected'
        WHEN AVG(los_index) < 0.9 THEN 'Below Expected'
        ELSE 'At Expected'
    END as performance
FROM metrics.metric_length_of_stay
WHERE metric_date >= CURRENT_DATE - INTERVAL '365 days'
GROUP BY drg_code, drg_description
ORDER BY total_discharges DESC
LIMIT 20;

-- Long Stay Patients
CREATE OR REPLACE VIEW metrics.v_long_stay_trend AS
SELECT
    metric_date,
    facility,
    SUM(discharge_count) as total_discharges,
    SUM(long_stay_count_7_plus) as stays_7_plus_days,
    SUM(long_stay_count_14_plus) as stays_14_plus_days,
    SUM(long_stay_count_30_plus) as stays_30_plus_days,
    ROUND(SUM(long_stay_count_7_plus)::NUMERIC / NULLIF(SUM(discharge_count), 0) * 100, 1) as pct_7_plus_days
FROM metrics.metric_length_of_stay
WHERE metric_date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY metric_date, facility
ORDER BY metric_date;

-- LOS Distribution Statistics
CREATE OR REPLACE VIEW metrics.v_los_distribution AS
SELECT
    service_line,
    ROUND(AVG(avg_los)::NUMERIC, 1) as mean_los,
    ROUND(AVG(median_los)::NUMERIC, 1) as median_los,
    ROUND(AVG(p25_los)::NUMERIC, 1) as p25_los,
    ROUND(AVG(p75_los)::NUMERIC, 1) as p75_los,
    ROUND(AVG(p90_los)::NUMERIC, 1) as p90_los,
    ROUND(AVG(std_dev_los)::NUMERIC, 2) as std_dev
FROM metrics.metric_length_of_stay
WHERE metric_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY service_line
ORDER BY service_line;
