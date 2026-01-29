-- Readmission Risk Views for Grafana Dashboards

-- 30-Day Readmission Rate Trend
CREATE OR REPLACE VIEW metrics.v_readmission_trend AS
SELECT
    discharge_date,
    facility,
    SUM(index_discharges) as discharges,
    SUM(readmissions_30_day) as readmissions,
    ROUND(SUM(readmissions_30_day)::NUMERIC / NULLIF(SUM(index_discharges), 0) * 100, 2) as readmission_rate_pct
FROM metrics.metric_readmission
WHERE discharge_date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY discharge_date, facility
ORDER BY discharge_date;

-- Readmission by Diagnosis Category
CREATE OR REPLACE VIEW metrics.v_readmission_by_diagnosis AS
SELECT
    discharge_diagnosis_category,
    SUM(index_discharges) as total_discharges,
    SUM(readmissions_30_day) as total_readmissions,
    ROUND(SUM(readmissions_30_day)::NUMERIC / NULLIF(SUM(index_discharges), 0) * 100, 2) as readmission_rate_pct,
    ROUND(AVG(cms_expected_rate) * 100, 2) as expected_rate_pct
FROM metrics.metric_readmission
WHERE discharge_date >= CURRENT_DATE - INTERVAL '365 days'
GROUP BY discharge_diagnosis_category
HAVING SUM(index_discharges) >= 10
ORDER BY readmission_rate_pct DESC;

-- Readmission by Payer Type
CREATE OR REPLACE VIEW metrics.v_readmission_by_payer AS
SELECT
    payer_type,
    SUM(index_discharges) as total_discharges,
    SUM(readmissions_30_day) as total_readmissions,
    ROUND(SUM(readmissions_30_day)::NUMERIC / NULLIF(SUM(index_discharges), 0) * 100, 2) as readmission_rate_pct
FROM metrics.metric_readmission
WHERE discharge_date >= CURRENT_DATE - INTERVAL '365 days'
GROUP BY payer_type
ORDER BY total_discharges DESC;

-- Potentially Preventable Readmissions
CREATE OR REPLACE VIEW metrics.v_preventable_readmissions AS
SELECT
    discharge_date,
    facility,
    SUM(readmissions_30_day) as all_readmissions,
    SUM(potentially_preventable_30_day) as preventable_readmissions,
    ROUND(SUM(potentially_preventable_30_day)::NUMERIC / NULLIF(SUM(readmissions_30_day), 0) * 100, 1) as preventable_pct
FROM metrics.metric_readmission
WHERE discharge_date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY discharge_date, facility
ORDER BY discharge_date;
