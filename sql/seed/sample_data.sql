-- Healthcare Analytics Starter Kit
-- Sample/Seed Data for Testing
-- ALL DATA IS SYNTHETIC - NO REAL PHI

-- IMPORTANT: This data is for demonstration and testing only.
-- All patient names start with "Test" and MRNs start with "FAKE-"
-- Do NOT use real patient data for testing.

-- ============================================================================
-- POPULATE DATE DIMENSION (5 years: 2020-2025)
-- ============================================================================

INSERT INTO dim.dim_date (date_key, full_date, year, quarter, month, month_name,
    week_of_year, day_of_month, day_of_week, day_name, day_of_year,
    fiscal_year, fiscal_quarter, fiscal_month, is_weekend, is_holiday,
    is_current_day, is_current_week, is_current_month, is_current_year)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INTEGER as date_key,
    d as full_date,
    EXTRACT(YEAR FROM d)::INTEGER as year,
    EXTRACT(QUARTER FROM d)::INTEGER as quarter,
    EXTRACT(MONTH FROM d)::INTEGER as month,
    TO_CHAR(d, 'Month') as month_name,
    EXTRACT(WEEK FROM d)::INTEGER as week_of_year,
    EXTRACT(DAY FROM d)::INTEGER as day_of_month,
    EXTRACT(DOW FROM d)::INTEGER as day_of_week,
    TO_CHAR(d, 'Day') as day_name,
    EXTRACT(DOY FROM d)::INTEGER as day_of_year,
    CASE WHEN EXTRACT(MONTH FROM d) >= 7 THEN EXTRACT(YEAR FROM d)::INTEGER + 1
         ELSE EXTRACT(YEAR FROM d)::INTEGER END as fiscal_year,
    CASE WHEN EXTRACT(MONTH FROM d) >= 7 THEN ((EXTRACT(MONTH FROM d)::INTEGER - 7) / 3) + 1
         ELSE ((EXTRACT(MONTH FROM d)::INTEGER + 5) / 3) + 1 END as fiscal_quarter,
    CASE WHEN EXTRACT(MONTH FROM d) >= 7 THEN EXTRACT(MONTH FROM d)::INTEGER - 6
         ELSE EXTRACT(MONTH FROM d)::INTEGER + 6 END as fiscal_month,
    EXTRACT(DOW FROM d) IN (0, 6) as is_weekend,
    FALSE as is_holiday,
    d = CURRENT_DATE as is_current_day,
    EXTRACT(WEEK FROM d) = EXTRACT(WEEK FROM CURRENT_DATE) AND EXTRACT(YEAR FROM d) = EXTRACT(YEAR FROM CURRENT_DATE) as is_current_week,
    EXTRACT(MONTH FROM d) = EXTRACT(MONTH FROM CURRENT_DATE) AND EXTRACT(YEAR FROM d) = EXTRACT(YEAR FROM CURRENT_DATE) as is_current_month,
    EXTRACT(YEAR FROM d) = EXTRACT(YEAR FROM CURRENT_DATE) as is_current_year
FROM generate_series('2020-01-01'::date, '2025-12-31'::date, '1 day'::interval) as d
ON CONFLICT (date_key) DO NOTHING;

-- ============================================================================
-- SAMPLE LOCATIONS
-- ============================================================================

