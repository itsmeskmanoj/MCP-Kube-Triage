import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS deployments (
    id INTEGER PRIMARY KEY,
    cluster_name TEXT NOT NULL,
    namespace TEXT NOT NULL,
    deployment_name TEXT NOT NULL,
    application_name TEXT NOT NULL,
    environment TEXT NOT NULL,
    owner_team TEXT NOT NULL,
    image TEXT NOT NULL,
    desired_replicas INTEGER NOT NULL,
    cpu_request_cores REAL NOT NULL,
    memory_request_bytes INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    UNIQUE (cluster_name, namespace, deployment_name)
)
"""

RECORDS = [
    (
        1,
        "cluster-a",
        "payments",
        "payments-api",
        "payments",
        "prod",
        "payments",
        "payments-api:1.8.2",
        3,
        0.75,
        805306368,
    ),
    (
        2,
        "cluster-b",
        "payments",
        "payments-api",
        "payments",
        "prod",
        "payments",
        "payments-api:1.8.2",
        2,
        0.5,
        536870912,
    ),
    (
        3,
        "cluster-a",
        "checkout",
        "checkout-api",
        "checkout",
        "prod",
        "checkout",
        "checkout-api:4.2.0",
        2,
        0.5,
        536870912,
    ),
    (
        4,
        "cluster-a",
        "platform",
        "event-consumer",
        "events",
        "prod",
        "platform",
        "event-consumer:2.3.1",
        2,
        0.4,
        402653184,
    ),
]


def seed(database: Path) -> None:
    database.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(database) as connection:
        connection.execute(SCHEMA)
        connection.execute("DELETE FROM deployments")
        connection.executemany(
            """
            INSERT INTO deployments (
                id, cluster_name, namespace, deployment_name, application_name,
                environment, owner_team, image, desired_replicas,
                cpu_request_cores, memory_request_bytes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [(*record, now, now) for record in RECORDS],
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the local read-only demo inventory.")
    parser.add_argument("--database", type=Path, default=Path("data/inventory.db"))
    args = parser.parse_args()
    seed(args.database)
    print(f"Seeded {len(RECORDS)} deployments in {args.database}")


if __name__ == "__main__":
    main()