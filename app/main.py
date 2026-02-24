from datetime import datetime
from pathlib import Path
from typing import Optional, List
import hashlib

from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from .config import is_production, COOKIE_DOMAIN
from .db import setup_db, get_session
from .models import User, DiningHall, CheckIn, Follow


# Paths relative to project root so static/templates work when run from any cwd (e.g. Railway)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_STATIC_DIR = _PROJECT_ROOT / "static"
_TEMPLATES_DIR = _PROJECT_ROOT / "templates"

app = FastAPI()

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _cookie_kwargs():
    """Cookie options for production: secure + SameSite so cookies work over HTTPS."""
    kwargs = {"httponly": True, "samesite": "lax", "path": "/"}
    if is_production():
        kwargs["secure"] = True
    if COOKIE_DOMAIN:
        kwargs["domain"] = COOKIE_DOMAIN
    return kwargs


@app.on_event("startup")
def boot_up():
    setup_db()


def read_user_from_cookie(req: Request, db_sess: Session) -> Optional[User]:
    cookie_val = req.cookies.get("user_id")
    if not cookie_val:
        return None
    try:
        user_id = int(cookie_val)
    except (ValueError, TypeError):
        return None
    return db_sess.get(User, user_id)


def make_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def check_password(raw: str, stored: str) -> bool:
    return make_hash(raw) == stored


@app.get("/", response_class=HTMLResponse)
def home(req: Request, db_sess: Session = Depends(get_session)):
    me = read_user_from_cookie(req, db_sess)
    if me:
        return RedirectResponse("/feed", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {"request": req, "error": None},
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(req: Request, db_sess: Session = Depends(get_session)):
    me = read_user_from_cookie(req, db_sess)
    if me:
        return RedirectResponse("/feed", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {"request": req, "error": None},
    )


@app.post("/login", response_class=HTMLResponse)
def login_submit(
    req: Request,
    username: str = Form(""),
    password: str = Form(""),
    db_sess: Session = Depends(get_session),
):
    username = username.strip()

    if not username or not password:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": req,
                "error": "please fill in both fields",
            },
            status_code=400,
        )

    user_row = db_sess.exec(
        select(User).where(User.username == username)
    ).first()
    if not user_row or not check_password(password, user_row.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": req,
                "error": "wrong username or password",
            },
            status_code=400,
        )

    resp = RedirectResponse("/feed", status_code=303)
    resp.set_cookie("user_id", str(user_row.id), **_cookie_kwargs())
    return resp


@app.get("/signup", response_class=HTMLResponse)
def signup_page(req: Request, db_sess: Session = Depends(get_session)):
    me = read_user_from_cookie(req, db_sess)
    if me:
        return RedirectResponse("/feed", status_code=303)
    return templates.TemplateResponse(
        "signup.html",
        {"request": req, "error": None},
    )


@app.post("/signup", response_class=HTMLResponse)
def signup_submit(
    req: Request,
    username: str = Form(""),
    password: str = Form(""),
    db_sess: Session = Depends(get_session),
):
    username = username.strip()

    if not username or len(password) < 4:
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": req,
                "error": "pick a username and a longer password",
            },
            status_code=400,
        )

    existing = db_sess.exec(
        select(User).where(User.username == username)
    ).first()
    if existing:
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": req,
                "error": "that username is taken",
            },
            status_code=400,
        )

    new_user = User(
        username=username,
        password_hash=make_hash(password),
    )
    db_sess.add(new_user)
    db_sess.commit()
    db_sess.refresh(new_user)

    resp = RedirectResponse("/feed", status_code=303)
    resp.set_cookie("user_id", str(new_user.id), **_cookie_kwargs())
    return resp


@app.post("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("user_id", **_cookie_kwargs())
    return resp


@app.get("/feed", response_class=HTMLResponse)
def feed_page(req: Request, db_sess: Session = Depends(get_session)):
    me = read_user_from_cookie(req, db_sess)
    if not me:
        return RedirectResponse("/", status_code=303)

    now = datetime.utcnow()
    follow_links = me.following
    id_list: List[int] = [me.id] + [row.following_id for row in follow_links]

    q = (
        select(CheckIn)
        .where(CheckIn.user_id.in_(id_list))
        .where(CheckIn.expires_at > now)
        .order_by(CheckIn.checked_at.desc())
    )
    feed_rows = db_sess.exec(q).all()

    halls = db_sess.exec(select(DiningHall)).all()

    all_users = db_sess.exec(select(User)).all()
    other_users = [u for u in all_users if u.id != me.id]
    following_ids = {row.following_id for row in follow_links}

    return templates.TemplateResponse(
        "feed.html",
        {
            "request": req,
            "user": me,
            "checkins": feed_rows,
            "halls": halls,
            "now": now,
            "other_users": other_users,
            "following_ids": following_ids,
            "matches": other_users,
        },
    )


@app.get("/dining/{hall_id}", response_class=HTMLResponse)
def dining_page(hall_id: int, req: Request, db_sess: Session = Depends(get_session)):
    me = read_user_from_cookie(req, db_sess)
    if not me:
        return RedirectResponse("/", status_code=303)

    hall_row = db_sess.get(DiningHall, hall_id)
    if not hall_row:
        return RedirectResponse("/feed", status_code=303)

    now = datetime.utcnow()
    q = (
        select(CheckIn)
        .where(CheckIn.hall_id == hall_id)
        .where(CheckIn.expires_at > now)
        .order_by(CheckIn.checked_at.desc())
    )
    hall_checkins = db_sess.exec(q).all()

    return templates.TemplateResponse(
        "dining.html",
        {
            "request": req,
            "user": me,
            "hall": hall_row,
            "checkins": hall_checkins,
            "now": now,
        },
    )


@app.get("/user/{user_id}", response_class=HTMLResponse)
def user_profile(user_id: int, req: Request, db_sess: Session = Depends(get_session)):
    me = read_user_from_cookie(req, db_sess)
    if not me:
        return RedirectResponse("/", status_code=303)

    target = db_sess.get(User, user_id)
    if not target:
        return RedirectResponse("/feed", status_code=303)

    follower_links = db_sess.exec(
        select(Follow).where(Follow.following_id == target.id)
    ).all()
    following_links = db_sess.exec(
        select(Follow).where(Follow.follower_id == target.id)
    ).all()

    follower_users: List[User] = []
    for link in follower_links:
        u = db_sess.get(User, link.follower_id)
        if u:
            follower_users.append(u)

    following_users: List[User] = []
    for link in following_links:
        u = db_sess.get(User, link.following_id)
        if u:
            following_users.append(u)

    follow_links_me = me.following
    following_ids_me = {row.following_id for row in follow_links_me}

    latest_checkin = db_sess.exec(
        select(CheckIn)
        .where(CheckIn.user_id == target.id)
        .order_by(CheckIn.checked_at.desc())
    ).first()

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": req,
            "user": me,
            "target": target,
            "followers": follower_users,
            "following": following_users,
            "following_ids_me": following_ids_me,
            "latest_checkin": latest_checkin,
        },
    )


