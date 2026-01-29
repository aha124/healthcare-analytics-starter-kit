-- Healthcare Analytics Starter Kit
-- Dimensional (Star Schema) Tables
-- Optimized for analytics queries and dashboard performance

-- ============================================================================
-- DIMENSION TABLES
-- ============================================================================

-- Dimension: Date
CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY,  -- YYYYMMDD format
    full_date DATE UNIQUE NOT NULL,

    -- Date components
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    week_of_year INTEGER NOT NULL,
    day_of_month INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    day_of_year INTEGER NOT NULL,

    -- Fiscal calendar (July fiscal year start)
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter INTEGER NOT NULL,
    fiscal_month INTEGER NOT NULL,

    -- Flags
    is_weekend BOOLEAN NOT NULL,
    is_holiday BOOLEAN DEFAULT FALSE,
    holiday_name VARCHAR(50),

    -- Relative dates (updated by scheduled job)
    is_current_day BOOLEAN DEFAULT FALSE,
    is_current_week BOOLEAN DEFAULT FALSE,
    is_current_month BOOLEAN DEFAULT FALSE,
    is_current_year BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS ix_dim_date_year_month ON dim_date(year, month);
CREATE INDEX IF NOT EXISTS ix_dim_date_fiscal ON dim_date(fiscal_year, fiscal_quarter);

