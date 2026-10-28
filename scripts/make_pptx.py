#!/usr/bin/env python3
"""
make_pptx.py — génère la présentation du processus « Du CAD au ROS 2 ».

Contenu : LE PROCESSUS ET SES 7 ÉTAPES uniquement, du design du robot dans
Onshape (ou tout CAD) jusqu'à RViz2 — pas d'agenda, pas de timing, pas
d'outillage interne.

Langue : texte FRANÇAIS, mots-clés importants en ANGLAIS (URDF, link, joint,
mate, TF, RViz2, frames, export, sliders, ...) pour coller à la doc ROS 2.

Images : screenshots RViz2 de docs/screenshots/ (01..05).

Run:  .venv/bin/python scripts/make_pptx.py
Out:  docs/presentation/du_cad_au_ros2.pptx
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SHOTS = PROJECT_ROOT / "docs" / "screenshots"
OUT = PROJECT_ROOT / "docs" / "presentation" / "du_cad_au_ros2.pptx"

# ----------------------------------------------------------------- styling
NAVY = RGBColor(0x1F, 0x38, 0x64)      # titres
BLUE = RGBColor(0x0B, 0x5F, 0xA5)      # mots-clés EN
ORANGE = RGBColor(0xE8, 0x75, 0x1A)    # badges, accents
INK = RGBColor(0x2B, 0x2F, 0x38)       # texte courant
GREY = RGBColor(0x5A, 0x62, 0x70)      # secondaire
LIGHT = RGBColor(0xF4, 0xF6, 0xFA)     # fond des cartes
BORDER = RGBColor(0xD9, 0xDF, 0xE9)    # bordures cartes
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x2E, 0x7D, 0x32)
RED = RGBColor(0xB0, 0x30, 0x30)
DARK = RGBColor(0x1E, 0x24, 0x30)      # fond des blocs de code
CODE_FG = RGBColor(0xCB, 0xD5, 0xE1)
FAINT = RGBColor(0x99, 0x9F, 0xA9)     # pied de page

W, H = 13.333, 7.5
FOOTER = "Du CAD au ROS 2 · Onshape → URDF → RViz2"

prs = Presentation()
prs.slide_width = Inches(W)
prs.slide_height = Inches(H)
BLANK = prs.slide_layouts[6]

_PAGE = {"n": 0}


def _page():
    _PAGE["n"] += 1
    return _PAGE["n"]


# ----------------------------------------------------------------- helpers
def _set(run, size=16, bold=False, color=INK, mono=False, italic=False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = "Consolas" if mono else "Calibri"


def textbox(slide, x, y, w, h, fill=None, line=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is not None:
        tb.fill.solid()
        tb.fill.fore_color.rgb = fill
    else:
        tb.fill.background()
    if line is not None:
        tb.line.color.rgb = line
        tb.line.width = Pt(1)
    else:
        tb.line.fill.background()
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.12)
    tf.margin_right = Inches(0.12)
    tf.margin_top = Inches(0.06)
    tf.margin_bottom = Inches(0.06)
    return tb, tf


def para(tf, first, runs, size=16, color=INK, space_before=4,
         align=PP_ALIGN.LEFT, bullet=None, mono=False):
    """runs: str or list of (text, dict-overrides); first => reuse paragraph 0."""
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.space_before = Pt(space_before)
    p.alignment = align
    if bullet:
        r = p.add_run()
        r.text = bullet + "  "
        _set(r, size=size, bold=True, color=ORANGE)
    if isinstance(runs, str):
        runs = [(runs, {})]
    for text, opt in runs:
        r = p.add_run()
        r.text = text
        kw = dict(size=size, color=color, mono=mono)
        kw.update(opt)
        _set(r, **kw)
    return p


def footer(slide, num):
    tb, tf = textbox(slide, 0.6, H - 0.46, W - 1.9, 0.3)
    para(tf, True, [(FOOTER, {})], size=10, color=FAINT, space_before=0)
    tb2, tf2 = textbox(slide, W - 1.15, H - 0.46, 0.55, 0.3)
    para(tf2, True, [(str(num), {"bold": True})], size=10, color=FAINT,
         align=PP_ALIGN.RIGHT, space_before=0)


def badge(slide, x, y, d, text, fill=ORANGE, size=20):
    """Cercle plein (numéro d'étape) centré sur (x, y) comme centre."""
    shp = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x - d / 2),
                                 Inches(y - d / 2), Inches(d), Inches(d))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.fill.background()
    shp.shadow.inherit = False
    tf = shp.text_frame
    tf.word_wrap = False
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Pt(0)
    tf.margin_right = Pt(0)
    tf.margin_top = Pt(0)
    tf.margin_bottom = Pt(0)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = str(text)
    _set(r, size=size, bold=True, color=WHITE)
    return shp


def card(slide, x, y, w, h, fill=LIGHT, line=BORDER):
    """Carte arrondie claire (aucun texte) — retourne la forme."""
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x),
                                 Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(1)
    shp.shadow.inherit = False
    try:
        shp.adjustments[0] = 0.07
    except (IndexError, ValueError):
        pass
    return shp


