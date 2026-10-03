import json
import os
import re
from utils.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = "data"
VARS_FILE = os.path.join(DATA_DIR, "variables.json")


# ---------------------------------------------------------------------------
# Persistence helpers — custom variables
# ---------------------------------------------------------------------------

def _load_vars() -> dict:
    """Load variables file: { "admin_id": { "var_name": "value" } }"""
    try:
        with open(VARS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_vars(data: dict) -> None:
    """Persist variables dict to disk."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(VARS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_vars(admin_id: int) -> dict:
    """Return the variable map for a specific admin."""
    return _load_vars().get(str(admin_id), {})


def set_var(admin_id: int, name: str, value: str) -> None:
    """Set (or update) a custom variable for an admin."""
    data = _load_vars()
    key = str(admin_id)
    if key not in data:
        data[key] = {}
    data[key][name] = value
    _save_vars(data)
    logger.info("Variable set by admin %s: $%s = %r", admin_id, name, value)


def delete_var(admin_id: int, name: str) -> bool:
    """Delete a custom variable. Returns True if it existed."""
    data = _load_vars()
    key = str(admin_id)
    if key in data and name in data[key]:
        del data[key][name]
        if not data[key]:
            del data[key]
        _save_vars(data)
        logger.info("Variable deleted by admin %s: $%s", admin_id, name)
        return True
    return False


# ---------------------------------------------------------------------------
# Variable interpolation
# ---------------------------------------------------------------------------

# Built-in variables resolved from Telegram user object.
_USER_VAR_MAP = {
    "first_name": lambda u: u.first_name or "",
    "last_name":  lambda u: u.last_name or "",
    "username":   lambda u: u.username or "",
    "id":         lambda u: str(u.id),
    "full_name":  lambda u: u.full_name or "",
    "language":   lambda u: u.language_code or "",
}


def resolve_variables(text: str, admin_id: int, user) -> str:
    """Replace $variable placeholders in *text* and return the interpolated string.

    Resolution order (first match wins):
      1. Built-in user variables  ($first_name, $last_name, $username, $id, $full_name, $language)
      2. Custom admin variables   (set via /setvar)
      3. Unknown variables        -> replaced with empty string (no error)

    Parameters
    ----------
    text:     The template string, e.g. "Ciao $username!"
    admin_id: ID of the admin who owns the reply rule
    user:     telegram.User object of the person who sent the message
    """
    if "$" not in text:
        return text

    custom_vars = get_vars(admin_id)

    def replacer(m: re.Match) -> str:
        var_name = m.group(1)

        # 1. Built-in user variable
        if var_name in _USER_VAR_MAP:
            try:
                return _USER_VAR_MAP[var_name](user)
            except Exception:
                return ""

        # 2. Custom admin variable
        if var_name in custom_vars:
            return custom_vars[var_name]

        # 3. Unknown -> empty string, silent
        logger.debug("Unknown variable $%s in reply template", var_name)
        return ""

    return re.sub(r"\$(\w+)", replacer, text)
