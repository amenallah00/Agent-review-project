"""
Connexion à la base de données du tableau de bord (cf. rapport PRLens §3.6).

SQLite en développement local (aucune installation supplémentaire requise),
PostgreSQL en production (`DATABASE_URL=postgresql+psycopg2://...`). Le
moteur de revue lui-même (webhook/Actions) n'a pas besoin de cette base :
elle ne sert qu'à la persistance nécessaire au tableau de bord (utilisateurs,
dépôts connectés, historique des revues).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dépendance FastAPI : ouvre une session, la ferme systématiquement après la requête."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Crée les tables manquantes au démarrage. `create_all` ne modifie jamais
    une table déjà existante (cf. rapport §4.5.2) : les évolutions de schéma
    sur une base déjà déployée doivent être gérées séparément (ALTER TABLE
    idempotents, ou un vrai outil de migration — cf. perspectives du rapport).
    """
    from . import db_models  # noqa: F401  (enregistre les modèles sur Base avant create_all)

    Base.metadata.create_all(bind=engine)
