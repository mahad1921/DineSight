import hashlib

from sqlmodel import SQLModel, create_engine, Session, select

from .config import DATABASE_URL
from .models import User, DiningHall, CheckIn, Follow


# Railway (and some hosts) expose Postgres as postgres://; SQLAlchemy 2 expects postgresql://
_url = DATABASE_URL
if _url.startswith("postgres://"):
    _url = "postgresql://" + _url[len("postgres://") :]

db_engine = create_engine(_url, echo=False)


def hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_db():
    SQLModel.metadata.create_all(db_engine)


def seed_if_empty():
    with Session(db_engine) as session_obj:
        halls_now = session_obj.exec(select(DiningHall)).all()
        if not halls_now:
            session_obj.add_all(
                [
                    DiningHall(hall_name="Hampshire Dining Commons"),
                    DiningHall(hall_name="Berkshire Dining Commons"),
                    DiningHall(hall_name="Worcester Dining Commons"),
                    DiningHall(hall_name="Franklin Dining Commons"),
                ]
            )

        users_now = session_obj.exec(select(User)).all()
        if not users_now:
            session_obj.add_all(
                [
                    User(username="Mahad", password_hash=hash_password("mahad123")),
                    User(username="Sarah", password_hash=hash_password("sarah123")),
                    User(username="Varisha", password_hash=hash_password("varisha123")),
                    User(username="Robert", password_hash=hash_password("robert123")),
                    User(username="Kazi", password_hash=hash_password("kazi123")),
                    User(username="Humza", password_hash=hash_password("humza123")),
                    User(username="Wajdan", password_hash=hash_password("wajdan123")),
                ]
            )

        session_obj.commit()


def setup_db():
    make_db()
    seed_if_empty()


def get_session():
    with Session(db_engine) as s:
        yield s