INSERT INTO dim.dim_location (location_id, facility_name, building, floor, unit, location_type, service_line, licensed_beds, operational_beds, is_active)
VALUES
    ('LOC-001', 'Sample General Hospital', 'Main Building', '1', 'Emergency Department', 'ED', 'Emergency Medicine', 30, 28, true),
    ('LOC-002', 'Sample General Hospital', 'Main Building', '2', 'Medical ICU', 'ICU', 'Critical Care', 20, 18, true),
    ('LOC-003', 'Sample General Hospital', 'Main Building', '3', 'Surgical ICU', 'ICU', 'Critical Care', 15, 14, true),
    ('LOC-004', 'Sample General Hospital', 'Main Building', '4', 'Medical/Surgical Unit', 'Med-Surg', 'Medical', 45, 42, true),
    ('LOC-005', 'Sample General Hospital', 'Main Building', '5', 'Cardiac Care Unit', 'Step-Down', 'Cardiology', 25, 24, true),
    ('LOC-006', 'Sample General Hospital', 'Tower A', '2', 'Labor & Delivery', 'L&D', 'OB/GYN', 15, 15, true),
    ('LOC-007', 'Sample General Hospital', 'Tower A', '3', 'Postpartum', 'Med-Surg', 'OB/GYN', 20, 20, true),
    ('LOC-008', 'Sample General Hospital', 'Tower B', '2', 'Pediatrics', 'Pediatric', 'Pediatrics', 25, 22, true),
    ('LOC-009', 'Sample General Hospital', 'Tower B', '3', 'Neonatal ICU', 'NICU', 'Neonatology', 30, 28, true),
    ('LOC-010', 'Sample General Hospital', 'Outpatient Center', '1', 'Primary Care Clinic', 'Clinic', 'Primary Care', 0, 0, true)
ON CONFLICT (location_id) DO NOTHING;

-- ============================================================================
-- SAMPLE PROVIDERS
-- ============================================================================

INSERT INTO dim.dim_provider (provider_id, npi, first_name, last_name, full_name, credentials, specialty, department, provider_type, is_active)
VALUES
    ('PROV-001', '1234567890', 'Test', 'Physician One', 'Test Physician One, MD', 'MD', 'Internal Medicine', 'Medicine', 'Physician', true),
    ('PROV-002', '1234567891', 'Test', 'Physician Two', 'Test Physician Two, MD', 'MD', 'Emergency Medicine', 'Emergency', 'Physician', true),
    ('PROV-003', '1234567892', 'Test', 'Surgeon One', 'Test Surgeon One, MD', 'MD, FACS', 'General Surgery', 'Surgery', 'Physician', true),
    ('PROV-004', '1234567893', 'Test', 'Cardiologist One', 'Test Cardiologist One, MD', 'MD, FACC', 'Cardiology', 'Cardiology', 'Physician', true),
    ('PROV-005', '1234567894', 'Test', 'Hospitalist One', 'Test Hospitalist One, MD', 'MD', 'Hospital Medicine', 'Medicine', 'Physician', true),
    ('PROV-006', '1234567895', 'Test', 'Nurse Practitioner', 'Test NP One, NP', 'NP', 'Family Medicine', 'Primary Care', 'NP', true),
    ('PROV-007', '1234567896', 'Test', 'Intensivist One', 'Test Intensivist One, MD', 'MD', 'Critical Care', 'ICU', 'Physician', true)
ON CONFLICT (provider_id) DO NOTHING;

-- ============================================================================
-- SAMPLE DIAGNOSES (Common ICD-10 codes)
-- ============================================================================

INSERT INTO dim.dim_diagnosis (code, code_system, short_description, long_description, chapter, category, is_chronic, is_comorbidity)
VALUES
    ('E11.9', 'ICD-10-CM', 'Type 2 DM w/o complications', 'Type 2 diabetes mellitus without complications', 'Endocrine diseases', 'E11', true, true),
    ('I10', 'ICD-10-CM', 'Essential hypertension', 'Essential (primary) hypertension', 'Circulatory system', 'I10', true, true),
    ('I50.9', 'ICD-10-CM', 'Heart failure, unspecified', 'Heart failure, unspecified', 'Circulatory system', 'I50', true, true),
    ('J44.1', 'ICD-10-CM', 'COPD with acute exacerbation', 'Chronic obstructive pulmonary disease with acute exacerbation', 'Respiratory system', 'J44', true, true),
    ('N18.3', 'ICD-10-CM', 'CKD stage 3', 'Chronic kidney disease, stage 3 (moderate)', 'Genitourinary system', 'N18', true, true),
    ('J18.9', 'ICD-10-CM', 'Pneumonia, unspecified', 'Pneumonia, unspecified organism', 'Respiratory system', 'J18', false, false),
    ('K92.2', 'ICD-10-CM', 'GI hemorrhage, unspecified', 'Gastrointestinal hemorrhage, unspecified', 'Digestive system', 'K92', false, false),
    ('A41.9', 'ICD-10-CM', 'Sepsis, unspecified', 'Sepsis, unspecified organism', 'Infectious diseases', 'A41', false, false),
    ('I21.3', 'ICD-10-CM', 'STEMI unspecified site', 'ST elevation myocardial infarction of unspecified site', 'Circulatory system', 'I21', false, false),
    ('S72.001A', 'ICD-10-CM', 'Fx femur, initial', 'Fracture of unspecified part of neck of right femur, initial encounter', 'Injury', 'S72', false, false),
    ('F32.9', 'ICD-10-CM', 'Major depression', 'Major depressive disorder, single episode, unspecified', 'Mental disorders', 'F32', true, true),
    ('G47.33', 'ICD-10-CM', 'Obstructive sleep apnea', 'Obstructive sleep apnea (adult) (pediatric)', 'Nervous system', 'G47', true, true)
