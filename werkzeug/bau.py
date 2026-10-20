#!/usr/bin/env python3
"""Baut die Bilder fürs GitHub-Profil in der Welt von mia-gruenwald.dev (DESIGN.md dort):
Verstärker-Blech oben und unten, dazwischen das Homelab als Pedalboard.
Je Bild eine breite und eine schmale Fassung fürs Handy (README wählt per <picture>).
Schrift ist Archivo, als Glyphen-Pfade eingebettet, weil GitHub Bilder ohne Webfonts zeigt.
Aufruf: python3 werkzeug/bau.py            alles nach bilder/ (Pegel braucht GITHUB_TOKEN)
        python3 werkzeug/bau.py --pegel DIR  nur den Pegel, für die tägliche Action"""
import json
import math
import os
import subprocess
import sys
import urllib.request
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.svgPathPen import SVGPathPen

HIER = Path(__file__).resolve().parent
SCHRIFT = HIER / "schrift" / "archivo-wdth.woff2"   # Archivo, SIL OFL 1.1 (schrift/OFL.txt)
LOGO = HIER / "logo.svg"                               # dasselbe Logo wie auf mia-gruenwald.dev
ZIEL = HIER.parent / "bilder"

F = dict(tolex="#141010", tolex_raute="#1c1616", blech="#0b0909", blech_kante="#241d1d", platte="#1a1515",
         kabel="#3a3030", rand="#3a3030", text="#f3ece9", leise="#b9aba7", karmin="#c8102e", ochsenblut="#6e1019",
         pedal_schwarz="#221c1c", alu="#cdc8c4", alu_tinte="#1b1515", chrom="#8d8783", led_an="#ff3347",
         led_aus="#3b0f15", led_aus_alu="#5a1a21", schalter="#c2bcb8", schalter_rand="#6d6763", regler="#0f0c0c")
KURVE = "cubic-bezier(.16,1,.3,1)"

# Inhalt wie src/data/homelab.js der Website, je Gruppe drei Pedale, damit die Spalten über alle Reihen fluchten.
G = {"betrieb": ("Betrieb und Sicherung", "alu", ["PBS", "Kuma", "NetBox"]),
     "zugang": ("Zugang", "schwarz", ["Authentik", "Vaultwarden", "Infisical"]),
     "eigen": ("Eigene Anwendungen", "rot", ["Mia OS", "WG OS", "Website"]),
     "daten": ("Daten und Medien", "schwarz", ["Nextcloud", "Immich", "Jellyfin"]),
     "ki": ("KI", "rot", ["Jana", "SearXNG", "Notebook"]),
     "spielen": ("Spielen", "alu", ["MC-Router", "Create", "Otherworld"])}
REIHEN_BREIT = [["betrieb", "zugang"], ["eigen", "daten"], ["ki", "spielen"]]
REIHEN_SCHMAL = [["eigen"], ["betrieb"], ["zugang"], ["daten"], ["ki"], ["spielen"]]
GEWAEHLT = ("eigen", 0)        # Mia OS leuchtet
PB, PH, FUGE, GRUPPE = 74, 118, 8, 34
ZEILE = PH + 64                # Pedal, Schiene, Beschriftung, Luft zur nächsten Reihe


# ---------------------------------------------------------------- Schrift
@lru_cache(None)
def schnitt(wght, wdth):
    return instantiateVariableFont(TTFont(SCHRIFT), {"wght": wght, "wdth": wdth})


GLYPHEN = {}   # id -> Pfad in Schrifteinheiten, je Datei neu


def breite(s, gr, wght, wdth, sperr=0.0):
    f = schnitt(wght, wdth); gs = f.getGlyphSet(); cm = f.getBestCmap()
    return sum(gs[cm[ord(c)]].width for c in s) * gr / f["head"].unitsPerEm + sperr * gr * (len(s) - 1)


def text(s, x, y, gr, wght, wdth, farbe, sperr=0.0, anker="start"):
    """Text als <use> auf einmal definierte Glyphen. y ist die Grundlinie."""
    f = schnitt(wght, wdth); gs = f.getGlyphSet(); cm = f.getBestCmap(); em = f["head"].unitsPerEm
    x -= {"start": 0, "middle": .5, "end": 1}[anker] * breite(s, gr, wght, wdth, sperr)
    teile, lauf = [], 0.0
    for c in s:
        g = cm[ord(c)]
        gid = f"g{wght}-{wdth}-{g}"
        if gid not in GLYPHEN:
            stift = SVGPathPen(gs, ntos=lambda v: str(round(v)))
            gs[g].draw(stift)
            GLYPHEN[gid] = stift.getCommands()
        if GLYPHEN[gid]:
            teile.append(f'<use href="#{gid}" x="{round(lauf)}"/>')
        lauf += gs[g].width + sperr * em
    return f'<g fill="{farbe}" transform="translate({x:.1f} {y:.1f}) scale({gr/em:.5f} {-gr/em:.5f})">{"".join(teile)}</g>'


