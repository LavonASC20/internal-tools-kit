-- Core schema. Applied by db/seed.py before each tool's schema.sql.

CREATE TABLE users (
    id    TEXT PRIMARY KEY,
    name  TEXT NOT NULL,
    roles TEXT[] NOT NULL DEFAULT '{}'
);

-- One approval table for every tool.
CREATE TABLE approval_requests (
    id          BIGSERIAL PRIMARY KEY,
    tool        TEXT NOT NULL,
    action      TEXT NOT NULL,          -- the action a decider must hold, e.g. kyc.decision.approve
    entity      TEXT NOT NULL,          -- e.g. kyc_case:7
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    proposed_by TEXT NOT NULL REFERENCES users (id),
    status      TEXT NOT NULL DEFAULT 'pending',
    decided_by  TEXT REFERENCES users (id),
    comment     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at  TIMESTAMPTZ,
    CONSTRAINT approval_requests_status_valid
        CHECK (status IN ('pending', 'approved', 'rejected')),
    CONSTRAINT approval_requests_decided_iff_not_pending
        CHECK ((status = 'pending') = (decided_by IS NULL)),
    -- The self-approval rule, enforced by the database even on a direct insert.
    CONSTRAINT approval_requests_no_self_approval
        CHECK (decided_by <> proposed_by)
);

CREATE INDEX approval_requests_status_idx ON approval_requests (status);
CREATE INDEX approval_requests_entity_idx ON approval_requests (tool, entity);

-- A request can only move from pending to decided once, and what was proposed cannot change.
CREATE FUNCTION approval_requests_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'approval_requests rows cannot be deleted';
    END IF;
    IF OLD.status <> 'pending' THEN
        RAISE EXCEPTION 'approval request % is already decided', OLD.id;
    END IF;
    IF NEW.tool IS DISTINCT FROM OLD.tool
        OR NEW.action IS DISTINCT FROM OLD.action
        OR NEW.entity IS DISTINCT FROM OLD.entity
        OR NEW.payload IS DISTINCT FROM OLD.payload
        OR NEW.proposed_by IS DISTINCT FROM OLD.proposed_by
        OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'approval request % cannot change what was proposed', OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER approval_requests_guard
    BEFORE UPDATE OR DELETE ON approval_requests
    FOR EACH ROW EXECUTE FUNCTION approval_requests_guard();

-- Append-only audit trail. Detail never contains PII.
CREATE TABLE audit_events (
    id     BIGSERIAL PRIMARY KEY,
    at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor  TEXT NOT NULL,
    role   TEXT NOT NULL,
    tool   TEXT NOT NULL,
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX audit_events_entity_idx ON audit_events (tool, entity);

CREATE FUNCTION audit_events_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only (% rejected)', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_events_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_append_only();

CREATE TRIGGER audit_events_no_truncate
    BEFORE TRUNCATE ON audit_events
    FOR EACH STATEMENT EXECUTE FUNCTION audit_events_append_only();
