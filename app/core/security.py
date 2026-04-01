"""
JWT security module with production-grade JWKS caching.

Production pattern: Cache the JWKS client so we don't make an HTTP call
to Clerk on every single API request. PyJWKClient has built-in caching
with a configurable TTL (lifespan).
"""

import logging
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
from functools import lru_cache

logger = logging.getLogger("finbot.security")

# Bearer token extractor
security = HTTPBearer()

# ── JWKS Client Cache ──────────────────────────────────────────────────────────
# One client per issuer, reused across all requests.
# PyJWKClient internally caches keys with its own lifespan (default 300s).
_jwks_clients: Dict[str, PyJWKClient] = {}


def _get_jwks_client(issuer: str) -> PyJWKClient:
    """
    Get or create a cached JWKS client for the given issuer.
    The client caches signing keys internally (lifespan=300s by default).
    """
    if issuer not in _jwks_clients:
        logger.info("Creating JWKS client for issuer", extra={"issuer": issuer})
        _jwks_clients[issuer] = PyJWKClient(
            f"{issuer}/.well-known/jwks.json",
            cache_keys=True,
            lifespan=300,  # Re-fetch keys every 5 minutes
        )
    return _jwks_clients[issuer]


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict[str, Any]:
    """
    Validates the Clerk JWT token using its dynamic JWKS endpoint.
    Returns the decoded token payload which contains the user ID (in 'sub').

    Production improvements:
    - JWKS client is cached per issuer (no HTTP call on every request)
    - Structured logging for auth failures
    """
    token = credentials.credentials
    try:
        # Extract unverified headers and payload to locate the issuer
        unverified_header = jwt.get_unverified_header(token)
        unverified_claims = jwt.decode(token, options={"verify_signature": False})

        issuer = unverified_claims.get("iss")
        if not issuer:
            logger.warning("Token missing issuer claim")
            raise HTTPException(status_code=401, detail="Invalid token formatting: missing issuer")

        # Get cached JWKS client (no repeated HTTP calls!)
        jwks_client = _get_jwks_client(issuer)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Verify the signature
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=[unverified_header["alg"]],
            issuer=issuer,
            options={"verify_aud": False}
        )

        logger.debug("Token validated", extra={"user_id": payload.get("sub")})
        return payload

    except jwt.ExpiredSignatureError:
        logger.info("Expired token rejected")
        raise HTTPException(status_code=401, detail="Token has expired")

    except jwt.PyJWTError as e:
        logger.warning("JWT validation failed", extra={"error": str(e)})
        raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is

    except Exception as e:
        logger.error("Unexpected auth error", exc_info=True)
        raise HTTPException(status_code=401, detail="Unauthorized")
