-- ED Throughput Views for Grafana Dashboards

-- Current ED Status
CREATE OR REPLACE VIEW metrics.v_ed_current_status AS
SELECT
    facility,
    ed_location,
    SUM(arrivals) as todays_arrivals,
    MAX(patients_in_ed) as current_patients,
    MAX(patients_waiting) as waiting_for_bed,
    ROUND(AVG(avg_door_to_provider)::NUMERIC, 0) as avg_wait_minutes,
    ROUND((AVG(avg_length_of_stay) / 60)::NUMERIC, 1) as avg_los_hours,
    SUM(admitted) as admitted_today,
    SUM(discharged) as discharged_today,
    SUM(left_without_seen) as lwbs_today
FROM metrics.metric_ed_throughput
WHERE metric_date = CURRENT_DATE
GROUP BY facility, ed_location;

-- ED Volume by Hour (Today vs Average)
CREATE OR REPLACE VIEW metrics.v_ed_hourly_pattern AS
WITH today_data AS (
    SELECT metric_hour, arrivals
    FROM metrics.metric_ed_throughput
    WHERE metric_date = CURRENT_DATE
),
avg_data AS (
    SELECT
        metric_hour,
        ROUND(AVG(arrivals)::NUMERIC, 1) as avg_arrivals
    FROM metrics.metric_ed_throughput
    WHERE metric_date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY metric_hour
)
SELECT
    a.metric_hour as hour,
    COALESCE(t.arrivals, 0) as today_arrivals,
    a.avg_arrivals as avg_arrivals,
    COALESCE(t.arrivals, 0) - a.avg_arrivals as variance
FROM avg_data a
LEFT JOIN today_data t ON t.metric_hour = a.metric_hour
ORDER BY a.metric_hour;

-- ED Length of Stay Trend
CREATE OR REPLACE VIEW metrics.v_ed_los_trend AS
SELECT
    metric_date,
    facility,
    ROUND((AVG(avg_length_of_stay) / 60)::NUMERIC, 1) as avg_los_hours,
    ROUND((AVG(median_los) / 60)::NUMERIC, 1) as median_los_hours,
    ROUND((AVG(p90_los) / 60)::NUMERIC, 1) as p90_los_hours,
    SUM(arrivals) as total_arrivals
FROM metrics.metric_ed_throughput
WHERE metric_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY metric_date, facility
ORDER BY metric_date;

-- ED Disposition Summary
CREATE OR REPLACE VIEW metrics.v_ed_disposition AS
SELECT
    metric_date,
    SUM(admitted) as admitted,
    SUM(discharged) as discharged,
    SUM(transferred) as transferred,
    SUM(left_without_seen) as lwbs,
    SUM(left_ama) as ama,
    SUM(arrivals) as total_arrivals,
    ROUND(SUM(admitted)::NUMERIC / NULLIF(SUM(arrivals), 0) * 100, 1) as admission_rate_pct
FROM metrics.metric_ed_throughput
WHERE metric_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY metric_date
ORDER BY metric_date;

-- ED Door-to-Provider Time by Hour
CREATE OR REPLACE VIEW metrics.v_ed_wait_times AS
SELECT
    metric_hour as hour,
    ROUND(AVG(avg_door_to_provider)::NUMERIC, 0) as avg_wait_minutes,
    ROUND(MIN(avg_door_to_provider)::NUMERIC, 0) as min_wait,
    ROUND(MAX(avg_door_to_provider)::NUMERIC, 0) as max_wait
FROM metrics.metric_ed_throughput
WHERE metric_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY metric_hour
ORDER BY metric_hour;