def siebdruck(s, x, y, gr, farbe=F["leise"], wdth=75, wght=650, sperr=0.07, anker="start"):
    return text(s.upper(), x, y, gr, wght, wdth, farbe, sperr, anker)


FILTER = (f'<pattern id="tolex" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="{F["tolex"]}"/>'
          f'<path d="M0 0L6 6M6 0L0 6" stroke="{F["tolex_raute"]}"/></pattern>'
          '<filter id="schatten" x="-20%" y="-20%" width="140%" height="160%">'
          '<feDropShadow dx="0" dy="2" stdDeviation="1" flood-color="#000" flood-opacity=".6"/>'
          '<feDropShadow dx="0" dy="9" stdDeviation="6" flood-color="#000" flood-opacity=".55"/></filter>')


def svg(b, h, innen, titel, stil=""):
    defs = "".join(f'<path id="{k}" d="{v}"/>' for k, v in GLYPHEN.items() if v)
    GLYPHEN.clear()
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {b:g} {h:g}" width="{b:g}" height="{h:g}" role="img">'
            f'<title>{titel}</title><defs>{defs}{FILTER}</defs>{f"<style>{stil}</style>" if stil else ""}{innen}</svg>\n')


# ---------------------------------------------------------------- Bauteile
def logo(x, y, hoehe):
    roh = Path(LOGO).read_text()
    vb = [float(v) for v in roh.split('viewBox="')[1].split('"')[0].split()]
    sk = hoehe / vb[3]
    innen = roh.split(">", 1)[1].rsplit("</svg>", 1)[0]
    return f'<g transform="translate({x:.1f} {y:.1f}) scale({sk:.5f}) translate({-vb[0]:g} {-vb[1]:g})">{innen}</g>', vb[2] * sk


def schraube(x, y):
    return (f'<circle cx="{x:g}" cy="{y:g}" r="4.5" fill="#2a2323" stroke="#0f0b0b"/>'
            f'<path d="M{x-3:g} {y+1.2:g}L{x+3:g} {y-1.2:g}" stroke="#0f0b0b" stroke-width="1.3"/>')


def buchse(x, y, d):
    return (f'<circle cx="{x:g}" cy="{y:g}" r="{d/2:g}" fill="{F["chrom"]}"/><circle cx="{x:g}" cy="{y:g}" r="{d/2-4:g}" fill="#1c1717"/>'
            f'<circle cx="{x:g}" cy="{y:g}" r="{d/2-7:g}" fill="#050404"/>')


def regler(x, y, r, winkel, chrom=False):
    a = math.radians(winkel - 90)
    return (f'<circle cx="{x:g}" cy="{y:g}" r="{r+1.5:g}" fill="#000" opacity=".5"/>'
            f'<circle cx="{x:g}" cy="{y:g}" r="{r:g}" fill="{F["regler"]}" stroke="{F["chrom"] if chrom else "#2b2424"}" stroke-width="{1.5 if chrom else 1}"/>'
            f'<path d="M{x+math.cos(a)*r*.25:.1f} {y+math.sin(a)*r*.25:.1f}L{x+math.cos(a)*r*.85:.1f} {y+math.sin(a)*r*.85:.1f}" '
            f'stroke="{F["text"]}" stroke-width="{max(1.6, r*.16):.1f}" stroke-linecap="round"/>')


def lampe(x, y, r, wort_y, gr):
    return (f'<circle cx="{x:g}" cy="{y:g}" r="{r:g}" fill="{F["chrom"]}"/><circle cx="{x:g}" cy="{y:g}" r="{r*.72:g}" fill="#1c1717"/>'
            f'<circle cx="{x:g}" cy="{y:g}" r="{r*.57:g}" fill="{F["led_an"]}" stroke="#ff8a96"/>' + siebdruck("An", x, wort_y, gr, anker="middle"))


NAMEN_GROESSE = {}


