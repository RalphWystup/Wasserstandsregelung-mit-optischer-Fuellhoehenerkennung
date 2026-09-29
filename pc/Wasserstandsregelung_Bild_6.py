import serial
import tkinter as tk
from tkinter import ttk
import time
import threading
import os

import cv2
import numpy as np
import requests
from PIL import Image, ImageTk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# --------------------------------------------------
# EasyPort  (unverändert)
# --------------------------------------------------

ser = serial.Serial(
    port="COM9",
    baudrate=115200,
    timeout=0.5,
    write_timeout=0.5,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE
)

serial_lock = threading.Lock()

def read_register(reg):
    with serial_lock:
        ser.reset_input_buffer()
        ser.write(f"D{reg}\r".encode("ascii"))
        ser.flush()
        rx = ser.read_until(b"\r").decode("ascii").strip()
    _, value = rx.split("=")
    return int(value, 16)

def write_register(reg, value):
    with serial_lock:
        ser.write(f"M{reg}={value:04X}\r".encode("ascii"))
        ser.flush()
        ser.read_until(b"\r")

def level_mm():
    raw = read_register("EW1.2")
    return 50.0 + raw * 220.0 / 32760.0

def durchfluss_volt():
    raw = read_register("EW1.4")
    return raw * 10.0 / 32760.0

def druck_volt():
    raw = read_register("EW1.6")
    return raw * 10.0 / 32760.0

def fs_unten():
    return (read_register("EW1.0") & (1 << 3)) != 0

def fs_oben():
    return (read_register("EW1.0") & (1 << 4)) != 0

def pump_set(percent):
    percent = max(0.0, min(100.0, percent))
    aw0 = read_register("AW1.0")
    aw0 |= 0x000C
    write_register("AW1.0", aw0)
    write_register("AW1.2", round(percent * 32760.0 / 100.0))

def pump_stop():
    write_register("AW1.2", 0)
    aw0 = read_register("AW1.0")
    aw0 &= 0xFFF3
    write_register("AW1.0", aw0)

# --------------------------------------------------
# Ablassventil  (unverändert)
# --------------------------------------------------

ventil_offen = False

def ventil_oeffnen():
    global ventil_offen
    aw0 = read_register("AW1.0")
    aw0 |= 0x0001
    write_register("AW1.0", aw0)
    ventil_offen = True
    btn_ventil.config(text="Ventil SCHLIESSEN", bg="#e74c3c", fg="white")
    lbl_ventil.config(text="Ablassventil: OFFEN  ⚠  STÖRUNG AKTIV", fg="#e74c3c")

def ventil_schliessen():
    global ventil_offen
    aw0 = read_register("AW1.0")
    aw0 &= 0xFFFE
    write_register("AW1.0", aw0)
    ventil_offen = False
    btn_ventil.config(text="Ventil ÖFFNEN  (Störung)", bg="#2ecc71", fg="white")
    lbl_ventil.config(text="Ablassventil: GESCHLOSSEN", fg="#27ae60")

def toggle_ventil():
    if ventil_offen:
        ventil_schliessen()
    else:
        ventil_oeffnen()

# --------------------------------------------------
# PI Regler  (unverändert)
# --------------------------------------------------

controller_active = False
integral  = 0.0
last_time = None
soll_prev = None

trend_time = []
trend_ist  = []
trend_soll = []
trend_out  = []
MAX_POINTS = 300

def toggle_controller():
    global controller_active, integral, last_time, soll_prev
    controller_active = not controller_active
    if controller_active:
        integral  = 0.0
        last_time = None
        soll_prev = None
        btn_start.config(text="Regler EIN")
    else:
        pump_stop()
        btn_start.config(text="Regler AUS")

def reset_integral():
    global integral
    integral = 0.0

