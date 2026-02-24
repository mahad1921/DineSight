from datetime import datetime, timedelta
from typing import Optional, List

from sqlmodel import SQLModel, Field, Relationship


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    joined_at: datetime = Field(default_factory=datetime.utcnow)

    checkins: List["CheckIn"] = Relationship(back_populates="user")
    followers: List["Follow"] = Relationship(
        back_populates="following_user",
        sa_relationship_kwargs={"foreign_keys": "[Follow.following_id]"},
    )
    following: List["Follow"] = Relationship(
        back_populates="follower_user",
        sa_relationship_kwargs={"foreign_keys": "[Follow.follower_id]"},
    )


class DiningHall(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hall_name: str

    checkins: List["CheckIn"] = Relationship(back_populates="hall")


class CheckIn(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="user.id")
    hall_id: int = Field(foreign_key="dininghall.id")

    checked_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(hours=1)
    )

    user: Optional[User] = Relationship(back_populates="checkins")
    hall: Optional[DiningHall] = Relationship(back_populates="checkins")


class Follow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    follower_id: int = Field(foreign_key="user.id")
    following_id: int = Field(foreign_key="user.id")
    made_at: datetime = Field(default_factory=datetime.utcnow)

    follower_user: Optional[User] = Relationship(
        back_populates="following",
        sa_relationship_kwargs={"foreign_keys": "[Follow.follower_id]"},
    )
    following_user: Optional[User] = Relationship(
        back_populates="followers",
        sa_relationship_kwargs={"foreign_keys": "[Follow.following_id]"},
    )