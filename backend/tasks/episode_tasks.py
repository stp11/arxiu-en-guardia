"""
Celery tasks for episode ingestion and classification.
"""

from celery import chain

from logger import logger

from .main import celery_app


@celery_app.task(
    bind=True,
    name="tasks.episode_tasks.ingest_data_task",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def ingest_data_task(self):
    """
    Celery task wrapper for episode ingestion.

    Ingests episode data from the 3Cat API.
    Handles initial bulk ingestion and subsequent incremental updates.
    """
    logger.info("Starting Celery task: ingest_data_task")

    try:
        from commands.ingest_data import ingest_data

        ingest_data()
        logger.info("Successfully completed ingest_data_task")
        return {
            "status": "success",
            "message": "Episodes ingested successfully",
        }

    except Exception as e:
        logger.error(f"Error in ingest_data_task: {e}", exc_info=True)
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    name="tasks.episode_tasks.classify_episodes_task",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def classify_episodes_task(
    self, previous_result=None, batch_size=50, max_total=None
):
    """
    Celery task wrapper for episode classification.

    Classifies unclassified episodes using OpenAI.

    Args:
        previous_result: Result from previous task in chain (ignored)
        batch_size: Number of episodes to process per database session
        max_total: Maximum total episodes to process (None = all)
    """
    logger.info(
        f"Starting Celery task: classify_episodes_task "
        f"(batch_size={batch_size}, max_total={max_total})"
    )

    if previous_result:
        logger.info(f"Previous task result: {previous_result}")

    try:
        from commands.classify_episodes import classify_episodes

        classify_episodes(batch_size=batch_size, max_total=max_total)
        logger.info("Successfully completed classify_episodes_task")
        return {
            "status": "success",
            "message": "Episodes classified successfully",
            "batch_size": batch_size,
            "max_total": max_total,
        }

    except Exception as e:
        logger.error(f"Error in classify_episodes_task: {e}", exc_info=True)
        raise self.retry(exc=e)


@celery_app.task(
    bind=True,
    name="tasks.episode_tasks.generate_embeddings_task",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def generate_embeddings_task(
    self, previous_result=None, batch_size=100, max_total=None
):
    """
    Celery task wrapper for embedding generation.

    Generates embeddings for episodes that don't have one yet.

    Args:
        previous_result: Result from previous task in chain (ignored)
        batch_size: Number of episodes per API call
        max_total: Maximum total episodes to process (None = all)
    """
    logger.info(
        f"Starting Celery task: generate_embeddings_task "
        f"(batch_size={batch_size}, max_total={max_total})"
    )

    if previous_result:
        logger.info(f"Previous task result: {previous_result}")

    try:
        from commands.backfill_embeddings import backfill_embeddings

        backfill_embeddings(batch_size=batch_size, max_total=max_total)
        logger.info("Successfully completed generate_embeddings_task")
        return {
            "status": "success",
            "message": "Embeddings generated successfully",
            "batch_size": batch_size,
            "max_total": max_total,
        }

    except Exception as e:
        logger.error(f"Error in generate_embeddings_task: {e}", exc_info=True)
        raise self.retry(exc=e)


@celery_app.task(name="tasks.episode_tasks.ingest_and_classify_chain")
def ingest_and_classify_chain(batch_size=50, max_total=None):
    """
    Chain ingestion, classification, and embedding tasks.
    Each step only runs if the previous succeeds.
    """
    logger.info("Starting chained ingest -> classify -> embed workflow")

    workflow = chain(
        ingest_data_task.s(),
        classify_episodes_task.s(batch_size=batch_size, max_total=max_total),
        generate_embeddings_task.s(),
    )

    result = workflow.apply_async()
    return {"chain_id": result.id, "status": "Chained workflow started"}