def regulation():
    global integral, last_time, soll_prev

    try:
        now = time.time()

        if last_time is None:
            last_time = now
            root.after(500, regulation)
            return

        dt = now - last_time
        dt = max(0.001, min(dt, 2.0))
        last_time = now

        ist  = level_mm()
        soll = float(entry_soll.get())
        kp   = float(entry_kp.get())
        ki   = float(entry_ki.get())
        output = 0

        if controller_active:
            if soll_prev is not None and abs(soll - soll_prev) > 1.0:
                integral = 0.0
            soll_prev  = soll
            error      = soll - ist
            integral  += error * dt
            output     = kp * error + ki * integral

            if output > 100.0:
                integral -= (output - 100.0) / (ki if ki != 0 else 1e-9)
                output = 100.0
            elif output < 0.0:
                integral -= output / (ki if ki != 0 else 1e-9)
                output = 0.0

            pump_set(output)

        df_v   = durchfluss_volt()
        dr_v   = druck_volt()
        sw_unt = fs_unten()
        sw_ob  = fs_oben()

        lbl_ist.config(text=f"Istwert: {ist:.1f} mm")
        lbl_soll.config(text=f"Sollwert: {soll:.1f} mm")
        lbl_out.config(text=f"Pumpenausgang: {output:.1f} %")
        lbl_integral.config(text=f"Integral: {integral:.2f}")
        lbl_df.config(text=f"Durchfluss: {df_v:.3f} V")
        lbl_dr.config(text=f"Druck: {dr_v:.3f} V")
        lbl_fs_unten.config(
            text=f"Schalter unten: {'EIN' if sw_unt else 'AUS'}",
            fg="#e74c3c" if sw_unt else "#555555")
        lbl_fs_oben.config(
            text=f"Schalter oben:  {'EIN' if sw_ob else 'AUS'}",
            fg="#e74c3c" if sw_ob else "#555555")

        trend_time.append(time.time())
        trend_ist.append(ist)
        trend_soll.append(soll)
        trend_out.append(output)

        if len(trend_time) > MAX_POINTS:
            trend_time.pop(0)
            trend_ist.pop(0)
            trend_soll.pop(0)
            trend_out.pop(0)

        ax1.clear()
        ax1.plot(trend_ist,  label="Istwert")
        ax1.plot(trend_soll, label="Sollwert")
        ax1.set_ylabel("mm")
        ax1.legend()

        ax2.clear()
        ax2.plot(trend_out, label="Pumpe %")
        ax2.set_ylabel("%")
        ax2.legend()

        canvas.draw()
        lbl_error.config(text="")

    except Exception as e:
        lbl_error.config(text=str(e))

    root.after(500, regulation)

# --------------------------------------------------
# ESP32-CAM – Stream
# --------------------------------------------------

IP_ADRESSE  = "<IP-der-Kamera>"
STREAM_URL  = f"http://{IP_ADRESSE}:81/stream"
CONTROL_URL = f"http://{IP_ADRESSE}/control"

CAM_W = 480
CAM_H = 360

RECONNECT_INTERVAL = 3
TIMEOUT_OFFLINE    = 5
ORDNER_NAME        = "ESP32_Aufnahmen"

cam_frame      = None
cam_online     = False
cam_last_time  = 0.0
cam_thread_run = True
cam_letztes    = None

WB_MODI = [
    {"id": 0, "name": "Auto"},
    {"id": 1, "name": "Sonnig"},
    {"id": 2, "name": "Bewoelkt"},
    {"id": 3, "name": "Buero"},
    {"id": 4, "name": "Wohnraum"},
]
wb_index = 0

def setze_weissabgleich(mid):
    def send():
        try:
            if mid == 0:
                requests.get(f"{CONTROL_URL}?var=awb&val=1",       timeout=2)
                requests.get(f"{CONTROL_URL}?var=wb_mode&val=0",    timeout=2)
            else:
                requests.get(f"{CONTROL_URL}?var=awb&val=0",            timeout=2)
                requests.get(f"{CONTROL_URL}?var=wb_mode&val={mid}",     timeout=2)
        except Exception:
            pass
    threading.Thread(target=send, daemon=True).start()

def mjpeg_thread():
    global cam_frame, cam_online, cam_last_time, cam_thread_run
    while cam_thread_run:
        try:
            resp = requests.get(STREAM_URL, stream=True, timeout=5)
            if resp.status_code != 200:
                cam_online = False
                time.sleep(RECONNECT_INTERVAL)
                continue
        except Exception:
            cam_online = False
            time.sleep(RECONNECT_INTERVAL)
            continue

        buf = b""
        try:
            for chunk in resp.iter_content(chunk_size=4096):
                if not cam_thread_run:
                    break
                if not chunk:
                    continue
                buf += chunk
                while True:
                    s = buf.find(b"\xff\xd8")
                    e = buf.find(b"\xff\xd9")
                    if s != -1 and e != -1 and s < e:
                        frm = cv2.imdecode(
                            np.frombuffer(buf[s:e+2], dtype=np.uint8),
                            cv2.IMREAD_COLOR)
                        buf = buf[e+2:]
                        if frm is not None and frm.size > 0:
                            cam_frame     = frm
                            cam_last_time = time.time()
                            cam_online    = True
                            bv_verarbeite(frm)   # Bildverarbeitung hier
                    else:
                        break
                if len(buf) > 100_000:
                    buf = b""
        except Exception:
            pass
        cam_online = False
        try:
            resp.close()
        except Exception:
            pass
        if cam_thread_run:
            time.sleep(RECONNECT_INTERVAL)

# --------------------------------------------------
# Bildverarbeitung  –  nur Erkennung + Anzeige
# --------------------------------------------------
#
#  ROI:  Bereich im Originalbild, der den Behälter zeigt.
#         Per Mausziehen im Kamerabild einstellbar.
#  Canny: findet horizontale Kanten; die stärkste = Wasserlinie.
#  Kalibrierung: 2 Punkte (Pixel ↔ mm) → lineare Umrechnung.
#  Ergebnis wird NUR angezeigt, beeinflusst die Regelung NICHT.

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

