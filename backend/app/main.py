import os
import uuid
import secrets
import datetime
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas, auth, mailer
from .database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Tea Stall Calculator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


def save_upload(file: UploadFile) -> str:
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(UPLOAD_DIR, filename)
    with open(dest, "wb") as f:
        f.write(file.file.read())
    return f"/uploads/{filename}"


def user_out(user: models.User) -> schemas.UserOut:
    return schemas.UserOut(
        id=user.id,
        email=user.email,
        shop_name=user.shop_name,
        qr_image_url=user.qr_image_path,
    )


def item_out(item: models.Item) -> schemas.ItemOut:
    return schemas.ItemOut(
        id=item.id,
        name=item.name,
        category=item.category,
        price=item.price,
        image_url=item.image_path,
    )


# ---------------- Auth ----------------

@app.post("/api/auth/signup", response_model=schemas.Token)
def signup(data: schemas.SignupIn, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    user = models.User(
        email=data.email,
        password_hash=auth.hash_password(data.password),
        shop_name=data.shop_name or "Tea Stall",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = auth.create_access_token(user.id)
    return schemas.Token(access_token=token)


@app.post("/api/auth/login", response_model=schemas.Token)
def login(data: schemas.LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user or not auth.verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    token = auth.create_access_token(user.id)
    return schemas.Token(access_token=token)


@app.post("/api/auth/forgot-password", response_model=schemas.MessageOut)
def forgot_password(data: schemas.ForgotPasswordIn, db: Session = Depends(get_db)):
    generic_message = "If an account exists for that email, a reset link has been sent."
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if user:
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expires = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        db.commit()
        mailer.send_password_reset_email(user.email, token)
    # Always return the same message whether or not the email exists,
    # so this endpoint can't be used to check which emails have accounts.
    return schemas.MessageOut(message=generic_message)


@app.post("/api/auth/reset-password", response_model=schemas.MessageOut)
def reset_password(data: schemas.ResetPasswordIn, db: Session = Depends(get_db)):
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password should be at least 6 characters.")
    user = db.query(models.User).filter(models.User.reset_token == data.token).first()
    if (
        not user
        or not user.reset_token_expires
        or user.reset_token_expires < datetime.datetime.utcnow()
    ):
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")
    user.password_hash = auth.hash_password(data.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()
    return schemas.MessageOut(message="Password updated. You can log in now.")


# ---------------- Shop / account ----------------

@app.get("/api/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return user_out(current_user)


@app.patch("/api/me", response_model=schemas.UserOut)
def update_me(
    data: schemas.ShopUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if data.shop_name is not None and data.shop_name.strip():
        current_user.shop_name = data.shop_name.strip()
    db.commit()
    db.refresh(current_user)
    return user_out(current_user)


@app.post("/api/me/qr", response_model=schemas.UserOut)
def upload_qr(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    current_user.qr_image_path = save_upload(file)
    db.commit()
    db.refresh(current_user)
    return user_out(current_user)


# ---------------- Items (menu) ----------------

@app.get("/api/items", response_model=List[schemas.ItemOut])
def list_items(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    items = db.query(models.Item).filter(models.Item.owner_id == current_user.id).all()
    return [item_out(i) for i in items]


@app.post("/api/items", response_model=schemas.ItemOut)
def create_item(
    name: str = Form(...),
    category: str = Form("tea_coffee"),
    price: float = Form(...),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    item = models.Item(
        owner_id=current_user.id,
        name=name,
        category=category,
        price=price,
        image_path=save_upload(image) if image else None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item_out(item)


@app.put("/api/items/{item_id}", response_model=schemas.ItemOut)
def update_item(
    item_id: int,
    name: str = Form(...),
    category: str = Form("tea_coffee"),
    price: float = Form(...),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    item = (
        db.query(models.Item)
        .filter(models.Item.id == item_id, models.Item.owner_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")
    item.name = name
    item.category = category
    item.price = price
    if image:
        item.image_path = save_upload(image)
    db.commit()
    db.refresh(item)
    return item_out(item)


@app.delete("/api/items/{item_id}")
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    item = (
        db.query(models.Item)
        .filter(models.Item.id == item_id, models.Item.owner_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")
    db.delete(item)
    db.commit()
    return {"ok": True}


# ---------------- Frontend (static files) ----------------

app.mount("/", StaticFiles(directory="static", html=True), name="frontend")
