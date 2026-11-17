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

import requests

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


def zustand_pfad(kunde):
    return os.path.join(BASIS, "kunden", kunde, "verwendet.json")


def lade_zustand(kunde):
    p = zustand_pfad(kunde)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"fotos": [], "zaehler": 0}


def speichere_zustand(kunde, z):
    with open(zustand_pfad(kunde), "w", encoding="utf-8") as f:
        json.dump(z, f, ensure_ascii=False, indent=2)
        f.write("\n")


def automatik(kunde, marke, tag, als_feed=False):
    """Baut einen Eintrag aus einem frischen Drive-Foto und dem Textpool.

    So muss niemand einen Plan pflegen: Fotos in den Drive-Ordner legen reicht.
    """
    import drive
    ordner = marke.get("drive_ordner") or []
    if not ordner:
        print(f"{kunde}: keine Drive-Ordner in marke.json hinterlegt.")
        return None, None

    with open(os.path.join(BASIS, "kunden", kunde, "texte.json"), encoding="utf-8") as f:
        pool = json.load(f)

    z = lade_zustand(kunde)
    token = drive._token()
    alle = drive.fotos(ordner, token)
    if not alle:
        print(f"{kunde}: in den Drive-Ordnern liegen keine Bilder.")
        return None, None

    offen = [f for f in alle if f["id"] not in z["fotos"]]
    if not offen:
        # Alle schon einmal dran gewesen: Runde zuruecksetzen und Bescheid geben.
        print(f"{kunde}: alle {len(alle)} Drive-Fotos waren schon dran - beginne von vorn.")
        erinnerung_fotos(kunde, len(alle))
        z["fotos"] = []
        offen = alle

    # Serienaufnahmen: aus 2-3 fast gleichen Bildern nur das schaerfste nehmen,
    # die anderen gelten als erledigt und kommen nie dran.
    import auswahl
    kandidaten = []
    for f in offen[:6]:
        roh = drive.vorschau(f, token)
        if roh:
            kandidaten.append((f["id"], roh))
    verbraucht = []
    foto = offen[0]
    if len(kandidaten) > 1:
        best_id, serie_ids = auswahl.serie(kandidaten)
        if len(serie_ids) > 1:
            nach_id = {f["id"]: f for f in offen}
            foto = nach_id.get(best_id, offen[0])
            verbraucht = [i for i in serie_ids if i != foto["id"]]
            namen = ", ".join(nach_id[i]["name"] for i in serie_ids if i in nach_id)
            print(f"Serie erkannt ({namen}) - genommen: {foto['name']}")

    ziel = os.path.join(BASIS, "kunden", kunde, "fotos", "_automatik.jpg")
    os.makedirs(os.path.dirname(ziel), exist_ok=True)
    drive.hole(foto["id"], ziel, token)
    print(f"aus Drive geholt: {foto['name']}")

    if als_feed:
        # Beitrag ohne jeden Text: nur das Bild im Feed-Format.
        eintrag = {"datum": tag.isoformat(), "typ": "feedfoto",
                   "foto": "_automatik.jpg", "bias_y": 0.5, "quelle": foto["name"],
                   "caption": marke.get("caption_ohne_text", "")}
        z["_kein_zaehler"] = True
        z["_foto_id"] = foto["id"]
        z["_serie"] = verbraucht
        return eintrag, z

    takt = pool.get("anteil_reine_fotos", 3)
    texte = pool["texte"]
    nr = z["zaehler"]
    reines_foto = takt and (nr + 1) % takt == 0

    eintrag = {"datum": tag.isoformat(), "typ": "foto" if reines_foto else "story",
               "foto": "_automatik.jpg", "bias_y": 0.5, "quelle": foto["name"]}
    if not reines_foto:
        eintrag.update(texte[nr % len(texte)])
    z["_foto_id"] = foto["id"]
    z["_serie"] = verbraucht
    return eintrag, z


