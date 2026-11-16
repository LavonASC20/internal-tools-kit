-- Feature flags tool tables. One row per flag per environment.

CREATE TABLE feature_flags (
    id                 SERIAL PRIMARY KEY,
    key                TEXT NOT NULL,
    environment        TEXT NOT NULL,
    description        TEXT NOT NULL DEFAULT '',
    enabled            BOOLEAN NOT NULL DEFAULT false,
    -- Set while a prod toggle waits for approval; at most one pending request per flag.
    pending_request_id BIGINT REFERENCES approval_requests (id),
    updated_by         TEXT REFERENCES users (id),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT feature_flags_environment_valid
        CHECK (environment IN ('dev', 'staging', 'prod')),
    CONSTRAINT feature_flags_pending_only_in_prod
        CHECK (pending_request_id IS NULL OR environment = 'prod'),
    CONSTRAINT feature_flags_key_environment_unique UNIQUE (key, environment)
);

CREATE INDEX feature_flags_environment_idx ON feature_flags (environment);
