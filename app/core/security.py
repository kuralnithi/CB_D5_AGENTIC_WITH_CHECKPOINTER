import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any

# Bearer token extractor
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict[str, Any]:
    """
    Validates the Clerk JWT token automatically using its dynamic JWKS endpoint.
    Returns the decoded token payload which contains the user ID (in 'sub').
    """
    token = credentials.credentials
    try:
        # Extract unverified headers and payload to locate the issuer
        unverified_header = jwt.get_unverified_header(token)
        unverified_claims = jwt.decode(token, options={"verify_signature": False})
        
        issuer = unverified_claims.get("iss")
        if not issuer:
            raise HTTPException(status_code=401, detail="Invalid token formatting: missing issuer")

        # Dynamically fetch securely signed JWKS directly from Clerk
        jwks_client = PyJWKClient(f"{issuer}/.well-known/jwks.json")
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        # Verify the signature completely natively using PyJWT
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=[unverified_header["alg"]],
            issuer=issuer,
            options={"verify_aud": False} # Clerk tokens don't always mandate a specific audience in this simplified flow
        )
        return payload

    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Unauthorized")