def erinnerung_fotos(kunde, anzahl):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        return
    titel = f"Neue Fotos noetig: {kunde}"
    vorhandene = requests.get(f"https://api.github.com/repos/{repo}/issues",
                              params={"state": "open", "per_page": 100},
                              headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if vorhandene.ok and any(i["title"] == titel for i in vorhandene.json()):
        return
    requests.post(f"https://api.github.com/repos/{repo}/issues",
                  headers={"Authorization": f"Bearer {token}"},
                  json={"title": titel,
                        "body": (f"Alle {anzahl} Fotos im Drive-Ordner von **{kunde}** waren "
                                 f"schon einmal in einer Story. Ab jetzt wiederholen sie sich.\n\n"
                                 f"Einfach neue Bilder in den Drive-Ordner legen - der Automat "
                                 f"nimmt sie beim naechsten Lauf von allein.")},
                  timeout=30)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kunde", required=True)
    p.add_argument("--typ", required=True, choices=["story", "feed", "feedfoto"],
                   help="feedfoto = Beitrag nur Bild, ohne Text, frisch aus Drive")
    p.add_argument("--trocken", action="store_true", help="nur rendern, nicht posten")
    p.add_argument("--datum", help="zum Testen: so tun, als waere dieser Tag (JJJJ-MM-TT)")
    a = p.parse_args()
    tag = dt.date.fromisoformat(a.datum) if a.datum else heute()

    marke = render.lade_marke(a.kunde)
    if not a.trocken and not (os.environ.get(marke["secret_token"])
                              and os.environ.get(marke["secret_account_id"])):
        print(f"{a.kunde}: Instagram-Zugangsdaten fehlen - uebersprungen.")
        return
    if a.typ in ("feed", "feedfoto") and not marke.get("postet_feed", False):
        print(f"{a.kunde}: Feed-Posts sind fuer diesen Kunden abgeschaltet - nichts zu tun.")
        return

    plan = lade_plan(a.kunde) if os.path.exists(plan_pfad(a.kunde)) else []
    eintrag = zustand = None

    if a.typ == "feedfoto":
        # Beitrag nur Bild: kommt immer frisch aus Drive, nicht aus dem Plan.
        eintrag, zustand = automatik(a.kunde, marke, tag, als_feed=True)
    else:
        # An einem Tag mit Beitrag kommt keine Story - so will es der Kunde.
        if a.typ == "story" and waehle(plan, ("feed", "feedfoto"), tag) is not None:
            print(f"{a.kunde}/story: heute ist ein Beitrag faellig - keine Story.")
            return
        # Stories: Design-Stories und reine Foto-Stories kommen aus demselben Plan.
        typen = ("story", "foto") if a.typ == "story" else ("feed",)
        eintrag = waehle(plan, typen, tag)
        if eintrag is None:
            if a.typ == "feed":
                # Geplante Beitraege haben Text und Hashtags - die kommen nur aus dem Plan.
                print(f"{a.kunde}/feed: heute kein Beitrag faellig.")
                return
            # Kein Plan-Eintrag faellig: Story automatisch aus Drive bauen.
            eintrag, zustand = automatik(a.kunde, marke, tag)
    if eintrag is None:
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

    if eintrag["typ"] in ("feed", "feedfoto"):
        mid = post.feed(account, token, adresse, eintrag.get("caption", ""))
    else:
        mid = post.story(account, token, adresse)
    print("veroeffentlicht:", mid)

    if zustand is None:
        # Eintrag kam aus dem Plan -> dort als erledigt markieren
        eintrag["erledigt"] = dt.datetime.now(ZEITZONE).isoformat(timespec="minutes")
        eintrag["instagram_id"] = mid
        speichere_plan(a.kunde, plan)
        committe([os.path.relpath(plan_pfad(a.kunde), BASIS)],
                 f"{a.kunde}: {eintrag['datum']} erledigt")
        rest = len([e for e in plan if not e.get("erledigt")])
        print("noch offen im Plan:", rest)
        if rest <= RESTWARNUNG:
            erinnerung(a.kunde, rest)
    else:
        # Automatiklauf -> verbrauchtes Foto und Textzaehler merken
        zustand["fotos"].append(zustand.pop("_foto_id"))
        zustand["fotos"].extend(zustand.pop("_serie", []))
        if not zustand.pop("_kein_zaehler", False):
            zustand["zaehler"] += 1          # Textrotation nur bei Stories weiterdrehen
        zustand["zuletzt"] = f"{tag.isoformat()} {eintrag.get('quelle', '')}"
        speichere_zustand(a.kunde, zustand)
        committe([os.path.relpath(zustand_pfad(a.kunde), BASIS)],
                 f"{a.kunde}: Foto {eintrag.get('quelle', '')} verwendet")


if __name__ == "__main__":
    main()