def note_card(slide, x, y, w, h, title, paragraphs, fill=LIGHT, line=BORDER,
              title_color=NAVY, size=14):
    """Carte avec titre gras + paragraphes (listes de runs)."""
    shp = card(slide, x, y, w, h, fill, line)
    tf = shp.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = Inches(0.18)
    tf.margin_right = Inches(0.18)
    tf.margin_top = Inches(0.12)
    tf.margin_bottom = Inches(0.1)
    first = True
    if title:
        para(tf, True, [(title, {"bold": True, "color": title_color})],
             size=size + 1, space_before=0)
        first = False
    for runs in paragraphs:
        para(tf, first, runs, size=size, color=INK,
             space_before=(0 if first else 6))
        first = False
    return shp


def box(slide, x, y, w, h, text, fill, fg=WHITE, size=13, bold=True, sub=None,
        anchor=MSO_ANCHOR.MIDDLE):
    """Encadré plein (bandeau, règle d'or...)."""
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x),
                                 Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.fill.background()
    shp.shadow.inherit = False
    tf = shp.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = Inches(0.16)
    tf.margin_right = Inches(0.16)
    lines = text.split("\n")
    para(tf, True, [(lines[0], {"bold": bold, "color": fg})], size=size,
         align=PP_ALIGN.CENTER, space_before=0)
    for ln in lines[1:]:
        para(tf, False, [(ln, {"bold": bold, "color": fg})], size=size,
             align=PP_ALIGN.CENTER, space_before=2)
    if sub:
        para(tf, False, [(sub, {})], size=size - 2, color=fg,
             align=PP_ALIGN.CENTER, space_before=4)
    return shp


def bullets(slide, x, y, w, h, items, size=16, space=9):
    """Liste à puces ▸ orange ; items = liste de listes de runs."""
    tb, tf = textbox(slide, x, y, w, h)
    first = True
    for runs in items:
        para(tf, first, runs, size=size, color=INK, bullet="▸",
             space_before=(2 if first else space))
        first = False
    return tb


def code_block(slide, x, y, w, h, lines, size=13):
    _, tf = textbox(slide, x, y, w, h, fill=DARK)
    tf.margin_top = Inches(0.12)
    tf.margin_left = Inches(0.16)
    for i, ln in enumerate(lines):
        para(tf, i == 0, [(ln, {})], size=size, color=CODE_FG, mono=True,
             space_before=1)


def picture_fit(slide, path, x, y, max_w, max_h):
    """Insère l'image en gardant le ratio, centrée dans la boîte."""
    with Image.open(path) as im:
        iw, ih = im.size
    scale = min(max_w / iw, max_h / ih)
    w, h = iw * scale, ih * scale
    left, top = x + (max_w - w) / 2, y + (max_h - h) / 2
    pic = slide.shapes.add_picture(str(path), Inches(left), Inches(top),
                                   width=Inches(w), height=Inches(h))
    pic.line.color.rgb = BORDER
    pic.line.width = Pt(1)
    return left, top, w, h


def caption(slide, x, y, w, text):
    _, tf = textbox(slide, x, y, w, 0.3)
    para(tf, True, [(text, {"italic": True})], size=11, color=GREY,
         align=PP_ALIGN.CENTER, space_before=0)


def arrow(slide, x, y, w=0.4, h=0.26):
    a = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y),
                               Inches(w), Inches(h))
    a.fill.solid()
    a.fill.fore_color.rgb = RGBColor(0xA8, 0xB1, 0xC0)
    a.line.fill.background()
    a.shadow.inherit = False
    return a


def chip(slide, x, y, w, h, text, fill, size=15):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x),
                                 Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.fill.background()
    shp.shadow.inherit = False
    tf = shp.text_frame
    tf.word_wrap = False
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Pt(0)
    tf.margin_right = Pt(0)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    _set(r, size=size, bold=True, color=WHITE)
    return shp


def content_slide(title, step=None, kicker=None):
    """Slide blanc : badge orange (étape) + titre navy + filet + pied de page."""
    s = prs.slides.add_slide(BLANK)
    y_mid = 0.78                      # centre vertical du titre
    x = 0.6
    if step is not None:
        badge(s, x + 0.31, y_mid, 0.62, step, size=23)
        x = 1.32
    tb, tf = textbox(s, x, 0.4, W - x - 0.5, 0.8)
    runs = [(title, {"size": 27, "bold": True, "color": NAVY})]
    if kicker:
        runs.append(("   ·   " + kicker, {"size": 15, "color": GREY}))
    para(tf, True, runs, space_before=0)
    # filet orange + hairline grise
    rule = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(1.3),
                              Inches(1.5), Inches(0.05))
    rule.fill.solid()
    rule.fill.fore_color.rgb = ORANGE
    rule.line.fill.background()
    rule.shadow.inherit = False
    hair = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(2.2), Inches(1.318),
                              Inches(W - 2.8), Inches(0.015))
    hair.fill.solid()
    hair.fill.fore_color.rgb = BORDER
    hair.line.fill.background()
    hair.shadow.inherit = False
    footer(s, _page())
    return s


def check(cond, msg):
    if not cond:
        sys.exit(f"[FAIL] {msg}")


# ================================================================= slides

# ---- 1. titre -----------------------------------------------------------
s = prs.slides.add_slide(BLANK)
_page()
_, tf = textbox(s, 1.0, 1.75, 11.4, 1.3)
para(tf, True, [("Du CAD au ROS 2", {"size": 46, "bold": True, "color": NAVY})],
     space_before=0)
rule = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.05), Inches(3.12),
                          Inches(2.6), Inches(0.07))
rule.fill.solid()
rule.fill.fore_color.rgb = ORANGE
rule.line.fill.background()
rule.shadow.inherit = False
_, tf = textbox(s, 1.0, 3.35, 11.4, 0.7)
para(tf, True, [("Concevoir un robot dans Onshape, le faire vivre dans RViz2",
                 {"size": 22, "color": GREY})], space_before=0)
