from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str 
    postgres_user: str
    postgres_db: str
    secret_key: str 
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    cors_origins: str = "http://localhost:3000"
    upload_dir: str = "uploads"

    # Environnement : "development" | "production"
    environment: str = "production"

    # # Stockage des fichiers : "local" ou "s3"
    storage_backend: str = "local"
    # s3_bucket: str = ""
    # s3_region: str = "eu-west-3"
    # s3_public_base_url: str = ""  # ex: https://cdn.mondomaine.com ou URL du bucket

    # Limitation de débit (requêtes / minute) sur les routes sensibles
    rate_limit_login: str = "10/minute"
    rate_limit_register: str = "5/minute"
    rate_limit_upload: str = "30/minute"

    # URL publique du frontend, utilisée pour construire les liens dans les
    # emails (réinitialisation de mot de passe, invitations).
    frontend_url: str = "http://localhost:3000"

    # SMTP (envoi d'emails). Si smtp_host est vide, les emails sont
    # simplement journalisés dans la console (pratique en développement).
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = "mgayeeeeee@gmail.com"
    smtp_password: str = "jxqxcawguytkogun"
    smtp_from: str = "MGaye <mgayeeeeee@gmail.com"
    smtp_use_tls: bool = True


    class Config:
        env_file = ".env.local"


settings = Settings()



# from pydantic_settings import BaseSettings, SettingsConfigDict


# class Settings(BaseSettings):
#     # model_config = SettingsConfigDict(
#     #     env_file=".env",
#     #     env_file_encoding="utf-8",
#     #     extra="ignore",
#     # )

#     # Database
#     database_url: str = "postgresql://editor_user:Postgres.2424@localhost:5432/editor_db"
#     postgres_user: str = "editor_user"
#     postgres_db: str = "editor_db"

#     # Authentication
#     secret_key: str = "GMwT7yI0ryNyDQGPKMdTvtBmMAPs3ILVvITi4Q9uPWY"
#     algorithm: str = "HS256"
#     access_token_expire_minutes: int = 1440

#     # CORS
#     cors_origins: str = "http://localhost:3000"

#     # Storage
#     upload_dir: str = "uploads"
#     storage_backend: str = "local"

#     # Environment
#     environment: str = "development"

#     # Rate limiting
#     rate_limit_login: str = "10/minute"
#     rate_limit_register: str = "5/minute"
#     rate_limit_upload: str = "30/minute"

#     # Frontend
#     frontend_url: str = "http://localhost:3000"

#     # SMTP
#     smtp_host: str = "smtp.gmail.com"
#     smtp_port: int = 587
#     smtp_user: str = "mgayeeeeee@gmail.com"
#     smtp_password: str = "jxqxcawguytkogun"
#     smtp_from: str = "MGaye <mgayeeeeee@gmail.com>"
#     smtp_use_tls: bool = True


# settings = Settings()