def pedal(x, y, name, art, nr, zustand=None, verz=0.0):
    """Feste Anatomie: zwei Regler oben, Name, LED-Zeile mit Wort, Fußschalter."""
    farbe = {"rot": F["ochsenblut"], "schwarz": F["pedal_schwarz"], "alu": F["alu"]}[art]
    tinte = F["alu_tinte"] if art == "alu" else F["text"]
    y += 1 if zustand else 0                                   # gedrückt sitzt 1px tiefer
    g = [f'<rect filter="url(#schatten)" x="{x:g}" y="{y:g}" width="{PB}" height="{PH}" rx="7" fill="{farbe}"/>',
         f'<rect x="{x+.5:g}" y="{y+.5:g}" width="{PB-1}" height="{PH-1}" rx="6.5" fill="none" stroke="#fff" stroke-opacity="{.22 if art=="alu" else .1}"/>',
         f'<path d="M{x+6:g} {y+PH-1.5:g}H{x+PB-6:g}" stroke="#000" stroke-opacity=".28" stroke-width="2"/>']
    for k, dx in enumerate((22, 52)):                          # Reglerstellung fest aus der Nummer
        g.append(regler(x + dx, y + 20, 9, (nr * 67 + k * 113) % 270 - 135))
    gr, sp = 12, .04
    while breite(name.upper(), gr, 700, 62, sp) > PB - 10:
        if sp > 0:
            sp = max(0, sp - .01)
        else:
            gr -= .25
    NAMEN_GROESSE[name] = gr
    g.append(text(name.upper(), x + PB / 2, y + 53, gr, 700, 62, tinte, sp, "middle"))
    ly = y + 73
    # LED in einer Fassung, damit sie auch aus auf dunklem Gehäuse sichtbar ist
    fassung = f'<circle cx="{{cx:.1f}}" cy="{ly:g}" r="5.5" fill="#0b0909" stroke="{"#9a938f" if art == "alu" else "#4a3e3e"}"/>'
    aus = F["led_aus_alu"] if art == "alu" else F["led_aus"]
    if zustand:
        wb = breite(zustand.upper(), 10, 700, 75, .08)
        lx = x + PB / 2 - (wb + 12) / 2 + 4
        g.append(fassung.format(cx=lx) + f'<circle cx="{lx:.1f}" cy="{ly:g}" r="3.5" fill="{aus}"/>')
        g.append(f'<g class="an" style="animation-delay:{verz:.2f}s"><circle cx="{lx:.1f}" cy="{ly:g}" r="3.5" fill="{F["led_an"]}"/>'
                 f'<circle cx="{lx:.1f}" cy="{ly:g}" r="7" fill="{F["led_an"]}" opacity=".18"/>'
                 + text(zustand.upper(), lx + 9, ly + 3.6, 10, 700, 75, tinte, .08) + "</g>")
    else:
        g.append(fassung.format(cx=x + PB / 2) + f'<circle cx="{x+PB/2:g}" cy="{ly:g}" r="3.5" fill="{aus}"/>')
    g.append(f'<circle cx="{x+PB/2:g}" cy="{y+97:g}" r="{12*(.94 if zustand else 1):.1f}" fill="{F["schalter"]}" stroke="{F["schalter_rand"]}" stroke-width="3"/>')
    return "".join(g)


def gruppen_breite(n):
    return n * PB + (n - 1) * FUGE


def reihen_setzen(reihen, x0, y0, takt):
    """Gruppen auf festen Spalten setzen. Gibt Pedale, Schienen und Anker (x, y, breite) je Gruppe zurück."""
    pedale, schienen, anker, nr = [], [], {}, 0
    for ri, reihe in enumerate(reihen):
        y, x = y0 + ri * ZEILE, x0
        for k in reihe:
            name, art, dienste = G[k]
            gb = gruppen_breite(len(dienste))
            anker[k] = (x, y, gb)
            for pi, n in enumerate(dienste):
                gew = (k, pi) == GEWAEHLT
                pedale.append(pedal(x + pi * (PB + FUGE), y, n, art, nr, "An" if gew else None, takt + .25 if gew else 0))
                nr += 1
            sy = y + PH + 10
            schienen.append(f'<rect x="{x:g}" y="{sy:g}" width="{gb}" height="2" fill="{F["kabel"]}"/>')
            if k == GEWAEHLT[0]:
                schienen.append(f'<rect class="fuell" style="animation-delay:{takt:.2f}s;transform-origin:{x:g}px 0" '
                                f'x="{x:g}" y="{sy:g}" width="{gb}" height="2" fill="{F["karmin"]}"/>')
            schienen.append(siebdruck(name, x, sy + 19, 12))
            x += gb + GRUPPE
    return pedale, schienen, anker