# chips du pipeline
chips = [("Onshape", NAVY, 1.7), ("onshape-to-robot", BLUE, 2.7),
         ("URDF", DARK, 1.4), ("ROS 2", BLUE, 1.55), ("RViz2", ORANGE, 1.55)]
gap = 0.6                       # flèche + marges
total = sum(c[2] for c in chips) + gap * (len(chips) - 1)
cx = (W - total) / 2
cy_chip, h_chip = 4.45, 0.62
for i, (label, fill, wc) in enumerate(chips):
    chip(s, cx, cy_chip, wc, h_chip, label, fill)
    cx += wc
    if i < len(chips) - 1:
        arrow(s, cx + 0.12, cy_chip + (h_chip - 0.26) / 2, 0.36, 0.26)
        cx += gap
_, tf = textbox(s, 1.0, 5.7, 11.4, 0.9)
para(tf, True, [("Texte en français · mots-clés importants en ",
                 {"size": 14, "color": GREY}),
                ("English", {"size": 14, "bold": True, "color": ORANGE}),
                (" (URDF, link, joint, mate, TF, frames, export, sliders…)",
                 {"size": 14, "color": GREY})], align=PP_ALIGN.CENTER,
     space_before=0)

# ---- 2. objectifs -------------------------------------------------------
s = content_slide("Objectifs", kicker="à la fin, vous savez…")
bullets(s, 0.7, 1.75, 12.0, 5.0, [
    [("Comprendre le flux complet ", {}),
     ("CAD → URDF → ROS 2 → RViz2", {"bold": True, "color": BLUE})],
    [("Modéliser un ", {}), ("assembly Onshape", {"bold": True}),
     (" : mates renommés ", {}), ("dof_*", {"bold": True, "color": ORANGE,
                                             "mono": True}),
     (" — 6 mates ", {}), ("revolute", {"bold": True}),
     (" = 6 articulations", {})],
    [("Exporter avec ", {}), ("onshape-to-robot", {"bold": True}),
     (" : ", {}), ("config.json", {"bold": True, "mono": True}),
     (" + clés API dans ", {}), (".env", {"bold": True, "mono": True})],
    [("Lire une ", {}), ("URDF", {"bold": True, "color": BLUE}),
     (" : ", {}), ("links", {"bold": True}), (", ", {}),
     ("joints", {"bold": True}), (", ", {}), ("frames", {"bold": True}),
     (", ", {}), ("limits", {"bold": True}), (", ", {}),
     ("root link", {"bold": True})],
    [("Animer le robot dans ", {}), ("RViz2", {"bold": True}),
     (" : ", {}), ("/joint_states", {"bold": True, "mono": True}),
     (" + ", {}), ("arbre TF", {"bold": True}), (" + ", {}),
     ("sliders", {"bold": True})],
    [("Fusionner la ", {}), ("cellule", {"bold": True}),
     (" (table, tube, machines) : ", {}), ("fixed link", {"bold": True}),
     (" + couleurs ", {}), ("CAD", {"bold": True})],
    [("Vérifier par la ", {}), ("TF", {"bold": True, "color": ORANGE}),
     (" puis rejouer le processus sur un ", {}),
     ("nouveau projet", {"bold": True, "color": ORANGE})],
], size=18, space=15)

# ---- 3. les 7 étapes (diagramme) ---------------------------------------
s = content_slide("Les 7 étapes du processus",
                  kicker="du design CAD à l'image RViz2")
steps = [
    ("1", "CAD Onshape", "assembly + mates dof_"),
    ("2", "Export", "onshape-to-robot + .env"),
    ("3", "URDF", "links · joints · frames"),
    ("4", "Paquet ROS 2", "colcon + launch"),
    ("5", "RViz2", "TF + sliders"),
    ("6", "Cellule", "fixed link + couleurs"),
    ("7", "Vérification", "TF · /joint_states"),
]
span = 12.3
x0 = (W - span) / 2
step_w = span / len(steps)
cy, d = 2.1, 0.72
conn = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x0 + step_w / 2),
                          Inches(cy - 0.02), Inches(span - step_w),
                          Inches(0.04))
conn.fill.solid()
conn.fill.fore_color.rgb = BORDER
conn.line.fill.background()
conn.shadow.inherit = False
for i, (num, title, sub) in enumerate(steps):
    cx = x0 + step_w * (i + 0.5)
    badge(s, cx, cy, d, num, size=20)
    tb, tf = textbox(s, cx - step_w / 2 + 0.04, cy + 0.5, step_w - 0.08, 1.0)
    para(tf, True, [(title, {"bold": True, "color": NAVY})], size=13,
         align=PP_ALIGN.CENTER, space_before=0)
    para(tf, False, [(sub, {})], size=10.5, color=GREY,
         align=PP_ALIGN.CENTER, space_before=3)

_, tf = textbox(s, 0.7, 3.72, 8.0, 0.3)
para(tf, True, [("CE QUI PILOTE LE PROCESSUS", {"bold": True, "color": ORANGE})],
     size=13, space_before=0)
