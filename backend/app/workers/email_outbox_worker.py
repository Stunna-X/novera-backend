"""
Email outbox worker.

Run continuously:

    python -m app.workers.email_outbox_worker

Process one available batch and exit:

    python -m app.workers.email_outbox_worker --once
"""

from __future__ import annotations

import argparse
import logging
import time
import uuid

from app.core.config import settings
from app.database.session import SessionLocal
from app.services.email_dispatcher_service import (
    EmailDispatcherService,
)


logger = logging.getLogger(
    "novera.email_outbox_worker"
)


def configure_logging() -> None:
    """
    Configure worker-safe console logging.
    """

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )


def recover_stale_messages() -> int:
    """
    Recover abandoned worker claims.
    """

    with SessionLocal() as db:
        service = EmailDispatcherService(db)

        return service.recover_stale_sending()


def claim_batch() -> list[uuid.UUID]:
    """
    Atomically claim one batch of due messages.
    """

    with SessionLocal() as db:
        service = EmailDispatcherService(db)

        return service.claim_due_batch()


def dispatch_message(
    email_outbox_id: uuid.UUID,
) -> bool:
    """
    Dispatch one claimed message in an isolated session.
    """

    with SessionLocal() as db:
        service = EmailDispatcherService(db)

        return service.dispatch_claimed(
            email_outbox_id=email_outbox_id,
        )


def run_batch() -> int:
    """
    Recover stale work, claim a batch, and process it.
    """

    recovered_count = recover_stale_messages()

    if recovered_count:
        logger.warning(
            "Recovered %s stale email claim(s).",
            recovered_count,
        )

    claimed_ids = claim_batch()

    if not claimed_ids:
        return 0

    logger.info(
        "Claimed %s email message(s).",
        len(claimed_ids),
    )

    succeeded = 0
    failed = 0

    for email_outbox_id in claimed_ids:
        try:
            accepted = dispatch_message(
                email_outbox_id
            )

            if accepted:
                succeeded += 1

                logger.info(
                    "Email %s was accepted.",
                    email_outbox_id,
                )

            else:
                failed += 1

                logger.warning(
                    "Email %s was not accepted.",
                    email_outbox_id,
                )

        except Exception:
            failed += 1

            logger.exception(
                (
                    "Unhandled worker failure while "
                    "processing email %s."
                ),
                email_outbox_id,
            )

    logger.info(
        (
            "Batch completed: claimed=%s, "
            "succeeded=%s, failed=%s."
        ),
        len(claimed_ids),
        succeeded,
        failed,
    )

    return len(
        claimed_ids
    )


def run_forever() -> None:
    """
    Poll indefinitely until interrupted.
    """

    logger.info(
        (
            "Novera email worker started with "
            "provider=%s, batch_size=%s, poll=%ss."
        ),
        settings.EMAIL_PROVIDER,
        settings.EMAIL_OUTBOX_BATCH_SIZE,
        settings.EMAIL_OUTBOX_POLL_SECONDS,
    )

    while True:
        processed_count = run_batch()

        if processed_count == 0:
            time.sleep(
                settings.EMAIL_OUTBOX_POLL_SECONDS
            )


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line worker arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Process queued Novera email messages."
        )
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help=(
            "Process one available batch and exit."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """
    Worker entry point.
    """

    configure_logging()
    arguments = parse_arguments()

    try:
        if arguments.once:
            processed_count = run_batch()

            logger.info(
                "Worker finished after processing %s message(s).",
                processed_count,
            )

            return

        run_forever()

    except KeyboardInterrupt:
        logger.info(
            "Novera email worker stopped."
        )


if __name__ == "__main__":
    main()