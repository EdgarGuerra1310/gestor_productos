from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Asistente de Retroalimentacion Moodle"
    app_host: str = "0.0.0.0"
    app_port: int = 7001

    db_name: str = "gestor_pdf"
    db_user: str = "postgres"
    db_password: str = ""
    db_host: str = "localhost"
    db_port: int = 5432
    database_url: str = ""

    azure_openai_api_key: str = Field(default="")
    azure_openai_api_version: str = "2024-05-01-preview"
    azure_openai_endpoint: str = "https://Minedu-IA.openai.azure.com"
    azure_openai_deployment: str = "gpt-4o"

    moodle_base_url: str = "http://161.132.50.205"
    moodle_token: str = ""
    moodle_service_path: str = "/webservice/rest/server.php"

    temp_dir: Path = Path("./tmp")
    max_pdf_mb: int = 30
    enable_ocr: bool = False
    tesseract_cmd: str = ""
    vision_max_pages: int = 3
    vision_dpi: int = 144
    min_extracted_chars: int = 80
    similarity_threshold: float = 0.88
    validation_max_chars: int = 25000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
