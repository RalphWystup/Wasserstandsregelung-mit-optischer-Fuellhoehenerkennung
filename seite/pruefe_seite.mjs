// Prüfung der Seite „Wasserstandsregelung mit optischer Füllhöhenerkennung“ im echten Browser (Chromium, Playwright).
// Geprüft wird, was die Seite behauptet: keine Konsolenfehler; Werkzeug vor Text; die Bildauswertung rechnet dasselbe wie
// die wörtlich aus dem Programm herausgeschnittene Python-Fassung; die Erkennung liest die gezeichnete Füllhöhe (Schranke
// in mm); der Kreis erreicht den Sollwert (Überschwingen und bleibende Abweichung mit Schranke); eine Störung wird
// ausgeregelt; die Verläufe laufen wirklich (zwei Abfragen im Abstand); die Dokumentation ist da und neutralisiert.
// Ergebnis: pruefe_seite.json (+ Bildschirmfotos im Ablageordner, die angesehen werden).
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require('/tmp/node_modules/playwright');
const H = '/workspace/Wasserstand/Seite/';
const V = fs.readFileSync(H + 'VERSION', 'utf8').trim();
const S = '/tmp/claude-1000/-workspace/905236e7-aea4-4c03-805a-5e5668f5230d/scratchpad/';

let fehler = 0; const BEF = [];
const sage = (gut, t) => { console.log(`  ${gut ? 'ok    ' : 'FEHLER'} ${t}`); BEF.push({ gut, text: t }); if (!gut) fehler++; };

const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } });
const konsole = [];
p.on('pageerror', e => konsole.push(e.message));
p.on('console', m => { if (m.type() === 'error') konsole.push(m.text()); });
await p.goto(`file://${H}Wasserstand_${V}.html`, { waitUntil: 'load', timeout: 180000 });
await p.waitForFunction(() => window.LABOR && window.LABOR.laufend, null, { timeout: 60000 });
await p.waitForTimeout(600);

// --- W1 --------------------------------------------------------------------------------------------------------
sage(konsole.length === 0, 'keine Konsolenfehler' + (konsole.length ? ': ' + konsole[0].slice(0, 160) : ''));

// --- W2 Werkzeug vor Text --------------------------------------------------------------------------------------
const lage = await p.evaluate(() => document.getElementById('regler').getBoundingClientRect().top);
sage(lage < 400, `Werkzeug vor Text: erster Knopf („Regler“) bei ${lage.toFixed(0)} px`);

// --- W3 Probe der Bildauswertung gegen bv_referenz.py -----------------------------------------------------------
const pr = await p.evaluate(() => window.LABOR.probe);
const sK = await p.evaluate(() => DATEN.schranke_probe_konf);
sage(pr.zeile_gleich, `Bildauswertung: JavaScript findet Zeile ${pr.zeile_js}, Python ${pr.zeile_py}`);
sage(pr.konf_abweichung <= sK, `Konfidenz ${pr.konf_js.toFixed(4)} gegen ${pr.konf_py.toFixed(4)} — Unterschied ${pr.konf_abweichung.toFixed(4)} (Schranke ${sK})`);

// --- W4 Kalibrierung -------------------------------------------------------------------------------------------
const kal = await p.evaluate(() => window.LABOR.kalibrierung);
sage(kal && kal.punkte.length === 2, `Zweipunktkalibrierung: ${kal ? kal.punkte.map(q => `Y ${q[0]} → ${q[1]} mm`).join(', ') : 'fehlt'} (${kal ? kal.mm_je_pixel : '—'} mm je Bildpunkt)`);

// --- W5 die Erkennung liest die gezeichnete Füllhöhe ------------------------------------------------------------
const setz = async (id, v) => p.evaluate(([id, v]) => { const e = document.getElementById(id); e.value = v; e.dispatchEvent(new Event('input')); }, [id, v]);
const sM = await p.evaluate(() => DATEN.schranke_kamera_mm);
const mess = [];
for (const hz of [100, 140, 180, 220, 255]) {
  await p.evaluate(h => {                     // Füllstand setzen und die 12 Bilder der Glättung durchlaufen lassen
    S.h = h; BV.puffer.length = 0; BV.pixel_y = null;
    for (let i = 0; i < BV.GLAETT_N + 3; i++) { zeichneBehaelter(ctx, h, bel, rausch, spiegel); bv_verarbeite(ctx); }
  }, hz);
  const e = await p.evaluate(() => ({ mm: BV.mm, konf: BV.konf }));
  mess.push({ soll: hz, mm: e.mm, abw: e.mm === null ? null : +(e.mm - hz).toFixed(2), konf: +e.konf.toFixed(3) });
}
const schlimmst = Math.max(...mess.map(m => m.abw === null ? 999 : Math.abs(m.abw)));
sage(schlimmst <= sM, `Erkennung gegen den gezeichneten Stand: ${mess.map(m => `${m.soll}→${m.mm === null ? '—' : m.mm.toFixed(1)}`).join(', ')} mm; größte Abweichung ${schlimmst.toFixed(2)} mm (Schranke ${sM} mm)`);

