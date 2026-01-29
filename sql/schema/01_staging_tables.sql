-- Healthcare Analytics Starter Kit
-- Staging Tables Schema
-- These tables receive raw data from EMR connectors before transformation

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create staging schema
CREATE SCHEMA IF NOT EXISTS staging;

-- ============================================================================
-- STAGING TABLES
-- ============================================================================

-- Staging: Patients
CREATE TABLE IF NOT EXISTS staging.staging_patient (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(50) NOT NULL,
    source_id VARCHAR(100) NOT NULL,
    batch_id VARCHAR(50),

    -- Demographics
    mrn VARCHAR(50),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    middle_name VARCHAR(100),
    date_of_birth DATE,
    gender VARCHAR(20),

    -- Address
    address_line1 VARCHAR(200),
    address_line2 VARCHAR(200),
    city VARCHAR(100),
    state VARCHAR(50),
    postal_code VARCHAR(20),
    country VARCHAR(50),

    -- Contact
    phone VARCHAR(30),
    email VARCHAR(100),

    -- Additional
    language VARCHAR(50),
    marital_status VARCHAR(20),
    race VARCHAR(50),
    ethnicity VARCHAR(50),
    deceased BOOLEAN DEFAULT FALSE,
    deceased_date DATE,
    ssn_hash VARCHAR(100),

    -- Raw data
    raw_data JSONB,

    -- Processing
    is_processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_staging_patient_source ON staging.staging_patient(source_system, source_id);
CREATE INDEX IF NOT EXISTS ix_staging_patient_mrn ON staging.staging_patient(mrn);
CREATE INDEX IF NOT EXISTS ix_staging_patient_batch ON staging.staging_patient(batch_id);
CREATE INDEX IF NOT EXISTS ix_staging_patient_processed ON staging.staging_patient(is_processed);

-- Staging: Encounters
CREATE TABLE IF NOT EXISTS staging.staging_encounter (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(50) NOT NULL,
    source_id VARCHAR(100) NOT NULL,
    batch_id VARCHAR(50),

    patient_source_id VARCHAR(100),
    encounter_type VARCHAR(50),
    encounter_class VARCHAR(50),
    status VARCHAR(30),

    admission_date TIMESTAMP WITH TIME ZONE,
    discharge_date TIMESTAMP WITH TIME ZONE,

    location VARCHAR(200),
    department VARCHAR(200),
    facility VARCHAR(200),
    attending_provider VARCHAR(200),

    admit_source VARCHAR(100),
    discharge_disposition VARCHAR(100),
    primary_diagnosis_code VARCHAR(20),
    drg_code VARCHAR(10),
    financial_class VARCHAR(50),

    length_of_stay_hours NUMERIC(10,2),
    length_of_stay_days NUMERIC(10,2),

    raw_data JSONB,
    is_processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_staging_encounter_source ON staging.staging_encounter(source_system, source_id);
CREATE INDEX IF NOT EXISTS ix_staging_encounter_patient ON staging.staging_encounter(patient_source_id);
CREATE INDEX IF NOT EXISTS ix_staging_encounter_batch ON staging.staging_encounter(batch_id);
CREATE INDEX IF NOT EXISTS ix_staging_encounter_dates ON staging.staging_encounter(admission_date, discharge_date);

-- Staging: Diagnoses
CREATE TABLE IF NOT EXISTS staging.staging_diagnosis (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(50) NOT NULL,
    source_id VARCHAR(100) NOT NULL,
    batch_id VARCHAR(50),

    patient_source_id VARCHAR(100),
    encounter_source_id VARCHAR(100),

    code VARCHAR(20) NOT NULL,
    code_system VARCHAR(50),
    description VARCHAR(500),

    diagnosis_type VARCHAR(50),
    clinical_status VARCHAR(30),
    verification_status VARCHAR(30),
    severity VARCHAR(30),

    onset_date DATE,
    abatement_date DATE,
    recorded_date DATE,

    rank INTEGER,
    present_on_admission VARCHAR(5),

    icd10_chapter VARCHAR(100),
    icd10_category VARCHAR(10),

    raw_data JSONB,
    is_processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_staging_diagnosis_source ON staging.staging_diagnosis(source_system, source_id);
CREATE INDEX IF NOT EXISTS ix_staging_diagnosis_code ON staging.staging_diagnosis(code);
CREATE INDEX IF NOT EXISTS ix_staging_diagnosis_encounter ON staging.staging_diagnosis(encounter_source_id);
CREATE INDEX IF NOT EXISTS ix_staging_diagnosis_batch ON staging.staging_diagnosis(batch_id);

-- Staging: Procedures
CREATE TABLE IF NOT EXISTS staging.staging_procedure (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(50) NOT NULL,
    source_id VARCHAR(100) NOT NULL,
    batch_id VARCHAR(50),

    patient_source_id VARCHAR(100),
    encounter_source_id VARCHAR(100),

    code VARCHAR(20) NOT NULL,
    code_system VARCHAR(50),
    description VARCHAR(500),

    status VARCHAR(30),
    performed_date TIMESTAMP WITH TIME ZONE,
    duration_minutes INTEGER,

    performer VARCHAR(200),
    location VARCHAR(200),
    laterality VARCHAR(20),
    body_site VARCHAR(100),
    device VARCHAR(200),
    anesthesia_type VARCHAR(50),

    cpt_category VARCHAR(50),
    is_surgical BOOLEAN,

    raw_data JSONB,
    is_processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_staging_procedure_source ON staging.staging_procedure(source_system, source_id);
CREATE INDEX IF NOT EXISTS ix_staging_procedure_code ON staging.staging_procedure(code);
CREATE INDEX IF NOT EXISTS ix_staging_procedure_encounter ON staging.staging_procedure(encounter_source_id);
CREATE INDEX IF NOT EXISTS ix_staging_procedure_batch ON staging.staging_procedure(batch_id);

-- Staging: Lab Results
CREATE TABLE IF NOT EXISTS staging.staging_lab_result (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(50) NOT NULL,
    source_id VARCHAR(100) NOT NULL,
    batch_id VARCHAR(50),

    patient_source_id VARCHAR(100),
    encounter_source_id VARCHAR(100),

    code VARCHAR(50) NOT NULL,
    code_system VARCHAR(50),
    test_name VARCHAR(200),
    category VARCHAR(100),

    value NUMERIC(18,6),
    value_string VARCHAR(500),
    value_unit VARCHAR(50),

    reference_range_low NUMERIC(18,6),
    reference_range_high NUMERIC(18,6),
    reference_range_text VARCHAR(200),

    interpretation VARCHAR(50),
    status VARCHAR(30),

    effective_date TIMESTAMP WITH TIME ZONE,
    issued_date TIMESTAMP WITH TIME ZONE,

    specimen_type VARCHAR(100),
    ordering_provider VARCHAR(200),
    performing_lab VARCHAR(200),

    is_abnormal BOOLEAN,
    is_critical BOOLEAN,

    raw_data JSONB,
    is_processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_staging_lab_source ON staging.staging_lab_result(source_system, source_id);
CREATE INDEX IF NOT EXISTS ix_staging_lab_code ON staging.staging_lab_result(code);
CREATE INDEX IF NOT EXISTS ix_staging_lab_patient ON staging.staging_lab_result(patient_source_id);
CREATE INDEX IF NOT EXISTS ix_staging_lab_date ON staging.staging_lab_result(effective_date);
CREATE INDEX IF NOT EXISTS ix_staging_lab_batch ON staging.staging_lab_result(batch_id);

-- Staging: Vitals
CREATE TABLE IF NOT EXISTS staging.staging_vital (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(50) NOT NULL,
    source_id VARCHAR(100) NOT NULL,
    batch_id VARCHAR(50),

    patient_source_id VARCHAR(100),
    encounter_source_id VARCHAR(100),

    recorded_date TIMESTAMP WITH TIME ZONE,

    heart_rate NUMERIC(6,2),
    respiratory_rate NUMERIC(6,2),
    systolic_bp NUMERIC(6,2),
    diastolic_bp NUMERIC(6,2),
    mean_arterial_pressure NUMERIC(6,2),
    temperature NUMERIC(6,2),
    oxygen_saturation NUMERIC(6,2),

    oxygen_device VARCHAR(100),
    fio2 NUMERIC(4,2),
    weight NUMERIC(8,2),
    height NUMERIC(6,2),
    bmi NUMERIC(6,2),
    pain_score INTEGER,

    gcs_total INTEGER,
    gcs_eye INTEGER,
    gcs_verbal INTEGER,
    gcs_motor INTEGER,

    position VARCHAR(50),
    location VARCHAR(200),
    recorder VARCHAR(200),

    news_score INTEGER,
    bp_classification VARCHAR(50),

    raw_data JSONB,
    is_processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_staging_vital_source ON staging.staging_vital(source_system, source_id);
CREATE INDEX IF NOT EXISTS ix_staging_vital_patient ON staging.staging_vital(patient_source_id);
CREATE INDEX IF NOT EXISTS ix_staging_vital_date ON staging.staging_vital(recorded_date);
CREATE INDEX IF NOT EXISTS ix_staging_vital_batch ON staging.staging_vital(batch_id);

-- Staging: Medications
CREATE TABLE IF NOT EXISTS staging.staging_medication (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(50) NOT NULL,
    source_id VARCHAR(100) NOT NULL,
    batch_id VARCHAR(50),

    patient_source_id VARCHAR(100),
    encounter_source_id VARCHAR(100),

    medication_code VARCHAR(50),
    medication_name VARCHAR(500) NOT NULL,
    generic_name VARCHAR(200),
    brand_name VARCHAR(200),
    ndc_code VARCHAR(20),
    rxnorm_code VARCHAR(20),

    status VARCHAR(30),
    intent VARCHAR(30),
    dose_value NUMERIC(12,4),
    dose_unit VARCHAR(30),
    route VARCHAR(50),
    frequency VARCHAR(100),
    prn BOOLEAN DEFAULT FALSE,

    start_date DATE,
    end_date DATE,
    authored_date TIMESTAMP WITH TIME ZONE,

    prescriber VARCHAR(200),
    pharmacy VARCHAR(200),

    quantity NUMERIC(12,4),
    refills INTEGER,
    days_supply INTEGER,

    drug_class VARCHAR(50),
    is_high_alert BOOLEAN,
    is_controlled BOOLEAN,
    is_opioid BOOLEAN,

    raw_data JSONB,
    is_processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_staging_medication_source ON staging.staging_medication(source_system, source_id);
CREATE INDEX IF NOT EXISTS ix_staging_medication_patient ON staging.staging_medication(patient_source_id);
CREATE INDEX IF NOT EXISTS ix_staging_medication_name ON staging.staging_medication(medication_name);
CREATE INDEX IF NOT EXISTS ix_staging_medication_batch ON staging.staging_medication(batch_id);

-- ETL Watermark tracking
CREATE TABLE IF NOT EXISTS staging.etl_watermark (
    id SERIAL PRIMARY KEY,
    source_system VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    last_value TIMESTAMP WITH TIME ZONE NOT NULL,
    last_run_at TIMESTAMP WITH TIME ZONE NOT NULL,
    records_processed INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_system, entity_type)
);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION staging.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to all staging tables
DO $$
DECLARE
    t TEXT;
BEGIN
    FOR t IN
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'staging'
        AND table_name LIKE 'staging_%'
    LOOP
        EXECUTE format('
            DROP TRIGGER IF EXISTS update_%I_updated_at ON staging.%I;
            CREATE TRIGGER update_%I_updated_at
            BEFORE UPDATE ON staging.%I
            FOR EACH ROW
            EXECUTE FUNCTION staging.update_updated_at_column();
        ', t, t, t, t);
    END LOOP;
END $$;