note_card(s, 0.6, 4.1, 3.9, 1.35, ".env", [
    [("Clés API Onshape ", {}),
     ("(ONSHAPE_ACCESS_KEY / ONSHAPE_SECRET_KEY)", {"mono": True, "size": 12}),
     (" — jamais dans git", {})],
], size=13.5)
note_card(s, 4.75, 4.1, 4.2, 1.35, "config.json", [
    [("url", {"bold": True}), (" (onglet), ", {}),
     ("ignore", {"bold": True}), (" (pièces étrangères), ", {}),
     ("robot_instance", {"bold": True}), (", ", {}),
     ("joint_properties", {"bold": True}), (", ", {}),
     ("output_filename", {"bold": True})],
], size=13.5)
note_card(s, 9.2, 4.1, 3.6, 1.35, "Paquet ROS 2", [
    [("urdf/ · meshes/ · launch/ · rviz/", {"mono": True, "size": 12}),
     ("  →  ", {}), ("colcon build", {"bold": True}), ("  →  ", {}),
     ("RViz2", {"bold": True})],
], size=13.5)

# bandeau : le flux d'un mouvement
band = card(s, 0.6, 5.8, 12.2, 0.85, NAVY, None)
tf = band.text_frame
tf.vertical_anchor = MSO_ANCHOR.MIDDLE
para(tf, True, [("Le mouvement :   ", {"bold": True, "color": WHITE}),
                ("slider", {"mono": True, "color": ORANGE, "bold": True}),
                ("  →  ", {"color": WHITE}),
                ("/joint_states", {"mono": True, "color": ORANGE, "bold": True}),
                ("  →  ", {"color": WHITE}),
                ("robot_state_publisher", {"mono": True, "color": ORANGE,
                                           "bold": True}),
                ("  →  ", {"color": WHITE}),
                ("arbre TF", {"color": WHITE, "bold": True}),
                ("  →  ", {"color": WHITE}),
                ("RViz2", {"color": ORANGE, "bold": True})],
     size=14, align=PP_ALIGN.CENTER, space_before=0)

# ---- 4. étape 1 : CAD ---------------------------------------------------
s = content_slide("Concevoir dans Onshape (CAD)", step=1,
                  kicker="l'assembly EST la cinématique")
bullets(s, 0.6, 1.7, 7.2, 5.2, [
    [("Deux tabs (elements) dans le même document : ", {}),
     ("« UR10 »", {"bold": True, "color": BLUE}),
     (" = le robot seul,  ", {}),
     ("« Whole setup »", {"bold": True, "color": BLUE}),
     (" = robot + table + tube + machines", {})],
    [("Assembler les pièces avec des ", {}), ("mates", {"bold": True}),
     (" — les 6 mates revolute du robot renommés avec le ", {}),
     ("prefix dof_", {"bold": True, "color": ORANGE}), (" :", {})],
    [("La cellule : mates ", {}), ("FASTENED", {"bold": True}),
     (" (0 ", {}), ("DOF", {"bold": True}), (") → elle reste ", {}),
     ("rigide", {"bold": True, "color": GREEN})],
    [("Un ", {}), ("mate", {"bold": True}),
     (" = une contrainte de position ; ", {}),
     ("dof_*", {"bold": True, "color": ORANGE, "mono": True}),
     (" = le contrat lu par l'exporter", {})],
    [("⚠ Jamais d'écriture de mates via l'", {}),
     ("API", {"bold": True}),
     (" (ça casse l'assembly) — toujours dans l'UI Onshape", {})],
], size=17, space=13)
code_block(s, 8.1, 1.7, 4.7, 3.0, [
    "# renommés dans l'assembly (UI) :",
    "dof_Revolute_base   # 1 axe (base)",
    "dof_shoulder        # 2 axe",
    "dof_elbow           # 3 axe",
    "dof_Revolute_2      # 4 axe",
    "dof_Revolute_3      # 5 axe",
    "dof_Revolute_4      # 6 axe",
    "",
    "# = 6 revolute joints -> 6",
    "#   articulations en URDF",
], size=12.5)
box(s, 8.1, 5.0, 4.7, 1.5,
    "Règle d'or\nL'assembly Onshape EST la cinématique du robot ;\n"
    "l'export n'en fait que la recopier en URDF.",
    ORANGE, size=13, anchor=MSO_ANCHOR.TOP)

# ---- 5. étape 2 : export ------------------------------------------------
s = content_slide("Exporter avec onshape-to-robot", step=2,
                  kicker="config + clés API")
bullets(s, 0.6, 1.7, 6.7, 5.2, [
    [("pip install ", {}), ("onshape-to-robot", {"mono": True, "bold": True,
                                                 "color": BLUE})],
    [("Clés API dans ", {}), (".env", {"mono": True, "bold": True}),
     (" — ", {}), ("jamais dans git", {"bold": True, "color": RED}),
     (" : ONSHAPE_ACCESS_KEY + ONSHAPE_SECRET_KEY", {"mono": True})],
    [("export/config.json", {"mono": True, "bold": True}),
     (" : ", {}), ("url", {"bold": True}), (" (onglet assembly), ", {}),
     ("ignore", {"bold": True}), (" (pièces étrangères), ", {}),
     ("robot_instance", {"bold": True}), (", ", {}),
     ("joint_properties", {"bold": True}), (" (effort / vitesse)", {})],
    [("Lancement : ", {}),
     ("onshape-to-robot export/config.json", {"mono": True, "bold": True})],
    [("→ ", {}), ("export/ur10.urdf", {"mono": True, "bold": True,
                                       "color": BLUE}),
     ("  +  ", {}),
     ("export/meshes/*.stl", {"mono": True, "bold": True, "color": BLUE})],
    [("export_env/config.json", {"mono": True, "bold": True}),
     (" : tab « Whole setup » + ", {}), ("ignore", {"bold": True}),
     (" = toutes les pièces du robot → URDF de la cellule (0 DOF)", {})],
], size=16, space=12)
code_block(s, 7.55, 1.7, 5.3, 4.0, [
    "{",
    '  "url": "https://cad.onshape.com/...",',
    '  "output_filename": "ur10",',
    '  "package_name": "ur10_robot_description",',
    '  "robot_instance": "UR10",',
    '  "ignore": { "table*": "all",',
    '              "*glory*": "all" },',
    '  "joint_properties": {',
    '    "default": { "max_effort": 150.0,',
    '                  "max_velocity": 3.15 },',
    '    "shoulder": { "max_effort": 300.0 }',
    "  }",
    "}",
], size=12)
note_card(s, 7.55, 5.9, 5.3, 0.9, None, [
    [("Le ", {}), ("dump", {"bold": True}),
     (" read-only de l'assembly fournit la pose du ", {}),
     ("mount", {"bold": True}), (" — jamais hard-codée.", {})],
], size=13)

