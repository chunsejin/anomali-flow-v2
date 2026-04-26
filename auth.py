import os
import uuid
from functools import lru_cache
from typing import Any, Dict, List, Optional

import jwt
from fastapi import Header, HTTPException, status
from jwt import PyJWKClient
from pydantic import BaseModel


class AuthSettings(BaseModel):
    auth_enabled: bool = True
    oidc_issuer_url: Optional[str] = None
    oidc_audience: Optional[str] = None
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "RS256"


class RequestContext(BaseModel):
    tenant_id: str
    actor_id: str
    roles: List[str]
    request_id: str
    plan_tier: str = "standard"

    def as_tenant_context(self) -> Dict[str, Any]:
        return self.dict()


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings(
        auth_enabled=os.getenv("AUTH_ENABLED", "true").lower() == "true",
        oidc_issuer_url=os.getenv("OIDC_ISSUER_URL"),
        oidc_audience=os.getenv("OIDC_AUDIENCE"),
        jwt_secret=os.getenv("JWT_SECRET"),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "RS256"),
    )


@lru_cache
def get_jwks_client(issuer_url: str) -> PyJWKClient:
    jwks_url = issuer_url.rstrip("/") + "/.well-known/jwks.json"
    return PyJWKClient(jwks_url)


def parse_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def _decode_hs_token(token: str, settings: AuthSettings) -> Dict[str, Any]:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET is required for HS token validation",
        )

    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        audience=settings.oidc_audience,
        issuer=settings.oidc_issuer_url,
        options={"verify_aud": bool(settings.oidc_audience)},
    )


def _decode_oidc_token(token: str, settings: AuthSettings) -> Dict[str, Any]:
    if not settings.oidc_issuer_url or not settings.oidc_audience:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OIDC_ISSUER_URL and OIDC_AUDIENCE are required",
        )

    signing_key = get_jwks_client(settings.oidc_issuer_url).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=[settings.jwt_algorithm],
        audience=settings.oidc_audience,
        issuer=settings.oidc_issuer_url,
    )


def decode_token(token: str, settings: AuthSettings) -> Dict[str, Any]:
    try:
        if settings.jwt_secret:
            return _decode_hs_token(token, settings)
        return _decode_oidc_token(token, settings)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def _roles_from_claims(claims: Dict[str, Any]) -> List[str]:
    roles = claims.get("roles") or claims.get("role") or claims.get("groups") or []
    if isinstance(roles, str):
        return [roles]
    if isinstance(roles, list):
        return [str(role) for role in roles]
    return []


def build_request_context(claims: Dict[str, Any], request_id: Optional[str]) -> RequestContext:
    tenant_id = claims.get("tenant_id") or claims.get("org_id") or claims.get("organization_id")
    actor_id = claims.get("sub")
    roles = _roles_from_claims(claims)

    if not tenant_id or not actor_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token must include tenant_id and sub claims",
        )
    if not roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token must include at least one role",
        )

    return RequestContext(
        tenant_id=str(tenant_id),
        actor_id=str(actor_id),
        roles=roles,
        request_id=request_id or str(uuid.uuid4()),
        plan_tier=str(claims.get("plan_tier") or "standard"),
    )


def require_request_context(
    authorization: Optional[str] = Header(default=None),
    x_request_id: Optional[str] = Header(default=None),
) -> RequestContext:
    settings = get_auth_settings()
    if not settings.auth_enabled:
        return RequestContext(
            tenant_id=os.getenv("DEV_TENANT_ID", "default"),
            actor_id=os.getenv("DEV_ACTOR_ID", "dev-user"),
            roles=os.getenv("DEV_ROLES", "tenant_admin,ml_operator,viewer").split(","),
            request_id=x_request_id or str(uuid.uuid4()),
            plan_tier=os.getenv("DEV_PLAN_TIER", "standard"),
        )

    token = parse_bearer_token(authorization)
    claims = decode_token(token, settings)
    return build_request_context(claims, x_request_id)


def require_roles(context: RequestContext, allowed_roles: set[str]) -> RequestContext:
    if "platform_admin" in context.roles or allowed_roles.intersection(context.roles):
        return context
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
