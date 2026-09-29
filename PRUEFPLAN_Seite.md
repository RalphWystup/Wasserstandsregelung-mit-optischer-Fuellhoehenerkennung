# Prüfplan — Seite „Wasserstandsregelung mit optischer Füllhöhenerkennung“ (Fassung 1.0, 29.09.2026)

Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic)

Die Seite trägt die Auswertung und die Regelung des Programms `Wasserstandsregelung_Bild_6.py` als JavaScript an einem
gezeichneten Behälter: die Bildauswertung nach der Methode „Helligkeit“ (Graustufen, Gauß 1 × 31, Zeilenmittel, Mittel
über 5 Zeilen, Gradient, Suche in den oberen 85 %, Schwelle −0,3 · Empfindlichkeit, Konfidenz, Halten über 10 Bilder,
Mittel über 12 Bilder, Zweipunktkalibrierung), dazu „Farbfilter (HSV)“ und ein nachgebildetes „Canny“; den PI-Regler
mit Anti-Windup im Takt 0,5 s; die Strecke als PT1 mit Totzeit aus der Messung vom 25.06.2026. Jede Zeile hat eine
Schranke, und jede Schranke ist gerechnet oder gemessen — keine ist geraten.

Prüfmittel für alle Zeilen: `pruefe_seite.mjs` (Playwright, echter Chromium, `file://`-Aufruf der ausgelieferten Seite).

| Nr. | Kriterium | Schranke | Ergebnis |
|:--|:--|:--|:--|
| W1 | keine Konsolenfehler | keine | ok |
| W2 | Werkzeug vor Text: der erste Knopf („Regler“) steht bei 154 px | erster Knopf oberhalb 400 px | ok |
| W3 | Bildauswertung gegen Python: JavaScript findet Zeile 109, `bv_referenz.py` findet Zeile 109 | dieselbe Zeile | ok |
| W4 | Konfidenz 0,2092 gegen 0,2077 — Unterschied 0,0014 | ≤ 0,005 (Rundung auf ganze Graustufen in `cv2.GaussianBlur`) | ok |
| W5 | Zweipunktkalibrierung selbsttätig: Y 255 → 100 mm, Y 63 → 250 mm, 0,78125 mm je Bildpunkt | zwei Punkte gesetzt | ok |
| W6 | Erkennung gegen den gezeichneten Stand: 100 → 100,0 … 100,8; 140 → 140,6; 180 → 180,5; 220 → 220,3; 255 → 255,5 mm — größte Abweichung 0,63 … 0,78 mm in mehreren Läufen (das Rauschen der Zeichnung läuft weiter) | ≤ 3,0 mm | ok |
| W7 | untere Erkennungsgrenze 80,4 mm (die unteren 15 % des ROI werden nicht durchsucht): 12 mm darunter wird nichts gefunden, 12 mm darüber 93,0 mm | die aus der Zeichnung gerechnete Grenze trennt wirklich | ok |
| W8 | zu dunkel (Beleuchtung 0,55): Gradient −5,96 liegt über der Schwelle −9 → Wert wird gehalten und nach 10 Bildern gelöscht | keine Kante mehr angezeigt | ok |
| W9 | Empfindlichkeit auf 12 gesenkt (Schwelle −3,6): Linie wieder gefunden | Linie wieder da | ok |
| W10 | Sollsprung 150 → 200 mm gegen `streckenmodell.py`: Überschwingen 2,62 mm (Python 2,62), bleibende Abweichung 0,002 mm (Python 0,004), Einschwingzeit 81 s (Python 81) | größter Unterschied ≤ 0,2 | ok |
| W11 | Sollwert wird erreicht: bleibende Abweichung 0,002 mm, Überschwingen 2,62 mm bei 50 mm Sprunghöhe | bleibende Abweichung ≤ 0,1 mm, Überschwingen ≤ 5 mm | ok |
| W12 | Störung 1 mm/s gegen `streckenmodell.py`: Einbruch 9,3 mm (Python 9,3), ausgeregelt in 60 s (Python 60), bleibende Abweichung 0,001 mm | größter Unterschied ≤ 0,2; bleibende Abweichung ≤ 0,1 mm | ok |
| W13 | die Verläufe laufen wirklich: zwei Abfragen im Abstand von 1,5 s zeigen andere Werte (Zeit, Bildzähler, Punktzahl) | alle drei Größen gewachsen | ok |
| W14 | laufender Kreis: Sollwert 180 mm über den Schieber gestellt und erreicht | Istwert innerhalb 0,5 mm | ok |
| W15 | Störung im laufenden Betrieb: Ablassventil geöffnet, Einbruch auf 171,4 mm, wieder auf 180,0 mm ausgeregelt, Pumpe von 69,2 % auf 88,8 % | Istwert innerhalb 0,5 mm, Stellgröße gestiegen | ok |
| W16 | Dokumentation in der Seite: 37 000 Zeichen mit Herleitung, Regler, Kalibrierung und der Liste des Offenen | Manuskript vollständig eingebaut | ok |
| W17 | neutralisiert: keine Netzadresse, keine Zugangsdaten; die Kameraadresse steht als `<IP-der-Kamera>` | keine Adresse der Form a.b.c.d, kein Kennwortwert | ok |
| W18 | Kopfzeile: Fassung 1.0 · 29.09.2026 · Prof. Dr.-Ing. Ralph Wystup M.Sc. — erstellt mit KI und Agent (Claude Code, Anthropic) | Fassung, Datum, Name | ok |