# ---- 6. étape 3 : URDF --------------------------------------------------
s = content_slide("Décoder l'URDF", step=3,
                  kicker="le format ROS 2 du CAD")
code_block(s, 0.5, 1.7, 6.4, 3.9, [
    '<robot name="ur10">',
    '  <link name="base">        <!-- frame + visuals -->',
    "    <visual><geometry>…stl…</geometry></visual>",
    "  </link>",
    '  <joint name="shoulder"    <!-- parent -> child -->',
    '          type="revolute">',
    '    <parent link="base"/>',
    '    <child  link="joint_size_4"/>',
    '    <origin xyz="0 0 0.1625" rpy="0 0 0"/>',
    '    <axis   xyz="0 0 1"/>',
    '    <limit lower="-0.266" upper="1.829"',
    '           effort="300" velocity="3.15"/>',
    "  </joint>",
    "</robot>",
], size=12.5)
note_card(s, 0.5, 5.8, 6.4, 1.0, None, [
    [("La synchronisation vers le paquet assainit les noms ", {}),
     ("(espaces → _)", {"bold": True}), (", réécrit les chemins ", {}),
     ("package://", {"mono": True, "bold": True}),
     (" et détecte le ", {}), ("root link", {"bold": True}), (".", {})],
], size=13)
bullets(s, 7.2, 1.7, 5.7, 5.4, [
    [("<link>", {"mono": True, "bold": True, "color": BLUE}),
     (" = solide rigide + son ", {}), ("frame", {"bold": True}),
     (" (sa coordonnée TF)", {})],
    [("<joint>", {"mono": True, "bold": True, "color": BLUE}),
     (" = relation ", {}), ("parent → child", {"bold": True}),
     (" (arbre, jamais de cycle)", {})],
    [("root link", {"bold": True, "color": ORANGE}), (" = ", {}),
     ("base", {"mono": True}), (" (aucun parent) → ", {}),
     ("Fixed Frame", {"bold": True}), (" de RViz2", {})],
    [("<origin xyz rpy>", {"mono": True, "bold": True}),
     (" = pose du child dans le parent", {})],
    [("<axis> + <limit>", {"mono": True, "bold": True}),
     (" = direction de rotation + bornes, effort, vitesse", {})],
    [("chain : ", {}), ("base → tool_flange", {"bold": True, "color": BLUE}),
     (" en 6 joints", {})],
    [("Ici : ", {}), ("7 links", {"bold": True}), (" robot (", {}),
     ("8", {"bold": True, "color": ORANGE}), (" avec la cellule) et ", {}),
     ("6 revolute joints", {"bold": True}), (" + 1 ", {}),
     ("fixed", {"bold": True}), (" (mount)", {})],
    [("Le mesh = décor ; la cinématique = ", {}),
     ("frames + joints", {"bold": True, "color": ORANGE})],
], size=16, space=11)

# ---- 7. étape 4 : paquet ROS 2 -----------------------------------------
s = content_slide("Le paquet ROS 2", step=4,
                  kicker="robot_description · TF · colcon")
code_block(s, 0.5, 1.7, 5.9, 3.3, [
    "ur10_robot_description/",
    "├── urdf/ur10.urdf      # le modèle",
    "├── meshes/*.stl        # 50 maillages",
    "├── launch/display.launch.py",
    "└── rviz/ur10.rviz      # vue sauvegardée",
    "",
    "$ colcon build",
    "$ source install/setup.bash",
    "$ ros2 launch ur10_robot_description \\",
    "    display.launch.py",
], size=12.5)
box(s, 0.5, 5.3, 5.9, 1.5,
    "Le flux d'un mouvement\n"
    "slider → /joint_states → robot_state_publisher → TF → RViz2",
    ORANGE, size=13, anchor=MSO_ANCHOR.TOP)
bullets(s, 6.7, 1.7, 6.2, 5.4, [
    [("robot_state_publisher", {"mono": True, "bold": True, "color": BLUE}),
     (" : écoute ", {}), ("/joint_states", {"mono": True}),
     (" + URDF → publie l'", {}), ("arbre TF", {"bold": True})],
    [("joint_state_publisher_gui", {"mono": True, "bold": True,
                                    "color": BLUE}),
     (" : les ", {}), ("sliders", {"bold": True}), (" → ", {}),
     ("/joint_states", {"mono": True}), ("  (l'articulation)", {})],
    [("robot_description", {"mono": True, "bold": True, "color": BLUE}),
     (" : le texte URDF publié (param + topic)", {})],
    [("TF", {"bold": True, "color": ORANGE}),
     (" = qui est le parent de qui, et à quelle pose → RViz2 affiche tout "
      "au même endroit", {})],
    [("Simulateur plus tard : ", {}),
     ("Gazebo / ros2_control", {"bold": True}),
     (" se branche sur la MÊME URDF", {})],
], size=16, space=13)

