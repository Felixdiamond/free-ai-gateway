from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    HEADLESS: bool = False 
    BROWSER_ARGS: list[str] = [
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
        "--disable-extensions",
        "--ignore-certificate-errors",
        "--window-size=1920,1080",
    ]
    BROWSER_PATH: str | None = None
    USER_DATA_DIR: str | None = None
    
    CHATGPT_URL: str = "https://chatgpt.com"
    GEMINI_URL: str = "https://gemini.google.com/app"
    GROK_URL: str = "https://grok.com"

    class Config:
        env_file = ".env"

settings = Settings()
