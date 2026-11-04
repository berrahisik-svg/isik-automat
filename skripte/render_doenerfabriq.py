# -*- coding: utf-8 -*-
"""Renderer fuer den DönerFabriq-Stil (1080x1920).

Masse, Schriftgroessen, Neigung und Verlaeufe stammen 1:1 aus den PSDs
2024-12-27_Dönerfabrik_SocialMedia_13/14/15 und sind hier fest verdrahtet.

Aufbau einer Story:
  Foto randlos  ->  Verlauf oben  ->  Verlauf unten  ->  Logo mittig oben
  ->  Headline (Bebas Neue, weiss, leicht nach rechts steigend)
  ->  optional Handschrift (Autography) und Akzentwort in Gold
  ->  optional Pfeil, Standort-Pin, Saison-Overlay
"""
import json
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHRIFTEN = os.path.join(BASIS, "schriften")
S = 2                                   # doppelt rendern, am Ende verkleinern
B, H = 1080 * S, 1920 * S

WEISS = (255, 255, 255)
GOLD = (255, 208, 61)                   # #FFD03D - aus der PSD ausgelesen

# --- Masse aus der PSD (in 1x-Pixeln) -------------------------------------
LOGO_BREITE = 212
LOGO_OBEN = 215
HEAD_LINKS = 100
HEAD_OBEN = 385
HEAD_ZEILENSCHRITT = 206                # Tinte Oberkante zu Oberkante
HEAD_GROESSE = 236                      # 211.667 pt * 1.1167 Skalierung
HEAD_NEIGUNG = -0.0799                  # steigt nach rechts (b/d aus der Matrix)
SCRIPT_NEIGUNG = -0.1343
ADRESSE_GROESSE = 151                   # 211.667 pt * 0.714
SCRIPT_GROESSE = 74                     # Autography 61.7 pt * 1.1946


def lade_marke(kunde):
    with open(os.path.join(BASIS, "kunden", kunde, "marke.json"), encoding="utf-8") as f:
        return json.load(f)


def _ink(im):
    bb = im.getbbox()
    return im.crop(bb) if bb else im


def _text(txt, pfad, groesse, farbe):
    f = ImageFont.truetype(pfad, groesse)
    pad = groesse
    d0 = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    bb = d0.textbbox((0, 0), txt, font=f)
    im = Image.new("RGBA", (bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - bb[0], pad - bb[1]), txt, font=f, fill=farbe)
    return _ink(im)


def neigen(im, faktor):
    """Vertikale Scherung wie in der PSD: die rechte Seite steigt.

    faktor ist b/d aus der Photoshop-Matrix und negativ.
    """
    if not faktor:
        return im
    k = abs(faktor)
    pad = int(k * im.width) + 2
    unter = Image.new("RGBA", (im.width, im.height + pad), (0, 0, 0, 0))
    unter.paste(im, (0, pad))
    # Quellkoordinate: y_quelle = y_ziel + k * x  ->  rechts wird nach oben gezogen
    gross = unter.transform(unter.size, Image.AFFINE, (1, 0, 0, k, 1, 0),
                            resample=Image.BICUBIC)
    return _ink(gross)


def glanz(im, glow=GOLD, glow_size=12, glow_deckkraft=0.36,
          schatten_size=35, schatten_abstand=11, schatten_deckkraft=0.47):
    """Ebenenstil aus der PSD: weicher goldener Schein plus dunkler Schlagschatten."""
    from PIL import ImageFilter
    pad = int(max(glow_size, schatten_size) * 2.2 * S) + schatten_abstand * S
    gross = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))

    alpha = Image.new("L", gross.size, 0)
    alpha.paste(im.split()[3], (pad, pad))

    sh = alpha.filter(ImageFilter.GaussianBlur(schatten_size * S / 2.2))
    sh = sh.point(lambda v: int(v * schatten_deckkraft))
    schatten = Image.new("RGBA", gross.size, (0, 0, 0, 0))
    schatten.putalpha(sh)
    schatten = Image.composite(Image.new("RGBA", gross.size, (0, 0, 0, 255)),
                               Image.new("RGBA", gross.size, (0, 0, 0, 0)), sh)
    gross.alpha_composite(schatten, (0, schatten_abstand * S))

    gl = alpha.filter(ImageFilter.GaussianBlur(glow_size * S / 2.2))
    gl = gl.point(lambda v: int(v * glow_deckkraft))
    schein = Image.composite(Image.new("RGBA", gross.size, glow + (255,)),
                             Image.new("RGBA", gross.size, (0, 0, 0, 0)), gl)
    gross.alpha_composite(schein)

    gross.alpha_composite(im, (pad, pad))
    return gross, pad


def passe_groesse(txt, pfad, maxbreite, deckel):
    lo, hi = 10, deckel
    while hi - lo > 1:
        m = (lo + hi) // 2
        if _text(txt, pfad, m, WEISS).width < maxbreite:
            lo = m
        else:
            hi = m
    return lo


def _fuellen(img, bias_x=0.5, bias_y=0.5):
    iw, ih = img.size
    if iw / ih > B / H:
        nw = int(ih * B / H)
        x = int((iw - nw) * bias_x)
        img = img.crop((x, 0, x + nw, ih))
    else:
        nh = int(iw * H / B)
        y = int((ih - nh) * bias_y)
        img = img.crop((0, y, iw, y + nh))
    return img.resize((B, H), Image.LANCZOS)