ON CONFLICT (code, code_system) DO NOTHING;

-- ============================================================================
-- SAMPLE PATIENTS (500 synthetic patients)
-- ============================================================================

INSERT INTO dim.dim_patient (mrn, effective_date, is_current, first_name, last_name, date_of_birth, age, age_group, gender, city, state, postal_code, country, language, marital_status, race, ethnicity, deceased, source_system, source_id)
SELECT
    'FAKE-' || LPAD(i::TEXT, 6, '0') as mrn,
    '2020-01-01'::DATE as effective_date,
    true as is_current,
    'Test Patient' as first_name,
    'Number ' || i as last_name,
    DATE '1940-01-01' + (random() * 30000)::INTEGER as date_of_birth,
    EXTRACT(YEAR FROM AGE(DATE '1940-01-01' + (random() * 30000)::INTEGER))::INTEGER as age,
    CASE
        WHEN EXTRACT(YEAR FROM AGE(DATE '1940-01-01' + (random() * 30000)::INTEGER)) < 18 THEN '0-17'
        WHEN EXTRACT(YEAR FROM AGE(DATE '1940-01-01' + (random() * 30000)::INTEGER)) < 45 THEN '18-44'
        WHEN EXTRACT(YEAR FROM AGE(DATE '1940-01-01' + (random() * 30000)::INTEGER)) < 65 THEN '45-64'
        ELSE '65+'
    END as age_group,
    CASE WHEN random() > 0.5 THEN 'male' ELSE 'female' END as gender,
    (ARRAY['Springfield', 'Riverside', 'Franklin', 'Greenville', 'Madison'])[1 + (random() * 4)::INTEGER] as city,
    (ARRAY['CA', 'NY', 'TX', 'FL', 'IL'])[1 + (random() * 4)::INTEGER] as state,
    LPAD((10000 + random() * 89999)::INTEGER::TEXT, 5, '0') as postal_code,
    'USA' as country,
    (ARRAY['English', 'Spanish', 'Chinese', 'Vietnamese', 'Korean'])[1 + (random() * 4)::INTEGER] as language,
    (ARRAY['single', 'married', 'divorced', 'widowed'])[1 + (random() * 3)::INTEGER] as marital_status,
    (ARRAY['White', 'Black', 'Asian', 'Hispanic', 'Other'])[1 + (random() * 4)::INTEGER] as race,
    (ARRAY['Non-Hispanic', 'Hispanic', 'Unknown'])[1 + (random() * 2)::INTEGER] as ethnicity,
    CASE WHEN random() > 0.98 THEN true ELSE false END as deceased,
    'sample_data' as source_system,
    'SAMPLE-' || i as source_id
FROM generate_series(1, 500) as i
ON CONFLICT DO NOTHING;

-- ============================================================================
-- SAMPLE ENCOUNTERS (2000 encounters over 12 months)
-- ============================================================================

INSERT INTO dim.fact_encounter (patient_key, admission_date_key, discharge_date_key, location_key, attending_provider_key, primary_diagnosis_key,
    encounter_number, encounter_type, encounter_class, status, admit_source, discharge_disposition,
    admission_datetime, discharge_datetime, length_of_stay_hours, length_of_stay_days, is_readmission, is_ed_visit, source_system, source_id)
