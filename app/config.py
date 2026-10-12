from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ta_url: str = "http://tubearchivist:8000"
    ta_api_key: str
    ta_public_url: str = ""

    # YouTube watch-history sync (app/yt_history.py); off while the cookie file is absent
    yt_cookie_file: str = "/app/secrets/youtube-cookies.txt"
    pot_provider_url: str = "http://bgutil-provider:4416"
    ntfy_url: str = ""
    ntfy_topic: str = ""
    ntfy_token: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