-- Dimension: Patient
CREATE TABLE IF NOT EXISTS dim_patient (
    patient_key SERIAL PRIMARY KEY,
    mrn VARCHAR(50) NOT NULL,

    -- SCD Type 2 fields
    effective_date DATE NOT NULL,
    expiration_date DATE,
    is_current BOOLEAN DEFAULT TRUE NOT NULL,

    -- Demographics
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    date_of_birth DATE,
    age INTEGER,
    age_group VARCHAR(20),
    gender VARCHAR(20),

    -- Geography
    city VARCHAR(100),
    state VARCHAR(50),
    postal_code VARCHAR(20),
    country VARCHAR(50),

    -- Additional
    language VARCHAR(50),
    marital_status VARCHAR(20),
    race VARCHAR(50),
    ethnicity VARCHAR(50),

    -- Status
    deceased BOOLEAN DEFAULT FALSE,
    deceased_date DATE,

    -- Audit
    row_hash VARCHAR(64),
    source_system VARCHAR(50),
    source_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_dim_patient_mrn_current ON dim_patient(mrn, is_current);
CREATE INDEX IF NOT EXISTS ix_dim_patient_demographics ON dim_patient(gender, age_group);
CREATE INDEX IF NOT EXISTS ix_dim_patient_geography ON dim_patient(state, city);
CREATE UNIQUE INDEX IF NOT EXISTS ix_dim_patient_mrn_effective ON dim_patient(mrn, effective_date);

-- Dimension: Provider
CREATE TABLE IF NOT EXISTS dim_provider (
    provider_key SERIAL PRIMARY KEY,
    provider_id VARCHAR(50) UNIQUE NOT NULL,
    npi VARCHAR(20),

    first_name VARCHAR(100),
    last_name VARCHAR(100),
    full_name VARCHAR(200),
    credentials VARCHAR(50),

    specialty VARCHAR(100),
    department VARCHAR(100),
    provider_type VARCHAR(50),

    is_active BOOLEAN DEFAULT TRUE,

    source_system VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_dim_provider_npi ON dim_provider(npi);
CREATE INDEX IF NOT EXISTS ix_dim_provider_specialty ON dim_provider(specialty);

-- Dimension: Location
CREATE TABLE IF NOT EXISTS dim_location (
    location_key SERIAL PRIMARY KEY,
    location_id VARCHAR(50) UNIQUE NOT NULL,

    facility_name VARCHAR(200),
    building VARCHAR(100),
    floor VARCHAR(20),
    unit VARCHAR(100),
    room VARCHAR(50),
    bed VARCHAR(20),

    location_type VARCHAR(50),
    service_line VARCHAR(100),
    cost_center VARCHAR(50),

    licensed_beds INTEGER,
    operational_beds INTEGER,

    is_active BOOLEAN DEFAULT TRUE,

    source_system VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_dim_location_facility ON dim_location(facility_name);
CREATE INDEX IF NOT EXISTS ix_dim_location_type ON dim_location(location_type);

-- Dimension: Diagnosis
CREATE TABLE IF NOT EXISTS dim_diagnosis (
    diagnosis_key SERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL,
    code_system VARCHAR(50) NOT NULL,

    short_description VARCHAR(100),
    long_description VARCHAR(500),

    chapter VARCHAR(100),
    category VARCHAR(10),
    subcategory VARCHAR(10),

    ccs_category VARCHAR(100),
    drg_mdc VARCHAR(100),

    is_chronic BOOLEAN,
    is_comorbidity BOOLEAN,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(code, code_system)
);

CREATE INDEX IF NOT EXISTS ix_dim_diagnosis_code ON dim_diagnosis(code);
CREATE INDEX IF NOT EXISTS ix_dim_diagnosis_chapter ON dim_diagnosis(chapter);

-- Dimension: Procedure
CREATE TABLE IF NOT EXISTS dim_procedure (
    procedure_key SERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL,
    code_system VARCHAR(50) NOT NULL,

    short_description VARCHAR(100),
    long_description VARCHAR(500),

    category VARCHAR(100),
    subcategory VARCHAR(100),

    is_surgical BOOLEAN,
    is_inpatient_only BOOLEAN,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(code, code_system)
);

CREATE INDEX IF NOT EXISTS ix_dim_procedure_code ON dim_procedure(code);

-- Dimension: Medication
CREATE TABLE IF NOT EXISTS dim_medication (
    medication_key SERIAL PRIMARY KEY,
    rxnorm_code VARCHAR(20),
    ndc_code VARCHAR(20),

    generic_name VARCHAR(200) NOT NULL,
    brand_name VARCHAR(200),

    drug_class VARCHAR(100),
    therapeutic_class VARCHAR(100),
    pharmacologic_class VARCHAR(100),

    route VARCHAR(50),
    form VARCHAR(50),
    strength VARCHAR(50),

    is_controlled BOOLEAN,
    dea_schedule VARCHAR(10),
    is_high_alert BOOLEAN,
    is_antibiotic BOOLEAN,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_dim_medication_rxnorm ON dim_medication(rxnorm_code);
CREATE INDEX IF NOT EXISTS ix_dim_medication_generic ON dim_medication(generic_name);
CREATE INDEX IF NOT EXISTS ix_dim_medication_class ON dim_medication(drug_class);

-- ============================================================================
-- FACT TABLES
-- ============================================================================

-- Fact: Encounters
CREATE TABLE IF NOT EXISTS fact_encounter (
    encounter_key SERIAL PRIMARY KEY,

    -- Dimension keys
    patient_key INTEGER NOT NULL REFERENCES dim_patient(patient_key),
    admission_date_key INTEGER REFERENCES dim_date(date_key),
    discharge_date_key INTEGER REFERENCES dim_date(date_key),
    location_key INTEGER REFERENCES dim_location(location_key),
    attending_provider_key INTEGER REFERENCES dim_provider(provider_key),
    primary_diagnosis_key INTEGER REFERENCES dim_diagnosis(diagnosis_key),

    -- Degenerate dimensions
    encounter_number VARCHAR(50),
    encounter_type VARCHAR(50),
    encounter_class VARCHAR(50),
    status VARCHAR(30),
    admit_source VARCHAR(100),
    discharge_disposition VARCHAR(100),
    drg_code VARCHAR(10),
    financial_class VARCHAR(50),

    -- Timestamps
    admission_datetime TIMESTAMP WITH TIME ZONE,
    discharge_datetime TIMESTAMP WITH TIME ZONE,

    -- Measures
    length_of_stay_hours NUMERIC(10,2),
    length_of_stay_days NUMERIC(10,2),
    diagnosis_count INTEGER,
    procedure_count INTEGER,
    total_charges NUMERIC(14,2),
    total_cost NUMERIC(14,2),

    -- Flags
    is_readmission BOOLEAN,
    days_since_last_discharge INTEGER,
    is_ed_visit BOOLEAN,
    was_admitted_from_ed BOOLEAN,

    -- Audit
    source_system VARCHAR(50),
    source_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_fact_encounter_patient ON fact_encounter(patient_key);
CREATE INDEX IF NOT EXISTS ix_fact_encounter_admission_date ON fact_encounter(admission_date_key);
CREATE INDEX IF NOT EXISTS ix_fact_encounter_type ON fact_encounter(encounter_type);
CREATE INDEX IF NOT EXISTS ix_fact_encounter_location ON fact_encounter(location_key);

-- Fact: Diagnoses (Bridge table)
CREATE TABLE IF NOT EXISTS fact_diagnosis (
    fact_diagnosis_key SERIAL PRIMARY KEY,

    encounter_key INTEGER NOT NULL REFERENCES fact_encounter(encounter_key),
    patient_key INTEGER NOT NULL REFERENCES dim_patient(patient_key),
    diagnosis_key INTEGER NOT NULL REFERENCES dim_diagnosis(diagnosis_key),
    diagnosis_date_key INTEGER REFERENCES dim_date(date_key),

    diagnosis_type VARCHAR(50),
    rank INTEGER,
    present_on_admission VARCHAR(5),
    clinical_status VARCHAR(30),

    source_system VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_fact_diagnosis_encounter ON fact_diagnosis(encounter_key);
CREATE INDEX IF NOT EXISTS ix_fact_diagnosis_diagnosis ON fact_diagnosis(diagnosis_key);
CREATE INDEX IF NOT EXISTS ix_fact_diagnosis_patient ON fact_diagnosis(patient_key);

-- Fact: Procedures
CREATE TABLE IF NOT EXISTS fact_procedure (
    fact_procedure_key SERIAL PRIMARY KEY,

    encounter_key INTEGER REFERENCES fact_encounter(encounter_key),
    patient_key INTEGER NOT NULL REFERENCES dim_patient(patient_key),
    procedure_key INTEGER NOT NULL REFERENCES dim_procedure(procedure_key),
    procedure_date_key INTEGER REFERENCES dim_date(date_key),
    location_key INTEGER REFERENCES dim_location(location_key),
    provider_key INTEGER REFERENCES dim_provider(provider_key),

    procedure_datetime TIMESTAMP WITH TIME ZONE,
    duration_minutes INTEGER,
    charges NUMERIC(14,2),

    status VARCHAR(30),
    anesthesia_type VARCHAR(50),

    source_system VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_fact_procedure_encounter ON fact_procedure(encounter_key);
CREATE INDEX IF NOT EXISTS ix_fact_procedure_patient ON fact_procedure(patient_key);
CREATE INDEX IF NOT EXISTS ix_fact_procedure_date ON fact_procedure(procedure_date_key);

-- Fact: Lab Results
CREATE TABLE IF NOT EXISTS fact_lab_result (
    fact_lab_key SERIAL PRIMARY KEY,

    encounter_key INTEGER REFERENCES fact_encounter(encounter_key),
    patient_key INTEGER NOT NULL REFERENCES dim_patient(patient_key),
    result_date_key INTEGER REFERENCES dim_date(date_key),

    test_code VARCHAR(50) NOT NULL,
    test_name VARCHAR(200),
    category VARCHAR(100),

    result_datetime TIMESTAMP WITH TIME ZONE,

    numeric_value NUMERIC(18,6),
    text_value VARCHAR(500),
    unit VARCHAR(50),

    reference_low NUMERIC(18,6),
    reference_high NUMERIC(18,6),

    interpretation VARCHAR(50),
    is_abnormal BOOLEAN,
    is_critical BOOLEAN,

    source_system VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_fact_lab_patient ON fact_lab_result(patient_key);
CREATE INDEX IF NOT EXISTS ix_fact_lab_encounter ON fact_lab_result(encounter_key);
CREATE INDEX IF NOT EXISTS ix_fact_lab_test ON fact_lab_result(test_code);
CREATE INDEX IF NOT EXISTS ix_fact_lab_date ON fact_lab_result(result_date_key);

-- Fact: Vitals
CREATE TABLE IF NOT EXISTS fact_vital (
    fact_vital_key SERIAL PRIMARY KEY,

    encounter_key INTEGER REFERENCES fact_encounter(encounter_key),
    patient_key INTEGER NOT NULL REFERENCES dim_patient(patient_key),
    recorded_date_key INTEGER REFERENCES dim_date(date_key),
    location_key INTEGER REFERENCES dim_location(location_key),

    recorded_datetime TIMESTAMP WITH TIME ZONE,

    heart_rate NUMERIC(6,2),
    respiratory_rate NUMERIC(6,2),
    systolic_bp NUMERIC(6,2),
    diastolic_bp NUMERIC(6,2),
    mean_arterial_pressure NUMERIC(6,2),
    temperature_f NUMERIC(6,2),
    oxygen_saturation NUMERIC(6,2),
    pain_score INTEGER,
    bmi NUMERIC(6,2),
    gcs_total INTEGER,

    news_score INTEGER,
    news_risk_level VARCHAR(20),
    bp_classification VARCHAR(50),

    source_system VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_fact_vital_patient ON fact_vital(patient_key);
CREATE INDEX IF NOT EXISTS ix_fact_vital_encounter ON fact_vital(encounter_key);
CREATE INDEX IF NOT EXISTS ix_fact_vital_date ON fact_vital(recorded_date_key);

-- Fact: Medications
CREATE TABLE IF NOT EXISTS fact_medication (
    fact_medication_key SERIAL PRIMARY KEY,

    encounter_key INTEGER REFERENCES fact_encounter(encounter_key),
    patient_key INTEGER NOT NULL REFERENCES dim_patient(patient_key),
    medication_key INTEGER NOT NULL REFERENCES dim_medication(medication_key),
    order_date_key INTEGER REFERENCES dim_date(date_key),
    provider_key INTEGER REFERENCES dim_provider(provider_key),

    order_datetime TIMESTAMP WITH TIME ZONE,
    start_date DATE,
    end_date DATE,

    dose_value NUMERIC(12,4),
    dose_unit VARCHAR(30),
    route VARCHAR(50),
    frequency VARCHAR(100),
    is_prn BOOLEAN,

    quantity NUMERIC(12,4),
    days_supply INTEGER,
    refills INTEGER,

    status VARCHAR(30),

    source_system VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_fact_medication_patient ON fact_medication(patient_key);
CREATE INDEX IF NOT EXISTS ix_fact_medication_encounter ON fact_medication(encounter_key);
CREATE INDEX IF NOT EXISTS ix_fact_medication_medication ON fact_medication(medication_key);
CREATE INDEX IF NOT EXISTS ix_fact_medication_date ON fact_medication(order_date_key);