SELECT
    p.patient_key,
    TO_CHAR(admit_date, 'YYYYMMDD')::INTEGER as admission_date_key,
    TO_CHAR(admit_date + (los_hours / 24.0 || ' hours')::INTERVAL, 'YYYYMMDD')::INTEGER as discharge_date_key,
    (SELECT location_key FROM dim.dim_location ORDER BY random() LIMIT 1) as location_key,
    (SELECT provider_key FROM dim.dim_provider ORDER BY random() LIMIT 1) as attending_provider_key,
    (SELECT diagnosis_key FROM dim.dim_diagnosis ORDER BY random() LIMIT 1) as primary_diagnosis_key,
    'ENC-' || LPAD(i::TEXT, 8, '0') as encounter_number,
    (ARRAY['inpatient', 'outpatient', 'emergency', 'observation'])[1 + (random() * 3)::INTEGER] as encounter_type,
    CASE WHEN random() > 0.7 THEN 'inpatient' ELSE 'outpatient' END as encounter_class,
    'finished' as status,
    (ARRAY['Emergency Room', 'Physician Referral', 'Transfer', 'Self Referral'])[1 + (random() * 3)::INTEGER] as admit_source,
    (ARRAY['Home', 'SNF', 'Rehab', 'Home Health', 'Expired'])[1 + (random() * 4)::INTEGER] as discharge_disposition,
    admit_date as admission_datetime,
    admit_date + (los_hours / 24.0 || ' hours')::INTERVAL as discharge_datetime,
    los_hours as length_of_stay_hours,
    ROUND((los_hours / 24.0)::NUMERIC, 2) as length_of_stay_days,
    CASE WHEN random() > 0.88 THEN true ELSE false END as is_readmission,
    CASE WHEN random() > 0.6 THEN true ELSE false END as is_ed_visit,
    'sample_data' as source_system,
    'ENC-SAMPLE-' || i as source_id
FROM (
    SELECT
        i,
        (SELECT patient_key FROM dim.dim_patient WHERE is_current ORDER BY random() LIMIT 1) as patient_key,
        CURRENT_DATE - ((random() * 365)::INTEGER || ' days')::INTERVAL as admit_date,
        (4 + random() * 200)::NUMERIC as los_hours
    FROM generate_series(1, 2000) as i
) as enc_data
JOIN dim.dim_patient p ON p.patient_key = enc_data.patient_key
ON CONFLICT DO NOTHING;

-- ============================================================================
-- SAMPLE CENSUS DATA (Last 90 days)
-- ============================================================================

INSERT INTO metrics.metric_patient_census (census_date, facility, department, unit, midnight_census, admissions, discharges, transfers_in, transfers_out, licensed_beds, operational_beds, occupancy_rate)
SELECT
    d::DATE as census_date,
    'Sample General Hospital' as facility,
    l.unit as department,
    l.unit as unit,
    (l.operational_beds * (0.6 + random() * 0.35))::INTEGER as midnight_census,
    (3 + random() * 10)::INTEGER as admissions,
    (3 + random() * 10)::INTEGER as discharges,
    (random() * 3)::INTEGER as transfers_in,
    (random() * 3)::INTEGER as transfers_out,
    l.licensed_beds,
    l.operational_beds,
    ROUND((0.6 + random() * 0.35) * 100, 1) as occupancy_rate
FROM generate_series(CURRENT_DATE - INTERVAL '90 days', CURRENT_DATE, '1 day'::INTERVAL) as d
CROSS JOIN dim.dim_location l
WHERE l.location_type IN ('Med-Surg', 'ICU', 'Step-Down')
ON CONFLICT (census_date, location_key) DO NOTHING;

-- ============================================================================
-- SAMPLE ED THROUGHPUT (Last 30 days, hourly)
-- ============================================================================

