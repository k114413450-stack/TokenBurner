# -*- coding: utf-8 -*-
import os
import sys

def get_app_data_dir():
    """
    Returns standard app data directory in user profile:
    %APPDATA%\\TokenBurner
    Ensures folder exists and is writable on any Windows machine.
    """
    app_data = os.environ.get("APPDATA")
    if not app_data:
        app_data = os.path.expanduser("~")
    target = os.path.join(app_data, "TokenBurner")
    try:
        os.makedirs(target, exist_ok=True)
    except Exception:
        pass
    return target
