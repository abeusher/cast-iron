"""Kafka ETL stream processing."""
import os
import subprocess
import tempfile
from io import BytesIO
from pathlib import PurePosixPath
from typing import AsyncIterable, Dict, List, Optional

import faust
import minio
from faust import TopicT
from kafka import KafkaProducer
from urllib3 import HTTPResponse

from python_worker.config import settings
from python_worker.processor import ProcessorConfig, try_loads

minio_client = minio.Minio(
    settings.minio_host,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_secure
)

processors: Dict[str, ProcessorConfig] = dict()

notification = {'QueueConfigurations': [
    {
        'Id': 'id',
        'Arn': settings.minio_notification_arn,
        'Events': ['s3:ObjectCreated:*', 's3:ObjectRemoved:*']
    }
]}

app = faust.App(
    settings.worker_name,
    broker=f'kafka://{settings.kafka_broker}',
    value_serializer='raw'
)

tsv_producer = KafkaProducer(bootstrap_servers=settings.kafka_broker)


class MinIONotification(faust.Record, serializer='json'):  # type: ignore
    """Model for a MinIO notification message."""
    EventName: str
    Key: str
    Records: List[Dict]

    def __abstract_init__(self):
        pass


def compute_config_path(config_file_name: str, *args) -> PurePosixPath:
    """Computes a bucket directory relative to a processor config path.

    :param config_file_name: The configuration file name.
    :return: The bucket path.
    """
    return PurePosixPath(config_file_name).parent.joinpath(*args)


def toml_put(bucket_name: str, file_name: str) -> bool:
    """Handle put event with TOML extension.

    :param bucket_name: The bucket name.
    :param file_name: The file name.
    :return: True if the operation is successful.
    """
    obj: Optional[HTTPResponse] = None
    try:
        obj = minio_client.get_object(bucket_name, file_name)
        data: str = obj.data.decode('utf-8')
        cfg: ProcessorConfig = try_loads(data)

        if cfg.enabled:
            # Register processor
            processors[file_name] = cfg

            # Create pipeline directories if they do not exist by writing a 0-byte .keep file
            inbox_dir = str(compute_config_path(file_name, cfg.inbox_dir, '.keep'))
            processing_dir = str(compute_config_path(file_name, cfg.processing_dir, '.keep'))
            archive_dir = str(compute_config_path(file_name, cfg.archive_dir, '.keep'))
            if not next(minio_client.list_objects(bucket_name, inbox_dir), None):
                minio_client.put_object(bucket_name, inbox_dir, BytesIO(b''), 0)
            if not next(minio_client.list_objects(bucket_name, processing_dir), None):
                minio_client.put_object(bucket_name, processing_dir, BytesIO(b''), 0)
            if not next(minio_client.list_objects(bucket_name, archive_dir), None):
                minio_client.put_object(bucket_name, archive_dir, BytesIO(b''), 0)

        return True
    except ValueError:
        # Raised if we fail to parse and validate config
        return False
    finally:
        if obj:
            obj.close()


def toml_delete(file_name) -> bool:
    """Handle remove event with TOML extension.

    :param file_name: The file name.
    :return: True if the delete is successful.
    """
    return bool(processors.pop(file_name, None))


def file_put(bucket_name, file_name) -> bool:
    """Handle possible data file puts.

    :param bucket_name: The bucket name.
    :param file_name: The file name.
    :return: True if successful.
    """

    # pylint: disable=too-many-locals
    for config_file_name, processor in processors.items():
        inbox_dir: PurePosixPath = compute_config_path(config_file_name, processor.inbox_dir)
        file_path = PurePosixPath(file_name)

        if file_path.parent != inbox_dir:
            # File isn't in our inbox directory
            continue

        relative_file_path = file_path.relative_to(inbox_dir)

        if not relative_file_path.match(processor.handled_file_glob):
            # Filename doesn't match our glob pattern
            continue

        processing_dir: PurePosixPath = compute_config_path(config_file_name, processor.processing_dir)
        archive_dir: PurePosixPath = compute_config_path(config_file_name, processor.archive_dir)
        error_dir: PurePosixPath = compute_config_path(config_file_name, processor.error_dir)

        # Hypothetical file paths for each directory
        processing_file_name = str(processing_dir.joinpath(relative_file_path))
        archive_file_name = str(archive_dir.joinpath(relative_file_path))
        error_file_name = str(error_dir.joinpath(relative_file_path))
        error_log_file_name = str(error_dir.joinpath(f'{relative_file_path.name.replace(".", "_")}_error_log.txt'))

        # mv to processing
        minio_client.copy_object(bucket_name, processing_file_name, f'{bucket_name}/{file_name}')
        minio_client.remove_object(bucket_name, file_name)

        with tempfile.TemporaryDirectory() as work_dir:
            # Download to local temp working directory
            local_data_file = os.path.join(work_dir, relative_file_path.name)
            minio_client.fget_object(bucket_name, processing_file_name, local_data_file)

            with open(os.path.join(work_dir, 'out.txt'), 'w') as out:
                # Run shell script
                env = {
                    'DATABASE_HOST': settings.database_host,
                    'DATABASE_PASSWORD': settings.database_password,
                    'DATABASE_PORT': str(settings.database_port),
                    'DATABASE_TABLE': str(settings.database_table),
                    'DATABASE_USER': str(settings.database_user),
                    'ETL_FILENAME': local_data_file
                }
                proc = subprocess.Popen(processor.shell,
                                        shell=True,
                                        env=env,
                                        stderr=subprocess.STDOUT,
                                        stdout=out if processor.save_error_log else subprocess.DEVNULL)
                exit_code = proc.wait()

                if exit_code == 0:
                    # Success. mv to archive
                    minio_client.copy_object(bucket_name, archive_file_name, f'{bucket_name}/{processing_file_name}')
                    minio_client.remove_object(bucket_name, processing_file_name)
                else:
                    # Failure. mv to failed
                    minio_client.copy_object(bucket_name, error_file_name, f'{bucket_name}/{processing_file_name}')
                    minio_client.remove_object(bucket_name, processing_file_name)

                    # Optionally save error log to failed
                    if processor.save_error_log:
                        minio_client.fput_object(bucket_name, error_log_file_name, os.path.join(work_dir, 'out.txt'))

            # Success or not, we handled this
            return True

    # Not our table
    return False


minio_topic: TopicT = app.topic(settings.kafka_minio_topic, value_type=MinIONotification)


@app.agent(minio_topic)
async def file_evt(evts: AsyncIterable[MinIONotification]) -> None:
    """A MinIO event signalling a file deployment.

    :param evts: The minio events.
    """
    async for evt in evts:
        bucket_name, file_name = evt.Key.split('/', 1)

        if bucket_name != settings.minio_etl_bucket:
            continue

        if evt.EventName.startswith('s3:ObjectRemoved'):
            if file_name.endswith('.toml'):
                toml_delete(file_name)
            continue

        if file_name.endswith('.toml'):
            toml_put(bucket_name, file_name)
        else:
            file_put(bucket_name, file_name)


# Create bucket notification
if not minio_client.bucket_exists(settings.minio_etl_bucket):
    minio_client.make_bucket(settings.minio_etl_bucket)
minio_client.set_bucket_notification(settings.minio_etl_bucket, notification)

# Load existing config files
for f in minio_client.list_objects(settings.minio_etl_bucket, recursive=True):
    if f.object_name.endswith('.toml'):
        toml_put(f.bucket_name, f.object_name)
