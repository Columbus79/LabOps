"""Run exactly one lightweight scheduler process beside the API service."""
import logging
import time

from app.services.reservation_service import expire_pending_reservations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("labops.scheduler")


def run():
    logger.info("Reservation expiration scheduler started")
    while True:
        try:
            expire_pending_reservations()
        except Exception:
            logger.exception("Reservation expiration scan failed")
        time.sleep(60)


if __name__ == "__main__":
    run()
