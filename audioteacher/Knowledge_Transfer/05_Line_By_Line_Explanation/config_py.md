# 📄 Line-by-Line Code Breakdown: `src/zwiggy_dwh/config.py`

**File Name**: `src/zwiggy_dwh/config.py`  
**Total Lines**: 174 Lines  
**Primary Purpose**: Configuration management loader. Reads environment variables (`.env`), defines database target paths (`DbTarget`), validates numerical configuration options, and provides a thread-safe cached settings singleton via `get_settings()`.

---

## 🔍 Module Overview & Import Dependencies
- Lines 1–25: Module docstrings and import statements (`os`, `sys`, `pathlib.Path`, `dataclasses.dataclass`, `dotenv.load_dotenv`).
- Lines 29–31: Custom `ConfigError(Exception)` class for configuration validation failures.
- Lines 39–72: `DbTarget` dataclass representing target database URI and masked string representation.
- Lines 79–160: `Settings` dataclass storing environment variables, path resolutions, and default thresholds.
- Lines 167–174: Singleton factory function `get_settings()`.

---

## 📜 Detailed Line-by-Line Walkthrough

* **Lines 1–15**: Module header comments establishing configuration management scope for Zwiggy Data Warehouse.
* **Line 16**: `import os` - Provides access to operating system environment variables (`os.getenv`).
* **Line 17**: `import sys` - System specific parameters and path manipulations.
* **Line 18**: `from pathlib import Path` - Provides object-oriented filesystem path operations.
* **Line 19**: `from dataclasses import dataclass, field` - Enables clean Python dataclasses with field definitions.
* **Line 20**: `from typing import Optional` - Type hint for parameters that can accept `None`.
* **Line 21**: `from dotenv import load_dotenv` - Loads key-value pairs from `.env` file into `os.environ`.
* **Line 24**: `load_dotenv()` - Invokes environment variable loading at module import time.
* **Line 29**: `class ConfigError(Exception):` - Custom exception raised when a required config setting is missing or invalid.
* **Line 30**: `    """Raised when environment variables or settings fail validation."""` - Docstring.
* **Line 31**: `    pass` - Exception body placeholder.
* **Line 39**: `@dataclass(frozen=True)` - Dataclass decorator creating an immutable (read-only) `DbTarget` object.
* **Line 40**: `class DbTarget:` - Class definition representing the target database URI configuration.
* **Line 41**: `    db_type: str = "sqlite"` - Database type identifier (defaults to SQLite).
* **Line 42**: `    db_path: Optional[Path] = None` - File path object pointing to SQLite database file.
* **Line 43**: `    host: Optional[str] = None` - Database host server name or IP address.
* **Line 44**: `    port: Optional[int] = None` - Database connection port number.
* **Line 45**: `    database: Optional[str] = None` - Database name identifier.
* **Line 46**: `    username: Optional[str] = None` - Database connection username.
* **Line 47**: `    password: Optional[str] = None` - Database connection password.
* **Line 64**: `    def masked_repr(self) -> str:` - Method returning a sanitized connection string for safe log output.
* **Line 65**: `        if self.db_type == "sqlite":` - Checks if connection target is SQLite file.
* **Line 66**: `            return f"sqlite:///{self.db_path}"` - Returns SQLite file URI path.
* **Line 67**: `        pwd = "****" if self.password else "none"` - Masks password string with asterisks.
* **Line 68**: `        return f"{self.db_type}://{self.username}:{pwd}@{self.host}:{self.port}/{self.database}"` - Returns masked URI string.
* **Line 79**: `@dataclass` - Dataclass decorator for global application `Settings`.
* **Line 80**: `class Settings:` - Primary configuration class.
* **Line 84**: `    def __init__(self):` - Settings constructor initializing environment properties.
* **Line 85**: `        self.env = os.getenv("APP_ENV", "development").lower()` - Reads `APP_ENV` environment variable with `"development"` fallback.
* **Line 86**: `        self.project_root = Path(__file__).resolve().parent.parent.parent` - Resolves root directory path of repository.
* **Line 87**: `        self.db_path = Path(os.getenv("DWH_DB_PATH", self.project_root / "zwiggy_dwh.db"))` - Resolves SQLite DB path.
* **Line 88**: `        self.batch_size = self._parse_int("BATCH_SIZE", 5000)` - Parses maximum row batch size (default 5000).
* **Line 89**: `        self.max_retries = self._parse_int("MAX_RETRIES", 3)` - Parses maximum query retry count (default 3).
* **Line 90**: `        self.backoff_factor = self._parse_float("BACKOFF_FACTOR", 1.5)` - Exponential backoff multiplier (default 1.5).
* **Line 91**: `        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()` - Logging verbosity level.
* **Line 129**: `    def _parse_int(self, key: str, default: int) -> int:` - Private helper validating integer environment settings.
* **Line 130**: `        val = os.getenv(key)` - Fetches environment variable string.
* **Line 131**: `        if val is None:` - Checks if variable is unset.
* **Line 132**: `            return default` - Returns default integer value.
* **Line 133**: `        try:` - Exception handling block.
* **Line 134**: `            return int(val)` - Converts string to integer.
* **Line 135**: `        except ValueError:` - Catches conversion failure.
* **Line 136**: `            raise ConfigError(f"Setting {key} must be an integer, got '{val}'")` - Raises clean `ConfigError`.
* **Line 150**: `    def target(self) -> DbTarget:` - Constructs and returns `DbTarget` instance for active database setup.
* **Line 151**: `        return DbTarget(db_type="sqlite", db_path=self.db_path)` - Returns SQLite `DbTarget`.
* **Line 167**: `_settings_instance: Optional[Settings] = None` - Global variable holding cached singleton instance.
* **Line 169**: `def get_settings() -> Settings:` - Factory function providing global access to settings.
* **Line 170**: `    global _settings_instance` - References global singleton variable.
* **Line 171**: `    if _settings_instance is None:` - Checks if settings object has not been instantiated yet.
* **Line 172**: `        _settings_instance = Settings()` - Instantiates `Settings` object.
* **Line 173**: `    return _settings_instance` - Returns cached `Settings` singleton.
