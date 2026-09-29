#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""erstelle_wasserstand_seite.py — die Seite „Wasserstandsregelung mit optischer Füllhöhenerkennung“
(Fassung aus der Datei VERSION; die Nummer steht nur dort).

Die Seite ist eigenständig und läuft offline — ohne Anlage, ohne EasyPort, ohne Kamera, ohne Netzzugang:

  * Ein gezeichneter Behälter mit Wasser bildet das Kamerabild nach (480 × 360, dieselbe Größe wie im Programm).
    Schieber für Beleuchtung, Rauschen und Spiegelung.
  * Darauf läuft dieselbe Bildauswertung wie in Wasserstandsregelung_Bild_6.py, Zeile für Zeile nach JavaScript
    übertragen: Graustufen mit der OpenCV-Gewichtung, Gauß (1 × 31), Zeilenmittel, Mittel über 5 Zeilen, Gradient,
    Suche im oberen 85-%-Bereich, Schwelle −0,3·Empfindlichkeit, Konfidenz, Halten, Mittel über 12 Bilder,
    Zweipunktkalibrierung. Dazu die Methoden „Farbfilter (HSV)“ (ebenfalls wörtlich übertragen) und „Canny“
    (nachgebildet: Gauß, Sobel, Nicht-Maximum-Unterdrückung, Hysterese).
  * Derselbe Regler: PI mit Anti-Windup, Zyklus 0,5 s, Integral-Reset bei Sollsprung über 1 mm, 16-Bit-Stellwert.
  * Dieselbe Strecke: T·dh/dt = K_u·u(t−Td) − (h−h0) − T·q_v mit den aus der Messung vom 25.06.2026 bestimmten
    Kennwerten (aus ../Modell/streckenmodell.json, nichts davon steht doppelt).
  * Laufende Verläufe h(t) und u(t) (300 Punkte wie MAX_POINTS im Programm).
  * Zwei Versuche ohne Warten (Sollsprung, Störung) mit dem Vergleich zur Python-Rechnung.
  * Eine Probe der Bildauswertung gegen bv_probe.json: dasselbe Prüfbild, dieselbe Zeile, dieselbe Konfidenz.
  * Das Manuskript als Reiter „Dokumentation“.

