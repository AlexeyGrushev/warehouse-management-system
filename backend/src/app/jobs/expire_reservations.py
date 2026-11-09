"""Освобождение истёкших резервов вручную или по cron: `python -m app.jobs.expire_reservations`."""

from app.db.session import SessionLocal
from app.modules.reservations.service import expire_due_reservations


def run_once() -> int:
    with SessionLocal() as session:
        count = expire_due_reservations(session)
        session.commit()
        return count


if __name__ == "__main__":
    print(f"Освобождено истёкших резервов: {run_once()}")
