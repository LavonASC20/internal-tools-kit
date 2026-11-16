"""Synthetic KYC cases. Every value is obviously fake."""

import random
from datetime import date, timedelta

from sqlalchemy import Connection, text

CASE_COUNT = 20

FIRST_NAMES = [
    "Avery",
    "Blake",
    "Casey",
    "Drew",
    "Emery",
    "Finley",
    "Gray",
    "Harper",
    "Indigo",
    "Jules",
]
RISK_FLAGS = [
    "pep_match",
    "sanctions_near_match",
    "adverse_media",
    "high_risk_country",
    "id_mismatch",
]


def seed(conn: Connection, rng: random.Random) -> None:
    for n in range(1, CASE_COUNT + 1):
        conn.execute(
            text(
                "INSERT INTO kyc_cases (subject_name, national_id, date_of_birth, risk_flag) "
                "VALUES (:subject_name, :national_id, :date_of_birth, :risk_flag)"
            ),
            {
                "subject_name": f"{rng.choice(FIRST_NAMES)} Testperson {n:02d}",
                "national_id": f"FAKE-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}",
                "date_of_birth": date(1950, 1, 1) + timedelta(days=rng.randint(0, 365 * 50)),
                "risk_flag": rng.choice(RISK_FLAGS),
            },
        )
