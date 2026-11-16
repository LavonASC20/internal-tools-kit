-- KYC review tool tables.

CREATE TABLE kyc_cases (
    id            SERIAL PRIMARY KEY,
    subject_name  TEXT NOT NULL,
    national_id   TEXT NOT NULL,   -- PII
    date_of_birth DATE NOT NULL,   -- PII
    risk_flag     TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'open',
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT kyc_cases_status_valid
        CHECK (status IN ('open', 'pending_approval', 'cleared', 'rejected'))
);

CREATE INDEX kyc_cases_status_idx ON kyc_cases (status);