// --- W5b die gerechnete untere Erkennungsgrenze stimmt mit dem Verhalten überein ------------------------------
const gr = await p.evaluate(() => window.LABOR.grenzen);
const unten = await p.evaluate(async g => {
  const probe = h => { BV.puffer.length = 0; BV.pixel_y = null; BV.mm = null;
    for (let i = 0; i < BV.GLAETT_N + 3; i++) { zeichneBehaelter(ctx, h, bel, rausch, spiegel); bv_verarbeite(ctx); }
    return BV.mm; };
  return { drunter: probe(g.unterste_erkennbare_hoehe_mm - 12), drueber: probe(g.unterste_erkennbare_hoehe_mm + 12) };
}, gr);
sage(unten.drunter === null && unten.drueber !== null,
  `untere Erkennungsgrenze ${gr.unterste_erkennbare_hoehe_mm} mm (untere 15 % des ROI werden nicht durchsucht): 12 mm darunter nichts gefunden, 12 mm darüber ${unten.drueber === null ? 'nichts' : unten.drueber.toFixed(1) + ' mm'}`);

// --- W6 die Methode hält bei zu schwachem Bild und meldet das ----------------------------------------------------
await setz('s_bel', 55);
await p.evaluate(() => { for (let i = 0; i < BV.HOLD_MAX + 4; i++) { zeichneBehaelter(ctx, S.h, bel, rausch, spiegel); bv_verarbeite(ctx); } });
const dunkel = await p.evaluate(() => ({ pixel: BV.pixel_y, hold: BV.hold, grad: BV.letztZusatz.min_grad, schwelle: BV.letztZusatz.schwelle }));
sage(dunkel.pixel === null, `zu dunkel (Beleuchtung 0,55): Gradient ${dunkel.grad === undefined ? '—' : dunkel.grad.toFixed(2)} über der Schwelle ${dunkel.schwelle} → gehalten und dann gelöscht`);
await setz('s_hell', 12);
await p.evaluate(() => { for (let i = 0; i < BV.GLAETT_N + 3; i++) { zeichneBehaelter(ctx, S.h, bel, rausch, spiegel); bv_verarbeite(ctx); } });
const gerettet = await p.evaluate(() => BV.pixel_y);
sage(gerettet !== null, `Empfindlichkeit auf 12 gesenkt: Linie wieder gefunden (Zeile ${gerettet})`);
await setz('s_hell', 30); await setz('s_bel', 100);

// --- W7 Versuch: Sollsprung, gegen die Python-Rechnung -----------------------------------------------------------
await p.click('#v_sprung'); await p.waitForTimeout(200);
const vs = await p.evaluate(() => window.LABOR.versuch.sprung);
sage(vs.groesster_unterschied <= vs.schranke,
  `Sollsprung 150 → 200 mm: Überschwingen ${vs.js.ueberschwingen_mm} mm (Python ${vs.python.ueberschwingen_mm}), bleibende Abweichung ${vs.js.bleibende_abweichung_mm} mm (Python ${vs.python.bleibende_abweichung_mm}), Einschwingzeit ${vs.js.einschwingzeit_s} s — größter Unterschied ${vs.groesster_unterschied} (Schranke ${vs.schranke})`);
sage(vs.js.bleibende_abweichung_mm <= 0.1 && vs.js.ueberschwingen_mm <= 5.0,
  `Sollwert erreicht: bleibende Abweichung ${vs.js.bleibende_abweichung_mm} mm (Schranke 0,1 mm), Überschwingen ${vs.js.ueberschwingen_mm} mm (Schranke 5 mm)`);

// --- W8 Versuch: Störung ----------------------------------------------------------------------------------------
await p.click('#v_stoerung'); await p.waitForTimeout(200);
const vt = await p.evaluate(() => window.LABOR.versuch.stoerung);
sage(vt.groesster_unterschied <= vt.schranke && vt.js.bleibende_abweichung_mm <= 0.1,
  `Störung ${vt.python.q_v_mm_je_s} mm/s: Einbruch ${vt.js.groesste_abweichung_mm} mm (Python ${vt.python.groesste_abweichung_mm}), ausgeregelt in ${vt.js.einschwingzeit_s} s, bleibende Abweichung ${vt.js.bleibende_abweichung_mm} mm — größter Unterschied ${vt.groesster_unterschied} (Schranke ${vt.schranke})`);

