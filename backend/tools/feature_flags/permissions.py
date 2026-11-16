NAMESPACE = "flags"

FLAG_READ = "flags.flag.read"
FLAG_TOGGLE = "flags.flag.toggle"
PROD_PROPOSE = "flags.prod.propose"
PROD_APPROVE = "flags.prod.approve"

ENGINEER = "engineer"
ENG_LEAD = "eng_lead"
AUDITOR = "auditor"

PERMISSIONS: dict[str, set[str]] = {
    FLAG_READ: {ENGINEER, ENG_LEAD, AUDITOR},
    FLAG_TOGGLE: {ENGINEER, ENG_LEAD},
    PROD_PROPOSE: {ENGINEER, ENG_LEAD},
    PROD_APPROVE: {ENG_LEAD},
}
