#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nachrechnung.py — der zweite, unabhängige Weg zu den Kennwerten des geschlossenen Kreises.

streckenmodell.py simuliert den Kreis Schritt für Schritt mit genau dem Algorithmus des Programms (Abtastung 0,5 s,
Totzeit, Anti-Windup, 16-Bit-Quantisierung). Dieses Blatt rechnet dieselben Größen auf dem anderen Weg: geschlossen im
Laplace-Bereich, ohne Abtastung, ohne Totzeit, ohne Stellgrößenbegrenzung — mit Formeln, die auf Papier nachvollziehbar
sind. Wo beide Wege auseinandergehen, ist der Unterschied die Wirkung genau dieser drei Dinge; er wird beziffert.

Alles kommt aus streckenmodell.json (K_u, T, Td, Kp, Ki); nichts wird hier neu angepasst.
Ergebnis: nachrechnung.json.   Aufruf: python3 nachrechnung.py
"""
from __future__ import annotations
import csv, json, math
from functools import reduce
from math import gcd
from pathlib import Path

H = Path(__file__).resolve().parent
J = json.loads((H / "streckenmodell.json").read_text(encoding="utf-8"))

K_u = J["pt1"]["K_u_mm_je_prozent"]      # mm je % Pumpe
T   = J["pt1"]["T_s"]                     # s
Td  = J["pt1"]["Td_s"]                    # s
h0  = J["pt1"]["h0_mm"]                   # mm
Kp  = J["programm"]["kp"]                 # %/mm
Ki  = J["programm"]["ki"]                 # %/(mm·s)


def main() -> int:
    # --- 1. Arbeitspunkt: im Beharrungszustand fließt so viel zu wie ab -----------------------------------------
    # 0 = K_u·u − (h − h0)  →  u = (h − h0)/K_u
    h_soll = J["programm"]["soll"]
    u_ruhe = (h_soll - h0) / K_u

    # --- 2. Kennkreisgleichung: T s² + (1 + K_u Kp) s + K_u Ki = 0 ---------------------------------------------
    a2, a1, a0 = T, 1.0 + K_u * Kp, K_u * Ki
    sigma = a1 / (2.0 * a2)                       # Abklingrate
    wn    = math.sqrt(a0 / a2)                    # Kennkreisfrequenz
    zeta  = a1 / (2.0 * math.sqrt(a2 * a0))       # Dämpfung
    wd    = wn * math.sqrt(1.0 - zeta * zeta)     # gedämpfte Kreisfrequenz

    # --- 3. Sollsprung: Führungsübertragungsfunktion T_w(s) = K_u(Kp s + Ki)/(T s² + a1 s + a0) -----------------
    # y(t)/Δw = 1 − e^{−σt}(cos ω_d t − B sin ω_d t) mit B = (g − σ)/ω_d,  g = K_u Kp / T
    # (aus y(0) = 0 und y'(0) = Δw·g; die Nullstelle bei s = −Ki/Kp steckt allein in g)
    g = K_u * Kp / T
    B = (g - sigma) / wd
    # Maximum: y'(t) = 0  →  tan(ω_d t) = −g/(ω_d − σB)
    kos, sin_ = g, wd - sigma * B
    wt = math.atan2(-kos, sin_)
    if wt < 0: wt += math.pi
    t_max = wt / wd
    y_max = 1.0 - math.exp(-sigma * t_max) * (math.cos(wt) - B * math.sin(wt))
    dw = 50.0                                     # der Sollsprung 150 → 200 mm der Referenzsimulation
    ueber_analytisch = (y_max - 1.0) * dw
    # bleibende Abweichung: T_w(0) = K_u Ki / (K_u Ki) = 1 exakt → 0 mm (I-Anteil im Regler)
    rest_analytisch = 0.0

    # --- 4. Störsprung Ablassventil: Δh(s) = −q_v/(s² + 2σ s + ω_n²) ------------------------------------------
    # Δh(t) = −(q_v/ω_d) e^{−σt} sin ω_d t ;  Größtwert bei tan(ω_d t) = ω_d/σ
    q_v = J["simulation"]["stoerung_qv_1mm_s"]["q_v_mm_je_s"]
    wt_s = math.atan2(wd, sigma)
    t_st = wt_s / wd
    tief_analytisch = (q_v / wd) * math.exp(-sigma * t_st) * math.sin(wt_s)

    # --- 5. Auflösung der Rückführung: was die Messreihe über den Wandler verrät --------------------------------
    # level_mm() rechnet mit der vollen Spanne 0 … 32760. Ob der Wandler wirklich so fein auflöst, steht in den Messwerten:
    # die Rohwerte werden zurückgerechnet und ihr größter gemeinsamer Schritt gesucht.
    stufe_mm = J["programm"]["sensor_spanne_mm"] / J["programm"]["sensor_roh_max"]
    hh = [float(z["Fuellstand_mm"]) for z in csv.DictReader(open(H.parent / "Daten" / J["quelle"]["datei"], encoding="utf-8"))]
    roh = [round((x - J["programm"]["sensor_null_mm"]) / J["programm"]["sensor_spanne_mm"] * J["programm"]["sensor_roh_max"]) for x in hh]
    schritte = sorted({abs(b - a) for a, b in zip(roh, roh[1:]) if b != a})
    teiler = reduce(gcd, schritte)
    reste = sorted({x % teiler for x in roh})
    stufen = J["programm"]["sensor_roh_max"] // teiler

    # --- 6. Vergleich mit der Schritt-für-Schritt-Simulation ---------------------------------------------------
    S = J["simulation"]
    sp, st = S["sprung_150_200"], S["stoerung_qv_1mm_s"]
    N = {
        "was": "geschlossene Rechnung im Laplace-Bereich, ohne Abtastung, ohne Totzeit, ohne Stellgrößenbegrenzung",
        "eingang": {"K_u_mm_je_prozent": K_u, "T_s": T, "Td_s": Td, "h0_mm": h0, "kp": Kp, "ki": Ki},
        "arbeitspunkt": {"h_mm": h_soll, "u_ruhe_prozent": round(u_ruhe, 3),
                         "u_ruhe_simuliert_prozent": S["u_ruhe_prozent"],
                         "unterschied_prozentpunkte": round(abs(u_ruhe - S["u_ruhe_prozent"]), 3)},
        "kennkreis": {"polynom": [round(a2, 3), round(a1, 4), round(a0, 5)], "sigma_1_je_s": round(sigma, 6),
                      "omega_n_rad_s": round(wn, 5), "daempfung": round(zeta, 4), "omega_d_rad_s": round(wd, 6),
                      "periode_s": round(2 * math.pi / wd, 1),
                      "gleich_wie_streckenmodell": abs(wn - J["kreis"]["omega_n_rad_s"]) < 5e-5 and abs(zeta - J["kreis"]["daempfung"]) < 5e-4},
        "sollsprung_50mm": {"B": round(B, 5), "t_max_s": round(t_max, 1), "ueberschwingen_mm": round(ueber_analytisch, 2),
                            "ueberschwingen_prozent": round((y_max - 1.0) * 100.0, 2),
                            "ueberschwingen_simuliert_mm": sp["ueberschwingen_mm"],
                            "unterschied_mm": round(ueber_analytisch - sp["ueberschwingen_mm"], 2),
                            "grund": "in der Simulation läuft die Pumpe am Anfang in die Begrenzung 100 % — der lineare Weg kennt keine Begrenzung und schwingt darum weiter über",
                            "bleibende_abweichung_mm": rest_analytisch,
                            "bleibende_abweichung_simuliert_mm": sp["bleibende_abweichung_mm"]},
        "stoersprung": {"q_v_mm_je_s": q_v, "t_tiefstwert_s": round(t_st, 1),
                        "groesste_abweichung_mm": round(tief_analytisch, 2),
                        "groesste_abweichung_simuliert_mm": st["groesste_abweichung_mm"],
                        "unterschied_mm": round(st["groesste_abweichung_mm"] - tief_analytisch, 2),
                        "grund": "Totzeit 1,25 s und Abtastung 0,5 s wirken wie zusätzliche Verzögerung; der Regler greift später ein"},
        "aufloesung": {"rechenstufe_mm": round(stufe_mm, 5), "pumpenstufe_prozent": round(100.0 / J["programm"]["pumpe_roh_max"], 6),
                       "gemessener_teiler_einheiten": teiler, "gemessene_stufe_mm": round(teiler * stufe_mm, 5),
                       "stufenzahl": stufen, "bit": round(math.log2(stufen + 1), 2), "reste_mod_teiler": reste,
                       "versatz_mm": round(reste[0] * stufe_mm, 5), "punkte": len(roh),
                       "befund": f"alle {len(roh)} Rohwerte sind Vielfache von {teiler} plus {reste[0]}: der Wandler liefert {stufen} Stufen ({round(math.log2(stufen+1))} Bit), nicht {J['programm']['sensor_roh_max']}"},
    }
    (H / "nachrechnung.json").write_text(json.dumps(N, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Arbeitspunkt  u = {u_ruhe:.3f} %   (simuliert {S['u_ruhe_prozent']:.3f} %)")
    print(f"Kennkreis     ω_n = {wn:.5f} rad/s, ζ = {zeta:.4f}, σ = {sigma:.6f} 1/s, ω_d = {wd:.6f} rad/s, Periode {2*math.pi/wd:.1f} s")
    print(f"Sollsprung    Überschwingen analytisch {ueber_analytisch:.2f} mm bei t = {t_max:.1f} s  (simuliert {sp['ueberschwingen_mm']:.2f} mm)")
    print(f"Auflösung     Rohwerte in Schritten von {teiler} (Rest {reste}): {teiler*stufe_mm:.4f} mm je Stufe, {stufen} Stufen = {math.log2(stufen+1):.0f} Bit")
    print(f"Störsprung    größte Abweichung analytisch {tief_analytisch:.2f} mm bei t = {t_st:.1f} s  (simuliert {st['groesste_abweichung_mm']:.2f} mm)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
