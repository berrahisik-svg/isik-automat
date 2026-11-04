# -*- coding: utf-8 -*-
"""Holt Fotos direkt aus Google Drive - bei jedem Lauf frisch.

Der Automat meldet sich mit einem Dienstkonto an (Zugangsdaten liegen als
GitHub-Secret GOOGLE_DIENSTKONTO, nie im Repo). Berrah teilt die Drive-Ordner
mit der E-Mail-Adresse des Dienstkontos - danach sieht der Automat jedes neue
Bild automatisch.
"""
import io
import json
import os

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/drive/v3"
BILDTYPEN = ("image/jpeg", "image/png", "image/heic")


def _zugang():
    roh = os.environ.get("GOOGLE_DIENSTKONTO")
    if not roh:
        raise RuntimeError("GOOGLE_DIENSTKONTO fehlt - Secret in GitHub hinterlegen")
    return json.loads(roh)


def _token():
    """Signiertes JWT gegen ein Zugriffstoken tauschen (nur Lesezugriff)."""
    import time
    import jwt  # PyJWT

    k = _zugang()
    jetzt = int(time.time())
    behauptung = {
        "iss": k["client_email"],
        "scope": "https://www.googleapis.com/auth/drive.readonly",
        "aud": TOKEN_URL,
        "iat": jetzt,
        "exp": jetzt + 3600,
    }
    signiert = jwt.encode(behauptung, k["private_key"], algorithm="RS256")
    r = requests.post(TOKEN_URL, data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": signiert}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def fotos(ordner_ids, token=None):
    """Alle Bilder in den angegebenen Ordnern, aelteste zuerst."""
    token = token or _token()
    kopf = {"Authorization": f"Bearer {token}"}
    gefunden = []
    for oid in ordner_ids:
        seite = None
        while True:
            p = {"q": f"'{oid}' in parents and trashed = false",
                 "fields": "files(id,name,mimeType,modifiedTime,size),nextPageToken",
                 "pageSize": 1000, "supportsAllDrives": "true",
                 "includeItemsFromAllDrives": "true"}
            if seite:
                p["pageToken"] = seite
            r = requests.get(f"{API}/files", headers=kopf, params=p, timeout=60)
            r.raise_for_status()
            d = r.json()
            for f in d.get("files", []):
                if f["mimeType"] in BILDTYPEN:
                    gefunden.append(f)
            seite = d.get("nextPageToken")
            if not seite:
                break
    gefunden.sort(key=lambda f: f.get("modifiedTime", ""))
    return gefunden


def hole(datei_id, ziel, token=None):
    """Laedt ein Bild herunter und verkleinert es auf Story-Groesse."""
    token = token or _token()
    r = requests.get(f"{API}/files/{datei_id}", params={"alt": "media",
                     "supportsAllDrives": "true"},
                     headers={"Authorization": f"Bearer {token}"}, timeout=300)
    r.raise_for_status()
    from PIL import Image
    im = Image.open(io.BytesIO(r.content))
    im = im.convert("RGB")
    lang = max(im.size)
    if lang > 2400:                      # mehr braucht eine Story nie
        f = 2400 / lang
        im = im.resize((int(im.width * f), int(im.height * f)), Image.LANCZOS)
    im.save(ziel, quality=94)
    return ziel
