#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Streckenmodell der Füllstandsregelung aus der gemessenen Sprungantwort (25.06.2026, Pumpe 100 %, 50 → 200 mm).

Rechnet — wie das Messwerkzeug Sprungantwort_3.py — ein PT1-Glied mit Totzeit an die Messung, dazu zwei Vergleichsmodelle
(reiner Integrator, Behälter mit Torricelli-Abfluss), leitet daraus die Behältergleichung ab, schließt den Kreis mit dem
PI-Regler des Programms (Kp = 1 %/mm, Ki = 0,05 %/(mm·s), Zyklus 0,5 s, Anti-Windup) und simuliert ihn mit genau dem
Algorithmus des Programms. Alle Zahlen gehen nach streckenmodell.json; Manuskript und Seite lesen nur von dort.
Bilder: ../Bilder/sprungantwort_fit.png, ../Bilder/kreis_simulation.png.   Aufruf: python3 streckenmodell.py
"""
from __future__ import annotations
import csv, json, math
from pathlib import Path
import numpy as np
from scipy.optimize import curve_fit, least_squares
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

H = Path(__file__).resolve().parent
DATEN = H.parent / "Daten" / "sprungantwort_2026-06-25.csv"
BILDER = H.parent / "Bilder"

# Zahlen des Programms Wasserstandsregelung_Bild_6.py (nur hier eingetragen, mit Zeile im Programm)
PROGRAMM = {
    "kp": 1.0, "ki": 0.05,               # entry_kp / entry_ki Voreinstellung
    "soll": 150.0,                        # entry_soll Voreinstellung
    "zyklus_s": 0.5,                      # root.after(500, regulation)
    "dt_min": 0.001, "dt_max": 2.0,       # dt = max(0.001, min(dt, 2.0))
    "u_min": 0.0, "u_max": 100.0,         # Anti-Windup-Grenzen, pump_set begrenzt 0..100
    "sprung_reset_mm": 1.0,               # |soll − soll_prev| > 1.0 → integral = 0
    "sensor_null_mm": 50.0, "sensor_spanne_mm": 220.0, "sensor_roh_max": 32760,   # level_mm(): 50 + raw·220/32760
    "pumpe_roh_max": 32760,               # pump_set: round(percent·32760/100)
}


def pt1(t, K, T, Td, y0):
    y = np.full_like(t, y0, dtype=float); m = t > Td
    y[m] = y0 + K * (1.0 - np.exp(-(t[m] - Td) / T)); return y


def integrator(t, a, Td, y0):
    y = np.full_like(t, y0, dtype=float); m = t > Td; y[m] = y0 + a * (t[m] - Td); return y


def torricelli(par, t, y0):
    a, c, Td, hb = par; y = np.empty_like(t); y[0] = y0
    for i in range(1, len(t)):
        d = (a - c * math.sqrt(max(y[i - 1] - hb, 0.0))) if t[i] > Td else 0.0
        y[i] = y[i - 1] + d * (t[i] - t[i - 1])
    return y


def sensor(h: float) -> float:
    """Ultraschallsensor über EasyPort: 16-Bit-Rohwert 0..32760 → 50..270 mm, genau wie level_mm()."""
    P = PROGRAMM; roh = round((h - P["sensor_null_mm"]) / P["sensor_spanne_mm"] * P["sensor_roh_max"])
    roh = max(0, min(P["sensor_roh_max"], roh)); return P["sensor_null_mm"] + roh * P["sensor_spanne_mm"] / P["sensor_roh_max"]


def simuliere(M: dict, soll_verlauf, stoerung, t_ende: float, h_start: float, dt_strecke: float = 0.1, integral_start: float = 0.0):
    """Der Kreis mit dem Algorithmus von regulation(): Zyklus 0,5 s, PI mit Anti-Windup, Integral-Reset bei Sollsprung.
    Strecke: T·dh/dt = K_u·u(t − Td) − (h − h0) − T·q_v(t)  (q_v: Störabfluss in mm/s), Euler mit dt_strecke."""
    P = PROGRAMM; K_u, T, Td, h0 = M["K_u"], M["T"], M["Td"], M["h0"]
    n_tot = int(round(Td / dt_strecke)); puffer = [0.0] * (n_tot + 1)
    n_zyk = int(round(P["zyklus_s"] / dt_strecke))
    h = h_start; integral = integral_start; soll_prev = None; u = 0.0; t = 0.0
    aus = {"t": [], "h": [], "u": [], "soll": [], "mess": [], "integral": []}
    k = 0
    while t <= t_ende + 1e-9:
        if k % n_zyk == 0:                                    # regulation()
            dt = P["zyklus_s"]; ist = sensor(h); soll = soll_verlauf(t)
            if soll_prev is not None and abs(soll - soll_prev) > P["sprung_reset_mm"]: integral = 0.0
            soll_prev = soll
            error = soll - ist; integral += error * dt
            output = P["kp"] * error + P["ki"] * integral
            if output > P["u_max"]: integral -= (output - P["u_max"]) / P["ki"]; output = P["u_max"]
            elif output < P["u_min"]: integral -= output / P["ki"]; output = P["u_min"]
            u = round(output * P["pumpe_roh_max"] / 100.0) * 100.0 / P["pumpe_roh_max"]   # pump_set: 16-Bit-Rohwert
            aus["t"].append(round(t, 3)); aus["h"].append(h); aus["u"].append(u); aus["soll"].append(soll); aus["mess"].append(ist); aus["integral"].append(integral)
        puffer.append(u); u_verz = puffer.pop(0)
        dh = (K_u * u_verz - (h - h0)) / T - stoerung(t)
        h = max(h0 - 0.0, h + dh * dt_strecke)
        t += dt_strecke; k += 1
    return aus


def kennwerte(aus, soll_neu, t_ab=0.0, band=2.0):
    t = np.array(aus["t"]); h = np.array(aus["mess"]); m = t >= t_ab
    tt, hh = t[m], h[m]
    ueber = float(max(0.0, hh.max() - soll_neu)); rest = float(abs(hh[-1] - soll_neu))
    ausserhalb = np.where(np.abs(hh - soll_neu) > band)[0]
    t_ein = float(tt[ausserhalb[-1] + 1] - t_ab) if len(ausserhalb) and ausserhalb[-1] + 1 < len(tt) else 0.0
    return {"ueberschwingen_mm": round(ueber, 2), "bleibende_abweichung_mm": round(rest, 3), "einschwingzeit_s": round(t_ein, 1)}


def main() -> int:
    r = list(csv.DictReader(open(DATEN, encoding="utf-8")))
    t = np.array([float(x["Zeit_s"]) for x in r]); h = np.array([float(x["Fuellstand_mm"]) for x in r])
    y0 = h[0]; td0 = float(t[np.argmax(h > y0 + 0.5)])
    p, cov = curve_fit(pt1, t, h, p0=[h[-1] - y0, 5.0, td0, y0], maxfev=20000); sig = np.sqrt(np.diag(cov))
    K, T, Td, y0f = (float(v) for v in p); rms_pt1 = float(np.sqrt(((h - pt1(t, *p)) ** 2).mean()))
    p2, _ = curve_fit(integrator, t, h, p0=[3.0, td0, y0]); rms_int = float(np.sqrt(((h - integrator(t, *p2)) ** 2).mean()))
    ls = least_squares(lambda q: torricelli(q, t, y0) - h, [5.0, 0.2, td0, 0.0], bounds=([0, 0, 0, -200], [20, 5, 10, 50]))
    rms_tor = float(np.sqrt((ls.fun ** 2).mean()))
    K_u = K / 100.0                                  # mm je % Pumpe
    P = PROGRAMM
    # geschlossener Kreis ohne Totzeit: T s² + (1 + K_u Kp) s + K_u Ki = 0
    a2, a1, a0 = T, 1.0 + K_u * P["kp"], K_u * P["ki"]
    wn = math.sqrt(a0 / a2); zeta = a1 / (2.0 * math.sqrt(a2 * a0)); disc = a1 * a1 - 4 * a2 * a0
    if disc < 0: pole = [(-a1 / (2 * a2), math.sqrt(-disc) / (2 * a2)), (-a1 / (2 * a2), -math.sqrt(-disc) / (2 * a2))]
    else: pole = [((-a1 + math.sqrt(disc)) / (2 * a2), 0.0), ((-a1 - math.sqrt(disc)) / (2 * a2), 0.0)]
    # Totzeit als Padé 1. Ordnung: e^{-Td s} ≈ (1 − Td s/2)/(1 + Td s/2) → kubisches Polynom
    # (T s² + (1+K_u Kp) s + K_u Ki)(1 + Td s/2) − K_u (Kp s + Ki)(… ) — hier numerisch über die Wurzeln
    # offener Kreis L(s) = K_u (Kp s + Ki) e^{-Td s} / (s (T s + 1)); Kreis: s(Ts+1)(1+Td s/2) + K_u(Kp s+Ki)(1−Td s/2) = 0
    c3 = T * Td / 2; c2 = T + Td / 2 - K_u * P["kp"] * Td / 2; c1 = 1 + K_u * P["kp"] - K_u * P["ki"] * Td / 2; c0 = K_u * P["ki"]
    wurz = np.roots([c3, c2, c1, c0]); pole_pade = [(float(w.real), float(w.imag)) for w in wurz]
    # Stabilitätsreserve: Phasenreserve numerisch am Durchtritt
    w = np.logspace(-4, 1, 20000); s = 1j * w
    L = K_u * (P["kp"] * s + P["ki"]) * np.exp(-Td * s) / (s * (T * s + 1)); mag = np.abs(L)
    i = int(np.argmin(np.abs(mag - 1.0))); w_d = float(w[i]); phase = float(np.degrees(np.angle(L[i]))); phasenreserve = 180.0 + phase
    # Verstärkungsreserve: Frequenz mit Phase −180°
    ph = np.degrees(np.unwrap(np.angle(L))); j = np.where(np.diff(np.sign(ph + 180.0)) != 0)[0]
    amplitudenreserve = float(1.0 / mag[j[0]]) if len(j) else float("inf")
    M = {"K": K, "T": T, "Td": Td, "h0": y0f, "K_u": K_u}
    # Referenzsimulation 1: Sollsprung 150 → 200 mm aus dem eingeschwungenen Zustand; 2: Störung Ablassventil q_v = 2 mm/s bei t = 0
    ruhe = simuliere(M, lambda tt: 150.0, lambda tt: 0.0, 600.0, y0f)
    h_ruhe = ruhe["h"][-1]; i_ruhe = ruhe["integral"][-1]
    sprung = simuliere(M, lambda tt: 200.0 if tt >= 0.0 else 150.0, lambda tt: 0.0, 300.0, h_ruhe, integral_start=i_ruhe)
    q_v = 1.0
    stoer = simuliere(M, lambda tt: 150.0, lambda tt: q_v if tt >= 0.0 else 0.0, 300.0, h_ruhe, integral_start=i_ruhe)
    ks = kennwerte(sprung, 200.0); kst = kennwerte(stoer, 150.0)
    kst["groesste_abweichung_mm"] = round(float(150.0 - min(stoer["mess"])), 2)
    stuetz = {str(int(tt)): round(hh, 3) for tt, hh in zip(sprung["t"], sprung["mess"]) if abs(tt - round(tt)) < 1e-6 and int(tt) % 10 == 0}
    stuetz_st = {str(int(tt)): round(hh, 3) for tt, hh in zip(stoer["t"], stoer["mess"]) if abs(tt - round(tt)) < 1e-6 and int(tt) % 10 == 0}
    J = {
        "quelle": {"datei": DATEN.name, "messung": "Sprungantwort 25.06.2026, Pumpe 0 → 100 % bei t = 0, Abbruch bei 200 mm",
                   "punkte": len(t), "abtastung_s": round(float(np.diff(t).mean()), 4), "dauer_s": round(float(t[-1]), 2),
                   "start_mm": round(float(h[0]), 2), "ende_mm": round(float(h[-1]), 2)},
        "programm": PROGRAMM,
        "pt1": {"K_mm_bei_100": round(K, 2), "T_s": round(T, 2), "Td_s": round(Td, 3), "h0_mm": round(y0f, 2), "rms_mm": round(rms_pt1, 2),
                "sigma": {"K": round(float(sig[0]), 2), "T": round(float(sig[1]), 2), "Td": round(float(sig[2]), 3), "h0": round(float(sig[3]), 2)},
                "K_u_mm_je_prozent": round(K_u, 4), "anfangssteigung_mm_je_s": round(K / T, 3)},
        "integrator": {"a_mm_je_s": round(float(p2[0]), 3), "Td_s": round(float(p2[1]), 2), "rms_mm": round(rms_int, 2)},
        "torricelli": {"a_mm_je_s": round(float(ls.x[0]), 3), "c": round(float(ls.x[1]), 4), "Td_s": round(float(ls.x[2]), 2), "hb_mm": round(float(ls.x[3]), 1), "rms_mm": round(rms_tor, 2)},
        "behaelter": {"tau_s": round(T, 2), "abfluss_beiwert_1_je_s": round(1.0 / T, 5), "zufluss_mm_je_s_je_prozent": round(K_u / T, 5)},
        "kreis": {"kp": P["kp"], "ki": P["ki"], "polynom": [round(a2, 3), round(a1, 4), round(a0, 5)], "omega_n_rad_s": round(wn, 5), "daempfung": round(zeta, 4),
                  "pole": [[round(a, 5), round(b, 5)] for a, b in pole], "periode_s": round(2 * math.pi / (wn * math.sqrt(max(1e-12, 1 - zeta * zeta))), 1) if zeta < 1 else None,
                  "pole_mit_totzeit_pade": [[round(a, 5), round(b, 5)] for a, b in pole_pade],
                  "durchtritt_rad_s": round(w_d, 5), "phasenreserve_grad": round(phasenreserve, 1), "amplitudenreserve": round(amplitudenreserve, 1)},
        "simulation": {"dt_strecke_s": 0.1, "ruhe_150_mm": round(h_ruhe, 3), "u_ruhe_prozent": round(ruhe["u"][-1], 3), "integral_ruhe": round(i_ruhe, 3),
                       "sprung_150_200": {**ks, "stuetzstellen_mm": stuetz},
                       "stoerung_qv_1mm_s": {**kst, "q_v_mm_je_s": q_v, "stuetzstellen_mm": stuetz_st}},
    }
    (H / "streckenmodell.json").write_text(json.dumps(J, indent=1, ensure_ascii=False), encoding="utf-8")
    BILDER.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.plot(t, h, ".", ms=3, color="#2b4c7e", label="Messung 25.06.2026 (Ultraschallsensor über EasyPort, 0,12 s)")
    tt = np.linspace(0, t[-1], 600)
    ax.plot(tt, pt1(tt, *p), "-", color="#b0171f", lw=1.8, label=f"PT1 mit Totzeit: K = {K:.1f} mm, T = {T:.1f} s, Td = {Td:.2f} s  (RMS {rms_pt1:.1f} mm)")
    ax.plot(tt, integrator(tt, *p2), "--", color="#666", lw=1.2, label=f"reiner Integrator (RMS {rms_int:.1f} mm)")
    ax.axvline(Td, color="#b06a00", ls=":", lw=1.2); ax.text(Td + 0.4, 195, f"Td = {Td:.2f} s", color="#b06a00", fontsize=9)
    ax.set_xlabel("Zeit t in s"); ax.set_ylabel("Füllstand h in mm"); ax.grid(alpha=0.3); ax.legend(fontsize=8.5, loc="lower right")
    ax.set_title("Sprungantwort der Strecke: Pumpe 0 → 100 %, Abbruch bei 200 mm", fontsize=11)
    fig.tight_layout(); fig.savefig(BILDER / "sprungantwort_fit.png", dpi=160); plt.close(fig)
    fig, (a1_, a2_) = plt.subplots(2, 1, figsize=(8.0, 6.2), sharex=True)
    for aus, farbe, name in ((sprung, "#2b4c7e", "Sollsprung 150 → 200 mm"), (stoer, "#b0171f", f"Störung: Ablassventil, q_v = {q_v:g} mm/s")):
        a1_.plot(aus["t"], aus["mess"], color=farbe, lw=1.6, label=name); a2_.plot(aus["t"], aus["u"], color=farbe, lw=1.4)
    a1_.plot(sprung["t"], sprung["soll"], ":", color="#2b4c7e", lw=1); a1_.plot(stoer["t"], stoer["soll"], ":", color="#b0171f", lw=1)
    a1_.set_ylabel("Füllstand in mm"); a1_.grid(alpha=0.3); a1_.legend(fontsize=9)
    a1_.set_title(f"Der geschlossene Kreis mit dem Programm-Regler (Kp = {P['kp']:g} %/mm, Ki = {P['ki']:g} %/(mm·s), Zyklus {P['zyklus_s']:g} s)", fontsize=10.5)
    a2_.set_ylabel("Pumpe in %"); a2_.set_xlabel("Zeit t in s"); a2_.grid(alpha=0.3); a2_.set_ylim(-3, 103)
    fig.tight_layout(); fig.savefig(BILDER / "kreis_simulation.png", dpi=160); plt.close(fig)
    print(f"PT1: K = {K:.1f} mm, T = {T:.2f} s, Td = {Td:.3f} s, h0 = {y0f:.2f} mm, RMS {rms_pt1:.2f} mm (Integrator {rms_int:.2f}, Torricelli {rms_tor:.2f})")
    print(f"Kreis: ω_n = {wn:.4f} rad/s, ζ = {zeta:.3f}, Pole {pole}, Padé {pole_pade}, φ_R = {phasenreserve:.1f}°, A_R = {amplitudenreserve:.1f}")
    print(f"Ruhe bei 150 mm: u = {ruhe['u'][-1]:.2f} %; Sprung: {ks}; Störung: {kst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
