# ==============================================================================
# ZWIGGY ANALYTICS PLATFORM - CONFIGURATION MANAGEMENT
# ==============================================================================
# File: src/zwiggy_dwh/config.py
# Purpose: Manages environment variable loading (.env), validates connection parameters,
#          masks sensitive passwords in logging, and exposes settings objects.
# ==============================================================================

# Import dataclass decorator for typed data holding.
from dataclasses import dataclass

# Import standard OS module.
import os

# Import Path library from pathlib for file path manipulation.
from pathlib import Path

# Import typing generics.
from typing import Optional

# Import dotenv loader.
from dotenv import load_dotenv


# ------------------------------------------------------------------------------
# CONFIGURATION EXCEPTION CLASS
# ------------------------------------------------------------------------------

class ConfigError(Exception):
    """Raised when environment configuration settings are missing or invalid."""
    pass


# ------------------------------------------------------------------------------
# DATABASE TARGET CREDENTIALS CLASS
# ------------------------------------------------------------------------------

@dataclass(frozen=True)
class DbTarget:
    """
    Data container holding target database credentials and connection parameters.
    """
    # Active engine type ('sqlite', 'duckdb', or 'postgres')
    engine: str
    
    # Path to local SQLite or DuckDB database file
    db_path: str
    
    # Database host IP or hostname for PostgreSQL
    host: str
    
    # Database port number
    port: int
    
    # Database name
    dbname: str
    
    # Username for authentication
    user: str
    
    # Password for authentication
    password: str

    def masked_repr(self) -> str:
        """Returns connection URI string with password safely masked."""
        if self.engine in ('sqlite', 'duckdb'):
            return f"{self.engine}://{self.db_path}"
        return f"postgresql://{self.user}:***@{self.host}:{self.port}/{self.dbname}"

    def __repr__(self) -> str:
        """Returns masked representation for string conversion."""
        return self.masked_repr()


# ------------------------------------------------------------------------------
# SETTINGS LOADER CLASS
# ------------------------------------------------------------------------------

class Settings:
    """
    Loads, parses, and validates application settings from environment variables.
    """

    def __init__(self, env_file: Optional[str] = None) -> None:
        """Constructor searching and loading environment settings."""
        paths_to_check = []
        if env_file:
            paths_to_check.append(Path(env_file))
        if os.getenv("ZWIGGY_ENV_FILE"):
            paths_to_check.append(Path(os.getenv("ZWIGGY_ENV_FILE")))
        
        root_dir = Path(__file__).resolve().parent.parent.parent
        paths_to_check.extend([
            root_dir / ".env",
            Path(".env")
        ])

        # Attempt loading first found .env file.
        for path in paths_to_check:
            if path.exists():
                load_dotenv(dotenv_path=path, override=False)
                break

        # Load Database Engine & File Parameters.
        self.db_engine: str = os.getenv("DB_ENGINE", "sqlite").lower()
        self.db_path: str = os.getenv("DB_PATH", "zwiggy_warehouse.db")

        # Load PostgreSQL Connection Parameters.
        self.pg_host: str = os.getenv("PG_HOST", "localhost")
        self.pg_port: int = self._parse_int("PG_PORT", 5432)
        self.pg_database: str = os.getenv("PG_DATABASE", "zwiggy_db")
        self.pg_user: str = os.getenv("PG_USER", "postgres")
        self.pg_password: str = os.getenv("PG_PASSWORD", "postgres")

        # Load Pipeline Operational Constants.
        self.default_lookback_days: int = self._parse_int("DEFAULT_LOOKBACK_DAYS", 7)
        self.batch_size: int = self._parse_int("BATCH_SIZE", 10000)
        self.business_timezone: str = os.getenv("BUSINESS_TIMEZONE", "UTC")
        self.code_version: str = os.getenv("CODE_VERSION", "1.0.0")

        # Load Resilience Parameters.
        self.max_retries: int = self._parse_int("MAX_RETRIES", 3)
        self.retry_backoff_seconds: float = self._parse_float("RETRY_BACKOFF_SECONDS", 2.0)

        # Configure Root Directory Paths.
        self.root_dir: Path = root_dir
        self.sql_dir: Path = root_dir / "src" / "zwiggy_dwh" / "sql"

    def _parse_int(self, env_var: str, default: int) -> int:
        """Parses integer environment variable with fallback."""
        val = os.getenv(env_var)
        if val is None:
            return default
        try:
            return int(val)
        except ValueError:
            raise ConfigError(f"Environment variable '{env_var}' must be an integer, got '{val}'.")

    def _parse_float(self, env_var: str, default: float) -> float:
        """Parses float environment variable with fallback."""
        val = os.getenv(env_var)
        if val is None:
            return default
        try:
            return float(val)
        except ValueError:
            raise ConfigError(f"Environment variable '{env_var}' must be a float, got '{val}'.")

    @property
    def target(self) -> DbTarget:
        """Returns instantiated DbTarget object."""
        return DbTarget(
            engine=self.db_engine,
            db_path=self.db_path,
            host=self.pg_host,
            port=self.pg_port,
            dbname=self.pg_database,
            user=self.pg_user,
            password=self.pg_password
        )


# Global singleton settings cache instance.
_settings_instance: Optional[Settings] = None


def get_settings(env_file: Optional[str] = None) -> Settings:
    """
    Returns global cached Settings instance or initializes new instance.
    """
    global _settings_instance
    if _settings_instance is None or env_file is not None:
        _settings_instance = Settings(env_file=env_file)
    return _settings_instance
