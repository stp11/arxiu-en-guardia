"""
Restore a PostgreSQL backup from Cloudflare R2.

Downloads the latest (or specified) .sql.gz backup from R2,
decompresses it, and restores into the target database via psql.

The target must be empty. Restore as the user the app connects with, so it
owns the tables, into a database where the superuser has already created
pgvector.

Usage:
    python -m commands.restore_backup
    python -m commands.restore_backup --file filename.sql.gz
    python -m commands.restore_backup --database-url db_url
"""

import argparse
import gzip
import logging
import os
import subprocess
import sys

import boto3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
    )


def list_backups(client, bucket: str, prefix: str) -> list[dict]:
    response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    objects = response.get("Contents", [])
    return sorted(objects, key=lambda o: o["LastModified"], reverse=True)


def download(client, bucket: str, key: str) -> bytes:
    log.info("Downloading s3://%s/%s...", bucket, key)
    response = client.get_object(Bucket=bucket, Key=key)
    data = response["Body"].read()
    log.info("Downloaded %d bytes", len(data))
    return data


def without_extension_comments(sql: bytes) -> bytes:
    """Drop COMMENT ON EXTENSION, which only the superuser may run"""
    lines = []
    # Rows of COPY data are kept whatever they start with.
    in_copy_data = False
    for line in sql.splitlines(keepends=True):
        if in_copy_data:
            in_copy_data = line.rstrip(b"\r\n") != b"\\."
        elif line.startswith(b"COPY ") and line.rstrip().endswith(b"stdin;"):
            in_copy_data = True
        elif line.startswith(b"COMMENT ON EXTENSION "):
            continue
        lines.append(line)
    return b"".join(lines)


def restore(sql: bytes, database_url: str):
    log.info("Restoring to %s...", database_url.split("@")[-1])
    sql = without_extension_comments(sql)
    # Without these psql carries on past errors and exits 0, leaving a
    # half-restored database that looks fine.
    result = subprocess.run(
        [
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "--single-transaction",
            database_url,
        ],
        input=sql,
        capture_output=True,
    )
    if result.returncode != 0:
        log.error("psql failed: %s", result.stderr.decode())
        sys.exit(1)
    log.info("Restore complete")


def main():
    parser = argparse.ArgumentParser(description="Restore a backup from R2")
    parser.add_argument(
        "--file", help="Specific backup key to restore (default: latest)"
    )
    parser.add_argument(
        "--database-url",
        help="Target database URL (default: DATABASE_URL env)",
    )
    args = parser.parse_args()

    bucket = os.environ["S3_BUCKET"]
    prefix = os.getenv("BACKUP_PREFIX", "en-guardia")
    database_url = args.database_url or os.environ["DATABASE_URL"]

    client = get_s3_client()

    if args.file:
        key = args.file
    else:
        backups = list_backups(client, bucket, f"{prefix}/")
        if not backups:
            log.error("No backups found in s3://%s/%s/", bucket, prefix)
            sys.exit(1)
        key = backups[0]["Key"]
        log.info("Latest backup: %s", key)

    compressed = download(client, bucket, key)
    log.info("Decompressing...")
    sql = gzip.decompress(compressed)
    log.info("Decompressed to %d bytes", len(sql))

    restore(sql, database_url)


if __name__ == "__main__":
    main()