# --------------------------------------------------
# Kamera-Anzeige (40 ms Loop)
# --------------------------------------------------

cam_aufnahme_aktiv = False
cam_video_writer   = None

def update_kamera():
    global cam_letztes, cam_aufnahme_aktiv, cam_video_writer

    jetzt    = time.time()
    verbunden = cam_online and (jetzt - cam_last_time) < TIMEOUT_OFFLINE

    if cam_frame is not None:
        cam_letztes = cam_frame.copy()

    if cam_letztes is None:
        bild = np.zeros((CAM_H, CAM_W, 3), dtype=np.uint8)
        bild[:] = (40, 40, 40)
        cv2.putText(bild, "Warte auf Kamera...",
                    (20, CAM_H // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        anzeige = bild
    else:
        h_orig, w_orig = cam_letztes.shape[:2]
        sx = CAM_W / w_orig
        sy = CAM_H / h_orig

        anzeige = cv2.resize(cam_letztes, (CAM_W, CAM_H))

        if not verbunden:
            ov = anzeige.copy(); ov[:] = 0
            anzeige = cv2.addWeighted(anzeige, 0.4, ov, 0.6, 0)
            cv2.putText(anzeige, "Kamera offline – Reconnect ...",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # ROI-Rahmen (grün)
        cv2.rectangle(anzeige,
                      (int(roi[0]*sx), int(roi[1]*sy)),
                      (int(roi[2]*sx), int(roi[3]*sy)),
                      (0, 180, 0), 1)

        # Kamera-BV-Linie (cyan) – NUR Anzeige
        py   = bv_pixel_y
        mm_v = bv_mm
        konf = bv_konf
        hold = bv_hold_count

        if py is not None:
            py_anz = int(py * sy)
            # Cyan = guter Wert, Orange = gehalten (schwaches Signal), Blau = sehr schwach
            if hold == 0:
                farbe = (0, 220, 220) if konf > 0.15 else (0, 150, 220)
            else:
                farbe = (0, 165, 255)   # Orange = gehaltener Wert
            cv2.line(anzeige, (0, py_anz), (CAM_W, py_anz), farbe, 2)
            pts = np.array([[0, py_anz],[16, py_anz-9],[16, py_anz+9]], np.int32)
            cv2.fillPoly(anzeige, [pts], farbe)

            if mm_v is not None:
                txt = f"Kamera: {mm_v:.1f} mm"
            else:
                txt = f"Kamera: --- (nicht kalibriert)"
            (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            xr = CAM_W - tw - 10
            yr = py_anz - 6
            cv2.rectangle(anzeige, (xr-3, yr-th-3), (xr+tw+3, yr+3), (0,0,0), -1)
            cv2.putText(anzeige, txt, (xr, yr),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, farbe, 2)

            # Kamera-BV-Wert ins Label schreiben
            if mm_v is not None:
                lbl_bv_wert.config(
                    text=f"Kamera-BV: {mm_v:.1f} mm  (Konf: {konf:.0%})"
                         + (f"  [Hold {hold}]" if hold > 0 else ""),
                    fg="#cc6600" if hold > 0 else ("#006600" if konf > 0.15 else "#aa8800"))
            else:
                lbl_bv_wert.config(
                    text="Kamera-BV: Linie erkannt – nicht kalibriert",
                    fg="#cc6600")
        else:
            lbl_bv_wert.config(text="Kamera-BV: keine Kante erkannt", fg="#888888")

        # Status-Dot
        st_txt   = "Live"   if verbunden else "Offline"
        st_farbe = (0, 200, 0) if verbunden else (0, 0, 220)
        tg = cv2.getTextSize(st_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        cv2.circle(anzeige, (CAM_W - tg[0] - 28, 18), 7, st_farbe, -1)
        cv2.putText(anzeige, st_txt, (CAM_W - tg[0] - 14, 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, st_farbe, 2)

    if cam_aufnahme_aktiv and cam_video_writer is not None:
        cam_video_writer.write(anzeige)

    rgb = cv2.cvtColor(anzeige, cv2.COLOR_BGR2RGB)
    img = ImageTk.PhotoImage(Image.fromarray(rgb))
    lbl_kamera.config(image=img)
    lbl_kamera.image = img

    root.after(40, update_kamera)

# --------------------------------------------------
# ROI per Maus ziehen
# --------------------------------------------------

def maus_press(event):
    global roi_ziehen, roi_start
    roi_ziehen = True
    roi_start  = (event.x, event.y)

def maus_release(event):
    global roi_ziehen, roi, bv_puffer
    roi_ziehen = False
    if cam_letztes is not None:
        h_orig, w_orig = cam_letztes.shape[:2]
        sx = w_orig / CAM_W
        sy = h_orig / CAM_H
        x1 = int(min(roi_start[0], event.x) * sx)
        y1 = int(min(roi_start[1], event.y) * sy)
        x2 = int(max(roi_start[0], event.x) * sx)
        y2 = int(max(roi_start[1], event.y) * sy)
        if x2 - x1 > 10 and y2 - y1 > 10:
            roi[:] = [x1, y1, x2, y2]
            bv_puffer.clear()

# --------------------------------------------------
# Kalibrierung
# --------------------------------------------------

def kalib_punkt_setzen():
    global kalib_gueltig
    py = bv_pixel_y
    if py is None:
        lbl_error.config(text="Kalibrierung: keine Kante erkannt!", fg="red")
        return
    try:
        mm_ref = float(entry_kalib_mm.get())
    except ValueError:
        lbl_error.config(text="Kalibrierung: ungültiger mm-Wert!", fg="red")
        return
    if len(kalib_punkte) >= 2:
        kalib_punkte.pop(0)
    kalib_punkte.append((py, mm_ref))
    kalib_gueltig = len(kalib_punkte) >= 2
    bv_puffer.clear()
    punkte_txt = "  |  ".join(f"Y={p} → {m:.0f} mm" for p, m in kalib_punkte)
    lbl_kalib_info.config(
        text=f"{'✓ Kalibriert' if kalib_gueltig else '1 Punkt – noch einen setzen'}:  {punkte_txt}",
        fg="#006600" if kalib_gueltig else "#aa6600")

def kalib_loeschen():
    global kalib_gueltig
    kalib_punkte.clear()
    kalib_gueltig = False
    bv_puffer.clear()
    lbl_kalib_info.config(text="Keine Kalibrierung", fg="#888888")

# --------------------------------------------------
# Kamera-Buttons
# --------------------------------------------------

def cam_wb_umschalten():
    global wb_index
    wb_index = (wb_index + 1) % len(WB_MODI)
    setze_weissabgleich(WB_MODI[wb_index]["id"])
    btn_wb.config(text=f"WB: {WB_MODI[wb_index]['name']}")

def cam_screenshot():
    if cam_letztes is None:
        lbl_error.config(text="Screenshot: noch kein Bild!", fg="red"); return
    if not os.path.exists(ORDNER_NAME): os.makedirs(ORDNER_NAME)
    ts   = time.strftime("%Y%m%d_%H%M%S")
    pfad = os.path.join(ORDNER_NAME, f"screenshot_{ts}.jpg")
    anzeige = cv2.resize(cam_letztes, (CAM_W, CAM_H))
    py = bv_pixel_y
    if py is not None:
        h_orig = cam_letztes.shape[0]
        py_anz = int(py * CAM_H / h_orig)
        cv2.line(anzeige, (0, py_anz), (CAM_W, py_anz), (0, 220, 220), 2)
    cv2.imwrite(pfad, anzeige)
    lbl_error.config(text=f"Screenshot: {pfad}", fg="green")

def cam_video_toggle():
    global cam_aufnahme_aktiv, cam_video_writer
    if not cam_aufnahme_aktiv:
        if cam_letztes is None:
            lbl_error.config(text="Video: noch kein Bild!", fg="red"); return
        if not os.path.exists(ORDNER_NAME): os.makedirs(ORDNER_NAME)
        ts     = time.strftime("%Y%m%d_%H%M%S")
        pfad   = os.path.join(ORDNER_NAME, f"video_{ts}.avi")
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        cam_video_writer   = cv2.VideoWriter(pfad, fourcc, 24.0, (CAM_W, CAM_H))
        cam_aufnahme_aktiv = True
        btn_video.config(text="⏹ REC STOP", bg="#e74c3c")
        lbl_error.config(text=f"Aufnahme: {pfad}", fg="green")
    else:
        cam_aufnahme_aktiv = False
        cam_video_writer.release(); cam_video_writer = None
        btn_video.config(text="⏺ Video", bg="#3498db")
        lbl_error.config(text="Video gespeichert.", fg="green")

def canny_update(*_):
    global canny_t1, canny_t2, blur_kern
    try:
        canny_t1  = int(slider_t1.get())
        canny_t2  = int(slider_t2.get())
        blur_kern = int(slider_blur.get())
        if blur_kern % 2 == 0: blur_kern += 1
        bv_puffer.clear()
    except NameError:
        pass   # Slider noch nicht alle erstellt

def hsv_update(*_):
    global hsv_h_lo, hsv_h_hi, hsv_s_lo, hsv_v_lo
    try:
        hsv_h_lo = int(slider_hlo.get())
        hsv_h_hi = int(slider_hhi.get())
        hsv_s_lo = int(slider_slo.get())
        hsv_v_lo = int(slider_vlo.get())
        bv_puffer.clear()
    except NameError:
        pass

def hell_update(*_):
    global hell_schwelle, konf_schwelle, HOLD_MAX
    try:
        hell_schwelle = int(slider_hell.get())
        konf_schwelle = slider_konf.get() / 100.0
        HOLD_MAX      = int(slider_hold.get())
        bv_puffer.clear()
    except NameError:
        pass

def set_methode(m):
    global bv_methode
    bv_methode = m
    bv_puffer.clear()
    if m == "canny":
        frame_canny.pack(fill="x", padx=6, pady=2)
        frame_hsv.pack_forget()
        frame_hell.pack_forget()
    elif m == "farbe":
        frame_canny.pack_forget()
        frame_hsv.pack(fill="x", padx=6, pady=2)
        frame_hell.pack_forget()
    else:  # helligkeit
        frame_canny.pack_forget()
        frame_hsv.pack_forget()
        frame_hell.pack(fill="x", padx=6, pady=2)
    btn_m_hell.config( relief="sunken" if m == "helligkeit" else "raised")
    btn_m_canny.config(relief="sunken" if m == "canny"      else "raised")
    btn_m_farbe.config(relief="sunken" if m == "farbe"      else "raised")

# --------------------------------------------------
# GUI  (Layout unverändert links, Kamera neu rechts)
# --------------------------------------------------

root = tk.Tk()
root.title("PI-Füllstandsregler  +  Kamera-BV   [Update v6b]")
root.geometry("1200x950")

tk.Label(root, text="PI Füllstandsregelung",
         font=("Arial", 18, "bold")).pack()

frame_haupt = ttk.Frame(root)
frame_haupt.pack(fill="both", expand=True, padx=10, pady=4)

frame_L = ttk.Frame(frame_haupt)
frame_L.pack(side="left", fill="both", expand=True)

frame_R = ttk.Frame(frame_haupt)
frame_R.pack(side="right", fill="both", padx=(10, 0))

# Scrollbarer Container: alle Bedien-Panels bleiben bei jeder Fensterhöhe/DPI erreichbar
cam_canvas = tk.Canvas(frame_R, width=CAM_W + 34, highlightthickness=0, borderwidth=0)
cam_scroll = ttk.Scrollbar(frame_R, orient="vertical", command=cam_canvas.yview)
cam_canvas.configure(yscrollcommand=cam_scroll.set)
cam_scroll.pack(side="right", fill="y")
cam_canvas.pack(side="left", fill="both", expand=True)

frame_R_inner = ttk.Frame(cam_canvas)
cam_canvas.create_window((0, 0), window=frame_R_inner, anchor="nw")

def _cam_scrollregion(_=None):
    cam_canvas.configure(scrollregion=cam_canvas.bbox("all"))
frame_R_inner.bind("<Configure>", _cam_scrollregion)

def _cam_wheel(event):
    cam_canvas.yview_scroll(int(-event.delta / 120), "units")
cam_canvas.bind_all("<MouseWheel>", _cam_wheel)

# ── linke Seite (identisch zur Originalversion) ──

frame_param = ttk.LabelFrame(frame_L, text="Regler-Parameter")
frame_param.pack(pady=6, fill="x")

ttk.Label(frame_param, text="Sollwert [mm]").grid(row=0, column=0, padx=8, pady=2, sticky="e")
entry_soll = ttk.Entry(frame_param, width=10); entry_soll.insert(0, "150")
entry_soll.grid(row=0, column=1, padx=4)

ttk.Label(frame_param, text="Kp").grid(row=1, column=0, padx=8, pady=2, sticky="e")
entry_kp = ttk.Entry(frame_param, width=10); entry_kp.insert(0, "1.0")
entry_kp.grid(row=1, column=1, padx=4)

ttk.Label(frame_param, text="Ki").grid(row=2, column=0, padx=8, pady=2, sticky="e")
entry_ki = ttk.Entry(frame_param, width=10); entry_ki.insert(0, "0.05")
entry_ki.grid(row=2, column=1, padx=4)

frame_btn = ttk.Frame(frame_L); frame_btn.pack(pady=4)
btn_start = ttk.Button(frame_btn, text="Regler AUS", command=toggle_controller)
btn_start.grid(row=0, column=0, padx=6)
ttk.Button(frame_btn, text="Integral zurücksetzen", command=reset_integral).grid(row=0, column=1, padx=6)
ttk.Button(frame_btn, text="Pumpe STOP", command=pump_stop).grid(row=0, column=2, padx=6)

frame_ventil = tk.LabelFrame(frame_L, text="Ablassventil  –  Störung",
                              font=("Arial", 10, "bold"), fg="#c0392b")
frame_ventil.pack(pady=6, fill="x")
btn_ventil = tk.Button(frame_ventil, text="Ventil ÖFFNEN  (Störung)",
                       font=("Arial", 12, "bold"), bg="#2ecc71", fg="white",
                       command=toggle_ventil)
btn_ventil.pack(side="left", padx=10, pady=6)
lbl_ventil = tk.Label(frame_ventil, text="Ablassventil: GESCHLOSSEN",
                      font=("Arial", 12), fg="#27ae60")
lbl_ventil.pack(side="left", padx=10)

frame_werte = ttk.LabelFrame(frame_L, text="Messwerte")
frame_werte.pack(pady=4, fill="x")

frame_mv_l = ttk.Frame(frame_werte); frame_mv_l.pack(side="left", padx=20, pady=4)
lbl_ist      = ttk.Label(frame_mv_l, text="Istwert: --- mm",       font=("Arial", 12)); lbl_ist.pack(anchor="w")
lbl_soll     = ttk.Label(frame_mv_l, text="Sollwert: --- mm",      font=("Arial", 12)); lbl_soll.pack(anchor="w")
lbl_out      = ttk.Label(frame_mv_l, text="Pumpenausgang: --- %",  font=("Arial", 12)); lbl_out.pack(anchor="w")
lbl_integral = ttk.Label(frame_mv_l, text="Integral: 0.00",        font=("Arial", 12)); lbl_integral.pack(anchor="w")

frame_mv_r = ttk.Frame(frame_werte); frame_mv_r.pack(side="left", padx=20, pady=4)
lbl_df       = ttk.Label(frame_mv_r, text="Durchfluss: --- V",     font=("Arial", 12)); lbl_df.pack(anchor="w")
lbl_dr       = ttk.Label(frame_mv_r, text="Druck: --- V",          font=("Arial", 12)); lbl_dr.pack(anchor="w")
lbl_fs_unten = tk.Label(frame_mv_r,  text="Schalter unten: ---",   font=("Arial", 12), fg="#555555"); lbl_fs_unten.pack(anchor="w")
lbl_fs_oben  = tk.Label(frame_mv_r,  text="Schalter oben:  ---",   font=("Arial", 12), fg="#555555"); lbl_fs_oben.pack(anchor="w")

fig = Figure(figsize=(7, 5), dpi=100)
ax1 = fig.add_subplot(211); ax1.set_title("Füllstand")
ax2 = fig.add_subplot(212); ax2.set_title("Pumpenausgang")
fig.tight_layout(pad=2.0)
canvas = FigureCanvasTkAgg(fig, master=frame_L)
canvas.draw()
canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

# ── rechte Seite: Kamera + BV-Anzeige ──

frame_cam = ttk.LabelFrame(frame_R_inner, text="ESP32-CAM  –  Wasserstand (Kamera)")
frame_cam.pack(fill="both", expand=True)

# Feste Pixelgröße erzwingen: ohne Bild würde ein Label width/height als
# Zeichen/Zeilen deuten und riesig werden -> Regler würden weggedrückt.
cam_holder = tk.Frame(frame_cam, width=CAM_W, height=CAM_H, bg="black")
cam_holder.pack_propagate(False)
cam_holder.pack(padx=4, pady=4)
lbl_kamera = tk.Label(cam_holder, bg="black")
lbl_kamera.pack(fill="both", expand=True)
lbl_kamera.bind("<ButtonPress-1>",   maus_press)
lbl_kamera.bind("<ButtonRelease-1>", maus_release)

tk.Label(frame_cam, text="← Maus ziehen = ROI neu setzen (grüner Rahmen)",
         font=("Arial", 8), fg="#555555").pack()

# BV-Istwert-Anzeige
lbl_bv_wert = tk.Label(frame_cam, text="Kamera-BV: ---",
                        font=("Arial", 12, "bold"), fg="#888888")
lbl_bv_wert.pack(pady=4)

# Kamera-Buttons
frame_cb = ttk.Frame(frame_cam); frame_cb.pack(pady=2)
btn_wb = tk.Button(frame_cb, text="WB: Auto", bg="#555555", fg="white",
                   font=("Arial", 9), command=cam_wb_umschalten)
btn_wb.grid(row=0, column=0, padx=4)
tk.Button(frame_cb, text="📷 Screenshot", bg="#27ae60", fg="white",
          font=("Arial", 9), command=cam_screenshot).grid(row=0, column=1, padx=4)
btn_video = tk.Button(frame_cb, text="⏺ Video", bg="#3498db", fg="white",
                      font=("Arial", 9), command=cam_video_toggle)
btn_video.grid(row=0, column=2, padx=4)

# Methoden-Auswahl
frame_methode = ttk.LabelFrame(frame_cam, text="Erkennungs-Methode")
frame_methode.pack(fill="x", padx=6, pady=4)
btn_m_hell  = tk.Button(frame_methode, text="Helligkeit",
                         font=("Arial", 9), relief="sunken",
                         command=lambda: set_methode("helligkeit"))
btn_m_hell.pack(side="left", padx=4, pady=3)
btn_m_canny = tk.Button(frame_methode, text="Canny",
                         font=("Arial", 9), relief="raised",
                         command=lambda: set_methode("canny"))
btn_m_canny.pack(side="left", padx=4, pady=3)
btn_m_farbe = tk.Button(frame_methode, text="Farbfilter (HSV)",
                         font=("Arial", 9), relief="raised",
                         command=lambda: set_methode("farbe"))
btn_m_farbe.pack(side="left", padx=4, pady=3)

# Canny-Parameter
frame_canny = ttk.LabelFrame(frame_cam, text="Canny – Parameter")
frame_canny.pack(fill="x", padx=6, pady=2)

ttk.Label(frame_canny, text="T1",   font=("Arial", 8)).grid(row=0, column=0, padx=4, sticky="e")
slider_t1 = tk.Scale(frame_canny, from_=5, to=150, orient="horizontal",
                     length=120, command=canny_update, showvalue=True, highlightthickness=0)
slider_t1.set(canny_t1); slider_t1.grid(row=0, column=1, padx=2)

ttk.Label(frame_canny, text="T2",   font=("Arial", 8)).grid(row=1, column=0, padx=4, sticky="e")
slider_t2 = tk.Scale(frame_canny, from_=10, to=300, orient="horizontal",
                     length=120, command=canny_update, showvalue=True, highlightthickness=0)
slider_t2.set(canny_t2); slider_t2.grid(row=1, column=1, padx=2)

ttk.Label(frame_canny, text="Blur", font=("Arial", 8)).grid(row=2, column=0, padx=4, sticky="e")
slider_blur = tk.Scale(frame_canny, from_=1, to=21, orient="horizontal",
                       length=120, command=canny_update, showvalue=True, highlightthickness=0)
slider_blur.set(blur_kern); slider_blur.grid(row=2, column=1, padx=2)

ttk.Label(frame_canny, text="Tipp: ROI eng um den mittleren Glasbereich ziehen",
          font=("Arial", 7), foreground="#666").grid(
    row=3, column=0, columnspan=2, padx=4, sticky="w")

# HSV-Farbfilter-Parameter (anfangs versteckt)
frame_hsv = ttk.LabelFrame(frame_cam, text="Farbfilter – HSV-Parameter")
# nicht gepackt – wird per set_methode() eingeblendet

def _hsv_row(parent, text, row, from_, to_, init, cmd):
    ttk.Label(parent, text=text, font=("Arial", 8)).grid(row=row, column=0, padx=4, sticky="e")
    s = tk.Scale(parent, from_=from_, to=to_, orient="horizontal", length=120,
                 command=cmd, showvalue=True, highlightthickness=0)
    s.set(init); s.grid(row=row, column=1, padx=2)
    return s

slider_hlo = _hsv_row(frame_hsv, "Hue min",  0,  0, 179, hsv_h_lo, hsv_update)
slider_hhi = _hsv_row(frame_hsv, "Hue max",  1,  0, 179, hsv_h_hi, hsv_update)
slider_slo = _hsv_row(frame_hsv, "Sat min",  2,  0, 255, hsv_s_lo, hsv_update)
slider_vlo = _hsv_row(frame_hsv, "Val min",  3,  0, 255, hsv_v_lo, hsv_update)
ttk.Label(frame_hsv,
          text="Tipp: Hue 0-20 = rot/braun, 20-35 = orange/gelb\n"
               "ROI eng um den Wasserbereich (ohne Glasrand) ziehen",
          font=("Arial", 7), foreground="#666").grid(
    row=4, column=0, columnspan=2, padx=4, sticky="w")

# Helligkeits-Parameter (Standard-Methode für trübes Wasser)
frame_hell = ttk.LabelFrame(frame_cam, text="Helligkeit – Parameter")
frame_hell.pack(fill="x", padx=6, pady=2)   # Standard sichtbar

ttk.Label(frame_hell, text="Empfindlichkeit", font=("Arial", 8)).grid(
    row=0, column=0, padx=4, sticky="e")
slider_hell = tk.Scale(frame_hell, from_=5, to=80, orient="horizontal",
                       length=130, command=hell_update, showvalue=True, highlightthickness=0)
slider_hell.set(hell_schwelle)
slider_hell.grid(row=0, column=1, padx=4)

ttk.Label(frame_hell, text="Konf-Schwelle %", font=("Arial", 8)).grid(
    row=1, column=0, padx=4, sticky="e")
slider_konf = tk.Scale(frame_hell, from_=1, to=30, orient="horizontal",
                       length=130, command=hell_update, showvalue=True, highlightthickness=0)
slider_konf.set(konf_schwelle * 100)
slider_konf.grid(row=1, column=1, padx=4)
ttk.Label(frame_hell, text="← niedriger = stabiler",
          font=("Arial", 7), foreground="#666").grid(row=1, column=2, padx=2, sticky="w")

ttk.Label(frame_hell, text="Hold (Frames)", font=("Arial", 8)).grid(
    row=2, column=0, padx=4, sticky="e")
slider_hold = tk.Scale(frame_hell, from_=1, to=60, orient="horizontal",
                       length=130, command=hell_update, showvalue=True, highlightthickness=0)
slider_hold.set(HOLD_MAX)
slider_hold.grid(row=2, column=1, padx=4)
ttk.Label(frame_hell, text="← Frames halten bei Signalverlust",
          font=("Arial", 7), foreground="#666").grid(row=2, column=2, padx=2, sticky="w")

ttk.Label(frame_hell,
          text="ROI eng um den GESAMTEN Glasinhalt ziehen\n"
               "(Luft oben + Wasser unten, kein Tisch)",
          font=("Arial", 7), foreground="#666").grid(
    row=3, column=0, columnspan=3, padx=4, sticky="w")

# Kalibrierung
frame_kalib = ttk.LabelFrame(frame_cam, text="Kalibrierung (2 Punkte nötig)")
frame_kalib.pack(fill="x", padx=6, pady=4)

ttk.Label(frame_kalib, text="Füllstand jetzt [mm]:", font=("Arial", 9)).grid(
    row=0, column=0, padx=4, sticky="e")
entry_kalib_mm = ttk.Entry(frame_kalib, width=8); entry_kalib_mm.insert(0, "100")
entry_kalib_mm.grid(row=0, column=1, padx=4)
ttk.Button(frame_kalib, text="Punkt setzen",
           command=kalib_punkt_setzen).grid(row=0, column=2, padx=6)
ttk.Button(frame_kalib, text="Löschen",
           command=kalib_loeschen).grid(row=0, column=3, padx=4)

lbl_kalib_info = tk.Label(frame_kalib, text="Keine Kalibrierung",
                           font=("Arial", 8), fg="#888888")
lbl_kalib_info.grid(row=1, column=0, columnspan=4, pady=2, sticky="w", padx=4)

tk.Label(frame_kalib,
         text="1. Füllstand auf Wert 1 bringen → mm eintragen → Punkt setzen\n"
              "2. Füllstand auf Wert 2 bringen → mm eintragen → Punkt setzen",
         font=("Arial", 7), fg="#555555").grid(
    row=2, column=0, columnspan=4, padx=4, sticky="w")

# Fehleranzeige
lbl_error = tk.Label(root, text="", fg="red", font=("Arial", 11))
lbl_error.pack()

# --------------------------------------------------
# Start
# --------------------------------------------------

# Nur das Panel der aktiven Methode zeigen (spart Höhe, konsistenter Zustand)
set_methode(bv_methode)

# ---- TEMP: Layout-Diagnose (druckt in die Konsole, kann später wieder raus) ----
def _diag_layout():
    try:
        print("[DIAG] Fenster:", root.winfo_width(), "x", root.winfo_height(),
              "  Bildschirm:", root.winfo_screenwidth(), "x", root.winfo_screenheight())
        print("[DIAG] lbl_kamera:", lbl_kamera.winfo_width(), "x", lbl_kamera.winfo_height())
        y0 = root.winfo_rooty()
        for name, w in [("frame_cam", frame_cam), ("frame_methode", frame_methode),
                        ("frame_hell", frame_hell), ("slider_hell", slider_hell),
                        ("cam_canvas", cam_canvas)]:
            print(f"[DIAG] {name:14s} mapped={w.winfo_ismapped()} "
                  f"size={w.winfo_width()}x{w.winfo_height()} "
                  f"y_im_Fenster={w.winfo_rooty()-y0}")
        print("[DIAG] scrollregion:", cam_canvas.cget("scrollregion"))
    except Exception as e:
        print("[DIAG] Fehler:", e)
root.after(1500, _diag_layout)
# --------------------------------------------------------------------------------

setze_weissabgleich(0)
threading.Thread(target=mjpeg_thread, daemon=True).start()

regulation()
root.after(40, update_kamera)

try:
    root.mainloop()
finally:
    cam_thread_run = False
    # Aufräumen robust: nach dem Fensterschließen sind Widgets weg -> Fehler abfangen
    try: pump_stop()
    except Exception: pass
    try:
        aw0 = read_register("AW1.0"); aw0 &= 0xFFFE; write_register("AW1.0", aw0)
    except Exception: pass
    try:
        if cam_video_writer is not None:
            cam_video_writer.release()
    except Exception: pass
    try: ser.close()
    except Exception: pass
