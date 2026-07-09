from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.models.refresh_token import RefreshToken
from backend.app.core.security import verify_password
from backend.app.core.jwt import (
    create_access_token,
    create_refresh_token,
    verify_token,
)


class AuthService:

    @staticmethod
    def login(db: Session, email: str, password: str):

        user = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not verify_password(password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        access_token = create_access_token(
            {
                "sub": str(user.id),
                "email": user.email,
                "plan": user.plan,
            }
        )

        refresh_token = create_refresh_token(
            {
                "sub": str(user.id),
            }
        )

        refresh = RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=datetime.utcnow() + timedelta(days=7),
        )

        db.add(refresh)
        db.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    @staticmethod
    def refresh(db: Session, refresh_token: str):

        payload = verify_token(refresh_token)

        if not payload:
            raise HTTPException(
                status_code=401,
                detail="Invalid refresh token",
            )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=401,
                detail="Invalid token type",
            )

        stored = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token == refresh_token,
                RefreshToken.revoked.is_(False),
            )
            .first()
        )

        if not stored:
            raise HTTPException(
                status_code=401,
                detail="Refresh token revoked",
            )

        if stored.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=401,
                detail="Refresh token expired",
            )

        user = (
            db.query(User)
            .filter(User.id == stored.user_id)
            .first()
        )

        access_token = create_access_token(
            {
                "sub": str(user.id),
                "email": user.email,
                "plan": user.plan,
            }
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
        }

    @staticmethod
    def logout(db: Session, refresh_token: str):

        stored = (
            db.query(RefreshToken)
            .filter(RefreshToken.token == refresh_token)
            .first()
        )

        if stored:
            stored.revoked = True
            db.commit()

        return {
            "message": "Logged out successfully"
        }