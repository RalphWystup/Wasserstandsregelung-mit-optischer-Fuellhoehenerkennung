#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""erstelle_bilder.py — die gezeichneten Bilder des Manuskripts „Wasserstandsregelung mit optischer Füllhöhenerkennung“.

Erzeugt in Bilder/:
  aufbau_schnittstellen.png    der Aufbau mit den realen Schnittstellen: Anlage, EasyPort (USB, ASCII-Register), PC-Programm, ESP32-CAM (WLAN, MJPEG)
  regelkreis_laplace.png       der geschlossene Kreis im Laplace-Bereich mit dem PI-Regler und der Strecke aus der Sprungantwort
  bildauswertung_ablauf.png    die Bildauswertung Schritt für Schritt (Methode „Helligkeit“) mit Profil und Gradient an einem Rechenbild
Zahlen kommen aus ../Modell/streckenmodell.json. Kastentexte werden nur verkleinert, wenn sie nicht hineinpassen (dann gemeldet).
Jedes Bild wird nach dem Bau angesehen.  Aufruf: python3 Bilder/erstelle_bilder.py
"""
import json, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

H = Path(__file__).resolve().parent
J = json.loads((H.parent / "Modell" / "streckenmodell.json").read_text(encoding="utf-8"))
N = json.loads((H.parent / "Modell" / "nachrechnung.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(H.parent / "Modell"))
BLAU, ROT, GRUEN, ORANGE, GRAU = "#2b4c7e", "#b0171f", "#2e7d32", "#b06a00", "#666666"
VERKLEINERT = []


def kasten(ax, x, y, w, h, titel, zeilen=(), farbe=BLAU, fuellung="#eef2fa", ts=10.5, zs=9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.15", lw=1.6, ec=farbe, fc=fuellung))
    if not zeilen:
        ax.text(x + w / 2, y + h / 2, titel, ha="center", va="center", fontsize=ts, fontweight="bold", color=farbe); return
    t1 = ax.text(x + w / 2, y + h - 0.16, titel, ha="center", va="top", fontsize=ts, fontweight="bold", color=farbe)
    t2 = ax.text(x + w / 2, y + h / 2, "\n".join(zeilen), ha="center", va="center", fontsize=zs, linespacing=1.3)
    r = ax.figure.canvas.get_renderer(); inv = ax.transData.inverted()
    def mass(t):
        bb = t.get_window_extent(renderer=r); (x0, y0), (x1, y1) = inv.transform([[bb.x0, bb.y0], [bb.x1, bb.y1]]); return x1 - x0, y1 - y0
    n = 0
    for _ in range(30):
        w1, h1 = mass(t1); w2, h2 = mass(t2)
        if w1 <= w - 0.25 and w2 <= w - 0.25 and h1 + h2 <= h - 0.4: break
        t1.set_fontsize(t1.get_fontsize() - 0.25); t2.set_fontsize(t2.get_fontsize() - 0.25); n += 1
    if n: VERKLEINERT.append(f"{titel.splitlines()[0]}: Schrift auf {t2.get_fontsize():.1f} pt")
    w1, h1 = mass(t1); t2.set_position((x + w / 2, y + (h - h1 - 0.16) / 2))


def pfeil(ax, p0, p1, text="", farbe="#222", lage="oben", ts=8.5, dx=0.0, dy=0.0, stil="-|>"):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=stil, mutation_scale=13, lw=1.4, color=farbe, shrinkA=0, shrinkB=0))
    if text:
        xm, ym = (p0[0] + p1[0]) / 2 + dx, (p0[1] + p1[1]) / 2 + dy
        va = {"oben": "bottom", "unten": "top", "mitte": "center"}[lage]; off = {"oben": 0.08, "unten": -0.08, "mitte": 0}[lage]
        ax.text(xm, ym + off, text, ha="center", va=va, fontsize=ts, color=farbe, bbox=dict(fc="white", ec="none", pad=1.0))


def aufbau():
    """Anlage links, EasyPort in der Mitte, PC rechts. Die Spalten stehen so weit auseinander, dass die
    Pfeilbeschriftungen („24 V-Klemmen“, „ist (EW1.2)“, „u (AW1.2)“) in den Zwischenraum passen und keinen Kasten berühren."""
    fig, ax = plt.subplots(figsize=(12.4, 6.6)); ax.set_xlim(0, 24); ax.set_ylim(0, 13.2); ax.axis("off")
    ax.text(12, 12.9, "Der Aufbau mit den realen Schnittstellen: Anlage — EasyPort — PC-Programm — ESP32-CAM", ha="center", va="top", fontsize=12.5, fontweight="bold")
    # Anlage
    ax.add_patch(FancyBboxPatch((0.4, 0.6), 7.4, 11.0, boxstyle="round,pad=0.02", lw=1.2, ec="#888", fc="#fafafa", ls="--"))
    ax.text(0.7, 11.2, "Füllstandsanlage", fontsize=10.0, color="#444", va="top")
    kasten(ax, 0.9, 7.4, 3.1, 3.2, "Behälter", ["Füllstand h in mm", "Ablauf zurück\nin den Vorratsbehälter"], farbe=BLAU)
    kasten(ax, 4.3, 7.4, 3.4, 3.2, "Ultraschallsensor", ["Analogwert → EW1.2", "Wort 0 … 32760", "h = 50 + roh·220/32760 mm", "Bereich 50 … 270 mm", ("gemessen: %.4f mm je Stufe" % N["aufloesung"]["gemessene_stufe_mm"]).replace(".", ","), "(%d Bit, nicht 16)" % round(N["aufloesung"]["bit"])], farbe=GRUEN, fuellung="#eef7ee")
    kasten(ax, 0.9, 4.0, 3.1, 3.0, "Pumpe", ["Stellgrad u in %", "AW1.2 = round(u·32760/100)", "Freigabe: AW1.0 |= 0x000C"], farbe=ROT, fuellung="#fbeeee")
    kasten(ax, 4.3, 4.0, 3.2, 3.0, "Ablassventil (Störung)", ["AW1.0 Bit 0", "1 = offen, 0 = zu", "Abfluss q_v (nicht gemessen)"], farbe=ORANGE, fuellung="#fdf3e6")
    kasten(ax, 0.9, 0.9, 6.6, 2.6, "weitere Sensoren (nur Anzeige)", ["Durchfluss EW1.4 → 0 … 10 V   ·   Druck EW1.6 → 0 … 10 V", "Schwimmerschalter unten / oben: EW1.0 Bit 3 / Bit 4"], farbe=GRAU, fuellung="#f2f2f2")
    # EasyPort
    kasten(ax, 9.0, 5.2, 3.6, 3.4, "EasyPort", ["USB → serielle Schnittstelle", "115200 Bd, 8N1", "ASCII-Register:", "lesen  „D<reg>\\r“ → „<reg>=hhhh“", "schreiben  „M<reg>=hhhh\\r“"], farbe=BLAU)
    pfeil(ax, (7.9, 6.9), (9.0, 6.9), "", stil="<|-|>")
    ax.text(8.45, 7.15, "24 V-\nKlemmen", ha="center", va="bottom", fontsize=7.5, color="#444", linespacing=1.2)
    # PC
    ax.add_patch(FancyBboxPatch((14.9, 0.6), 8.7, 11.0, boxstyle="round,pad=0.02", lw=1.2, ec="#888", fc="#fafafa", ls="--"))
    ax.text(15.2, 11.2, "PC-Programm  (Python, Tkinter, OpenCV)", fontsize=10.0, color="#444", va="top")
    P = J["programm"]
    kasten(ax, 15.3, 7.3, 7.9, 3.4, "PI-Regler  (Zyklus %g s)" % P["zyklus_s"], ["e = soll − ist   ·   I += e·dt", f"u = Kp·e + Ki·I   (Kp = {P['kp']:g} %/mm, Ki = {P['ki']:g} %/(mm·s))", "Anti-Windup: u auf 0 … 100 %, I zurückgerechnet", "Sollsprung > 1 mm → I = 0"], farbe=ROT, fuellung="#fbeeee")
    kasten(ax, 15.3, 3.6, 7.9, 3.3, "Bildauswertung", ["greift nicht in die Regelung ein, nur Anzeige", "ROI → Grau → Gauß (1×31) → Zeilenmittel → Mittel über 5", "Gradient → stärkster Abfall hell→dunkel = Wasserlinie", "Konfidenz, Halten (10 Bilder), Mittel über 12, 2-Punkt-Kalibrierung"], farbe=GRUEN, fuellung="#eef7ee")
    kasten(ax, 15.3, 0.9, 7.9, 2.4, "Oberfläche", ["Sollwert, Kp, Ki, Regler EIN/AUS, Ventil,", "Messwerte, Verläufe (300 Punkte)", "Kamerabild 480×360 mit ROI, Linie, Methode, Kalibrierung"], farbe=GRAU, fuellung="#f2f2f2")
    pfeil(ax, (12.6, 8.2), (15.3, 8.2), "ist (EW1.2)", lage="oben")
    pfeil(ax, (15.3, 7.5), (12.6, 7.5), "u (AW1.2)", lage="unten")
    # Kamera: der Blick auf den Behälter steht im Kasten selbst, damit keine Linie die Anlagenkästen kreuzt
    kasten(ax, 9.0, 0.9, 3.6, 3.4, "ESP32-CAM", ["blickt von außen auf den", "Behälter der Anlage", "WLAN", "MJPEG-Strom  http://…:81/stream", "Weißabgleich  http://…/control"], farbe=GRUEN, fuellung="#eef7ee")
    pfeil(ax, (12.6, 2.6), (15.3, 4.4), "JPEG-Bilder", lage="oben", dx=-0.3, dy=0.1)
    fig.savefig(H / "aufbau_schnittstellen.png", dpi=150, bbox_inches="tight"); plt.close(fig)


def regelkreis():
    M, K, P = J["pt1"], J["kreis"], J["programm"]
    fig, ax = plt.subplots(figsize=(11, 4.9)); ax.set_xlim(0, 22); ax.set_ylim(-0.9, 9.2); ax.axis("off")
    ax.text(11, 8.9, "Der geschlossene Kreis im Laplace-Bereich (Strecke aus der Sprungantwort vom 25.06.2026)", ha="center", va="top", fontsize=12.5, fontweight="bold")
    ax.add_patch(plt.Circle((3.2, 5.0), 0.42, ec="#222", fc="white", lw=1.4)); ax.text(3.2, 5.0, "Σ", ha="center", va="center", fontsize=12)
    ax.text(2.62, 5.48, "+", fontsize=11); ax.text(3.4, 4.2, "−", fontsize=12)
    pfeil(ax, (0.5, 5.0), (2.78, 5.0), "w(s) = Sollwert in mm", lage="oben", ts=8.0, dx=-0.62)
    kasten(ax, 4.6, 3.9, 4.6, 2.3, "PI-Regler (Programm)", [f"C(s) = Kp + Ki/s", f"Kp = {P['kp']:g} %/mm,  Ki = {P['ki']:g} %/(mm·s)", f"Zyklus {P['zyklus_s']:g} s, u = 0 … 100 %"], farbe=ROT, fuellung="#fbeeee")
    pfeil(ax, (3.62, 5.0), (4.6, 5.0), "e", lage="oben")
    kasten(ax, 10.3, 3.9, 3.3, 2.3, "Totzeit", [f"e^(−Td s)", f"Td = {M['Td_s']:.2f} s"], farbe=GRAU, fuellung="#f2f2f2")
    pfeil(ax, (9.2, 5.0), (10.3, 5.0), "u in %", lage="oben")
    kasten(ax, 14.7, 3.9, 5.2, 2.3, "Strecke: Behälter mit Pumpe", [f"G(s) = K_u/(T s + 1)", f"K_u = {M['K_u_mm_je_prozent']:.4f} mm/%,  T = {M['T_s']:.1f} s"], farbe=BLAU)
    pfeil(ax, (13.6, 5.0), (14.7, 5.0))
    pfeil(ax, (19.9, 5.0), (21.6, 5.0), "h in mm", lage="oben")
    # Störung
    ax.add_patch(plt.Circle((14.15, 5.0), 0.0, ec="none"));
    ax.text(16.6, 7.6, "Störung: Ablassventil q_v(s) (nicht gemessen, in der Simulation einstellbar)", ha="center", fontsize=8.5, color=ORANGE)
    pfeil(ax, (17.3, 7.3), (17.3, 6.2), "", farbe=ORANGE)
    # Rückführung
    ax.plot([20.8, 20.8, 3.2, 3.2], [5.0, 1.6, 1.6, 4.58], color="#222", lw=1.4)
    ax.add_patch(FancyArrowPatch((3.2, 1.9), (3.2, 4.58), arrowstyle="-|>", mutation_scale=13, lw=1.4, color="#222"))
    kasten(ax, 7.6, 0.7, 6.0, 1.8, "Ultraschallsensor über EasyPort", ["gemessen: %.4f mm je Stufe (%d Bit), Zyklus 0,5 s" % (N["aufloesung"]["gemessene_stufe_mm"], round(N["aufloesung"]["bit"]))], farbe=GRUEN, fuellung="#eef7ee", ts=9.5, zs=8.5)
    ax.text(20.3, 2.6, f"Kreis: T s² + (1 + K_u Kp) s + K_u Ki = 0\nω_n = {K['omega_n_rad_s']:.4f} rad/s, ζ = {K['daempfung']:.2f}\nPhasenreserve {K['phasenreserve_grad']:.0f}°, Amplitudenreserve {K['amplitudenreserve']:.0f}", ha="right", va="bottom", fontsize=8.5, color=BLAU, bbox=dict(fc="white", ec=BLAU, pad=3))
    ax.text(0.3, -0.55, "parallel, nur Anzeige: Kamera → Bildauswertung → h_Kamera in mm (2-Punkt-Kalibrierung); die Regelung nutzt allein den Ultraschallsensor", fontsize=8.5, color=GRUEN, ha="left", va="bottom")
    fig.savefig(H / "regelkreis_laplace.png", dpi=150, bbox_inches="tight"); plt.close(fig)


def bildauswertung():
    """Rechenbild: heller Hintergrund, Behälter mit Luft (hell) über trübem Wasser (dunkel), Reflex; dann die Schritte der Methode „Helligkeit“."""
    import cv2, bv_referenz as B
    rng = np.random.default_rng(3)
    img = np.full((480, 640, 3), 205, np.uint8)
    cv2.rectangle(img, (150, 40), (490, 460), (150, 150, 150), 2)                      # Glasrand
    img[42:458, 152:488] = (215, 215, 210)                                              # Luft im Glas (hell)
    y_w = 262
    img[y_w:458, 152:488] = (35, 55, 85)                                                 # trübes Wasser BGR (bräunlich); der Helligkeitssprung Luft→Wasser (214 → 62 Graustufen)
    #   muss den Gradienten nach dem Gauß (1×31) unter die Schwelle −0,3·30 = −9 drücken; gerechnet: −10,9 (bei Grauwert 88 wären es −8,9 und die Methode fände nichts
    img[y_w:y_w + 4, 152:488] = (120, 140, 170)                                         # heller Meniskus
    cv2.rectangle(img, (200, 60), (215, 440), (235, 235, 235), -1)                      # Reflexstreifen
    img = np.clip(img.astype(np.int16) + rng.normal(0, 4, img.shape).astype(np.int16), 0, 255).astype(np.uint8)
    B.roi[:] = [150, 40, 490, 460]
    x1, y1, x2, y2 = B.roi; aus = img[y1:y2, x1:x2]
    grau = cv2.cvtColor(aus, cv2.COLOR_BGR2GRAY); grau_b = cv2.GaussianBlur(grau, (1, 31), 0)
    prof = grau_b.mean(axis=1).astype(np.float32); prof5 = np.convolve(prof, np.ones(5) / 5.0, mode="same"); grad = np.gradient(prof5)
    n = len(prof5); such_bis = int(n * 0.85); beste = int(np.argmin(grad[:such_bis]))
    zeile, konf = B._suche_helligkeit(aus)
    assert zeile == beste, ("die Methode des Programms findet die gezeichnete Linie nicht", zeile, beste)
    fig, axs = plt.subplots(1, 3, figsize=(11, 5.0), gridspec_kw={"width_ratios": [1.25, 1, 1]})
    axs[0].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)); axs[0].add_patch(plt.Rectangle((x1, y1), x2 - x1, y2 - y1, ec="#2e7d32", fc="none", lw=1.5))
    axs[0].axhline(y1 + zeile, color="#00dddd", lw=2); axs[0].set_title("1 Rechenbild mit ROI (grün) und gefundener Linie (cyan)", fontsize=9.5); axs[0].axis("off")
    ys = np.arange(n)
    axs[1].plot(prof, ys, color="#bbb", lw=1, label="Zeilenmittel nach Gauß (1×31)"); axs[1].plot(prof5, ys, color=BLAU, lw=1.6, label="… und Mittel über 5 Zeilen")
    axs[1].invert_yaxis(); axs[1].set_xlabel("Helligkeit"); axs[1].set_ylabel("Zeile im ROI"); axs[1].legend(fontsize=7.5, loc="center left"); axs[1].grid(alpha=0.3)
    axs[1].set_title("2 Helligkeitsprofil von oben nach unten", fontsize=9.5)
    axs[2].plot(grad, ys, color=ROT, lw=1.4); axs[2].invert_yaxis(); axs[2].axhline(beste, color="#00aaaa", lw=1.2, ls="--")
    axs[2].axvline(-B.hell_schwelle * 0.3, color=ORANGE, ls=":", lw=1.2); axs[2].text(-B.hell_schwelle * 0.3 + 0.3, n * 0.05, f"Schwelle −0,3·{B.hell_schwelle} = {-B.hell_schwelle*0.3:g}", fontsize=7.5, color=ORANGE, rotation=90, va="top")
    axs[2].axhspan(such_bis, n, color="#eee"); axs[2].text(grad.min() * 0.95, such_bis + 12, "untere 15 %: nicht durchsucht", fontsize=7.5, color="#666")
    axs[2].set_xlabel("Gradient je Zeile"); axs[2].grid(alpha=0.3); axs[2].set_title(f"3 stärkster Abfall: Zeile {beste}, Konfidenz {konf:.2f}", fontsize=9.0)
    fig.suptitle("Die Bildauswertung nach der Methode „Helligkeit“ (Programmfunktion _suche_helligkeit, wörtlich)", fontsize=11, fontweight="bold")
    fig.tight_layout(); fig.savefig(H / "bildauswertung_ablauf.png", dpi=150); plt.close(fig)
    return {"zeile": zeile, "konf": round(float(konf), 3), "wasserlinie_gezeichnet": y_w - y1}


def main() -> int:
    aufbau(); regelkreis(); e = bildauswertung()
    print("Bilder: aufbau_schnittstellen, regelkreis_laplace, bildauswertung_ablauf", e)
    for v in VERKLEINERT: print("  verkleinert:", v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