INSERT INTO metrics.metric_ed_throughput (metric_date, metric_hour, facility, ed_location, arrivals, departures, patients_in_ed, patients_waiting, avg_door_to_provider, avg_length_of_stay, admitted, discharged, left_without_seen)
SELECT
    d::DATE as metric_date,
    h as metric_hour,
    'Sample General Hospital' as facility,
    'Emergency Department' as ed_location,
    CASE
        WHEN h BETWEEN 10 AND 20 THEN (5 + random() * 10)::INTEGER
        ELSE (2 + random() * 5)::INTEGER
    END as arrivals,
    CASE
        WHEN h BETWEEN 10 AND 20 THEN (4 + random() * 8)::INTEGER
        ELSE (2 + random() * 4)::INTEGER
    END as departures,
    (15 + random() * 25)::INTEGER as patients_in_ed,
    (2 + random() * 8)::INTEGER as patients_waiting,
    (15 + random() * 45)::NUMERIC as avg_door_to_provider,
    (120 + random() * 180)::NUMERIC as avg_length_of_stay,
    (1 + random() * 3)::INTEGER as admitted,
    (3 + random() * 6)::INTEGER as discharged,
    CASE WHEN random() > 0.9 THEN 1 ELSE 0 END as left_without_seen
FROM generate_series(CURRENT_DATE - INTERVAL '30 days', CURRENT_DATE, '1 day'::INTERVAL) as d
CROSS JOIN generate_series(0, 23) as h
ON CONFLICT (metric_date, metric_hour, facility) DO NOTHING;

-- ============================================================================
-- SAMPLE QUALITY INDICATORS (Monthly for last 12 months)
-- ============================================================================

INSERT INTO metrics.metric_quality_indicator (metric_date, metric_period, facility, indicator_code, indicator_name, indicator_category, numerator, denominator, rate, target_rate, meets_target)
SELECT
    (DATE_TRUNC('month', CURRENT_DATE) - (i || ' months')::INTERVAL)::DATE as metric_date,
    'monthly' as metric_period,
    'Sample General Hospital' as facility,
    qi.code as indicator_code,
    qi.name as indicator_name,
    qi.category as indicator_category,
    (qi.base_num * (0.8 + random() * 0.4))::INTEGER as numerator,
    (qi.base_denom * (0.9 + random() * 0.2))::INTEGER as denominator,
    (qi.base_rate * (0.8 + random() * 0.4))::NUMERIC as rate,
    qi.target as target_rate,
    CASE WHEN random() > 0.3 THEN true ELSE false END as meets_target
FROM generate_series(0, 11) as i
CROSS JOIN (
    VALUES
        ('READM_30_HF', '30-Day Readmission - Heart Failure', 'Readmission', 15, 100, 0.15, 0.12),
        ('READM_30_AMI', '30-Day Readmission - AMI', 'Readmission', 12, 80, 0.15, 0.12),
        ('MORT_30_HF', '30-Day Mortality - Heart Failure', 'Mortality', 8, 100, 0.08, 0.10),
        ('CAUTI', 'Catheter-Associated UTI', 'HAI', 2, 500, 0.004, 0.003),
        ('CLABSI', 'Central Line-Associated BSI', 'HAI', 1, 300, 0.003, 0.002),
        ('FALLS', 'Patient Falls', 'Safety', 5, 1000, 0.005, 0.004),
        ('PRESSURE_INJ', 'Pressure Injuries', 'Safety', 3, 800, 0.00375, 0.003)
) as qi(code, name, category, base_num, base_denom, base_rate, target)
ON CONFLICT DO NOTHING;

-- Update row counts for verification
DO $$
BEGIN
    RAISE NOTICE 'Sample data loaded successfully';
    RAISE NOTICE 'Patients: %', (SELECT COUNT(*) FROM dim.dim_patient);
    RAISE NOTICE 'Encounters: %', (SELECT COUNT(*) FROM dim.fact_encounter);
    RAISE NOTICE 'Census Records: %', (SELECT COUNT(*) FROM metrics.metric_patient_census);
    RAISE NOTICE 'ED Throughput Records: %', (SELECT COUNT(*) FROM metrics.metric_ed_throughput);
    RAISE NOTICE 'Quality Indicators: %', (SELECT COUNT(*) FROM metrics.metric_quality_indicator);
END $$;
