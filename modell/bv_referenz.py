#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Referenz der Bildauswertung: die Zeilen 327–508 aus Wasserstandsregelung_Bild_6.py, WÖRTLICH herausgeschnitten
(erzeugt von erstelle_bv_referenz.py, nicht von Hand ändern). Damit läuft dieselbe Erkennung ohne Kamera, EasyPort und
Oberfläche auf beliebigen Bildern — als Maßstab für die JavaScript-Fassung der Seite (pruefe_bildauswertung.py).
Prüfung der Wörtlichkeit: pruefe_bildauswertung.py vergleicht diesen Block Zeichen für Zeichen mit dem Programm."""
import threading
import numpy as np
import cv2

# --- Beginn wörtlicher Block (Programmzeilen 327–508) ---
roi = [50, 30, 590, 450]   # [x1, y1, x2, y2] im Originalbild – per Maus ändern

canny_t1  = 30
canny_t2  = 80
blur_kern = 5

# Farbfilter HSV
hsv_h_lo = 10;  hsv_h_hi = 30
hsv_s_lo = 40
hsv_v_lo = 40

# Helligkeitsschwelle (Methode "helligkeit"):
# Wasser ist dunkler als Luft → Übergang hell→dunkel von oben = Wasserlinie
hell_schwelle = 30   # Mindest-Helligkeitsabfall zwischen Luft und Wasser

# Erkennungsmethode: "helligkeit" | "canny" | "farbe"
bv_methode = "helligkeit"

kalib_punkte  = []
kalib_gueltig = False

GLAETT_N  = 12
bv_puffer = []

bv_lock    = threading.Lock()
bv_pixel_y = None
bv_mm      = None
bv_konf    = 0.0

# Stabilität: Schwelle und Hold-Logik
konf_schwelle  = 0.05   # per Schieberegler einstellbar (0..0.5)
HOLD_MAX       = 10     # so viele Zyklen wird der letzte gültige Wert gehalten
bv_hold_count  = 0      # Zähler wie lange schon gehalten wird

roi_ziehen = False
roi_start  = (0, 0)


def pixel_zu_mm(py):
    if not kalib_gueltig or len(kalib_punkte) < 2:
        return None
    (p1, m1), (p2, m2) = kalib_punkte[0], kalib_punkte[1]
    if p1 == p2:
        return None
    return m1 + (py - p1) * (m2 - m1) / (p2 - p1)


def _suche_helligkeit(ausschnitt):
    """
    Hauptmethode für trübes Wasser in transparentem Behälter.

    Idee: Zeilenmittelwert der Helligkeit von oben nach unten.
    Luft über dem Wasser ist heller als das trübe Wasser.
    Die erste Zeile, bei der die Helligkeit deutlich abfällt,
    ist die Wasserlinie.

    Gibt (zeile_im_roi, konfidenz) zurück.
    """
    grau = cv2.cvtColor(ausschnitt, cv2.COLOR_BGR2GRAY)
    # Starken Blur → Reflexionen und Rauschen unterdrücken
    grau = cv2.GaussianBlur(grau, (1, 31), 0)

    # Mittlere Helligkeit pro Zeile
    hell_profil = grau.mean(axis=1).astype(np.float32)

    # Gleitender Mittelwert über 5 Zeilen für noch mehr Glättung
    kernel = np.ones(5) / 5.0
    hell_profil = np.convolve(hell_profil, kernel, mode='same')

    n = len(hell_profil)
    if n < 10:
        return None, 0.0

    # Ableitung (Gradient): negative Werte = Helligkeitsabfall nach unten
    grad = np.gradient(hell_profil)

    # Suche den stärksten negativen Gradienten (hell→dunkel Übergang)
    # nur im oberen 80% der ROI suchen (unterer Teil = Boden/Tisch)
    such_bis = int(n * 0.85)
    grad_such = grad[:such_bis]

    min_grad = grad_such.min()
    if min_grad > -hell_schwelle * 0.3:
        # Kein deutlicher Übergang gefunden
        return None, 0.0

    beste = int(np.argmin(grad_such))
    # Konfidenz: wie stark ist der Abfall relativ zum Helligkeitsbereich
    hell_range = float(hell_profil.max() - hell_profil.min())
    if hell_range < 5:
        return None, 0.0
    konf = min(1.0, abs(min_grad) / (hell_range * 0.3))

    return beste, konf


def _suche_wasserlinie_canny(ausschnitt, roi_breite):
    """Canny – bewertet horizontal durchgehende Kanten."""
    k    = blur_kern if blur_kern % 2 == 1 else blur_kern + 1
    grau = cv2.cvtColor(ausschnitt, cv2.COLOR_BGR2GRAY)
    grau = cv2.GaussianBlur(grau, (k, k), 0)
    kanten = cv2.Canny(grau, canny_t1, canny_t2)

    zeilen_anteil = kanten.sum(axis=1).astype(np.float32) / (255.0 * roi_breite)
    kandidaten    = np.where(zeilen_anteil > 0.06)[0]

    if len(kandidaten) == 0:
        return None, 0.0

    beste = kandidaten[np.argmax(zeilen_anteil[kandidaten])]
    return int(beste), min(1.0, float(zeilen_anteil[beste]) / 0.4)


def _suche_wasserlinie_farbe(ausschnitt):
    """HSV-Farbfilter – Oberkante der farbigen Wassermaske."""
    hsv   = cv2.cvtColor(ausschnitt, cv2.COLOR_BGR2HSV)
    maske = cv2.inRange(hsv,
                        (hsv_h_lo, hsv_s_lo, hsv_v_lo),
                        (hsv_h_hi, 255, 220))
    kern  = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
    maske = cv2.morphologyEx(maske, cv2.MORPH_CLOSE, kern)

    zeilen_summe = maske.sum(axis=1).astype(np.float32)
    roi_breite   = ausschnitt.shape[1]
    mindest      = 0.12 * 255 * roi_breite
    kandidaten   = np.where(zeilen_summe > mindest)[0]

    if len(kandidaten) == 0:
        return None, 0.0

    beste = int(kandidaten.min())
    konf  = min(1.0, float(zeilen_summe[beste]) / (255.0 * roi_breite * 0.5))
    return beste, konf


def bv_verarbeite(frame_orig):
    global bv_puffer, bv_pixel_y, bv_mm, bv_konf, bv_hold_count
    x1, y1, x2, y2 = roi
    h, w = frame_orig.shape[:2]
    x1c, x2c = max(0, x1), min(x2, w)
    y1c, y2c = max(0, y1), min(y2, h)
    if x2c - x1c < 10 or y2c - y1c < 10:
        return

    ausschnitt = frame_orig[y1c:y2c, x1c:x2c]
    roi_breite = x2c - x1c

    if bv_methode == "farbe":
        beste_roi, konfidenz = _suche_wasserlinie_farbe(ausschnitt)
    elif bv_methode == "canny":
        beste_roi, konfidenz = _suche_wasserlinie_canny(ausschnitt, roi_breite)
    else:
        beste_roi, konfidenz = _suche_helligkeit(ausschnitt)

    if beste_roi is None or konfidenz < konf_schwelle:
        # Kein gültiger Wert – Hold-Logik: letzten Wert behalten
        if bv_pixel_y is not None:
            bv_hold_count += 1
            if bv_hold_count > HOLD_MAX:
                # Zu lange kein Signal → Linie ausblenden
                bv_pixel_y = None
                bv_mm      = None
                bv_konf    = 0.0
            # sonst: bv_pixel_y bleibt unverändert erhalten
        return

    # Gültiger Wert → Hold zurücksetzen
    bv_hold_count = 0

    beste_orig = y1c + beste_roi

    bv_puffer.append(beste_orig)
    if len(bv_puffer) > GLAETT_N:
        bv_puffer.pop(0)
    geglättet = int(np.mean(bv_puffer))

    mm_wert = pixel_zu_mm(geglättet)

    bv_pixel_y = geglättet
    bv_mm      = mm_wert
    bv_konf    = konfidenz

# --- Ende wörtlicher Block ---
