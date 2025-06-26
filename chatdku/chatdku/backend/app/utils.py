#Utils file for 

from flask import request

ALLOWED_EXTENSIONS={"pdf"}

def shib_attrs():
    """Pull attributes added by Apache ↔︎ Shibboleth."""
    return {
        "eppn":        request.headers.get("X-EPPN"),         # e.g. jbd123@duke.edu
        "displayName": request.headers.get("X-DisplayName"),  # e.g. Jane BlueDevil
    }


def allowed_file(filename): 
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS