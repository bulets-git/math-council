import asyncio
import logging
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.run import Run
from app.orchestrator.state_machine import council_orchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")


async def run_worker():
    logger.info("Math Council Background Worker started, polling for queued runs...")
    while True:
        try:
            async with AsyncSessionLocal() as session:
                # Poll for queued run
                stmt = select(Run).where(Run.status == "queued").order_by(Run.created_at.asc()).limit(1)
                result = await session.execute(stmt)
                run = result.scalar_one_or_none()

                if run:
                    logger.info("Processing run %s...", run.id)
                    await council_orchestrator.run_pipeline(session, run.id)
                    logger.info("Finished processing run %s.", run.id)
                else:
                    await asyncio.sleep(2.0)
        except Exception as e:
            logger.exception("Worker error encountered: %s", e)
            await asyncio.sleep(3.0)


if __name__ == "__main__":
    asyncio.run(run_worker())
