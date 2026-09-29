#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Schneidet die Bildauswertung (Globale, pixel_zu_mm, _suche_helligkeit, _suche_wasserlinie_canny, _suche_wasserlinie_farbe,
bv_verarbeite) wörtlich aus Wasserstandsregelung_Bild_6.py nach bv_referenz.py. Aufruf: python3 erstelle_bv_referenz.py"""
from pathlib import Path
H = Path(__file__).resolve().parent
PROGRAMM = Path("/workspace/Wasserstandsregelung_Bild_6.py")
src = PROGRAMM.read_text(encoding="utf-8").splitlines()
def zeile(muster):
    for i, z in enumerate(src):
        if z.startswith(muster): return i
    raise SystemExit("nicht gefunden: " + muster)
a = zeile("roi = [50, 30, 590, 450]"); d = zeile("# Kamera-Anzeige (40 ms Loop)") - 2
kopf = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Referenz der Bildauswertung: die Zeilen {a+1}–{d+1} aus Wasserstandsregelung_Bild_6.py, WÖRTLICH herausgeschnitten
(erzeugt von erstelle_bv_referenz.py, nicht von Hand ändern). Damit läuft dieselbe Erkennung ohne Kamera, EasyPort und
Oberfläche auf beliebigen Bildern — als Maßstab für die JavaScript-Fassung der Seite (pruefe_bildauswertung.py).
Prüfung der Wörtlichkeit: pruefe_bildauswertung.py vergleicht diesen Block Zeichen für Zeichen mit dem Programm."""
import threading
import numpy as np
import cv2

# --- Beginn wörtlicher Block (Programmzeilen {a+1}–{d+1}) ---
'''
(H / "bv_referenz.py").write_text(kopf + "\n".join(src[a:d + 1]) + "\n# --- Ende wörtlicher Block ---\n", encoding="utf-8")
print(f"bv_referenz.py: Programmzeilen {a+1}–{d+1}")