## Woher die Schranken kommen

* **3,0 mm (W6).** Die Zeichnung bildet 220 mm auf 282 Bildpunkte ab, also 0,78 mm je Bildpunkt. Die Erkennung mittelt
  über 12 Bilder und schneidet den Mittelwert auf ganze Bildpunkte ab (`int(np.mean(...))` im Programm), was bis zu
  einen Bildpunkt Versatz nach oben ergibt. Die Schranke liegt rund viermal über dieser Auflösung und ist damit auch
  gegen Rauschen und Spiegelung gestellt. Gemessen wurden 0,63 bis 0,78 mm.
* **0,005 (W4).** `cv2.GaussianBlur` rundet in OpenCV jeden Bildpunkt auf ganze Graustufen, bevor das Zeilenmittel
  gebildet wird; die Seite mittelt zuerst und glättet dann (beides linear, also vertauschbar) und rundet dabei nicht.
  Der Unterschied im Helligkeitsprofil bleibt unter 0,3 Graustufen und wirkt sich auf die Konfidenz mit 0,0014 aus.
* **0,2 (W10, W12).** Beide Wege rechnen denselben Algorithmus; übrig bleiben die Rundungen von `round()` in Python
  gegen `Math.round()` in JavaScript. Erreicht wurden 0,002 beim Sollsprung und 0,000 bei der Störung.
* **0,1 mm (W11, W12).** Die Stufe des Ultraschallwerts im Programm beträgt 220/32760 mm = 0,0067 mm; die bleibende
  Abweichung kann darunter nicht sinnvoll geprüft werden. 0,1 mm ist das Fünfzehnfache.
* **0,5 mm (W14, W15).** Der laufende Kreis wird im Zeitraffer beobachtet und zu einem beliebigen Zeitpunkt abgefragt;
  0,5 mm ist der Rest der abklingenden Schwingung nach der geforderten Wartezeit.
* **400 px (W2).** Der erste Bedienknopf muss ohne Blättern sichtbar sein.

## Was die Prüfung nicht prüft

* **Die Methode „Canny“ ist nachgebildet, nicht wörtlich übertragen** (Gauß, Sobel, Nicht-Maximum-Unterdrückung,
  Hysterese — der Standardablauf, den auch `cv2.Canny` geht, aber nicht Bit für Bit dieselbe Rechnung). Sie ist in der
  Seite bedienbar; eine zahlenmäßige Übereinstimmung mit OpenCV wird nicht behauptet und nicht geprüft.
* **Die Methode „Farbfilter (HSV)“ ist wörtlich übertragen**, aber die Formoperation `MORPH_CLOSE` mit einem Rechteck
  5 × 3 wirkt in der Seite nur in Zeilenrichtung (die Breite 5 fällt bei der Zeilensumme ohnehin heraus, die Höhe 3
  ist nachgebildet). Das ist im Quelltext an der Stelle vermerkt.
* **Die Bildauswertung ist an gezeichneten Bildern geprüft, nicht an Kamerabildern der Anlage.** Damit ist gezeigt, dass
  die Seite rechnet, was das Programm rechnet — nicht, wie genau das Verfahren an der Anlage arbeitet.
* **Es gibt keine Messung am geschlossenen Kreis.** Alle Aussagen über Überschwingen, Einschwingzeit und
  Störausregelung sind gerechnet. Zwei unabhängige Rechenwege ersetzen keine dritte Messung.
* Die Versuche W10 und W12 bilden die Referenzsimulation aus `streckenmodell.py` Zug um Zug nach — einschließlich
  zweier Eigenheiten, die dort aus dem Aufbau der Funktion folgen: der Lauf beginnt mit `soll_prev = None` (der
  Sollsprung löst also keinen Integral-Reset aus) und mit leerem Totzeitpuffer (die Pumpe setzt zu Beginn für 1,25 s
  aus). Im laufenden Betrieb der Seite gilt dagegen das Verhalten des Programms.

Stand: siehe `pruefe_seite.json` · 0 Beanstandung(en) bei 18 Kriterien. Bildschirmfotos angesehen (Laborseite mit
gezeichnetem Behälter, erkannter Wasserlinie und laufenden Verläufen; Störungsverlauf; Probe der Bildauswertung und
Kennzahlentafel; Dokumentationsreiter).