def _asset(kundenordner, name):
    return Image.open(os.path.join(kundenordner, "assets", name)).convert("RGBA")


def baue(kunde, eintrag, ziel):
    marke = lade_marke(kunde)
    ko = os.path.join(BASIS, "kunden", kunde)
    f_head = os.path.join(SCHRIFTEN, "BebasNeue-Regular.ttf")
    f_script = os.path.join(SCHRIFTEN, "Autography.otf")

    foto = Image.open(os.path.join(ko, "fotos", eintrag["foto"])).convert("RGB")
    a = np.asarray(_fuellen(foto, eintrag.get("bias_x", 0.5), eintrag.get("bias_y", 0.5)))
    a = a.astype(np.float32) / 255
    a = np.clip((a - 0.5) * 1.08 + 0.5 + 0.02, 0, 1)      # dezent, kein Farbstich
    cv = Image.fromarray((a * 255).astype(np.uint8)).convert("RGBA")

    if eintrag["typ"] == "foto":
        cv.convert("RGB").resize((1080, 1920), Image.LANCZOS).save(ziel, quality=95)
        return ziel

    # Verlaeufe aus der PSD, nur skaliert
    oben = _asset(ko, "verlauf_oben.png").resize((B, int(1155 * S)), Image.LANCZOS)
    cv.alpha_composite(oben, (0, 0))
    unten = _asset(ko, "verlauf_unten.png").resize((B, int(1329 * S)), Image.LANCZOS)
    cv.alpha_composite(unten, (0, 591 * S))

    logo = Image.open(os.path.join(ko, marke["logo"])).convert("RGBA")
    lb = LOGO_BREITE * S
    logo = logo.resize((lb, int(logo.height * lb / logo.width)), Image.LANCZOS)
    cv.alpha_composite(logo, ((B - lb) // 2, LOGO_OBEN * S))

    zeilen = eintrag["headline"]
    wunsch = eintrag.get("head_groesse", HEAD_GROESSE) * S
    groesse = min(wunsch,
                  min(passe_groesse(z, f_head, B - 2 * HEAD_LINKS * S, 320 * S) for z in zeilen))
    schritt = int(HEAD_ZEILENSCHRITT * S * groesse / (HEAD_GROESSE * S))
    y = eintrag.get("head_y", HEAD_OBEN) * S
    mittig = eintrag.get("head_x") == "mitte"
    mit_glanz = eintrag.get("glanz", bool(eintrag.get("pin")))
    for z in zeilen:
        bild = neigen(_text(z, f_head, groesse, WEISS), HEAD_NEIGUNG)
        pad = 0
        if mit_glanz:
            bild, pad = glanz(bild)
        x = (B - bild.width) // 2 if mittig else int(eintrag.get("head_x", HEAD_LINKS)) * S - pad
        cv.alpha_composite(bild, (x, y - pad))
        y += schritt

    if eintrag.get("script"):
        sg = eintrag.get("script_groesse", SCRIPT_GROESSE) * S
        sc = neigen(_text(eintrag["script"], f_script, sg, WEISS), SCRIPT_NEIGUNG)
        spad = 0
        if mit_glanz:
            sc, spad = glanz(sc, glow=(168, 218, 230), glow_size=8, glow_deckkraft=0.33,
                             schatten_size=70, schatten_abstand=0, schatten_deckkraft=0.43)
        sx = eintrag.get("script_x", HEAD_LINKS) * S - spad
        sy = eintrag.get("script_y", y // S + 30) * S - spad
        cv.alpha_composite(sc, (sx, sy))

    if eintrag.get("akzent"):
        ag = eintrag.get("akzent_groesse", 108) * S
        ak = neigen(_text(eintrag["akzent"], f_head, ag, GOLD), HEAD_NEIGUNG)
        cv.alpha_composite(ak, (eintrag.get("akzent_x", 440) * S,
                                eintrag.get("akzent_y", 1417) * S))

    if eintrag.get("pfeil"):
        pf = _asset(ko, "pfeil.png")
        pb = int(eintrag.get("pfeil_breite", 161) * S)
        pf = pf.resize((pb, int(pf.height * pb / pf.width)), Image.LANCZOS)
        cv.alpha_composite(pf, (int(eintrag["pfeil"][0] * S), int(eintrag["pfeil"][1] * S)))

    if eintrag.get("pin"):
        pn = _asset(ko, "pin.png")
        nb = int(107 * S)
        pn = pn.resize((nb, int(pn.height * nb / pn.width)), Image.LANCZOS)
        cv.alpha_composite(pn, ((B - nb) // 2, int(eintrag["pin"] * S)))

    if eintrag.get("overlay"):
        ov = _asset(ko, os.path.join("saison", eintrag["overlay"]))
        ov = ov.resize((int(2047 * S), int(2047 * S)), Image.LANCZOS)
        cv.alpha_composite(ov, (-483 * S, 0))

    cv.convert("RGB").resize((1080, 1920), Image.LANCZOS).save(ziel, quality=95)
    return ziel