@app.get("/people/search", response_class=HTMLResponse)
def people_search(
    req: Request,
    q: str = "",
    db_sess: Session = Depends(get_session),
):
    me = read_user_from_cookie(req, db_sess)
    if not me:
        return RedirectResponse("/", status_code=303)

    q_clean = q.strip()
    matches: List[User] = []

    if q_clean:
        matches = db_sess.exec(
            select(User)
            .where(User.id != me.id)
            .where(User.username.contains(q_clean))
        ).all()

    follow_links = me.following
    following_ids = {row.following_id for row in follow_links}

    return templates.TemplateResponse(
        "fragments/people_results.html",
        {
            "request": req,
            "matches": matches,
            "following_ids": following_ids,
        },
    )


@app.post("/checkin")
def checkin_post(
    req: Request,
    hall_id: int = Form(...),
    db_sess: Session = Depends(get_session),
):
    me = read_user_from_cookie(req, db_sess)
    if not me:
        return RedirectResponse("/", status_code=303)

    hall_row = db_sess.get(DiningHall, hall_id)
    if not hall_row:
        return RedirectResponse("/feed", status_code=303)

    old_rows = db_sess.exec(
        select(CheckIn).where(CheckIn.user_id == me.id)
    ).all()
    for row in old_rows:
        db_sess.delete(row)

    new_row = CheckIn(user_id=me.id, hall_id=hall_id)
    db_sess.add(new_row)
    db_sess.commit()

    if req.headers.get("HX-Request") == "true":
        now = datetime.utcnow()
        follow_links = me.following
        id_list: List[int] = [me.id] + [link.following_id for link in follow_links]

        q = (
            select(CheckIn)
            .where(CheckIn.user_id.in_(id_list))
            .where(CheckIn.expires_at > now)
            .order_by(CheckIn.checked_at.desc())
        )
        feed_rows = db_sess.exec(q).all()

        return templates.TemplateResponse(
            "fragments/activity.html",
            {
                "request": req,
                "user": me,
                "checkins": feed_rows,
                "now": now,
            },
        )

    return RedirectResponse("/feed", status_code=303)


@app.post("/checkin/clear")
def clear_checkin(
    req: Request,
    db_sess: Session = Depends(get_session),
):
    me = read_user_from_cookie(req, db_sess)
    if not me:
        return RedirectResponse("/", status_code=303)

    rows = db_sess.exec(
        select(CheckIn).where(CheckIn.user_id == me.id)
    ).all()
    for row in rows:
        db_sess.delete(row)
    db_sess.commit()

    if req.headers.get("HX-Request") == "true":
        now = datetime.utcnow()
        follow_links = me.following
        id_list: List[int] = [me.id] + [link.following_id for link in follow_links]

        q = (
            select(CheckIn)
            .where(CheckIn.user_id.in_(id_list))
            .where(CheckIn.expires_at > now)
            .order_by(CheckIn.checked_at.desc())
        )
        feed_rows = db_sess.exec(q).all()

        return templates.TemplateResponse(
            "fragments/activity.html",
            {
                "request": req,
                "user": me,
                "checkins": feed_rows,
                "now": now,
            },
        )

    return RedirectResponse("/feed", status_code=303)


@app.post("/follow")
def follow_user(
    req: Request,
    user_id: int = Form(...),
    db_sess: Session = Depends(get_session),
):
    me = read_user_from_cookie(req, db_sess)
    if not me:
        return RedirectResponse("/", status_code=303)

    if user_id == me.id:
        return RedirectResponse("/feed", status_code=303)

    existing = db_sess.exec(
        select(Follow).where(
            Follow.follower_id == me.id,
            Follow.following_id == user_id,
        )
    ).first()

    if not existing:
        row = Follow(follower_id=me.id, following_id=user_id)
        db_sess.add(row)
        db_sess.commit()

    return RedirectResponse("/feed", status_code=303)


@app.post("/unfollow")
def unfollow_user(
    req: Request,
    user_id: int = Form(...),
    db_sess: Session = Depends(get_session),
):
    me = read_user_from_cookie(req, db_sess)
    if not me:
        return RedirectResponse("/", status_code=303)

    rows = db_sess.exec(
        select(Follow).where(
            Follow.follower_id == me.id,
            Follow.following_id == user_id,
        )
    ).all()

    for row in rows:
        db_sess.delete(row)

    db_sess.commit()
    return RedirectResponse("/feed", status_code=303)