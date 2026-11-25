from functools import wraps

from flask import abort
from flask_login import current_user


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                from flask_login import login_required
                return login_required(view)(*args, **kwargs)
            if current_user.role_name not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator
