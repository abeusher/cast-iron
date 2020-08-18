"""Handles parsing and validating ETL processor configs."""
from pydantic import BaseModel
from toml import loads


class ProcessorConfig(BaseModel):
    """An ETL processor configuration."""
    enabled: bool
    handled_file_glob: str
    inbox_dir: str
    processing_dir: str
    archive_dir: str
    error_dir: str
    save_error_log: bool
    shell: str


def try_loads(file_contents: str) -> ProcessorConfig:
    """Attempts to parse a TOML configuration file. Raises a ValueError on failure.

    :param file_contents: String to parse.
    :return: The Processor Config.
    """
    try:
        toml = loads(file_contents)
        cfg = toml.get('castiron', {}).get('etl', {})
        return ProcessorConfig(**cfg)
    except Exception as ex:
        raise ValueError(ex)