# ---- 8. étape 5 : RViz2 -------------------------------------------------
s = content_slide("RViz2 : le robot prend vie", step=5,
                  kicker="sliders + Randomize")
bullets(s, 0.6, 1.7, 5.9, 3.4, [
    [("Fixed Frame = ", {}), ("base", {"mono": True, "color": BLUE,
                                       "bold": True}),
     (" (le ", {}), ("root link", {"bold": True}), (")", {})],
    [("Display ", {}), ("RobotModel", {"bold": True, "color": BLUE}),
     (" : Description Source = ", {}), ("Topic", {"bold": True}),
     (" ", {}), ("/robot_description", {"mono": True})],
    [("Articuler : ", {}), ("sliders", {"bold": True}), (", boutons ", {}),
     ("Randomize", {"bold": True, "color": ORANGE}), (" / ", {}),
     ("Center", {"bold": True, "color": ORANGE})],
    [("Les 6 joints bougent, la ", {}), ("cellule", {"bold": True}),
     (" reste ", {}), ("fixe", {"bold": True, "color": GREEN}),
     (" ✓", {})],
], size=16, space=12)
note_card(s, 0.6, 5.2, 5.9, 1.5, "Vérification express", [
    [("$ ros2 topic echo /joint_states", {"mono": True, "size": 13})],
    [("$ ros2 run tf2_tools view_frames", {"mono": True, "size": 13})],
], size=13.5)
lx, ly, lw, lh = picture_fit(s, SHOTS / "03_articulated_environment.png",
                             6.9, 1.6, 5.9, 4.7)
caption(s, 6.9, ly + lh + 0.06, 5.9,
        "Cellule complète, robot articulé (Randomize)")

# ---- 9. étape 6 : cellule ----------------------------------------------
s = content_slide("La cellule dans l'URDF", step=6,
                  kicker="2e export · fixed link · couleurs")
bullets(s, 0.6, 1.65, 12.2, 2.0, [
    [("tab « Whole setup »", {"mono": True, "bold": True, "color": BLUE}),
     (" exporté avec ", {}), ("ignore", {"bold": True, "mono": True}),
     (" = toutes les pièces robot → 1 seul ", {}),
     ("link rigide", {"bold": True}), (" (", {}),
     ("environment", {"mono": True, "bold": True}), (")", {})],
    [("Synchronisation : merge en ", {}),
     ("environment", {"mono": True, "bold": True}), (" + ", {}),
     ("environment_mount", {"mono": True, "bold": True}),
     (" (", {}), ("fixed joint", {"bold": True}), (" sur ", {}),
     ("base", {"mono": True}), ("), pose tirée du ", {}),
     ("dump", {"bold": True}), (" (jamais hard-codée)", {})],
    [("Couleurs : ", {}), ("palette", {"bold": True, "color": BLUE}),
     (" pour le robot (aspect UR white/blue), la cellule garde ses "
      "couleurs ", {}), ("CAD", {"bold": True})],
], size=16, space=11)
lx1, ly1, lw1, lh1 = picture_fit(s, SHOTS / "01_before_grey_robot.png",
                                 0.6, 3.7, 6.0, 2.75)
lx2, ly2, lw2, lh2 = picture_fit(s, SHOTS / "02_after_environment_colors.png",
                                 6.85, 3.7, 6.0, 2.75)
caption(s, 0.6, ly1 + lh1 + 0.06, 6.0, "avant : robot grey, pas de cellule")
caption(s, 6.85, ly2 + lh2 + 0.06, 6.0,
        "après : palette UR + cellule aux couleurs CAD")

# ---- 10. étape 7 : vérification ----------------------------------------
s = content_slide("Vérifier par la TF", step=7,
                  kicker="mesurer, pas seulement regarder")
rows = [
    ("6 positions de joints", "0, 0, 0, 0, 0, 0",
     "-0.09, -1.85, 2.04, -1.68, 1.24, -0.36"),
    ("base → tool_flange", "[-0.282, 0.175, 0.221]",
     "[-0.116, 0.066, 0.984]   (l'arm bouge)"),
    ("base → environment", "[0.000, -0.000, -0.816]",
     "[0.000, -0.000, -0.816]   (fixe ✓)"),
]
tbl = s.shapes.add_table(len(rows) + 1, 3, Inches(0.6), Inches(1.7),
                         Inches(12.1), Inches(2.3)).table
tbl.columns[0].width = Inches(3.2)
tbl.columns[1].width = Inches(4.2)
tbl.columns[2].width = Inches(4.7)
for c, text in enumerate(["Contrôle (TF)", "avant Randomize",
                          "après Randomize"]):
    cell = tbl.cell(0, c)
    cell.text = text
    _set(cell.text_frame.paragraphs[0].runs[0], size=14, bold=True, color=WHITE)
    cell.fill.solid()
    cell.fill.fore_color.rgb = NAVY
