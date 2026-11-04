# -*- coding: utf-8 -*-
"""Rendert eine Story (1080x1920) oder einen Feed-Post (1080x1350) im Kundenstil.

Aufruf aus run.py. Braucht nur Pillow und numpy.
"""
import json
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHRIFTEN = os.path.join(BASIS, "schriften")
S = 2                      # doppelt rendern, am Ende verkleinern = scharfe Kanten
WEISS = (250, 250, 250)
UML = {"Ä": "A", "Ö": "O", "Ü": "U", "ä": "a", "ö": "o", "ü": "u"}


def lade_marke(kunde):
    with open(os.path.join(BASIS, "kunden", kunde, "marke.json"), encoding="utf-8") as f:
        return json.load(f)


def _ink(im):
    bb = im.getbbox()
    return im.crop(bb) if bb else im


def akira(text, groesse, pfad, fill=WEISS):
    """Akira Expanded hat keine Umlaute - Punkte werden passend selbst gesetzt."""
    basis = "".join(UML.get(c, c) for c in text)
    f = ImageFont.truetype(pfad, groesse)
    pad = groesse
    d0 = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    breite = int(d0.textlength(basis, font=f))
    im = Image.new("RGBA", (breite + 2 * pad, groesse * 3), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((pad, pad), basis, font=f, fill=fill)
    bb = im.getbbox()
    oben, hoehe = bb[1], bb[3] - bb[1]
    punkt = int(hoehe * 0.150)
    abstand = hoehe * 0.185
    luft = int(hoehe * 0.11)
    for i, c in enumerate(text):
        if c in UML:
            x0 = pad + d.textlength(basis[:i], font=f)
            x1 = pad + d.textlength(basis[:i + 1], font=f)
            mitte = (x0 + x1) / 2
            y = oben - luft - punkt
            for x in (mitte - abstand, mitte + abstand):
                d.rounded_rectangle([x - punkt / 2, y, x + punkt / 2, y + punkt],
                                    radius=punkt * 0.22, fill=fill)
    return _ink(im)


def passe_akira(zeilen, maxbreite, pfad, deckel):
    d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    s = 30 * S
    while s < deckel:
        f = ImageFont.truetype(pfad, s + 4)
        if max(d.textlength("".join(UML.get(c, c) for c in z), font=f) for z in zeilen) > maxbreite:
            break
        s += 4
    return s


def script(text, groesse, pfad, farbe):
    f = ImageFont.truetype(pfad, groesse)
    d0 = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    pad = groesse
    bb = d0.textbbox((0, 0), text, font=f)
    im = Image.new("RGBA", (bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - bb[0], pad - bb[1]), text, font=f, fill=farbe)
    return _ink(im)


def passe_script(text, maxbreite, pfad):
    d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    s = 60
    while s < 260 * S:
        if d.textlength(text, font=ImageFont.truetype(pfad, s + 6)) > maxbreite:
            break
        s += 6
    return s


def gesperrt(text, font, farbe, sperrung):
    d = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    breiten = [d.textlength(c, font=font) for c in text]
    asc, desc = font.getmetrics()
    im = Image.new("RGBA", (int(sum(breiten) + sperrung * len(text)) + 40, asc + desc + 40), (0, 0, 0, 0))
    dd = ImageDraw.Draw(im)
    x = 20
    for c, b in zip(text, breiten):
        dd.text((x, 20), c, font=font, fill=farbe)
        x += b + sperrung
    return _ink(im)


def schatten(ebene, weichheit, versatz, deckkraft):
    p = weichheit * 3
    sh = Image.new("RGBA", (ebene.width + p * 2, ebene.height + p * 2), (0, 0, 0, 0))
    a = ebene.split()[3].point(lambda v: min(v, deckkraft))
    schwarz = Image.new("RGBA", ebene.size, (0, 0, 0, 255))
    schwarz.putalpha(a)
    sh.paste(schwarz, (p + versatz[0], p + versatz[1]), schwarz)
    sh = sh.filter(ImageFilter.GaussianBlur(weichheit))
    sh.alpha_composite(ebene, (p, p))
    return sh


def _fuellen(img, B, H, bias_x=0.5, bias_y=0.5):
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


def baue(kunde, eintrag, ziel):
    """eintrag: ein Element aus plan.json. Gibt den Pfad des fertigen Bildes zurueck."""
    marke = lade_marke(kunde)
    kundenordner = os.path.join(BASIS, "kunden", kunde)
    rot = tuple(marke["farbe_rot"])
    f_head = os.path.join(SCHRIFTEN, marke["schrift_headline"])
    f_script = os.path.join(SCHRIFTEN, marke["schrift_script"])
    f_fliess = os.path.join(SCHRIFTEN, marke["schrift_fliess"])

    typ = eintrag["typ"]                      # story | foto | feed
    story = typ in ("story", "foto")
    B, H = (1080 * S, 1920 * S) if story else (1080 * S, 1350 * S)
    rand = 80 * S
    kopf = eintrag.get("head_c", 0.73 if story else 0.76)
    scrim = eintrag.get("scrim", 1.2)

    foto = Image.open(os.path.join(kundenordner, "fotos", eintrag["foto"])).convert("RGB")
    a = np.asarray(_fuellen(foto, B, H, eintrag.get("bias_x", 0.5), eintrag.get("bias_y", 0.5)))
    a = a.astype(np.float32) / 255
    a = np.clip((a - 0.5) * 1.14 + 0.5 + 0.03, 0, 1)
    hell = a.mean(2, keepdims=True)
    a = a * 0.92 + np.clip(hell * np.array([1.16, 0.66, 0.55]), 0, 1) * 0.08

    if typ == "foto":
        # Reines Foto: kein Text, kein Logo, nur sauber zugeschnitten und leicht angehoben.
        Image.fromarray((a * 255).astype(np.uint8)).resize((1080, 1920), Image.LANCZOS) \
             .save(ziel, quality=95)
        return ziel

    yy = np.linspace(0, 1, H)[:, None]
    oben = np.clip((0.15 - yy) / 0.15, 0, 1) * 0.34            # Platz fuers Logo
    unten = np.clip((yy - 0.66) / 0.34, 0, 1) ** 1.3 * (0.70 * scrim)
    band = np.exp(-((yy - kopf) / 0.125) ** 2) * (0.34 * scrim)  # nur hinter der Schrift
    xx = np.linspace(-1, 1, B)[None, :]
    yv = np.linspace(-1, 1, H)[:, None]
    vignette = np.clip((np.sqrt(xx ** 2 + yv ** 2) - 0.95) / 0.9, 0, 1) * 0.10
    ov = np.clip(oben + unten + band + vignette, 0, 0.92)[:, :, None]
    cv = Image.fromarray((a * (1 - ov) * 255).astype(np.uint8)).convert("RGBA")

    logo = Image.open(os.path.join(kundenordner, marke["logo"])).convert("RGBA")
    lb = (215 if story else 200) * S
    logo = logo.resize((lb, int(logo.height * lb / logo.width)), Image.LANCZOS)
    logo_y = (205 if story else 50) * S
    cv.alpha_composite(schatten(logo, 12 * S, (0, 4 * S), 120),
                       (int((B - logo.width) / 2 - 36 * S), int(logo_y - 36 * S)))

    zeilen = eintrag["headline"]
    groesse = passe_akira(zeilen, B - 2 * rand, f_head, 130 * S)
    bilder = [akira(z, groesse, f_head) for z in zeilen]
    luft = int(groesse * 0.15)
    gesamt = sum(b.height for b in bilder) + luft * (len(bilder) - 1)
    y = int(H * kopf - gesamt / 2)
    erste_y = y
    for b in bilder:
        cv.alpha_composite(schatten(b, 14 * S, (0, 8 * S), 195),
                           ((B - b.width) // 2 - 42 * S, y - 42 * S))
        y += b.height + luft

    if eintrag.get("script"):
        sg = passe_script(eintrag["script"], int((B - 2 * rand) * 0.66), f_script)
        sc = schatten(script(eintrag["script"], sg, f_script, rot), 9 * S, (0, 5 * S), 175)
        sc = sc.rotate(7, expand=True, resample=Image.BICUBIC)
        cv.alpha_composite(sc, ((B - sc.width) // 2, int(erste_y - sc.height * 0.98)))

    ff = ImageFont.truetype(f_fliess, 20 * S)
    try:
        ff.set_variation_by_axes([600])
    except Exception:
        pass
    fuss = gesperrt(marke["fusszeile"], ff, WEISS, int(3 * S))
    fuss_y = (1690 if story else 1280) * S
    cv.alpha_composite(schatten(fuss, 7 * S, (0, 3 * S), 160),
                       ((B - fuss.width) // 2 - 21 * S, int(fuss_y - fuss.height) - 21 * S))

    endgroesse = (1080, 1920) if story else (1080, 1350)
    cv.convert("RGB").resize(endgroesse, Image.LANCZOS).save(ziel, quality=95)
    return ziel