STIL = (f".zieh{{stroke-dasharray:1;animation:zieh .42s {KURVE} both}}@keyframes zieh{{from{{stroke-dashoffset:1}}to{{stroke-dashoffset:0}}}}"
        f".an{{animation:an .2s {KURVE} both}}@keyframes an{{from{{opacity:0}}to{{opacity:1}}}}"
        f".fuell{{animation:fuell .4s {KURVE} both}}@keyframes fuell{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}"
        "@media (prefers-reduced-motion:reduce){.zieh,.an,.fuell{animation:none}}")


def kabel(zug):
    """zug: Liste (Pfad, aktiv). Ruhende Kabel grau, die aktive Kette rot und nacheinander gezogen."""
    ruhe = "".join(f'<path d="{d}" fill="none" stroke="#4a3d3d" stroke-width="5" stroke-linecap="round"/>' for d, a in zug if not a)
    rot = "".join(f'<path class="zieh" pathLength="1" style="animation-delay:{.5 + i*.11:.2f}s" d="{d}" fill="none" stroke="{F["karmin"]}" '
                  f'stroke-width="7" stroke-linecap="round"/>' for i, d in enumerate(d for d, a in zug if a))
    return ruhe + rot


def input_kasten(x, y, b, h=58, buchse_x=None):
    """Flach (h=58): Buchse links, Text daneben. Hoch: Text oben, Buchse unten über buchse_x, dort geht das Kabel ab."""
    g = [f'<rect filter="url(#schatten)" x="{x:g}" y="{y:g}" width="{b:g}" height="{h:g}" rx="6" fill="{F["blech"]}" stroke="{F["karmin"]}"/>']
    if buchse_x is None:
        m = y + h / 2
        return g + [buchse(x + 30, m, 26), siebdruck("Input", x + 54, m - 5, 12), text("Internet", x + 54, m + 15, 16, 700, 100, F["text"])]
    m = y + h / 2
    return g + [buchse(buchse_x, m, 32), siebdruck("Input", buchse_x + 30, m - 8, 12), text("Internet", buchse_x + 30, m + 18, 24, 800, 75, F["text"], .01)]


TYPENSCHILD = ("HPE ProLiant ML350p Gen8", "2 × Xeon E5-2630", "128 GB ECC", "über 40 Container und VMs")


def typenschild(x, y, b, h):
    g = [f'<rect filter="url(#schatten)" x="{x:g}" y="{y:g}" width="{b:g}" height="{h:g}" rx="6" fill="{F["platte"]}" stroke="{F["rand"]}"/>',
         schraube(x + 9, y + 9), schraube(x + b - 9, y + 9), schraube(x + 9, y + h - 9), schraube(x + b - 9, y + h - 9)]
    oben = y + (h - 104) / 2                                   # Block senkrecht mittig
    g.append(siebdruck("Proxmox VE 9", x + 22, oben + 14, 13, F["text"], wght=750))
    g += [text(z, x + 22, oben + 40 + i * 19, 13, 400, 100, F["leise"]) for i, z in enumerate(TYPENSCHILD)]
    return g


