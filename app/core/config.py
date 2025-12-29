from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
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
    
    TIMEOUT_INPUT: int = 10
    TIMEOUT_BUTTON: int = 5
    TIMEOUT_RESPONSE: int = 120
    TIMEOUT_STABLE_CONTENT: int = 30
    TIMEOUT_PAGE_LOAD: int = 15
    TIMEOUT_ELEMENT_CHECK: int = 1
    
    TAB_INACTIVE_MINUTES: int = 10
    TAB_POOL_SIZE: int = 3
    TAB_CLEANUP_INTERVAL: int = 60

settings = Settings()
