"""
Authentication utilities placeholder.

In production, integrate JWT or session-based auth as needed and enforce on routes.
"""

from fastapi import Depends


# PUBLIC_INTERFACE
def require_user():
    """Placeholder dependency to represent an authenticated user context."""
    return {"user_id": "anonymous"}