# ---------------------------------------------------------------- Board
def board_breit():
    rand, spalt = 28, 52
    ketten_luecke = 40                                         # zwischen OPNsense und Proxy, Platz fürs Kabel
    lb = math.ceil(max(2 * PB + ketten_luecke, max(breite(z, 13, 400, 100) for z in TYPENSCHILD) + 44))
    ketten_luecke = lb - 2 * PB                                # Pedale bündig mit Input und Typenschild
    rb = max(sum(gruppen_breite(len(G[k][2])) for k in r) + GRUPPE * (len(r) - 1) for r in REIHEN_BREIT)
    b = rand + lb + spalt + rb + rand
    h = rand + len(REIHEN_BREIT) * ZEILE - (ZEILE - PH - 38) + rand
    rx0 = rand + lb + spalt
    zeilen_y = [rand + i * ZEILE for i in range(len(REIHEN_BREIT))]
    # Linke Spalte auf dem Reihenraster: Input in Reihe 1, Kette in Reihe 2, Typenschild in Reihe 3
    k0 = rand + (lb - 2 * PB - ketten_luecke) / 2
    opn_x, prx_x = k0, k0 + PB + ketten_luecke
    ky = zeilen_y[1]
    eingang = input_kasten(rand, zeilen_y[0], lb, PH, opn_x + PB / 2)
    links = []
    zug = [(f"M{opn_x+PB/2:g} {zeilen_y[0]+PH/2:g}V{ky:g}", True),
           (f"M{opn_x+PB:g} {ky+PH/2:g}H{prx_x:g}", True)]
    links.append(pedal(opn_x, ky, "OPNsense", "rot", 90, "Durch", .5 + .11 + .25))
    links.append(pedal(prx_x, ky, "Proxy", "schwarz", 91, "Durch", .5 + .22 + .25))
    links += typenschild(rand, zeilen_y[2], lb, h - rand - zeilen_y[2])
    pedale, schienen, anker = reihen_setzen(REIHEN_BREIT, rx0, rand, .5 + 3 * .11 + .2)
    # Vom Proxy je Reihe ein Kabel aus eigenem Ausgang, dazu Brücken zwischen den Gruppen einer Reihe
    for ri, reihe in enumerate(REIHEN_BREIT):
        x, y, gb = anker[reihe[0]]
        ay = ky + PH / 2 + (ri - 1) * 30
        mx = rand + lb + spalt / 2
        aktiv = reihe[0] == GEWAEHLT[0]
        d = f"M{prx_x+PB:g} {ay:g}H{x-2:g}" if ay == y + PH / 2 else f"M{prx_x+PB:g} {ay:g}C{mx:g} {ay:g} {mx:g} {y+PH/2:g} {x-2:g} {y+PH/2:g}"
        zug.append((d, aktiv))
        for a, z in zip(reihe, reihe[1:]):
            ax, ay2, agb = anker[a]
            zug.append((f"M{ax+agb+2:g} {ay2+PH/2:g}H{anker[z][0]-2:g}", False))
    innen = (f'<rect width="{b:g}" height="{h:g}" rx="12" fill="url(#tolex)"/>'
             f'<rect x=".5" y=".5" width="{b-1:g}" height="{h-1:g}" rx="11.5" fill="none" stroke="#000" stroke-opacity=".5"/>'
             + "".join(eingang) + kabel(zug) + "".join(links) + "".join(schienen) + "".join(pedale))
    return svg(b, h, innen, "Mein Homelab als Signalkette auf einem Pedalboard", STIL), b


def board_schmal():
    """Fürs Handy: Kette oben in einer Zeile, darunter je Reihe eine Gruppe."""
    rand = 20
    rb = gruppen_breite(3)
    b = rand * 2 + rb + 2 * 22
    x0 = rand + 22
    ky = rand
    opn_x, prx_x = x0 + PB + FUGE, x0 + 2 * (PB + FUGE)
    eingang = [f'<rect filter="url(#schatten)" x="{x0:g}" y="{ky:g}" width="{PB}" height="{PH}" rx="6" fill="{F["blech"]}" stroke="{F["karmin"]}"/>',
               siebdruck("Input", x0 + PB / 2, ky + 24, 11, anker="middle"), buchse(x0 + PB / 2, ky + 56, 30),
               text("Internet", x0 + PB / 2, ky + 100, 14, 800, 75, F["text"], .01, "middle")]
    zug = [(f"M{x0+PB/2:g} {ky+56:g}H{opn_x:g}", True), (f"M{opn_x+PB:g} {ky+PH/2:g}H{prx_x:g}", True)]
    teile = [pedal(opn_x, ky, "OPNsense", "rot", 90, "Durch", .61 + .25), pedal(prx_x, ky, "Proxy", "schwarz", 91, "Durch", .72 + .25)]
    oben = ky + PH + 44
    pedale, schienen, anker = reihen_setzen(REIHEN_SCHMAL, x0, oben, .5 + 3 * .11 + .2)
    # Das Signal läuft links an den Reihen herunter; die gewählte Reihe bekommt den roten Abzweig
    px = prx_x + PB / 2
    gx = rand + 9
    ziel = anker[GEWAEHLT[0]]
    zug.append((f"M{px:g} {ky+PH:g}V{ky+PH+22:g}H{gx:g}V{ziel[1]+PH/2:g}H{x0-2:g}", True))
    for k, (x, y, gb) in anker.items():
        if k != GEWAEHLT[0]:
            zug.append((f"M{gx:g} {y+PH/2:g}H{x-2:g}", False))
    unten = max(y for _, y, _ in anker.values())
    zug.append((f"M{gx:g} {ziel[1]+PH/2:g}V{unten+PH/2:g}", False))
    h = oben + len(REIHEN_SCHMAL) * ZEILE - (ZEILE - PH - 38) + rand
    innen = (f'<rect width="{b:g}" height="{h:g}" rx="10" fill="url(#tolex)"/>'
             f'<rect x=".5" y=".5" width="{b-1:g}" height="{h-1:g}" rx="9.5" fill="none" stroke="#000" stroke-opacity=".5"/>'
             + "".join(eingang) + kabel(zug) + "".join(teile) + "".join(schienen) + "".join(pedale))
    return svg(b, h, innen, "Mein Homelab als Signalkette auf einem Pedalboard", STIL), b


