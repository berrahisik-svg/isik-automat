# -*- coding: utf-8 -*-
"""Erkennt Serienaufnahmen und sucht aus jeder Serie das schaerfste Bild.

Hintergrund: beim Shooting entstehen 2-3 fast gleiche Aufnahmen vom selben
Motiv. Davon soll nur eine in die Story, der Rest wird uebersprungen.

Die Schwelle 0.21 wurde an 64 echten Prime-Doener-Aufnahmen geprueft: sie
findet genau die Doppel (gleicher Teller, gleicher Winkel) und trennt
Aufnahmen, die sich wirklich unterscheiden.
"""
import io

import numpy as np
from PIL import Image

SCHWELLE = 0.21        # Anteil unterschiedlicher Bits, ab dem zwei Bilder verschieden sind
KANTE = 16             # Rastergroesse des Fingerabdrucks


def _bild(quelle):
    if isinstance(quelle, (bytes, bytearray)):
        return Image.open(io.BytesIO(quelle))
    return Image.open(quelle)


def fingerabdruck(quelle):
    """Differenz-Hash: hell/dunkel-Vergleich benachbarter Felder."""
    im = _bild(quelle).convert("L").resize((KANTE + 1, KANTE), Image.LANCZOS)
    a = np.asarray(im, dtype=np.int16)
    return (a[:, 1:] > a[:, :-1]).flatten()


def schaerfe(quelle):
    """Laplace-Varianz: je hoeher, desto knackiger das Bild."""
    im = _bild(quelle).convert("L").resize((400, 400), Image.LANCZOS)
    a = np.asarray(im, dtype=np.float32)
    lap = (-4 * a + np.roll(a, 1, 0) + np.roll(a, -1, 0)
           + np.roll(a, 1, 1) + np.roll(a, -1, 1))[1:-1, 1:-1]
    return float(lap.var())


def abstand(h1, h2):
    return float((h1 != h2).mean())


def serie(kandidaten, schwelle=SCHWELLE):
    """kandidaten: [(schluessel, vorschau_bytes), ...], erster ist der Anker.

    Gibt zurueck: (schluessel des besten Bildes, alle Schluessel der Serie).
    Faellt bei fehlenden oder kaputten Vorschauen auf den Anker zurueck.
    """
    if not kandidaten:
        return None, []
    gut = []
    for s, roh in kandidaten:
        try:
            gut.append((s, fingerabdruck(roh), roh))
        except Exception:
            continue
    if not gut:
        return kandidaten[0][0], [kandidaten[0][0]]

    anker = gut[0]
    gruppe = [anker] + [g for g in gut[1:] if abstand(anker[1], g[1]) < schwelle]
    if len(gruppe) == 1:
        return anker[0], [anker[0]]

    bestes = max(gruppe, key=lambda g: schaerfe(g[2]))
    return bestes[0], [g[0] for g in gruppe]
