import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv ikhtiyari
    pass


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me-in-production")
    DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
    SQLITE_PATH = os.getenv("SQLITE_PATH", "stock.db")

    LIMITE_FREE = 20        # produits max fel plan Free
    MAX_EQUIPE_FREE = 1     # users max fel plan Free
    PAR_PAGE = 10           # lignes par page