window.LABOR trägt alle Ergebnisse für pruefe_seite.mjs.
Aufruf: python3 Seite/erstelle_wasserstand_seite.py   →   Seite/Wasserstand_<VERSION>.html
"""
from __future__ import annotations
import base64, json, re, subprocess
from pathlib import Path

H = Path(__file__).resolve().parent
P = H.parent
VERSION = (H / "VERSION").read_text(encoding="utf-8").strip()
DATUM = "29.09.2026"
NAMENSNENNUNG = "Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic)"
ZIEL = H / f"Wasserstand_{VERSION}.html"

# Eine Regel je Ersetzung, nur in der Kopie für die Seite (der Arbeitsbereich bleibt unverändert).
# Es geht allein um die Heimnetzadresse der Kamera; Kennwörter und Netznamen kommen in diesem Projekt nicht vor.
NEUTRAL = [(r"\b192\.168\.\d{1,3}\.\d{1,3}\b", "<IP-der-Kamera>")]
if (H / "neutral_privat.json").is_file():      # falls je etwas Privates hinzukommt: steht dort, nicht hier
    NEUTRAL += [(m, e) for m, e in json.loads((H / "neutral_privat.json").read_text(encoding="utf-8"))]


def neutral(text: str) -> str:
    for m, e in NEUTRAL:
        text = re.sub(m, e, text)
    return text


def daten_uri(pfad: Path) -> str:
    typ = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}[pfad.suffix.lower().lstrip(".")]
    return f"data:{typ};base64," + base64.b64encode(pfad.read_bytes()).decode()


def dokument_html(pfad: Path) -> str:
    md = neutral(pfad.read_text(encoding="utf-8"))
    kopf = re.match(r"---\n(.*?)\n---\n", md, re.S)
    md = md[kopf.end():] if kopf else md
    html = subprocess.run(["pandoc", "-f", "markdown", "-t", "html", "--mathml"],
                          input=md, capture_output=True, text=True, check=True).stdout
    for bild in sorted((P / "Bilder").glob("*.png")):
        html = html.replace(f'src="Bilder/{bild.name}"', f'src="{daten_uri(bild)}"')
    return html


STIL = """
:root{--grund:#fbfbfa;--text:#1d2025;--leise:#5d6470;--linie:#d6d9de;--blau:#2b4c7e;--rot:#b0171f;--gruen:#2e7d32;--orange:#b06a00;--feld:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--grund);color:var(--text);font:15px/1.55 system-ui,"Segoe UI",Roboto,sans-serif}
header{background:#22314a;color:#fff;padding:14px 20px}
header h1{margin:0;font-size:1.25rem;font-weight:650}
header .fassung{font-size:.85rem;opacity:.85;margin-top:3px}
nav{display:flex;gap:2px;background:#182238;padding:0 14px}
nav button{background:none;border:0;color:#cbd4e4;padding:9px 16px;font:inherit;font-size:.92rem;cursor:pointer;border-bottom:3px solid transparent}
nav button[aria-selected=true]{color:#fff;border-bottom-color:#7fa8e8;background:#22314a}
main{padding:14px 20px 40px;max-width:1500px;margin:0 auto}
.reihe{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start}
.karte{background:var(--feld);border:1px solid var(--linie);border-radius:8px;padding:12px 14px;margin:0 0 14px}
.karte h2{margin:0 0 8px;font-size:1rem;color:var(--blau)}
.karte h3{margin:10px 0 4px;font-size:.88rem;color:var(--leise);font-weight:650;text-transform:none}
canvas{display:block;background:#000;border-radius:5px;max-width:100%}
.knopf{font:inherit;font-size:.9rem;padding:7px 13px;border:1px solid var(--linie);border-radius:6px;background:#f2f4f7;cursor:pointer;margin:0 6px 6px 0}
.knopf:hover{background:#e6eaf0}
.knopf.an{background:var(--gruen);border-color:var(--gruen);color:#fff}
.knopf.warn{background:var(--rot);border-color:var(--rot);color:#fff}
.knopf.gewaehlt{background:var(--blau);border-color:var(--blau);color:#fff}
.schieber{display:grid;grid-template-columns:132px 1fr 76px;gap:6px;align-items:center;margin:3px 0;font-size:.86rem}
.schieber input[type=range]{width:100%}
.schieber .wert{text-align:right;font-variant-numeric:tabular-nums;color:var(--leise)}
.werte{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));gap:7px;margin-top:8px}
.wertfeld{background:#f5f7fa;border:1px solid var(--linie);border-radius:6px;padding:6px 9px}
.wertfeld .name{font-size:.72rem;color:var(--leise);text-transform:uppercase;letter-spacing:.03em}
.wertfeld .zahl{font-size:1.06rem;font-variant-numeric:tabular-nums;font-weight:600}
table{border-collapse:collapse;font-size:.85rem;margin:6px 0}
th,td{border:1px solid var(--linie);padding:4px 8px;text-align:left}
th{background:#f2f4f7;font-weight:620}
td.z{text-align:right;font-variant-numeric:tabular-nums}
.gut{color:var(--gruen);font-weight:620}.schlecht{color:var(--rot);font-weight:620}
.hinweis{font-size:.82rem;color:var(--leise);margin:6px 0 0}
.doku{background:var(--feld);border:1px solid var(--linie);border-radius:8px;padding:18px 26px;max-width:62em}
.doku img{max-width:100%;height:auto;border:1px solid var(--linie);border-radius:5px}
.doku table{font-size:.86rem}
.doku h1{font-size:1.5rem;color:var(--blau);border-bottom:2px solid var(--linie);padding-bottom:5px}
.doku h2{font-size:1.15rem;color:var(--blau);margin-top:1.6em}
.doku h3{font-size:1rem;margin-top:1.3em}
.doku code{background:#f2f4f7;padding:1px 4px;border-radius:3px;font-size:.9em}
.doku pre{background:#f2f4f7;padding:9px 11px;border-radius:5px;overflow-x:auto}
.doku blockquote{border-left:3px solid var(--blau);margin-left:0;padding-left:14px;color:var(--leise)}
[hidden]{display:none!important}
@media (max-width:760px){.schieber{grid-template-columns:104px 1fr 62px}main{padding:10px}}
"""

JS = r"""
// ====================================================================================================
//  Alle Zahlen kommen aus DATEN (streckenmodell.json, nachrechnung.json, bv_probe.json). Hier steht keine
//  zweite Fassung einer Zahl. Die Funktionsnamen sind die des Python-Programms, damit der Vergleich leichtfällt.
// ====================================================================================================
const M  = { K_u: DATEN.modell.pt1.K_u_mm_je_prozent, T: DATEN.modell.pt1.T_s, Td: DATEN.modell.pt1.Td_s, h0: DATEN.modell.pt1.h0_mm };
const PR = DATEN.modell.programm;                       // kp, ki, soll, zyklus_s, u_min, u_max, sensor_* …
const DT = DATEN.modell.simulation.dt_strecke_s;        // 0,1 s Schritt der Strecke

// ---------------------------------------------------------------------------- Rückführung: level_mm() des Programms
function sensor(h){
  let roh = Math.round((h - PR.sensor_null_mm) / PR.sensor_spanne_mm * PR.sensor_roh_max);
  roh = Math.max(0, Math.min(PR.sensor_roh_max, roh));
  return PR.sensor_null_mm + roh * PR.sensor_spanne_mm / PR.sensor_roh_max;
}

// ---------------------------------------------------------------------------- der Kreis: regulation() + Behälter
// Ein Zustand, den sowohl die laufende Anzeige als auch die Versuche ohne Warten benutzen.
function neuerKreis(h_start, integral_start, soll_start){
  const n_tot = Math.round(M.Td / DT);
  return { h: h_start, integral: integral_start, soll_prev: (soll_start===undefined?null:soll_start), u: 0,
           puffer: new Array(n_tot + 1).fill(0), t: 0, k: 0, mess: sensor(h_start), fehler: 0 };
}
// Ein Schritt von DT Sekunden. Alle n_zyk Schritte läuft der Regler — genau wie root.after(500, regulation).
function schritt(S, soll, q_v, regelt){
  const n_zyk = Math.round(PR.zyklus_s / DT);
  let neuerZyklus = false;
  if (S.k % n_zyk === 0){
    const dt = PR.zyklus_s;                                   // dt = max(0.001, min(dt, 2.0)) — hier immer 0,5 s
    const ist = sensor(S.h);
    if (S.soll_prev !== null && Math.abs(soll - S.soll_prev) > PR.sprung_reset_mm) S.integral = 0.0;
    S.soll_prev = soll;
    let output = 0.0;
    if (regelt){
      const error = soll - ist;
      S.integral += error * dt;
      output = PR.kp * error + PR.ki * S.integral;
      if (output > PR.u_max){ S.integral -= (output - PR.u_max) / PR.ki; output = PR.u_max; }
      else if (output < PR.u_min){ S.integral -= output / PR.ki; output = PR.u_min; }
      S.u = Math.round(output * PR.pumpe_roh_max / 100.0) * 100.0 / PR.pumpe_roh_max;   // pump_set: 16-Bit-Rohwert
    } else { S.u = 0.0; }
    S.mess = ist; S.fehler = soll - ist;
    neuerZyklus = true;
  }
  S.puffer.push(S.u);
  const u_verz = S.puffer.shift();
  const dh = (M.K_u * u_verz - (S.h - M.h0)) / M.T - q_v;
  S.h = Math.max(M.h0, S.h + dh * DT);
  S.t += DT; S.k += 1;
  return neuerZyklus;
}

// ====================================================================================================
//  Das gezeichnete Kamerabild: Behälter, Luft, trübes Wasser, Meniskus, Spiegelung, Rauschen
// ====================================================================================================
const BILD = { w: 480, h: 360 };
const GLAS = { x0: 140, x1: 340, y0: 20, y1: 330 };                 // Außenkante des Glases
const INNEN = { x0: 146, x1: 334, y0: 26, y1: 324 };                // Innenraum
const ROI = [INNEN.x0, INNEN.y0, INNEN.x1, INNEN.y1];               // der Auswertebereich
const SKALA = { h_unten: 50.0, h_oben: 270.0, y_unten: 318, y_oben: 36 };
// Die Methode durchsucht nur die oberen 85 % des ROI (such_bis = int(n·0,85)) — der untere Rand ist im Aufbau
// Behälterboden und Tisch. Damit ist ein Füllstand unterhalb dieser Grenze für die Kamera nicht auffindbar.
// Die Grenze wird hier aus der Zeichnung gerechnet, nicht angenommen.
function grenze_mm(){
  const n = ROI[3] - ROI[1], such_bis = Math.trunc(n * 0.85), y = ROI[1] + such_bis;
  return SKALA.h_unten + (SKALA.y_unten - y) * (SKALA.h_oben - SKALA.h_unten) / (SKALA.y_unten - SKALA.y_oben);
}
function y_von_h(h){ return SKALA.y_unten - (h - SKALA.h_unten) * (SKALA.y_unten - SKALA.y_oben) / (SKALA.h_oben - SKALA.h_unten); }
function mm_je_pixel(){ return (SKALA.h_oben - SKALA.h_unten) / (SKALA.y_unten - SKALA.y_oben); }

let saatBild = 7;
function zufall(){ saatBild = (saatBild * 48271) % 2147483647; return saatBild / 2147483647; }

function zeichneBehaelter(ctx, h_mm, bel, rausch, spiegel){
  const yw = y_von_h(h_mm);
  ctx.setTransform(1,0,0,1,0,0);
  // Hintergrund (Tisch)
  const g = ctx.createLinearGradient(0,0,0,BILD.h); g.addColorStop(0,'#9a9a97'); g.addColorStop(1,'#77777a');
  ctx.fillStyle = g; ctx.fillRect(0,0,BILD.w,BILD.h);
  // Glasrand
  ctx.fillStyle = '#b8bcc0'; ctx.fillRect(GLAS.x0, GLAS.y0, GLAS.x1-GLAS.x0, GLAS.y1-GLAS.y0);
  // Luft über dem Wasser (hell) — die Beleuchtung wirkt auf Luft und Wasser gleich
  const luft = [215,215,210].map(v => Math.min(255, Math.round(v*bel)));
  const wass = [ 85, 55, 35].map(v => Math.min(255, Math.round(v*bel)));
  ctx.fillStyle = `rgb(${luft[0]},${luft[1]},${luft[2]})`;
  ctx.fillRect(INNEN.x0, INNEN.y0, INNEN.x1-INNEN.x0, Math.max(0, yw-INNEN.y0));
  // trübes Wasser (dunkel)
  ctx.fillStyle = `rgb(${wass[0]},${wass[1]},${wass[2]})`;
  ctx.fillRect(INNEN.x0, Math.max(INNEN.y0, yw), INNEN.x1-INNEN.x0, Math.max(0, INNEN.y1-Math.max(INNEN.y0,yw)));
  // Meniskus: ein schmales helleres Band unmittelbar an der Oberfläche
  if (yw > INNEN.y0 && yw < INNEN.y1){
    ctx.fillStyle = `rgba(${Math.round(170*bel)},${Math.round(150*bel)},${Math.round(130*bel)},0.9)`;
    ctx.fillRect(INNEN.x0, yw, INNEN.x1-INNEN.x0, 3);
  }
  // Spiegelung: ein senkrechter Glanzstreifen über die ganze Höhe
  if (spiegel > 0.01){
    ctx.fillStyle = `rgba(255,255,255,${0.85*spiegel})`;
    ctx.fillRect(INNEN.x0+22, INNEN.y0+4, 11, INNEN.y1-INNEN.y0-8);
  }
  // Skalenstriche außen (nur Zierde, außerhalb des ROI)
  ctx.strokeStyle = '#3c4048'; ctx.lineWidth = 1; ctx.font = '10px system-ui'; ctx.fillStyle = '#2a2d33';
  for (let hm = 50; hm <= 270; hm += 50){
    const y = y_von_h(hm); ctx.beginPath(); ctx.moveTo(GLAS.x1+2, y); ctx.lineTo(GLAS.x1+11, y); ctx.stroke();
    ctx.fillText(hm + ' mm', GLAS.x1+14, y+3);
  }
  // Rauschen: zuletzt, über das ganze Bild — wie bei einer Kamera
  if (rausch > 0.01){
    const d = ctx.getImageData(0,0,BILD.w,BILD.h), a = d.data;
    for (let i = 0; i < a.length; i += 4){
      const r = Math.round(rausch * (zufall() - 0.5) * 2);
      a[i] = Math.min(255, Math.max(0, a[i]+r)); a[i+1] = Math.min(255, Math.max(0, a[i+1]+r)); a[i+2] = Math.min(255, Math.max(0, a[i+2]+r));
    }
    ctx.putImageData(d, 0, 0);
  }
}

// ====================================================================================================
//  Die Bildauswertung — Zeile für Zeile aus Wasserstandsregelung_Bild_6.py
// ====================================================================================================
// Einstellungen mit den Voreinstellungen des Programms
const BV = { methode:'helligkeit', hell_schwelle:30, konf_schwelle:0.05, HOLD_MAX:10, GLAETT_N:12,
             canny_t1:30, canny_t2:80, blur_kern:5, hsv_h_lo:10, hsv_h_hi:30, hsv_s_lo:40, hsv_v_lo:40,
             puffer:[], pixel_y:null, mm:null, konf:0.0, hold:0, kalib:[], kalib_gueltig:false };

// cv2.getGaussianKernel(n, 0): sigma = 0.3*((n-1)*0.5 - 1) + 0.8, Gewichte exp(−(i−m)²/2σ²), auf 1 normiert
function gaussKern(n){
  const sig = 0.3*((n-1)*0.5 - 1) + 0.8, m = (n-1)/2, k = new Float64Array(n); let s = 0;
  for (let i = 0; i < n; i++){ k[i] = Math.exp(-(i-m)*(i-m)/(2*sig*sig)); s += k[i]; }
  for (let i = 0; i < n; i++) k[i] /= s;
  return k;
}
const KERN31 = gaussKern(31);
// BORDER_REFLECT_101 (OpenCV-Voreinstellung): der Rand wird gespiegelt, ohne ihn zu wiederholen
function spiegel101(i, n){ while (i < 0 || i >= n){ if (i < 0) i = -i; if (i >= n) i = 2*n - 2 - i; } return i; }

// Graustufen mit der OpenCV-Gewichtung 0,299 R + 0,587 G + 0,114 B, gerundet wie cvtColor
function grauZeilenmittel(daten, breiteBild, x0, y0, x1, y1){
  const n = y1 - y0, b = x1 - x0, p = new Float64Array(n);
  for (let i = 0; i < n; i++){
    let s = 0;
    for (let j = 0; j < b; j++){
      const o = ((y0+i)*breiteBild + (x0+j))*4;
      s += Math.round(0.299*daten[o] + 0.587*daten[o+1] + 0.114*daten[o+2]);
    }
    p[i] = s / b;
  }
  return p;
}
// GaussianBlur(grau,(1,31)) wirkt nur in Spaltenrichtung; Glättung und Zeilenmittel sind beide linear und
// vertauschbar, darum wird zuerst gemittelt und dann geglättet (viel weniger Rechenarbeit, gleiches Ergebnis
// bis auf die Rundung auf ganze Graustufen in OpenCV — die Probe gegen bv_probe.json beziffert diesen Rest).
function gauss31(p){
  const n = p.length, q = new Float64Array(n);
  for (let i = 0; i < n; i++){ let s = 0; for (let j = 0; j < 31; j++) s += KERN31[j]*p[spiegel101(i+j-15, n)]; q[i] = s; }
  return q;
}
// np.convolve(p, ones(5)/5, mode='same'): volle Faltung, Rand mit Nullen, danach die mittleren n Werte
function mittel5(p){
  const n = p.length, q = new Float64Array(n);
  for (let i = 0; i < n; i++){ let s = 0; for (let k = 0; k < 5; k++){ const j = i + 2 - k; if (j >= 0 && j < n) s += p[j]; } q[i] = s/5; }
  return q;
}
// np.gradient: innen zentraler Differenzenquotient, an den Rändern einseitig
function gradient(p){
  const n = p.length, g = new Float64Array(n);
  if (n < 2) return g;
  g[0] = p[1]-p[0]; g[n-1] = p[n-1]-p[n-2];
  for (let i = 1; i < n-1; i++) g[i] = (p[i+1]-p[i-1])/2;
  return g;
}

// _suche_helligkeit(ausschnitt) → [zeile_im_roi, konfidenz]
function _suche_helligkeit(prof_roh){
  const hell_profil0 = gauss31(prof_roh);
  const hell_profil = mittel5(hell_profil0);
  const n = hell_profil.length;
  if (n < 10) return [null, 0.0, {}];
  const grad = gradient(hell_profil);
  const such_bis = Math.trunc(n * 0.85);
  let min_grad = Infinity, beste = 0;
  for (let i = 0; i < such_bis; i++) if (grad[i] < min_grad){ min_grad = grad[i]; beste = i; }
  const schwelle = -BV.hell_schwelle * 0.3;
  if (min_grad > schwelle) return [null, 0.0, {min_grad, schwelle}];
  let mx = -Infinity, mn = Infinity;
  for (let i = 0; i < n; i++){ if (hell_profil[i] > mx) mx = hell_profil[i]; if (hell_profil[i] < mn) mn = hell_profil[i]; }
  const hell_range = mx - mn;
  if (hell_range < 5) return [null, 0.0, {hell_range}];
  const konf = Math.min(1.0, Math.abs(min_grad) / (hell_range * 0.3));
  return [beste, konf, {min_grad, hell_range, schwelle, profil: hell_profil, grad}];
}

// _suche_wasserlinie_farbe(ausschnitt) → HSV-Maske, oberste hinreichend gefüllte Zeile
// OpenCV-HSV für 8 Bit: H = Farbton/2 (0…179), S = 255·(max−min)/max, V = max
function rgb2hsv(r,g,b){
  const mx = Math.max(r,g,b), mn = Math.min(r,g,b), d = mx - mn;
  let h = 0;
  if (d !== 0){
    if (mx === r) h = 60*(((g-b)/d) % 6); else if (mx === g) h = 60*((b-r)/d + 2); else h = 60*((r-g)/d + 4);
    if (h < 0) h += 360;
  }
  return [Math.round(h/2), mx === 0 ? 0 : Math.round(255*d/mx), mx];
}
function _suche_wasserlinie_farbe(daten, breiteBild, x0, y0, x1, y1){
  const n = y1-y0, b = x1-x0, mindest = 0.12*255*b;
  const summe = new Float64Array(n);
  for (let i = 0; i < n; i++){
    let s = 0;
    for (let j = 0; j < b; j++){
      const o = ((y0+i)*breiteBild + (x0+j))*4;
      const [hh,ss,vv] = rgb2hsv(daten[o], daten[o+1], daten[o+2]);
      if (hh >= BV.hsv_h_lo && hh <= BV.hsv_h_hi && ss >= BV.hsv_s_lo && vv >= BV.hsv_v_lo && vv <= 220) s += 255;
    }
    summe[i] = s;
  }
  // MORPH_CLOSE mit einem Rechteck 5×3 schließt Lücken; auf dem Zeilenprofil wirkt davon die Höhe 3:
  // eine einzelne leere Zeile zwischen zwei vollen wird gefüllt (Dilatation, dann Erosion, je 1 Zeile).
  const dil = new Float64Array(n), erz = new Float64Array(n);
  for (let i = 0; i < n; i++) dil[i] = Math.max(summe[Math.max(0,i-1)], summe[i], summe[Math.min(n-1,i+1)]);
  for (let i = 0; i < n; i++) erz[i] = Math.min(dil[Math.max(0,i-1)], dil[i], dil[Math.min(n-1,i+1)]);
  for (let i = 0; i < n; i++) if (erz[i] > mindest) return [i, Math.min(1.0, erz[i]/(255*b*0.5))];
  return [null, 0.0];
}

// _suche_wasserlinie_canny: hier nachgebildet (Gauß k×k, Sobel 3×3, Nicht-Maximum-Unterdrückung, Hysterese).
// Das ist der Standardablauf, den auch cv2.Canny geht; Bit für Bit gleich ist er nicht — so steht es im Prüfplan.
function _suche_wasserlinie_canny(daten, breiteBild, x0, y0, x1, y1){
  const n = y1-y0, b = x1-x0;
  let k = BV.blur_kern % 2 === 1 ? BV.blur_kern : BV.blur_kern + 1;
  const kern = gaussKern(k), m = (k-1)/2;
  const grau = new Float64Array(n*b);
  for (let i = 0; i < n; i++) for (let j = 0; j < b; j++){
    const o = ((y0+i)*breiteBild + (x0+j))*4;
    grau[i*b+j] = Math.round(0.299*daten[o] + 0.587*daten[o+1] + 0.114*daten[o+2]);
  }
  const t1 = new Float64Array(n*b), gl = new Float64Array(n*b);
  for (let i = 0; i < n; i++) for (let j = 0; j < b; j++){ let s = 0; for (let q = 0; q < k; q++) s += kern[q]*grau[i*b + spiegel101(j+q-m, b)]; t1[i*b+j] = s; }
  for (let i = 0; i < n; i++) for (let j = 0; j < b; j++){ let s = 0; for (let q = 0; q < k; q++) s += kern[q]*t1[spiegel101(i+q-m, n)*b + j]; gl[i*b+j] = s; }
  const mag = new Float64Array(n*b), ri = new Int8Array(n*b);
  const S = (i,j) => gl[spiegel101(i,n)*b + spiegel101(j,b)];
  for (let i = 0; i < n; i++) for (let j = 0; j < b; j++){
    const gx = (S(i-1,j+1)+2*S(i,j+1)+S(i+1,j+1)) - (S(i-1,j-1)+2*S(i,j-1)+S(i+1,j-1));
    const gy = (S(i+1,j-1)+2*S(i+1,j)+S(i+1,j+1)) - (S(i-1,j-1)+2*S(i-1,j)+S(i-1,j+1));
    mag[i*b+j] = Math.abs(gx) + Math.abs(gy);                       // L1 wie cv2.Canny ohne L2gradient
    const w = (Math.atan2(gy, gx) * 180/Math.PI + 180) % 180;
    ri[i*b+j] = w < 22.5 || w >= 157.5 ? 0 : (w < 67.5 ? 1 : (w < 112.5 ? 2 : 3));
  }
  const kante = new Uint8Array(n*b);
  const NACHBAR = [[0,-1,0,1],[-1,1,1,-1],[-1,0,1,0],[-1,-1,1,1]];
  for (let i = 1; i < n-1; i++) for (let j = 1; j < b-1; j++){
    const [a,c,d,e] = NACHBAR[ri[i*b+j]], v = mag[i*b+j];
    if (v >= mag[(i+a)*b+(j+c)] && v >= mag[(i+d)*b+(j+e)]) kante[i*b+j] = v >= BV.canny_t2 ? 2 : (v >= BV.canny_t1 ? 1 : 0);
  }
  let neu = true;
  while (neu){ neu = false;
    for (let i = 1; i < n-1; i++) for (let j = 1; j < b-1; j++) if (kante[i*b+j] === 1)
      for (let a = -1; a <= 1 && kante[i*b+j] === 1; a++) for (let c = -1; c <= 1; c++)
        if (kante[(i+a)*b+(j+c)] === 2){ kante[i*b+j] = 2; neu = true; break; }
  }
  let beste = null, bester = 0;
  for (let i = 0; i < n; i++){
    let z = 0; for (let j = 0; j < b; j++) if (kante[i*b+j] === 2) z++;
    const anteil = z / b;
    if (anteil > 0.06 && anteil > bester){ bester = anteil; beste = i; }
  }
  return beste === null ? [null, 0.0] : [beste, Math.min(1.0, bester/0.4)];
}

// pixel_zu_mm(py) — die Gerade durch die beiden Kalibrierpunkte
function pixel_zu_mm(py){
  if (!BV.kalib_gueltig || BV.kalib.length < 2) return null;
  const [p1,m1] = BV.kalib[0], [p2,m2] = BV.kalib[1];
  if (p1 === p2) return null;
  return m1 + (py - p1) * (m2 - m1) / (p2 - p1);
}

// bv_verarbeite(frame_orig): Annahme/Halten, Rückrechnung ins Bild, Mittel über 12, Umrechnung in mm
function bv_verarbeite(ctx){
  const [x1,y1,x2,y2] = ROI;
  if (x2-x1 < 10 || y2-y1 < 10) return;
  const d = ctx.getImageData(0,0,BILD.w,BILD.h).data;
  let beste_roi = null, konfidenz = 0.0, zusatz = {};
  if (BV.methode === 'farbe'){ [beste_roi, konfidenz] = _suche_wasserlinie_farbe(d, BILD.w, x1,y1,x2,y2); }
  else if (BV.methode === 'canny'){ [beste_roi, konfidenz] = _suche_wasserlinie_canny(d, BILD.w, x1,y1,x2,y2); }
  else { const prof = grauZeilenmittel(d, BILD.w, x1,y1,x2,y2); [beste_roi, konfidenz, zusatz] = _suche_helligkeit(prof); }
  BV.letztKonf = konfidenz; BV.letztZusatz = zusatz;
  if (beste_roi === null || konfidenz < BV.konf_schwelle){
    if (BV.pixel_y !== null){
      BV.hold += 1;
      if (BV.hold > BV.HOLD_MAX){ BV.pixel_y = null; BV.mm = null; BV.konf = 0.0; }
    }
    return;
  }
  BV.hold = 0;
  const beste_orig = y1 + beste_roi;
  BV.puffer.push(beste_orig);
  if (BV.puffer.length > BV.GLAETT_N) BV.puffer.shift();
  const geglaettet = Math.trunc(BV.puffer.reduce((a,b)=>a+b,0) / BV.puffer.length);   // int(np.mean(...))
  BV.pixel_y = geglaettet; BV.mm = pixel_zu_mm(geglaettet); BV.konf = konfidenz;
}

// ====================================================================================================
//  Probe gegen die Python-Fassung: dasselbe Prüfbild, dieselbe Zeile, dieselbe Konfidenz
// ====================================================================================================
function probeBild(){
  const B = DATEN.probe.bild;
  let s = B.saat; const p = new Float64Array(B.zeilen);
  for (let i = 0; i < B.zeilen; i++){
    let summe = 0;
    for (let j = 0; j < B.spalten; j++){
      s = (s * 48271) % 2147483647;
      const v = s / 2147483647;
      const grund = (j >= B.reflex_von && j < B.reflex_bis) ? B.reflex : (i < B.kante ? B.hell : B.dunkel);
      summe += Math.min(255, Math.max(0, Math.round(grund + B.rauschen*(v - 0.5))));
    }
    p[i] = summe / B.spalten;
  }
  return p;
}
function probeRechnen(){
  const alt = BV.hell_schwelle; BV.hell_schwelle = DATEN.probe.einstellung.hell_schwelle;
  const [zeile, konf, z] = _suche_helligkeit(probeBild());
  BV.hell_schwelle = alt;
  const py = DATEN.probe.ergebnis;
  return { zeile_js: zeile, konf_js: konf === null ? null : +konf.toFixed(6),
           zeile_py: py.zeile, konf_py: py.konfidenz,
           min_grad_js: +z.min_grad.toFixed(6), min_grad_py: py.min_gradient,
           hell_range_js: +z.hell_range.toFixed(6), hell_range_py: py.hell_range,
           zeile_gleich: zeile === py.zeile, konf_abweichung: +Math.abs(konf - py.konfidenz).toFixed(6) };
}
"""

# ---------------------------------------------------------------------------------------------------------------
# Der Bedienteil der Seite (Oberfläche, Anzeige, Versuche) — getrennt gehalten, damit der Rechenteil oben
# unvermischt bleibt und Zeile für Zeile mit dem Python-Programm verglichen werden kann.
# ---------------------------------------------------------------------------------------------------------------
JS_BEDIENUNG = r"""
const $ = id => document.getElementById(id);
const ctx = $('kamera').getContext('2d', { willReadFrequently: true });

// --- Zustand der Anlage -------------------------------------------------------------------------------------
let S = null, regelt = false, ventil = false, soll = PR.soll, raffer = 10;
let bel = 1.0, rausch = 4, spiegel = 0.5;
const Q_V = DATEN.modell.simulation.stoerung_qv_1mm_s.q_v_mm_je_s;     // Abfluss des Ablassventils in mm/s
const VERLAUF = { t: [], h: [], soll: [], u: [] }, MAX_POINTS = 300;

function ruhewerte(){
  // Wie in streckenmodell.py: 600 s bei 150 mm einlaufen lassen. Dort ist h_ruhe der zuletzt AUFGEZEICHNETE Wert
  // (also h vor dem letzten Integrationsschritt) und i_ruhe das Integral des Zyklus bei t = 600 s — deshalb hier
  // erst 6000 Schritte, h merken, dann noch ein Schritt, der den Zyklus bei t = 600 s ausführt.
  const R = neuerKreis(M.h0, 0.0, null);
  const n = Math.round(600/DT);
  for (let i = 0; i < n; i++) schritt(R, PR.soll, 0, true);
  const h_ruhe = R.h;
  schritt(R, PR.soll, 0, true);
  return { h: h_ruhe, integral: R.integral, u: R.u };
}

function neustart(){
  const w = ruhewerte();
  S = neuerKreis(w.h, w.integral, soll);
  S.puffer.fill(w.u); S.u = w.u;          // die Leitung ist im Betrieb gefüllt — kein Pumpenaussetzer beim Start
  VERLAUF.t.length = 0; VERLAUF.h.length = 0; VERLAUF.soll.length = 0; VERLAUF.u.length = 0;
  BV.puffer.length = 0; BV.pixel_y = null; BV.mm = null; BV.konf = 0; BV.hold = 0;
  regelt = true; ventil = false; knoepfeFrischen();
}

// --- Verläufe -----------------------------------------------------------------------------------------------
function zeichneVerlauf(id, werte, zweit, farbe, farbe2, einheit, fest){
  const c = $(id), g = c.getContext('2d'), w = c.width, hh = c.height;
  g.setTransform(1,0,0,1,0,0); g.fillStyle = '#fff'; g.fillRect(0,0,w,hh);
  const L = 44, R = 8, O = 16, U = 22;
  let mn, mx;
  if (fest){ mn = fest[0]; mx = fest[1]; }
  else {
    const alle = werte.concat(zweit || []); if (!alle.length){ mn = 0; mx = 1; } else { mn = Math.min(...alle); mx = Math.max(...alle); }
    const rand = Math.max(1, (mx-mn)*0.12); mn -= rand; mx += rand;
  }
  const X = i => L + (w-L-R) * (werte.length < 2 ? 0 : i/(werte.length-1));
  const Y = v => O + (hh-O-U) * (1 - (v-mn)/(mx-mn || 1));
  g.strokeStyle = '#e3e6ea'; g.fillStyle = '#5d6470'; g.font = '10px system-ui'; g.lineWidth = 1;
  for (let q = 0; q <= 4; q++){
    const v = mn + (mx-mn)*q/4, y = Y(v);
    g.beginPath(); g.moveTo(L, y); g.lineTo(w-R, y); g.stroke();
    g.fillText(v.toFixed(v > 99 ? 0 : 1), 4, y+3);
  }
  g.fillText(einheit, 4, 8);                                    // Einheit oben links, damit die Zeitmarken unten frei bleiben
  if (VERLAUF.t.length > 1){
    g.fillText(VERLAUF.t[0].toFixed(0) + ' s', L, hh-6);
    g.fillText(VERLAUF.t[VERLAUF.t.length-1].toFixed(0) + ' s', w-R-34, hh-6);
  }
  const linie = (arr, f, breit) => { if (arr.length < 2) return; g.strokeStyle = f; g.lineWidth = breit; g.beginPath();
    for (let i = 0; i < arr.length; i++){ const x = X(i), y = Y(arr[i]); i ? g.lineTo(x,y) : g.moveTo(x,y); } g.stroke(); };
  if (zweit) linie(zweit, farbe2, 1.2);
  linie(werte, farbe, 1.8);
}

// --- Anzeige ------------------------------------------------------------------------------------------------
function zeichneUeberlagerung(){
  if (BV.pixel_y === null) return;
  const y = BV.pixel_y;
  ctx.strokeStyle = BV.hold > 0 ? '#ffa500' : (BV.konf > 0.15 ? '#00dcdc' : '#0096dc');
  ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(0, y+0.5); ctx.lineTo(BILD.w, y+0.5); ctx.stroke();
  ctx.fillStyle = ctx.strokeStyle; ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(16,y-9); ctx.lineTo(16,y+9); ctx.fill();
  const txt = BV.mm === null ? 'Kamera: --- (nicht kalibriert)' : `Kamera: ${BV.mm.toFixed(1)} mm`;
  ctx.font = 'bold 13px system-ui'; const bw = ctx.measureText(txt).width;
  ctx.fillStyle = '#000'; ctx.fillRect(BILD.w-bw-14, y-20, bw+8, 17);
  ctx.fillStyle = ctx.strokeStyle; ctx.fillText(txt, BILD.w-bw-10, y-7);
  // grüner ROI-Rahmen wie im Programm
  ctx.strokeStyle = '#00b400'; ctx.lineWidth = 1; ctx.strokeRect(ROI[0]+0.5, ROI[1]+0.5, ROI[2]-ROI[0], ROI[3]-ROI[1]);
}

function setz(id, txt, klasse){ const e = $(id); e.textContent = txt; if (klasse !== undefined) e.className = 'zahl ' + klasse; }
function frischen(){
  const abw = (BV.mm === null) ? null : BV.mm - S.h;
  setz('w_ist', S.mess.toFixed(1) + ' mm');
  setz('w_soll', soll.toFixed(0) + ' mm');
  setz('w_u', S.u.toFixed(1) + ' %');
  setz('w_int', S.integral.toFixed(1));
  setz('w_kamera', BV.mm === null ? (BV.pixel_y === null ? '—' : 'nicht kalibriert') : BV.mm.toFixed(1) + ' mm');
  setz('w_abw', abw === null ? '—' : (abw >= 0 ? '+' : '') + abw.toFixed(2) + ' mm', abw === null ? '' : (Math.abs(abw) <= DATEN.schranke_kamera_mm ? 'gut' : 'schlecht'));
  setz('w_konf', BV.pixel_y === null ? 'keine Kante' : (BV.konf*100).toFixed(0) + ' %' + (BV.hold ? ` (gehalten ${BV.hold})` : ''));
  setz('w_zeit', S.t.toFixed(0) + ' s');
  LABOR.kamera = { h_wahr_mm: +S.h.toFixed(3), pixel: BV.pixel_y, mm: BV.mm === null ? null : +BV.mm.toFixed(3),
                   konf: +BV.konf.toFixed(4), hold: BV.hold, abweichung_mm: abw === null ? null : +abw.toFixed(3),
                   kalibriert: BV.kalib_gueltig, methode: BV.methode };
  LABOR.kreis = { t: +S.t.toFixed(1), h: +S.h.toFixed(3), mess: +S.mess.toFixed(3), u: +S.u.toFixed(3),
                  soll: soll, integral: +S.integral.toFixed(2), punkte: VERLAUF.t.length, regelt, ventil };
}

function knoepfeFrischen(){
  const b = $('regler'); b.textContent = regelt ? 'Regler EIN' : 'Regler AUS'; b.className = 'knopf ' + (regelt ? 'an' : '');
  const v = $('ventil'); v.textContent = ventil ? 'Ventil SCHLIESSEN' : 'Ventil ÖFFNEN (Störung)'; v.className = 'knopf ' + (ventil ? 'warn' : '');
  for (const m of ['helligkeit','canny','farbe']) $('m_'+m).className = 'knopf ' + (BV.methode === m ? 'gewaehlt' : '');
  $('p_hell').hidden = BV.methode !== 'helligkeit'; $('p_canny').hidden = BV.methode !== 'canny'; $('p_farbe').hidden = BV.methode !== 'farbe';
}

// --- Schleife -----------------------------------------------------------------------------------------------
let letzteZeit = 0, rest = 0, rahmen = 0;
function takt(jetzt){
  if (!letzteZeit) letzteZeit = jetzt;
  const dtEcht = Math.min(0.25, (jetzt - letzteZeit)/1000); letzteZeit = jetzt;
  rest += dtEcht * raffer;
  let n = 0;
  while (rest >= DT && n < 4000){
    const neu = schritt(S, soll, ventil ? Q_V : 0, regelt);
    rest -= DT; n++;
    if (neu){
      VERLAUF.t.push(S.t); VERLAUF.h.push(S.mess); VERLAUF.soll.push(soll); VERLAUF.u.push(S.u);
      if (VERLAUF.t.length > MAX_POINTS){ VERLAUF.t.shift(); VERLAUF.h.shift(); VERLAUF.soll.shift(); VERLAUF.u.shift(); }
    }
  }
  zeichneBehaelter(ctx, S.h, bel, rausch, spiegel);
  bv_verarbeite(ctx);
  zeichneUeberlagerung();
  zeichneVerlauf('gh', VERLAUF.h, VERLAUF.soll, '#2b4c7e', '#b0171f', 'h in mm', null);
  zeichneVerlauf('gu', VERLAUF.u, null, '#b06a00', null, 'u in %', [0, 100]);
  frischen();
  rahmen++; LABOR.rahmen = rahmen; LABOR.laufend = true;
  requestAnimationFrame(takt);
}

// --- Kalibrierung (der Ablauf des Programms, nur selbsttätig durchgefahren) ----------------------------------
function kalibriere(){
  BV.kalib.length = 0; BV.kalib_gueltig = false; BV.puffer.length = 0; BV.pixel_y = null; BV.mm = null;
  const h_alt = S.h;
  for (const ziel of DATEN.kalibrierhoehen_mm){
    zeichneBehaelter(ctx, ziel, bel, rausch, spiegel);
    for (let i = 0; i < BV.GLAETT_N + 3; i++){ zeichneBehaelter(ctx, ziel, bel, rausch, spiegel); bv_verarbeite(ctx); }
    if (BV.pixel_y === null){ $('kalib_info').textContent = `Kalibrierung: bei ${ziel} mm keine Kante erkannt`; $('kalib_info').className = 'hinweis schlecht'; S.h = h_alt; return; }
    if (BV.kalib.length >= 2) BV.kalib.shift();
    BV.kalib.push([BV.pixel_y, ziel]);
    BV.kalib_gueltig = BV.kalib.length >= 2;
    BV.puffer.length = 0;
  }
  S.h = h_alt;
  $('kalib_info').textContent = 'Kalibriert: ' + BV.kalib.map(([p,m]) => `Y = ${p} → ${m} mm`).join('  |  ')
    + `   (${(Math.abs(BV.kalib[1][1]-BV.kalib[0][1])/Math.abs(BV.kalib[1][0]-BV.kalib[0][0])).toFixed(4)} mm je Bildpunkt)`;
  $('kalib_info').className = 'hinweis gut';
  $('grenze').textContent = grenze_mm().toFixed(1);
  LABOR.grenzen = { unterste_erkennbare_hoehe_mm: +grenze_mm().toFixed(2),
                    hoechster_stand_mit_offenem_ventil_mm: +(M.h0 + M.K_u*PR.u_max - M.T*Q_V).toFixed(2) };
  LABOR.kalibrierung = { punkte: BV.kalib, mm_je_pixel: +(Math.abs(BV.kalib[1][1]-BV.kalib[0][1])/Math.abs(BV.kalib[1][0]-BV.kalib[0][0])).toFixed(5) };
}

// --- Versuche ohne Warten -----------------------------------------------------------------------------------
function kennwerte(reihe, ziel, band){
  const h = reihe.map(r => r.mess);
  const ueber = Math.max(0, Math.max(...h) - ziel), rest = Math.abs(h[h.length-1] - ziel);
  let letzterAusserhalb = -1;
  for (let i = 0; i < h.length; i++) if (Math.abs(h[i]-ziel) > band) letzterAusserhalb = i;
  const t_ein = (letzterAusserhalb >= 0 && letzterAusserhalb+1 < reihe.length) ? reihe[letzterAusserhalb+1].t : 0;
  return { ueberschwingen_mm: +ueber.toFixed(2), bleibende_abweichung_mm: +rest.toFixed(3),
           einschwingzeit_s: +t_ein.toFixed(1), groesste_abweichung_mm: +(ziel - Math.min(...h)).toFixed(2) };
}
function versuch(art){
  // Der Versuch bildet die Referenzsimulation aus streckenmodell.py Zug um Zug nach, damit der Vergleich etwas wert
  // ist. Dazu gehören drei Einzelheiten, die dort aus dem Aufbau der Funktion folgen:
  //   1. der Lauf beginnt mit soll_prev = None — der Sollsprung löst also KEINEN Integral-Reset aus,
  //   2. der Totzeitpuffer beginnt LEER (mit Nullen): die Pumpe setzt zu Beginn für Td = 1,25 s aus,
  //   3. aufgezeichnet wird der Messwert des Zyklus, bevor der Schritt der Strecke gerechnet wird.
  // Im laufenden Betrieb weiter oben gilt dagegen das Verhalten des Programms (Sollwert verstellen setzt das
  // Integral zurück) und eine gefüllte Leitung.
  const w = ruhewerte();
  const R = neuerKreis(w.h, w.integral, null);
  const soll_neu = art === 'sprung' ? 200.0 : PR.soll, q = art === 'stoerung' ? Q_V : 0.0;
  const reihe = [];
  for (let i = 0; i <= Math.round(300/DT); i++){
    const tv = R.t;
    if (schritt(R, soll_neu, q, true)) reihe.push({ t: tv, mess: R.mess, u: R.u });
  }
  const k = kennwerte(reihe, soll_neu, 2.0);
  const ref = art === 'sprung' ? DATEN.modell.simulation.sprung_150_200 : DATEN.modell.simulation.stoerung_qv_1mm_s;
  const zeilen = art === 'sprung'
    ? [['Überschwingen', 'mm', k.ueberschwingen_mm, ref.ueberschwingen_mm],
       ['bleibende Abweichung', 'mm', k.bleibende_abweichung_mm, ref.bleibende_abweichung_mm],
       ['Einschwingzeit (±2 mm)', 's', k.einschwingzeit_s, ref.einschwingzeit_s]]
    : [['größter Einbruch', 'mm', k.groesste_abweichung_mm, ref.groesste_abweichung_mm],
       ['bleibende Abweichung', 'mm', k.bleibende_abweichung_mm, ref.bleibende_abweichung_mm],
       ['Einschwingzeit (±2 mm)', 's', k.einschwingzeit_s, ref.einschwingzeit_s]];
  const schranke = DATEN.schranke_versuch;
  let schlimmst = 0;
  const tr = zeilen.map(([n,e,js,py]) => { const d = Math.abs(js-py); schlimmst = Math.max(schlimmst, d);
    return `<tr><td>${n}</td><td class="z">${js}</td><td class="z">${py}</td><td class="z ${d <= schranke ? 'gut':'schlecht'}">${d.toFixed(3)}</td><td>${e}</td></tr>`; }).join('');
  $('versuch_' + art).innerHTML = `<table><tr><th>Kennwert</th><th>Seite (JavaScript)</th><th>Python</th><th>Unterschied</th><th></th></tr>${tr}</table>`;
  LABOR.versuch[art] = { js: k, python: ref, groesster_unterschied: +schlimmst.toFixed(4), schranke };
  return k;
}

// --- Bedienung anschließen ----------------------------------------------------------------------------------
function reiter(n){
  for (const t of ['labor','doku']){ $('r_'+t).setAttribute('aria-selected', String(t===n)); $('t_'+t).hidden = t !== n; }
}
window.addEventListener('DOMContentLoaded', () => {
  LABOR.fassung = document.getElementById('fassung').textContent;
  neustart();
  $('regler').onclick = () => { regelt = !regelt; if (regelt){ S.integral = 0; S.soll_prev = null; } knoepfeFrischen(); };
  $('ventil').onclick = () => { ventil = !ventil; knoepfeFrischen(); };
  $('neustart').onclick = neustart;
  $('kalibrieren').onclick = kalibriere;
  $('v_sprung').onclick = () => versuch('sprung');
  $('v_stoerung').onclick = () => versuch('stoerung');
  for (const m of ['helligkeit','canny','farbe']) $('m_'+m).onclick = () => { BV.methode = m; BV.puffer.length = 0; knoepfeFrischen(); };
  const bind = (id, f, format) => { const e = $(id), a = $(id+'_w');
    const zeig = () => { const v = +e.value; a.textContent = format(v); f(v); };
    e.addEventListener('input', zeig); zeig(); };
  bind('s_soll',   v => { soll = v; }, v => v.toFixed(0) + ' mm');
  bind('s_raffer', v => { raffer = v; }, v => v + '×');
  bind('s_bel',    v => { bel = v/100; }, v => (v/100).toFixed(2));
  bind('s_rausch', v => { rausch = v; }, v => v.toFixed(0));
  bind('s_spiegel',v => { spiegel = v/100; }, v => (v/100).toFixed(2));
  bind('s_hell',   v => { BV.hell_schwelle = v; BV.puffer.length = 0; }, v => v.toFixed(0));
  bind('s_konf',   v => { BV.konf_schwelle = v/100; BV.puffer.length = 0; }, v => (v/100).toFixed(2));
  bind('s_hold',   v => { BV.HOLD_MAX = v; }, v => v.toFixed(0));
  bind('s_t1',     v => { BV.canny_t1 = v; BV.puffer.length = 0; }, v => v.toFixed(0));
  bind('s_t2',     v => { BV.canny_t2 = v; BV.puffer.length = 0; }, v => v.toFixed(0));
  bind('s_blur',   v => { BV.blur_kern = v; BV.puffer.length = 0; }, v => v.toFixed(0));
  bind('s_hlo',    v => { BV.hsv_h_lo = v; BV.puffer.length = 0; }, v => v.toFixed(0));
  bind('s_hhi',    v => { BV.hsv_h_hi = v; BV.puffer.length = 0; }, v => v.toFixed(0));
  bind('s_slo',    v => { BV.hsv_s_lo = v; BV.puffer.length = 0; }, v => v.toFixed(0));
  bind('s_vlo',    v => { BV.hsv_v_lo = v; BV.puffer.length = 0; }, v => v.toFixed(0));
  $('r_labor').onclick = () => reiter('labor'); $('r_doku').onclick = () => reiter('doku');
  // Probe der Bildauswertung sofort rechnen, damit sie ohne Knopfdruck im Laborbericht steht
  const pr = probeRechnen(); LABOR.probe = pr;
  $('probe').innerHTML = `<table><tr><th>Größe</th><th>Seite (JavaScript)</th><th>Python (bv_referenz.py)</th><th>Unterschied</th></tr>`
    + `<tr><td>gefundene Zeile</td><td class="z">${pr.zeile_js}</td><td class="z">${pr.zeile_py}</td><td class="z ${pr.zeile_gleich?'gut':'schlecht'}">${pr.zeile_js-pr.zeile_py}</td></tr>`
    + `<tr><td>Konfidenz</td><td class="z">${pr.konf_js.toFixed(4)}</td><td class="z">${pr.konf_py.toFixed(4)}</td><td class="z ${pr.konf_abweichung<=DATEN.schranke_probe_konf?'gut':'schlecht'}">${pr.konf_abweichung.toFixed(4)}</td></tr>`
    + `<tr><td>kleinster Gradient</td><td class="z">${pr.min_grad_js.toFixed(3)}</td><td class="z">${pr.min_grad_py.toFixed(3)}</td><td class="z">${(pr.min_grad_js-pr.min_grad_py).toFixed(3)}</td></tr>`
    + `<tr><td>Helligkeitsspanne</td><td class="z">${pr.hell_range_js.toFixed(3)}</td><td class="z">${pr.hell_range_py.toFixed(3)}</td><td class="z">${(pr.hell_range_js-pr.hell_range_py).toFixed(3)}</td></tr></table>`;
  kalibriere();
  requestAnimationFrame(takt);
});
"""


def schieber(id_: str, name: str, mn, mx, schritt_, wert) -> str:
    return (f'<div class="schieber"><label for="{id_}">{name}</label>'
            f'<input type="range" id="{id_}" min="{mn}" max="{mx}" step="{schritt_}" value="{wert}">'
            f'<span class="wert" id="{id_}_w"></span></div>')


def main() -> int:
    modell = json.loads((P / "Modell" / "streckenmodell.json").read_text(encoding="utf-8"))
    nach = json.loads((P / "Modell" / "nachrechnung.json").read_text(encoding="utf-8"))
    probe = json.loads((P / "Modell" / "bv_probe.json").read_text(encoding="utf-8"))
    daten = {
        "modell": modell, "nachrechnung": nach, "probe": probe,
        "kalibrierhoehen_mm": [100, 250],     # die beiden Punkte der Zweipunktkalibrierung (beide im durchsuchten Teil des ROI)
        "schranke_kamera_mm": 3.0,            # zulässige Abweichung der Bilderkennung vom gezeichneten Stand
        "schranke_versuch": 0.2,              # zulässiger Unterschied JavaScript ↔ Python in den Versuchen
        "schranke_probe_konf": 0.005,         # zulässiger Unterschied der Konfidenz (Rundung in cv2.GaussianBlur)
    }
    doku = dokument_html(P / "MANUSKRIPT_Wasserstand.md")
    M = modell["pt1"]
    kopf = f"Fassung {VERSION} · {DATUM} · {NAMENSNENNUNG}"

    html = f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wasserstandsregelung mit optischer Füllhöhenerkennung {VERSION}</title>
<style>{STIL}</style></head><body>
<header>
  <h1>Wasserstandsregelung mit optischer Füllhöhenerkennung</h1>
  <div class="fassung" id="fassung">{kopf}</div>
</header>
<nav>
  <button id="r_labor" role="tab" aria-selected="true">Labor</button>
  <button id="r_doku" role="tab" aria-selected="false">Dokumentation</button>
</nav>
<main>
<section id="t_labor">

  <div class="karte">
    <button class="knopf" id="regler">Regler EIN</button>
    <button class="knopf" id="ventil">Ventil ÖFFNEN (Störung)</button>
    <button class="knopf" id="kalibrieren">Kamera kalibrieren (2 Punkte)</button>
    <button class="knopf" id="neustart">Zurücksetzen</button>
    <span style="display:inline-block;min-width:260px;vertical-align:middle">{schieber('s_soll', 'Sollwert', 60, 250, 1, 150)}</span>
    <span style="display:inline-block;min-width:240px;vertical-align:middle">{schieber('s_raffer', 'Zeitraffer', 1, 100, 1, 10)}</span>
    <div class="werte">
      <div class="wertfeld"><div class="name">Istwert (Sensor)</div><div class="zahl" id="w_ist">—</div></div>
      <div class="wertfeld"><div class="name">Sollwert</div><div class="zahl" id="w_soll">—</div></div>
      <div class="wertfeld"><div class="name">Pumpe</div><div class="zahl" id="w_u">—</div></div>
      <div class="wertfeld"><div class="name">Integral</div><div class="zahl" id="w_int">—</div></div>
      <div class="wertfeld"><div class="name">Kamera</div><div class="zahl" id="w_kamera">—</div></div>
      <div class="wertfeld"><div class="name">Kamera − wahr</div><div class="zahl" id="w_abw">—</div></div>
      <div class="wertfeld"><div class="name">Konfidenz</div><div class="zahl" id="w_konf">—</div></div>
      <div class="wertfeld"><div class="name">Zeit</div><div class="zahl" id="w_zeit">—</div></div>
    </div>
  </div>

  <div class="reihe">
    <div class="karte" style="flex:0 0 auto">
      <h2>Kamerabild (gezeichnet, 480 × 360)</h2>
      <canvas id="kamera" width="480" height="360"></canvas>
      <p class="hinweis" id="kalib_info">noch nicht kalibriert</p>
      <h3>Aufnahmebedingungen</h3>
      {schieber('s_bel', 'Beleuchtung', 40, 130, 1, 100)}
      {schieber('s_rausch', 'Rauschen', 0, 20, 1, 4)}
      {schieber('s_spiegel', 'Spiegelung', 0, 100, 1, 50)}
    </div>

    <div class="karte" style="flex:1 1 420px;min-width:380px">
      <h2>Verläufe</h2>
      <canvas id="gh" width="560" height="190" style="background:#fff;border:1px solid #d6d9de"></canvas>
      <canvas id="gu" width="560" height="150" style="background:#fff;border:1px solid #d6d9de;margin-top:8px"></canvas>
      <p class="hinweis">Oben Füllstand (blau) und Sollwert (rot), unten der Stellgrad der Pumpe. 300 Punkte wie
      <code>MAX_POINTS</code> im Programm, ein Punkt je Reglerzyklus (0,5 s). Der Zeitraffer oben beschleunigt nur die
      Darstellung — gerechnet wird mit denselben 0,5 s.</p>
    </div>

    <div class="karte" style="flex:1 1 300px;min-width:290px">
      <h2>Erkennungsmethode</h2>
      <button class="knopf" id="m_helligkeit">Helligkeit</button>
      <button class="knopf" id="m_canny">Canny</button>
      <button class="knopf" id="m_farbe">Farbfilter (HSV)</button>
      <div id="p_hell">
        {schieber('s_hell', 'Empfindlichkeit', 5, 80, 1, 30)}
        {schieber('s_konf', 'Konf-Schwelle', 1, 30, 1, 5)}
        {schieber('s_hold', 'Hold (Bilder)', 1, 60, 1, 10)}
        <p class="hinweis">Die Schwelle ist −0,3 · Empfindlichkeit Graustufen je Zeile. Wird die Beleuchtung
        heruntergedreht, unterschreitet der Gradient sie irgendwann — dann hält die Anzeige den letzten Wert
        (orange Linie) und löscht ihn nach „Hold“ Bildern. Empfindlichkeit senken hilft.</p>
      </div>
      <div id="p_canny" hidden>
        {schieber('s_t1', 'T1', 5, 150, 1, 30)}
        {schieber('s_t2', 'T2', 10, 300, 1, 80)}
        {schieber('s_blur', 'Weichzeichnung', 1, 21, 1, 5)}
        <p class="hinweis">Nachgebildet: Gauß, Sobel, Nicht-Maximum-Unterdrückung, Hysterese. Gewählt wird die Zeile
        mit dem größten Anteil an Kantenpunkten (mindestens 6 % der Breite).</p>
      </div>
      <div id="p_farbe" hidden>
        {schieber('s_hlo', 'Hue min', 0, 179, 1, 10)}
        {schieber('s_hhi', 'Hue max', 0, 179, 1, 30)}
        {schieber('s_slo', 'Sat min', 0, 255, 1, 40)}
        {schieber('s_vlo', 'Val min', 0, 255, 1, 40)}
        <p class="hinweis">Oberste Zeile, die zu mehr als 12 % in der Farbmaske liegt. Hellwerte über 220 gelten als
        Glanzlicht und zählen nicht mit.</p>
      </div>
    </div>
  </div>

  <div class="karte">
    <h2>Versuche ohne Warten — und der Vergleich mit der Python-Rechnung</h2>
    <p class="hinweis">Beide Versuche laufen mit demselben Algorithmus 300 s durch und werden mit
    <code>Modell/streckenmodell.py</code> verglichen. Das ist der zweite unabhängige Weg: gleiche Gleichung, andere
    Sprache, anderer Zeitgeber.</p>
    <button class="knopf" id="v_sprung">Sollsprung 150 → 200 mm</button>
    <button class="knopf" id="v_stoerung">Störung: Ablassventil {modell['simulation']['stoerung_qv_1mm_s']['q_v_mm_je_s']:g} mm/s</button>
    <div id="versuch_sprung"></div>
    <div id="versuch_stoerung"></div>
  </div>

  <div class="karte">
    <h2>Probe der Bildauswertung gegen die Python-Fassung</h2>
    <p class="hinweis">Dasselbe rechnerisch erzeugte Prüfbild ({probe['bild']['zeilen']} × {probe['bild']['spalten']}
    Bildpunkte, Kante bei Zeile {probe['bild']['kante']}) läuft hier in JavaScript und in
    <code>Modell/bv_referenz.py</code> — dem wörtlich aus dem Programm herausgeschnittenen Block. Die gefundene Zeile
    muss gleich sein; die Konfidenz darf um bis zu {daten['schranke_probe_konf']} abweichen, weil OpenCV im
    Weichzeichner auf ganze Graustufen rundet.</p>
    <div id="probe"></div>
  </div>

  <div class="karte">
    <h2>Womit hier gerechnet wird</h2>
    <table>
      <tr><th>Größe</th><th>Wert</th><th>Herkunft</th></tr>
      <tr><td>Stellverstärkung K_u</td><td class="z">{M['K_u_mm_je_prozent']} mm/%</td><td>Sprungantwort 25.06.2026</td></tr>
      <tr><td>Zeitkonstante T</td><td class="z">{M['T_s']} s</td><td>Sprungantwort 25.06.2026</td></tr>
      <tr><td>Totzeit T_d</td><td class="z">{M['Td_s']} s</td><td>Sprungantwort 25.06.2026</td></tr>
      <tr><td>Grundstand h₀</td><td class="z">{M['h0_mm']} mm</td><td>Sprungantwort 25.06.2026</td></tr>
      <tr><td>K_p / K_i</td><td class="z">{modell['programm']['kp']:g} %/mm · {modell['programm']['ki']:g} %/(mm·s)</td><td>Voreinstellung des Programms</td></tr>
      <tr><td>Reglerzyklus</td><td class="z">{modell['programm']['zyklus_s']:g} s</td><td><code>root.after(500, regulation)</code></td></tr>
      <tr><td>Dämpfung ζ · Kennkreisfrequenz ω_n</td><td class="z">{modell['kreis']['daempfung']} · {modell['kreis']['omega_n_rad_s']} rad/s</td><td>Kennkreisgleichung</td></tr>
      <tr><td>Phasenreserve</td><td class="z">{modell['kreis']['phasenreserve_grad']}°</td><td>offener Kreis mit Totzeit</td></tr>
      <tr><td>unterste von der Kamera erkennbare Höhe</td><td class="z"><span id="grenze">—</span> mm</td><td>untere 15 % des ROI werden nicht durchsucht</td></tr>
      <tr><td>höchster mit offenem Ventil haltbarer Stand</td><td class="z">{modell['pt1']['h0_mm'] + modell['pt1']['K_u_mm_je_prozent']*100 - modell['pt1']['T_s']*modell['simulation']['stoerung_qv_1mm_s']['q_v_mm_je_s']:.1f} mm</td><td>h₀ + K_u·100 % − T·q_v (Pumpe am Anschlag)</td></tr>
      <tr><td>gemessene Stufe des Wandlers</td><td class="z">{nach['aufloesung']['gemessene_stufe_mm']} mm</td><td>aus den Rohwerten der Messreihe ({nach['aufloesung']['bit']:g} Bit)</td></tr>
    </table>
    <p class="hinweis">Die Bildauswertung greift — wie im Programm — <strong>nicht</strong> in die Regelung ein.
    Geregelt wird mit dem Ultraschallwert; die Kamera ist der zweite, unabhängige Messweg auf dieselbe Größe.</p>
  </div>

</section>

<section id="t_doku" hidden>
  <div class="doku">{doku}</div>
</section>
</main>

<script>
const DATEN = {json.dumps(daten, ensure_ascii=False)};
window.LABOR = {{ fassung: null, rahmen: 0, laufend: false, kamera: null, kreis: null, probe: null, versuch: {{}}, kalibrierung: null }};
{JS}
{JS_BEDIENUNG}
</script>
</body></html>
"""
    html = neutral(html)
    ZIEL.write_text(html, encoding="utf-8")
    print(f"{ZIEL.name}: {len(html)/1024:.0f} kB · Fassung {VERSION} · {DATUM}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
