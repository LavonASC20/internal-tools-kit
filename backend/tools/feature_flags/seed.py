"""Synthetic feature flags: six made-up keys in each of dev, staging and prod."""

import random

from sqlalchemy import Connection, text

ENVIRONMENTS = ("dev", "staging", "prod")

FLAGS = [
    ("demo_new_checkout", "Fake checkout redesign for the demo"),
    ("demo_dark_mode", "Fake dark theme toggle"),
    ("demo_search_v2", "Fake second search backend"),
    ("demo_beta_banner", "Fake banner for beta testers"),
    ("demo_fast_export", "Fake faster CSV export"),
    ("demo_sample_widget", "Fake dashboard widget"),
]

# Probability a flag starts enabled, per environment: most things are on in dev, few in prod.
ENABLED_CHANCE = {"dev": 0.8, "staging": 0.5, "prod": 0.2}


def seed(conn: Connection, rng: random.Random) -> None:
    for environment in ENVIRONMENTS:
        for key, description in FLAGS:
            conn.execute(
                text(
                    "INSERT INTO feature_flags (key, environment, description, enabled) "
                    "VALUES (:key, :environment, :description, :enabled)"
                ),
                {
                    "key": key,
                    "environment": environment,
                    "description": description,
                    "enabled": rng.random() < ENABLED_CHANCE[environment],
                },
            )
