from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/fixed_asset_manager"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 1440
    cors_origins: str = "http://localhost:8080,http://localhost:5000,http://127.0.0.1:8080"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_database_url(self) -> str:
        """
        Accepts the plain `postgresql://...` format (same as your other project's
        .env) and rewrites it to use the psycopg3 driver under the hood, since
        that's what's installed in requirements.txt. You never need to touch
        this — just set DATABASE_URL as a normal postgresql:// URL in .env.
        """
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


settings = Settings()