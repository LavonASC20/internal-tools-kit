CASE_READ = "kyc.case.read"
PII_READ = "kyc.pii.read"
DECISION_PROPOSE = "kyc.decision.propose"
DECISION_APPROVE = "kyc.decision.approve"
AUDIT_READ = "audit.read"

ANALYST = "analyst"
SENIOR_REVIEWER = "senior_reviewer"
AUDITOR = "auditor"

PERMISSIONS: dict[str, set[str]] = {
    CASE_READ: {ANALYST, SENIOR_REVIEWER, AUDITOR},
    PII_READ: {ANALYST, SENIOR_REVIEWER},
    DECISION_PROPOSE: {ANALYST},
    DECISION_APPROVE: {SENIOR_REVIEWER},
    AUDIT_READ: {AUDITOR},
}
