from fastapi import Header, HTTPException

API_KEYS = {
    "demo_key_123": {
        "user_id": "u1",
        "plan": "free",
        "preferences": {
            "keywords": ["backend", "python"],
            "location": "remote",
            "remote": True
        }
    }
}


def get_current_user(x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    user = API_KEYS.get(x_api_key)

    if not user:
        raise HTTPException(status_code=403, detail="Invalid API key")

    # ✅ IMPORTANT: return a COPY (prevents accidental mutation bugs)
    return {
        "api_key": x_api_key,
        "user_id": user["user_id"],
        "plan": user["plan"],
        "preferences": user["preferences"]
    }


# -------------------------
# STRIPE UPGRADE FUNCTION
# -------------------------
def upgrade_user_plan(api_key: str, new_plan: str):
    user = API_KEYS.get(api_key)

    if not user:
        return False

    user["plan"] = new_plan
    return True
