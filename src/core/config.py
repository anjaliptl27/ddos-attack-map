# src/core/config.py
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional, List
import os
from pathlib import Path

class Settings(BaseSettings):
    # API Keys (required)
    cloudflare_api_token: str = Field(..., description="Cloudflare API token for Radar data")
    abuseipdb_api_key: str = Field(..., description="AbuseIPDB API key for malicious IP data")
    
    # Database Configuration
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/attacks.db",
        description="Database connection URL"
    )
    geoip_db_path: str = Field(
        default="./data/geoip_cache.db", 
        description="Path to GeoIP cache database"
    )
    
    # Application Settings
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    host: str = Field(default="0.0.0.0", description="Server host address")
    port: int = Field(default=8000, description="Server port")
    
    # Rate Limiting Configuration
    cloudflare_rate_limit: int = Field(
        default=1000, 
        ge=1, 
        description="Cloudflare API rate limit per timeframe"
    )
    abuseipdb_rate_limit: int = Field(
        default=1000, 
        ge=1, 
        description="AbuseIPDB API rate limit per timeframe"
    )
    cloudflare_timeframe: int = Field(
        default=300, 
        description="Cloudflare rate limit timeframe in seconds (5 minutes)"
    )
    abuseipdb_timeframe: int = Field(
        default=86400, 
        description="AbuseIPDB rate limit timeframe in seconds (24 hours)"
    )
    collection_interval: int = Field(
        default=60, 
        ge=30, 
        description="Data collection interval in seconds"
    )
    
    # ML Configuration
    ml_model_path: str = Field(
        default="./models/ddos_classifier.joblib",
        description="Path to trained ML model"
    )
    
    # Error Handling Configuration
    max_retries: int = Field(
        default=3, 
        ge=1, 
        le=10, 
        description="Maximum retry attempts for API calls"
    )
    base_retry_delay: float = Field(
        default=1.0, 
        ge=0.1, 
        description="Base delay for exponential backoff in seconds"
    )
    
    # GeoIP Configuration
    geoip_batch_size: int = Field(
        default=10, 
        ge=1, 
        le=50, 
        description="Batch size for GeoIP lookups"
    )
    geoip_cache_days: int = Field(
        default=30, 
        ge=1, 
        description="Number of days to cache GeoIP data"
    )
    
    # Data Retention
    data_retention_days: int = Field(
        default=30, 
        ge=1, 
        le=365, 
        description="Number of days to keep attack data"
    )
    
    # WebSocket Configuration
    websocket_ping_interval: float = Field(
        default=20.0, 
        description="WebSocket ping interval in seconds"
    )
    websocket_ping_timeout: float = Field(
        default=10.0, 
        description="WebSocket ping timeout in seconds"
    )
    
    # CORS Configuration
    cors_origins: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS origins"
    )
    
    # Validation methods
    @validator("log_level")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()
    
    @property
    def base_dir(self) -> Path:
        """Get base project directory"""
        return Path(__file__).parent.parent.parent
    
    @property
    def data_dir(self) -> Path:
        """Get data directory path"""
        data_path = self.base_dir / "data"
        data_path.mkdir(exist_ok=True)
        return data_path
    
    @property
    def logs_dir(self) -> Path:
        """Get logs directory path"""
        logs_path = self.base_dir / "logs"
        logs_path.mkdir(exist_ok=True)
        return logs_path
    
    @property
    def models_dir(self) -> Path:
        """Get models directory path"""
        models_path = self.base_dir / "models"
        models_path.mkdir(exist_ok=True)
        return models_path
    
    def get_database_url(self) -> str:
        """Get full database URL for SQLAlchemy"""
        if self.database_url.startswith("sqlite"):
            # Extract path from SQLite URL and make it absolute
            db_path = self.database_url.split("///")[-1]
            return f"sqlite+aiosqlite:///{self.data_dir / db_path}"
        return self.database_url
    
    def get_database_path(self) -> str:
        """Get just the file path for SQLite database (for AttackDatabase)"""
        if self.database_url.startswith("sqlite"):
            # Extract just the file path part
            db_path = self.database_url.split("///")[-1]
            return str(self.data_dir / db_path)
        # For non-SQLite databases, return a default path
        return str(self.data_dir / "attacks.db")
    
    def get_geoip_db_path(self) -> str:
        """Get full GeoIP database path"""
        return str(self.data_dir / Path(self.geoip_db_path).name)
    
    def get_ml_model_path(self) -> str:
        """Get full ML model path"""
        return str(self.models_dir / Path(self.ml_model_path).name)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env file

# Global settings instance
settings = Settings()