# ---------------------------------------------------------------- Kopf und Fuß
def kopf_breit(b):
    h, rand = 156, 40
    lg, lbr = logo(rand, 52, 54 * .72)
    nx = rand + lbr + 18
    ende = nx + breite("MIA GRÜNWALD", 54, 800, 75, .01)
    lampe_x = b - rand - 14
    reg_x = [lampe_x - 66 * (3 - i) for i in range(3)]
    assert reg_x[0] - 19 - ende > 80, f"Name zu nah an den Reglern: {reg_x[0]-19-ende:.0f}"
    g = [f'<rect width="{b:g}" height="{h}" rx="12" fill="{F["blech"]}"/>', f'<rect y="{h-3}" width="{b:g}" height="3" fill="{F["blech_kante"]}"/>',
         lg, text("MIA GRÜNWALD", nx, 90, 54, 800, 75, F["text"], .01), siebdruck("Fachinformatikerin für Systemintegration", nx + 2, 120, 14)]
    for x, (wort, w) in zip(reg_x, (("Homelab", 150), ("Code", 95), ("Bass", 120))):
        g += [regler(x, 71, 19, w, chrom=True), siebdruck(wort, x, 120, 12, anker="middle")]
    g.append(lampe(lampe_x, 71, 14, 120, 12))
    return svg(b, h, "".join(g), "Mia Grünwald, Fachinformatikerin für Systemintegration")


def kopf_schmal(b):
    h, rand, gr = 214, 22, 38
    while logo(0, 0, gr * .72)[1] + 12 + breite("MIA GRÜNWALD", gr, 800, 75, .01) > b - 2 * rand:
        gr -= .5
    lg, lbr = logo(rand, 59 - gr * .72, gr * .72)
    g = [f'<rect width="{b:g}" height="{h}" rx="10" fill="{F["blech"]}"/>', f'<rect y="{h-3}" width="{b:g}" height="3" fill="{F["blech_kante"]}"/>',
         lg, text("MIA GRÜNWALD", rand + lbr + 12, 59, gr, 800, 75, F["text"], .01),
         siebdruck("Fachinformatikerin für Systemintegration", rand, 92, 12),
         f'<rect x="{rand}" y="112" width="{b-2*rand:g}" height="1" fill="#241d1d"/>']
    schritt = (b - 2 * rand - 40) / 3
    for i, (wort, w) in enumerate((("Homelab", 150), ("Code", 95), ("Bass", 120))):
        x = rand + 20 + i * schritt
        g += [regler(x, 152, 17, w, chrom=True), siebdruck(wort, x, 192, 11, anker="middle")]
    g.append(lampe(rand + 20 + 3 * schritt, 152, 12, 192, 11))
    return svg(b, h, "".join(g), "Mia Grünwald, Fachinformatikerin für Systemintegration")


def fuss(b, rand, gr):
    h = 64
    g = [f'<rect width="{b:g}" height="{h}" rx="{12 if b > 500 else 10}" fill="{F["blech"]}"/><rect width="{b:g}" height="3" fill="{F["blech_kante"]}"/>',
         siebdruck("Raum Hamburg", rand, 39, gr), siebdruck("mia-gruenwald.dev", b - rand, 39, gr, anker="end")]
    return svg(b, h, "".join(g), "Raum Hamburg, mia-gruenwald.dev")


# ---------------------------------------------------------------- Pegel (täglich neu per Action)
MONATE = "Jan Feb Mär Apr Mai Jun Jul Aug Sep Okt Nov Dez".split()
STUFEN = ("#7a1020", "#b3122b", "#e31a36", F["led_an"])