// --- W9 die Verläufe laufen wirklich ------------------------------------------------------------------------------
const a1 = await p.evaluate(() => ({ t: window.LABOR.kreis.t, rahmen: window.LABOR.rahmen, punkte: window.LABOR.kreis.punkte }));
await p.waitForTimeout(1500);
const a2 = await p.evaluate(() => ({ t: window.LABOR.kreis.t, rahmen: window.LABOR.rahmen, punkte: window.LABOR.kreis.punkte }));
sage(a2.t > a1.t && a2.rahmen > a1.rahmen && a2.punkte >= a1.punkte,
  `Verläufe laufen: Zeit ${a1.t} s → ${a2.t} s, Bilder ${a1.rahmen} → ${a2.rahmen}, Punkte ${a1.punkte} → ${a2.punkte} (in 1,5 s)`);

// --- W10 der laufende Kreis folgt einem Sollsprung ------------------------------------------------------------------
await setz('s_raffer', 100); await setz('s_soll', 180);
await p.waitForFunction(() => Math.abs(window.LABOR.kreis.mess - 180) < 0.5 && window.LABOR.kreis.t > 200, null, { timeout: 180000 });
const l1 = await p.evaluate(() => window.LABOR.kreis);
sage(Math.abs(l1.mess - 180) < 0.5, `laufender Kreis: Sollwert 180 mm erreicht (Istwert ${l1.mess} mm, Pumpe ${l1.u} %, Schranke 0,5 mm)`);
await p.screenshot({ path: S + 'wasserstand_labor.png', fullPage: false });

// --- W11 eine Störung wird im laufenden Betrieb ausgeregelt -------------------------------------------------------
const vorher = await p.evaluate(() => window.LABOR.kreis.t);
await p.click('#ventil');
await p.waitForFunction(t0 => window.LABOR.kreis.t > t0 + 30 && window.LABOR.kreis.mess < 179.0, vorher, { timeout: 180000 });
const tief = await p.evaluate(() => window.LABOR.kreis.mess);
await p.waitForFunction(t0 => window.LABOR.kreis.t > t0 + 250 && Math.abs(window.LABOR.kreis.mess - 180) < 0.5, vorher, { timeout: 240000 });
const nachher = await p.evaluate(() => window.LABOR.kreis);
sage(Math.abs(nachher.mess - 180) < 0.5 && nachher.u > l1.u,
  `Störung im Betrieb: Einbruch bis ${tief.toFixed(1)} mm, wieder auf ${nachher.mess} mm ausgeregelt, Pumpe von ${l1.u} % auf ${nachher.u} % (Schranke 0,5 mm)`);
await p.screenshot({ path: S + 'wasserstand_stoerung.png', fullPage: false });
await p.click('#ventil');

// --- W12 Dokumentation ---------------------------------------------------------------------------------------------
await p.click('#r_doku'); await p.waitForTimeout(400);
await p.screenshot({ path: S + 'wasserstand_doku.png', fullPage: false });
const doku = (await p.evaluate(() => document.getElementById('t_doku').textContent)).replace(/\s+/g, ' ');
sage(doku.includes('Torricelli') && doku.includes('Anti-Windup') && doku.includes('Zweipunktkalibrierung') && doku.includes('Was offen ist') && doku.length > 20000,
  `Dokumentation in der Seite: ${(doku.length / 1000).toFixed(0)} Tausend Zeichen, Herleitung, Regler, Kalibrierung und die Liste des Offenen`);
const ganz = await p.evaluate(() => document.body.textContent);
sage(!/\b(?:\d{1,3}\.){3}\d{1,3}\b/.test(ganz) && ganz.includes('<IP-der-Kamera>') && !/passwor[dt]\s*[:=]/i.test(ganz),
  'neutralisiert: keine Netzadresse, keine Zugangsdaten — die Kameraadresse steht als Platzhalter');

// --- W13 Kopfzeile ----------------------------------------------------------------------------------------------
const kopf = await p.$eval('#fassung', e => e.textContent);
sage(kopf.includes(`Fassung ${V}`) && kopf.includes('29.09.2026') && kopf.includes('Ralph Wystup'), `Kopf: ${kopf}`);

await p.click('#r_labor'); await p.waitForTimeout(300);
await p.evaluate(() => window.scrollTo(0, document.getElementById('probe').getBoundingClientRect().top + window.scrollY - 120));
await p.waitForTimeout(300);
await p.screenshot({ path: S + 'wasserstand_probe.png', fullPage: false });
await b.close();

fs.writeFileSync(H + 'pruefe_seite.json', JSON.stringify({
  datum: new Date().toISOString(), fassung: V, befunde: BEF, fehler,
  messreihe_erkennung: mess, schranke_kamera_mm: sM, probe: pr
}, null, 1));
console.log(fehler ? `${fehler} Beanstandung(en)` : 'alles in Ordnung');
process.exit(fehler ? 1 : 0);