for i, row in enumerate(rows, start=1):
    for c, text in enumerate(row):
        cell = tbl.cell(i, c)
        cell.text = text
        _set(cell.text_frame.paragraphs[0].runs[0], size=13, bold=(c == 0),
             color=(GREEN if c == 2 else INK))
        cell.fill.solid()
        cell.fill.fore_color.rgb = LIGHT if i % 2 else WHITE
bullets(s, 0.6, 4.35, 12.1, 2.5, [
    [("L'articulation bouge = joints + frames robot OK ; ", {}),
     ("l'environment ne bouge PAS", {"bold": True, "color": GREEN}),
     (" = mount correct", {})],
    [("ros2 topic echo /joint_states --once", {"mono": True, "bold": True,
                                               "color": BLUE}),
     ("   ·   ", {}),
     ("ros2 run tf2_tools view_frames", {"mono": True, "bold": True,
                                         "color": BLUE}),
     ("   ·   ", {}),
     ("ros2 run tf2_ros tf2_echo base tool_flange",
      {"mono": True, "bold": True, "color": BLUE})],
    [("Contrôle intégré : au moins 1 joint non-", {}),
     ("fixed", {"bold": True}),
     (" obligatoire → une cellule 0 DOF ne peut jamais passer pour un "
      "robot", {})],
    [("Les ", {}), ("limits", {"bold": True}),
     (" affichées dans les sliders doivent correspondre à celles de "
      "l'URDF", {})],
], size=15, space=10)

# ---- 11. étude de cas robot ↔ tube -------------------------------------
s = content_slide("Étude de cas — robot ↔ tube",
                  kicker="un bug de frame, pas de 3D")
bullets(s, 0.6, 1.65, 7.1, 3.6, [
    [("Symptôme : ", {"bold": True, "color": RED}),
     ("dans RViz2 le robot est ", {}), ("déconnecté", {"bold": True}),
     (" du tube alors que l'assembly Onshape est correct", {})],
    [("Cause : ", {"bold": True, "color": ORANGE}),
     ("le ", {}), ("mount", {"bold": True}),
     (" était calculé depuis l'", {}),
     ("origine du sub-assembly", {"bold": True}), (" (", {}),
     ("UR10 <1>", {"mono": True}), (") et non la pièce mated (", {}),
     ("UR10 <1>/Base <3>", {"mono": True}), (" ) : écart = 0,816 m", {})],
    [("Les ", {}), ("mates", {"bold": True}),
     (" déplacent les pièces par rapport à l'origine du sous-ensemble → "
      "transformations DIFFÉRENTES", {})],
    [("Fix : ", {"bold": True, "color": GREEN}),
     ("T_W_R = T_part @ inv(T_R_part)", {"mono": True}), (", ", {}),
     ("T_mount = inv(T_W_R)", {"mono": True}),
     (" → résidu du mate = 0,6 mm ✓", {})],
    [("Leçon : ", {"bold": True, "color": BLUE}),
     ("prendre la pose ", {}), ("contrainte par le mate", {"bold": True}),
     (" (pièce au contact), jamais l'origine d'un sous-ensemble", {})],
], size=15, space=11)
code_block(s, 0.6, 5.5, 7.1, 1.3, [
    "base -> environment = xyz(0.000, -0.000, -0.816)  [fixe]",
    "flange tube (0,0,0.816) -> base = (0.0001, -0.0003, 0.0000)",
], size=12.5)
lx, ly, lw, lh = picture_fit(s, SHOTS / "05_base_tube_junction.png",
                             8.0, 1.65, 4.8, 4.6)
caption(s, 8.0, ly + lh + 0.06, 4.8, "Jonction base ↔ tube : contact rétabli ✓")

# ---- 12. pièges courants ------------------------------------------------
s = content_slide("Pièges courants (pitfalls)",
                  kicker="ce qui casse, et la parade")