def kalender(token):
    """Beitragskalender der letzten 12 Monate. Private Beiträge zählen mit, seit Mia sie im Profil freigegeben hat."""
    q = ('{ user(login:"MiaLaMala"){ contributionsCollection{ contributionCalendar{ totalContributions '
         'weeks{ contributionDays{ date contributionCount } } } } } }')
    r = urllib.request.Request("https://api.github.com/graphql", data=json.dumps({"query": q}).encode(),
                               headers={"Authorization": f"bearer {token}", "User-Agent": "MiaLaMala-pegel"})
    k = json.load(urllib.request.urlopen(r, timeout=30))["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    tage = sorted((date.fromisoformat(d["date"]), d["contributionCount"]) for w in k["weeks"] for d in w["contributionDays"])
    return k["totalContributions"], tage


def kennzahlen(tage):
    an = [c > 0 for _, c in tage]
    laengste = lauf = 0
    for a in an:
        lauf = lauf + 1 if a else 0
        laengste = max(laengste, lauf)
    i, aktuell = (len(an) - 1 if an[-1] else len(an) - 2), 0   # heute ohne Beitrag bricht die Serie noch nicht
    while i >= 0 and an[i]:
        aktuell, i = aktuell + 1, i - 1
    return laengste, aktuell, sum(an)


def stufe(c, grenzen):
    return 0 if c == 0 else 1 + sum(c > g for g in grenzen)


def zahl_de(n):
    return f"{n:,}".replace(",", ".")


def led_matrix(tage, x0, y0, abstand, verz0):
    """Montag oben, eine Spalte je Woche. Die Spalten leuchten beim Laden nacheinander auf."""
    werte = sorted(c for _, c in tage if c)
    grenzen = [werte[int(len(werte) * q)] for q in (.25, .5, .75)] if werte else [0, 0, 0]
    start = tage[0][0] - timedelta(days=tage[0][0].weekday())
    r = abstand * .33
    aus = (f'<g id="led"><circle r="{r+1.6:.1f}" fill="#0b0909" stroke="#3a3030"/>'
           f'<circle r="{r:.1f}" fill="{F["led_aus"]}"/></g>')
    unten, spalten, monate = [], {}, []
    for d, c in tage:
        sp, z = (d - start).days // 7, d.weekday()
        x, y = x0 + sp * abstand + abstand / 2, y0 + z * abstand + abstand / 2
        unten.append(f'<use href="#led" x="{x:.1f}" y="{y:.1f}"/>')
        s = stufe(c, grenzen)
        if s:
            glut = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r*2:.1f}" fill="{STUFEN[3]}" opacity=".16"/>' if s == 4 else ""
            spalten.setdefault(sp, []).append(glut + f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{STUFEN[s-1]}"/>')
        if d.day == 1 or d == tage[0][0]:
            monate.append((sp, MONATE[d.month - 1]))
    if len(monate) > 1 and monate[1][0] - monate[0][0] < 3:      # angeschnittener erster Monat klebt sonst am zweiten
        monate.pop(0)
    beschriftet = [siebdruck(m, x0 + sp * abstand + 1, y0 + 7 * abstand + 17, 11) for sp, m in monate]
    an = "".join(f'<g class="an" style="animation-delay:{verz0 + sp * .022:.2f}s">{"".join(v)}</g>' for sp, v in sorted(spalten.items()))
    return aus, "".join(unten) + an + "".join(beschriftet), (tage[-1][0] - start).days // 7 + 1


def anzeige(x, y, b, h, titel, wert, einheit, gr_titel=11, gr_wert=24):
    pad = 14 if b > 120 else 10
    while breite(titel.upper(), gr_titel, 650, 75, .07) > b - 2 * pad:
        gr_titel -= .25
    return (f'<rect x="{x:g}" y="{y:g}" width="{b:g}" height="{h:g}" rx="6" fill="{F["platte"]}" stroke="{F["rand"]}"/>'
            + siebdruck(titel, x + pad, y + 22, gr_titel)
            + text(wert, x + pad, y + h - 14, gr_wert, 800, 75, F["text"], .01)
            + (siebdruck(einheit, x + pad + 6 + breite(wert, gr_wert, 800, 75, .01), y + h - 14, gr_titel) if einheit else ""))


def pegel(gesamt, tage, b):
    schmal = b < 500
    rand = 22 if schmal else 40
    laengste, aktuell, aktiv = kennzahlen(tage)
    g = [f'<rect width="{b:g}" height="{{h}}" rx="{10 if schmal else 12}" fill="{F["blech"]}"/>',
         f'<rect y="{{kante}}" width="{b:g}" height="3" fill="{F["blech_kante"]}"/>',
         siebdruck("Beiträge auf GitHub, letzte 12 Monate", rand, 44 if not schmal else 38, 12 if not schmal else 11),
         text(zahl_de(gesamt), rand, 94 if not schmal else 80, 46 if not schmal else 38, 800, 75, F["text"], .01)]
    werte = (("Längste Serie", str(laengste), "Tage"), ("Aktuelle Serie", str(aktuell), "Tage"), ("Aktive Tage", str(aktiv), ""))
    if schmal:
        ab = (b - 2 * rand - 16) / 3
        for i, (t, w, e) in enumerate(werte):
            g.append(anzeige(rand + i * (ab + 8), 100, ab, 58, t, w, e, 9.5, 20))
        oben = 196
        g.append(siebdruck("Letzte Wochen", rand, oben - 12, 11))
    else:
        ab = 158
        for i, (t, w, e) in enumerate(werte):
            g.append(anzeige(b - rand - 3 * ab - 2 * 14 + i * (ab + 14), 28, ab, 66, t, w, e))
        oben = 128
    links = 22 if schmal else 30
    platz = b - 2 * rand - links
    spalten_alle = (tage[-1][0] - (tage[0][0] - timedelta(days=tage[0][0].weekday()))).days // 7 + 1
    abstand = min(16, platz / spalten_alle)
    montag = tage[0][0] + timedelta(days=(7 - tage[0][0].weekday()) % 7)
    tage = [t for t in tage if t[0] >= montag]                  # die Matrix zeigt nur ganze Wochen ab Montag
    spalten_alle = (tage[-1][0] - montag).days // 7 + 1
    abstand = min(16, platz / spalten_alle)
    if schmal:                                                 # aufs Handy passen nur die letzten Wochen
        n = int(platz // 15)
        abstand = platz / n
        grenze = tage[-1][0] - timedelta(days=tage[-1][0].weekday() + 7 * (n - 1))
        tage = [t for t in tage if t[0] >= grenze]
    g += [siebdruck(t, rand, oben + z * abstand + abstand / 2 + 3.5, 10 if not schmal else 9) for z, t in ((0, "Mo"), (2, "Mi"), (4, "Fr"), (6, "So"))]
    defs, matrix, _ = led_matrix(tage, rand + links, oben, abstand, .3)
    h = oben + 7 * abstand + 50
    g[0], g[1] = g[0].replace("{h}", f"{h:g}"), g[1].replace("{kante}", f"{h-3:g}")
    titel = f"{zahl_de(gesamt)} Beiträge in 12 Monaten, längste Serie {laengste} Tage, aktuelle Serie {aktuell} Tage, {aktiv} aktive Tage"
    return svg(b, h, f"<defs>{defs}</defs>" + "".join(g) + matrix, titel, STIL)


def pegel_bauen(ziel):
    token = os.environ.get("GITHUB_TOKEN") or subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
    gesamt, tage = kalender(token)
    ziel.mkdir(parents=True, exist_ok=True)
    for name, b in (("pegel", 960), ("pegel-schmal", 322)):
        (ziel / f"{name}.svg").write_text(pegel(gesamt, tage, b))
    print("Pegel:", gesamt, "Beiträge, Serien und aktive Tage:", kennzahlen(tage))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--pegel"]:
        pegel_bauen(Path(sys.argv[2]))
        sys.exit()
    ZIEL.mkdir(exist_ok=True)
    pegel_bauen(ZIEL)
    breit, bb = board_breit()
    schmal, sb = board_schmal()
    for name, inhalt in (("board", breit), ("board-schmal", schmal), ("kopf", kopf_breit(960)), ("kopf-schmal", kopf_schmal(sb)),
                         ("fuss", fuss(960, 40, 13)), ("fuss-schmal", fuss(sb, 22, 12))):
        (ZIEL / f"{name}.svg").write_text(inhalt)
        print(name, round(len(inhalt) / 1024), "KB")
    print("Breiten:", bb, sb, "| Pedalnamen unter 11px:", {k: v for k, v in NAMEN_GROESSE.items() if v < 11})
