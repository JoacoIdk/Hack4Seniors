"""
Translation files for the frontends: ``locales/<code>.json`` in the backend
folder. Each file may include ``"_meta": {"name": "Español"}`` for listings.
"""

import json
import re

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

import config
from models import LanguageOut

router = APIRouter(prefix="/languages", tags=["Languages"])

_CODE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$")


@router.get("", response_model=list[LanguageOut])
async def list_languages():
    languages = []
    for file in sorted(config.LOCALES_DIR.glob("*.json")):
        try:
            name = json.loads(file.read_text(encoding="utf-8")).get("_meta", {}).get("name", file.stem)
        except (OSError, ValueError, AttributeError):
            continue
        languages.append({"code": file.stem, "name": name})
    return languages


@router.get("/{code}", response_class=FileResponse)
async def get_language(code: str):
    """Download the translation file for ``code`` (e.g. ``es``, ``en``, ``es-CL``)."""
    if not _CODE.match(code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid language code")
    file = config.LOCALES_DIR / f"{code}.json"
    if not file.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Language not found")
    return FileResponse(file, media_type="application/json", headers={"Cache-Control": "public, max-age=3600"})
