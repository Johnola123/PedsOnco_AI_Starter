from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://pedsonco:pedsonco@localhost:5432/pedsonco"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "pedsonco_minio"
    s3_secret_key: str = "change_me_minio"
    s3_bucket: str = "pedsonco-uploads"
    s3_region: str = "us-east-1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
