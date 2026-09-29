#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pruefe_bildauswertung.py — der Maßstab für die JavaScript-Fassung der Bildauswertung.

Die Seite im Browser rechnet die Erkennung in JavaScript nach. Damit das nicht bloß behauptet ist, wird hier ein
Prüfbild **ohne Zeichenprogramm** erzeugt — allein aus einer Formel und einem Zufallszahlengenerator, den beide Seiten
Schritt für Schritt gleich ausführen können (Lehmer: s ← 48271·s mod 2147483647). Dieses Bild geht durch die wörtlich
aus dem Programm herausgeschnittene Bildauswertung (bv_referenz.py). Zeile, Konfidenz und einige Stützstellen des
Helligkeitsprofils gehen nach bv_probe.json; die Seite rechnet dasselbe Bild in JavaScript und muss dieselbe Zeile und
dieselbe Konfidenz finden. pruefe_seite.mjs vergleicht.

Zusätzlich wird geprüft, dass der Block in bv_referenz.py Zeichen für Zeichen noch im Programm steht.
Aufruf: python3 pruefe_bildauswertung.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import cv2

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import bv_referenz as B

PROGRAMM = Path("/workspace/Wasserstandsregelung_Bild_6.py")

ZEILEN, SPALTEN = 300, 40          # Größe des Prüfbildes
KANTE = 110                        # Zeile, ab der „Wasser“ steht
HELL, DUNKEL = 205, 55             # Graustufen Luft / Wasser
REFLEX_VON, REFLEX_BIS = 5, 9      # Spalten des Spiegelstreifens
REFLEX = 235
RAUSCHEN = 12                      # Spanne des Rauschens in Graustufen
SAAT = 12345


def pruefbild() -> np.ndarray:
    """Das Prüfbild als BGR-Bild mit R = G = B, damit cvtColor genau den Grauwert liefert (0,299+0,587+0,114 = 1).
    Die Reihenfolge der Zufallszahlen ist zeilenweise, dann spaltenweise — die JavaScript-Fassung macht es genauso."""
    s = SAAT
    bild = np.empty((ZEILEN, SPALTEN, 3), np.uint8)
    for i in range(ZEILEN):
        for j in range(SPALTEN):
            s = (s * 48271) % 2147483647
            v = s / 2147483647.0
            grund = REFLEX if REFLEX_VON <= j < REFLEX_BIS else (HELL if i < KANTE else DUNKEL)
            w = int(min(255, max(0, round(grund + RAUSCHEN * (v - 0.5)))))
            bild[i, j] = (w, w, w)
    return bild


def wortgleich() -> bool:
    """bv_referenz.py trägt einen Block aus dem Programm. Steht er dort noch genauso?"""
    quelle = PROGRAMM.read_text(encoding="utf-8")
    ref = (H / "bv_referenz.py").read_text(encoding="utf-8")
    a = ref.index("--- Beginn wörtlicher Block")
    a = ref.index("\n", a) + 1
    b = ref.index("# --- Ende wörtlicher Block ---")
    return ref[a:b].strip() in quelle


def main() -> int:
    bild = pruefbild()
    B.roi[:] = [0, 0, SPALTEN, ZEILEN]
    aus = bild
    zeile, konf = B._suche_helligkeit(aus)
    # Zwischenstufen mitschreiben, damit ein Unterschied in der Seite lokalisierbar ist
    grau = cv2.cvtColor(aus, cv2.COLOR_BGR2GRAY)
    grau_b = cv2.GaussianBlur(grau, (1, 31), 0)
    prof = grau_b.mean(axis=1).astype(np.float32)
    prof5 = np.convolve(prof, np.ones(5) / 5.0, mode="same")
    grad = np.gradient(prof5)
    n = len(prof5)
    P = {
        "bild": {"zeilen": ZEILEN, "spalten": SPALTEN, "kante": KANTE, "hell": HELL, "dunkel": DUNKEL,
                 "reflex_von": REFLEX_VON, "reflex_bis": REFLEX_BIS, "reflex": REFLEX, "rauschen": RAUSCHEN, "saat": SAAT,
                 "generator": "s = 48271*s mod 2147483647, zeilenweise, v = s/2147483647, Wert = round(grund + rauschen*(v-0.5))"},
        "einstellung": {"hell_schwelle": B.hell_schwelle, "such_anteil": 0.85, "glaettung_zeilen": 5, "gauss": [1, 31]},
        "ergebnis": {"zeile": int(zeile), "konfidenz": round(float(konf), 6),
                     "min_gradient": round(float(grad[:int(n * 0.85)].min()), 6),
                     "hell_range": round(float(prof5.max() - prof5.min()), 6)},
        "profil_stuetzstellen": {str(i): round(float(prof5[i]), 4) for i in range(0, ZEILEN, 20)},
        "gradient_stuetzstellen": {str(i): round(float(grad[i]), 6) for i in range(0, ZEILEN, 20)},
        "bv_referenz_wortgleich_mit_programm": wortgleich(),
    }
    (H / "bv_probe.json").write_text(json.dumps(P, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Prüfbild {ZEILEN}×{SPALTEN}, Kante bei Zeile {KANTE}")
    print(f"  gefunden: Zeile {zeile}, Konfidenz {konf:.6f}, min. Gradient {P['ergebnis']['min_gradient']}, Spanne {P['ergebnis']['hell_range']}")
    print(f"  bv_referenz.py wortgleich mit dem Programm: {P['bv_referenz_wortgleich_mit_programm']}")
    return 0 if P["bv_referenz_wortgleich_mit_programm"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
