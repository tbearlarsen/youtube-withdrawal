from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ta_url: str = "http://tubearchivist:8000"
    ta_api_key: str

    model_config = {"env_file": ".env"}


settings = Settings()
