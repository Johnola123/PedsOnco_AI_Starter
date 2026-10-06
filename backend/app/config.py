from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://pedsonco:pedsonco@localhost:5432/pedsonco"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_public_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "pedsonco_minio"
    s3_secret_key: str = "change_me_minio"
    s3_bucket: str = "pedsonco-uploads"
    s3_region: str = "us-east-1"
    presign_expires_seconds: int = 3600
    max_url_import_bytes: int = 5 * 1024 * 1024 * 1024  # 5 GiB safety cap for URL/API imports
    web_origins: str = "http://localhost:8080,http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def web_origin_list(self) -> list[str]:
        return [item.strip() for item in self.web_origins.split(",") if item.strip()]


settings = Settings()
