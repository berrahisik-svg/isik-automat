# -*- coding: utf-8 -*-
"""Veroeffentlicht ein Bild als Instagram-Story oder Feed-Post (Meta Graph API).

Braucht einen Instagram-Professional-Account, der mit einer Facebook-Seite
verknuepft ist, und einen Zugangstoken mit den Rechten
instagram_basic, instagram_content_publish, pages_show_list.
"""
import time
import requests

API = "https://graph.facebook.com/v21.0"


def _container(account_id, token, **felder):
    r = requests.post(f"{API}/{account_id}/media", data={"access_token": token, **felder}, timeout=60)
    r.raise_for_status()
    return r.json()["id"]


def _warte_bereit(container_id, token, versuche=20):
    """Meta laedt das Bild erst herunter - erst danach darf veroeffentlicht werden."""
    for _ in range(versuche):
        r = requests.get(f"{API}/{container_id}",
                         params={"fields": "status_code,status", "access_token": token}, timeout=30)
        r.raise_for_status()
        status = r.json().get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Meta konnte das Bild nicht verarbeiten: {r.json()}")
        time.sleep(5)
    raise RuntimeError("Zeitueberschreitung: Container wurde nicht fertig")


def _veroeffentliche(account_id, token, container_id):
    r = requests.post(f"{API}/{account_id}/media_publish",
                      data={"creation_id": container_id, "access_token": token}, timeout=60)
    r.raise_for_status()
    return r.json()["id"]


def story(account_id, token, bild_url):
    cid = _container(account_id, token, image_url=bild_url, media_type="STORIES")
    _warte_bereit(cid, token)
    return _veroeffentliche(account_id, token, cid)


def feed(account_id, token, bild_url, caption):
    cid = _container(account_id, token, image_url=bild_url, caption=caption)
    _warte_bereit(cid, token)
    return _veroeffentliche(account_id, token, cid)


def pruefe_token(account_id, token):
    """Kurzer Test ohne zu posten - sagt, ob Token und Account-ID stimmen."""
    r = requests.get(f"{API}/{account_id}",
                     params={"fields": "username,name", "access_token": token}, timeout=30)
    r.raise_for_status()
    return r.json()