pitfalls = [
    ("Espaces dans les noms de joints/links",
     "TF interdit les espaces → noms assainis à chaque synchronisation "
     "(espaces → _)"),
    ("Fenêtre RViz2 invisible",
     "Qt choisit Wayland → lancer avec QT_QPA_PLATFORM=xcb"),
    ("Robot tout grey",
     "Onshape = aspects gris → palette UR appliquée (option pour garder "
     "l'aspect CAD brut)"),
    ("Onshape modifié, RViz pas à jour",
     "résidu obsolète → resynchroniser : dump + URDF + rebuild"),
    ("Noms non-ASCII / mojibake",
     "réparés et translittérés en ASCII automatiquement"),
    ("Mate renommé ou supprimé",
     "recommencer l'export ; ne JAMAIS écrire de mates via l'API"),
    ("Clés API exposées",
     ".env uniquement, hors git (.gitignore)"),
    ("Robot déconnecté de la cellule",
     "mount calculé depuis la pièce mated, pas l'origine du sub-assembly"),
]
cw, ch = 5.95, 1.16
xs = [0.55, 6.85]
ys = [1.65, 2.96, 4.27, 5.58]
for i, (problem, fix) in enumerate(pitfalls):
    x = xs[i % 2]
    y = ys[i // 2]
    note_card(s, x, y, cw, ch, problem, [[(fix, {})]],
              title_color=RED, size=13)

# ---- 13. atelier 1/2 ----------------------------------------------------
s = content_slide("Atelier (1/2) — du CAD à l'URDF", kicker="étapes 1 → 3")
box(s, 0.6, 1.6, 12.2, 0.62,
    "Objectif : votre propre robot/cellule dans RViz2 avec le MÊME processus",
    ORANGE, size=15)
items1 = [
    (1, "CAD",
     "Nouveau document Onshape (ou duplicate) — 2 tabs : « Robot » (seul) + "
     "« Cellule » (robot + environnement)."),
    (2, "Mates",
     "Dans l'UI : 6 mates revolute renommés dof_* ; cellule = FASTENED ; "
     "base fixée au sol (ground)."),
    (3, "Configs",
     "export/config.json (url tab robot, robot_instance, output_filename, "
     "ignore, joint_properties) ; export_env/config.json (url tab cellule, "
     "ignore = pièces robot) ; .env (clés API)."),
    (4, "Export",
     "onshape-to-robot pour le robot puis la cellule → 2 URDF + meshes ; "
     "contrôle : ≥ 1 joint non-fixed."),
]
gx = [0.6, 6.85]
gy = [2.5, 4.65]
for i, (num, title, text) in enumerate(items1):
    x, y = gx[i % 2], gy[i // 2]
    note_card(s, x, y, 5.95, 1.95, None, [], line=BORDER)
    badge(s, x + 0.42, y + 0.42, 0.5, num, size=17)
    tb, tf = textbox(s, x + 0.78, y + 0.16, 5.0, 1.7)
    para(tf, True, [(title, {"bold": True, "color": NAVY})], size=16,
         space_before=0)
    para(tf, False, [(text, {})], size=13, color=INK, space_before=5)

# ---- 14. atelier 2/2 ----------------------------------------------------
s = content_slide("Atelier (2/2) — de ROS 2 à la vérification",
                  kicker="étapes 4 → 7")
box(s, 0.6, 1.6, 12.2, 0.62,
    "Même processus, mêmes contrôles — votre projet à la place de l'UR10",
    ORANGE, size=15)
items2 = [
    (5, "Paquet",
     "URDF + meshes dans urdf/ et meshes/ du paquet ; colcon build ; "
     "source install/setup.bash."),
    (6, "RViz2",
     "ros2 launch … display.launch.py ; Fixed Frame = base ; RobotModel "
     "via /robot_description ; sliders + Randomize."),
    (7, "Cellule",
     "merge comme fixed link sur base (mount depuis la pièce mated) + "
     "couleurs : palette robot / couleurs CAD."),
    (8, "Vérifier",
     "Les joints bougent ? La cellule reste fixe ? tf2_echo base tool_flange "
     "pour les chiffres."),
]
for i, (num, title, text) in enumerate(items2):
    x, y = 0.6, 2.5 + i * 1.12
    note_card(s, x, y, 7.3, 1.0, None, [], line=BORDER)
    badge(s, x + 0.4, y + 0.5, 0.48, num, size=16)
    tb, tf = textbox(s, x + 0.75, y + 0.1, 6.4, 0.85)
    para(tf, True, [(title + " — ", {"bold": True, "color": NAVY}),
                    (text, {})], size=13, space_before=0)
lx, ly, lw, lh = picture_fit(s, SHOTS / "04_joint_sliders_articulated.png",
                             8.2, 2.5, 4.6, 3.5)
caption(s, 8.2, ly + lh + 0.06, 4.6,
        "Résultat attendu : 6 sliders, robot articulé, cellule fixe")

# ---- 15. récap ----------------------------------------------------------
s = content_slide("Ce qu'il faut retenir — 5 règles")
rules = [
    [("L'assembly Onshape est la ", {}),
     ("source de vérité", {"bold": True}),
     (" — les mates SONT la cinématique", {})],
    [("Le prefix ", {}),
     ("dof_", {"mono": True, "bold": True, "color": ORANGE}),
     (" est le contrat d'export : 1 mate revolute = 1 joint", {})],
    [("Une URDF est un ", {}), ("arbre de frames", {"bold": True}),
     (", pas une boîte à meshes", {})],
    [("Vérifier par la ", {}), ("TF", {"bold": True, "color": ORANGE}),
     (" : joints bougent ✓ · cellule fixe ✓ · résidu mate ≈ 0", {})],
    [("Reproductible : ", {}), ("configs", {"bold": True}),
     (" seulement (url, ignore, .env) → un nouveau projet = mêmes étapes",
      {})],
]
y = 1.72
for i, runs in enumerate(rules, start=1):
    badge(s, 0.95, y + 0.26, 0.5, i, size=17)
    tb, tf = textbox(s, 1.45, y, 11.4, 0.75)
    para(tf, True, runs, size=18, color=INK, space_before=0)
    y += 0.88
band = card(s, 0.6, 6.2, 12.2, 0.68, NAVY, None)
tf = band.text_frame
tf.vertical_anchor = MSO_ANCHOR.MIDDLE
para(tf, True, [("1 CAD  ·  2 Export  ·  3 URDF  ·  4 Paquet ROS 2  ·  "
                 "5 RViz2  ·  6 Cellule  ·  7 Vérification",
                 {"bold": True, "color": WHITE})], size=15,
     align=PP_ALIGN.CENTER, space_before=0)

# ================================================================= save
check(SHOTS.is_dir(), f"missing {SHOTS}")
for shot in ("01_before_grey_robot.png", "02_after_environment_colors.png",
             "03_articulated_environment.png", "04_joint_sliders_articulated.png",
             "05_base_tube_junction.png"):
    check((SHOTS / shot).is_file(), f"missing screenshot {shot}")
OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(str(OUT))
print(f"OK — {len(prs.slides._sldIdLst)} slides -> {OUT}")
