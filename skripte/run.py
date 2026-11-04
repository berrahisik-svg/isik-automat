#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Taeglicher Lauf: naechsten faelligen Planeintrag rendern, hochladen, posten.

Aufruf (macht GitHub Actions automatisch):
    python skripte/run.py --kunde prime-doener --typ story
    python skripte/run.py --kunde prime-doener --typ feed
    python skripte/run.py --kunde prime-doener --typ story --trocken   # nur rendern

Was passiert:
 1. plan.json des Kunden lesen, ersten faelligen und noch offenen Eintrag nehmen
 2. Bild rendern (skripte/render.py)
 3. Bild ins Repo committen -> dadurch bekommt es eine oeffentliche Adresse
 4. Ueber die Instagram-API als Story bzw. Beitrag veroeffentlichen
 5. Eintrag im Plan als erledigt markieren und das ebenfalls committen
 6. Wenn der Plan knapp wird: Erinnerung als GitHub-Issue anlegen
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import zoneinfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render
import render_doenerfabriq
import post

RENDERER = {"primedoener": render, "doenerfabriq": render_doenerfabriq}

BASIS = render.BASIS
ZEITZONE = zoneinfo.ZoneInfo("Europe/Berlin")
RESTWARNUNG = 8          # ab so wenigen offenen Eintraegen gibt es eine Erinnerung


def heute():
    return dt.datetime.now(ZEITZONE).date()


def sh(*befehl, pflicht=True):
    e = subprocess.run(befehl, cwd=BASIS, capture_output=True, text=True)
    if pflicht and e.returncode != 0:
        raise RuntimeError(f"{' '.join(befehl)}\n{e.stdout}\n{e.stderr}")
    return e


def plan_pfad(kunde):
    return os.path.join(BASIS, "kunden", kunde, "plan.json")


def lade_plan(kunde):
    with open(plan_pfad(kunde), encoding="utf-8") as f:
        return json.load(f)


def speichere_plan(kunde, plan):
    with open(plan_pfad(kunde), "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
        f.write("\n")


def waehle(plan, typen, tag):
    """Erster Eintrag, der faellig ist (Datum heute oder frueher) und noch offen.

    Nur faellige Eintraege - der Plan bestimmt also den Takt. Faellt ein Lauf aus,
    bleibt der Eintrag offen und wird am naechsten Tag nachgeholt.
    """
    faellig = [e for e in plan
               if not e.get("erledigt")
               and e["typ"] in typen
               and dt.date.fromisoformat(e["datum"]) <= tag]
    return faellig[0] if faellig else None


def oeffentliche_adresse(relativ):
    """raw.githubusercontent.com liefert Dateien aus oeffentlichen Repos direkt aus.

    Instagram muss das Bild selbst herunterladen koennen - darum muss das Repo
    oeffentlich sein. Zugangsdaten liegen nie im Repo, sondern in den Secrets.
    """
    repo = os.environ.get("GITHUB_REPOSITORY")
    zweig = os.environ.get("GITHUB_REF_NAME", "main")
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY fehlt - laeuft das wirklich in GitHub Actions?")
    return f"https://raw.githubusercontent.com/{repo}/{zweig}/{relativ}"


def committe(dateien, nachricht):
    sh("git", "config", "user.name", "Automat")
    sh("git", "config", "user.email", "292820202+berrahisik-svg@users.noreply.github.com")
    sh("git", "add", *dateien)
    if not sh("git", "diff", "--cached", "--quiet", pflicht=False).returncode:
        return False                      # nichts geaendert
    sh("git", "commit", "-m", nachricht)
    for versuch in range(3):
        if sh("git", "push", pflicht=False).returncode == 0:
            return True
        sh("git", "pull", "--rebase", pflicht=False)
    raise RuntimeError("git push hat nicht funktioniert")


def erinnerung(kunde, offen):
    """Legt ein GitHub-Issue an, wenn der Themenplan zur Neige geht."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        return
    import requests
    titel = f"Nachschub noetig: {kunde} hat nur noch {offen} geplante Posts"
    vorhandene = requests.get(f"https://api.github.com/repos/{repo}/issues",
                              params={"state": "open", "per_page": 100},
                              headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if vorhandene.ok and any(kunde in i["title"] and "Nachschub" in i["title"]
                            for i in vorhandene.json()):
        return
    requests.post(f"https://api.github.com/repos/{repo}/issues",
                  headers={"Authorization": f"Bearer {token}"},
                  json={"title": titel,
                        "body": (f"Der Themenplan von **{kunde}** hat nur noch {offen} offene "
                                 f"Eintraege.\n\nNeue Fotos in den Google-Drive-Ordner legen und "
                                 f"Bescheid geben - dann wird der Plan nachgefuellt.")},
                  timeout=30)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kunde", required=True)
    p.add_argument("--typ", required=True, choices=["story", "feed"])
    p.add_argument("--trocken", action="store_true", help="nur rendern, nicht posten")
    p.add_argument("--datum", help="zum Testen: so tun, als waere dieser Tag (JJJJ-MM-TT)")
    a = p.parse_args()
    tag = dt.date.fromisoformat(a.datum) if a.datum else heute()

    marke = render.lade_marke(a.kunde)
    if a.typ == "feed" and not marke.get("postet_feed", False):
        print(f"{a.kunde}: Feed-Posts sind fuer diesen Kunden abgeschaltet - nichts zu tun.")
        return

    # Stories: Design-Stories und reine Foto-Stories kommen aus demselben Plan.
    typen = ("story", "foto") if a.typ == "story" else ("feed",)
    plan = lade_plan(a.kunde)
    eintrag = waehle(plan, typen, tag)
    if eintrag is None:
        rest = len([e for e in plan if not e.get("erledigt")])
        print(f"{a.kunde}/{a.typ}: heute nichts faellig. Noch offen im Plan: {rest}")
        if rest <= RESTWARNUNG:
            erinnerung(a.kunde, rest)
        return

    ordner = os.path.join(BASIS, "veroeffentlicht", a.kunde)
    os.makedirs(ordner, exist_ok=True)
    name = f"{tag.isoformat()}-{eintrag['typ']}.jpg"
    ziel = os.path.join(ordner, name)
    RENDERER[marke.get("stil", "primedoener")].baue(a.kunde, eintrag, ziel)
    print("gerendert:", ziel)

    if a.trocken:
        return

    token = os.environ[marke["secret_token"]]
    account = os.environ[marke["secret_account_id"]]

    relativ = os.path.relpath(ziel, BASIS).replace(os.sep, "/")
    committe([relativ], f"Bild fuer {a.kunde} am {tag.isoformat()}")
    adresse = oeffentliche_adresse(relativ)
    print("Adresse:", adresse)

    if eintrag["typ"] == "feed":
        mid = post.feed(account, token, adresse, eintrag.get("caption", ""))
    else:
        mid = post.story(account, token, adresse)
    print("veroeffentlicht:", mid)

    eintrag["erledigt"] = dt.datetime.now(ZEITZONE).isoformat(timespec="minutes")
    eintrag["instagram_id"] = mid
    speichere_plan(a.kunde, plan)
    committe([os.path.relpath(plan_pfad(a.kunde), BASIS)],
             f"{a.kunde}: {eintrag['datum']} erledigt")

    rest = len([e for e in plan if not e.get("erledigt")])
    print("noch offen im Plan:", rest)
    if rest <= RESTWARNUNG:
        erinnerung(a.kunde, rest)


if __name__ == "__main__":
    main()
