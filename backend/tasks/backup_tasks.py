"""
Celery task for PostgreSQL backup to Cloudflare R2.

Runs pg_dump | gzip, uploads to R2, and cleans up old backups.
"""

import gzip
import os
import subprocess
from datetime import datetime, timedelta, timezone

import boto3

from logger import logger

from .main import celery_app


def _get_database_url() -> str:
    user = os.environ["PGUSER"]
    password = os.environ["PGPASSWORD"]
    host = os.environ["PGHOST"]
    port = os.environ.get("PGPORT", "5432")
    db = os.environ["PGDATABASE"]
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
    )


def _dump_database(database_url: str) -> bytes:
    result = subprocess.run(
        ["pg_dump", "--no-owner", "--no-acl", database_url],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr.decode()}")
    return result.stdout


def _cleanup_old_backups(
    client, bucket: str, prefix: str, retention_days: int
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    deleted = 0
    for obj in response.get("Contents", []):
        if obj["LastModified"] < cutoff:
            client.delete_object(Bucket=bucket, Key=obj["Key"])
            logger.info("Deleted old backup: %s", obj["Key"])
            deleted += 1
    return deleted


@celery_app.task(
    bind=True,
    name="tasks.backup_tasks.backup_database",
    max_retries=2,
    default_retry_delay=600,
)
def backup_database(self):
    """Dump the database, compress, upload to R2, and clean up old backups."""
    bucket = os.environ["S3_BUCKET"]
    prefix = os.getenv("BACKUP_PREFIX", "en-guardia")
    retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    key = f"{prefix}/{timestamp}.sql.gz"

    try:
        database_url = _get_database_url()

        logger.info("Starting database backup...")
        sql = _dump_database(database_url)
        logger.info("pg_dump completed (%d bytes)", len(sql))

        compressed = gzip.compress(sql)
        logger.info("Compressed %d -> %d bytes", len(sql), len(compressed))

        client = _get_s3_client()
        client.put_object(Bucket=bucket, Key=key, Body=compressed)
        logger.info("Uploaded to s3://%s/%s", bucket, key)

        deleted = _cleanup_old_backups(
            client, bucket, f"{prefix}/", retention_days
        )
        logger.info(
            "Backup complete: %s (cleaned up %d old backups)", key, deleted
        )

        return {
            "status": "success",
            "key": key,
            "size_bytes": len(compressed),
            "old_backups_deleted": deleted,
        }

    except Exception as e:
        logger.error("Backup failed: %s", e, exc_info=True)
        raise self.retry(exc=e)
