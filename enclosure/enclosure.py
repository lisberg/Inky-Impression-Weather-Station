#!/usr/bin/env python3
"""Parametric enclosure for the Inky Impression 7.3" + Raspberry Pi Zero 2 W.

Three printed parts:
  bezel  front frame; the panel drops in from the back, glass against the bezel
  back   rear shell: holds the Pi, presses the board into the bezel, has
         flexure buttons over the board's rear buttons, keyholes for wall
         hanging and for the stand, vents and a USB cable slot
  stand  desk stand that hooks into the lower keyholes, 15° lean

Hardware: 4× M3 heat-set inserts (M3 × 5.7, 4.0 mm hole) in the bezel and
4× M3×25 socket-head screws from the back.

Coordinates: X across, Y up, Z from the front face (0) towards the back.
Everything that depends on the board is in BOARD below; measure your board
with calipers and adjust before printing (see enclosure/README.md).

    pip install cadquery
    python3 enclosure/enclosure.py          # checks fit, writes enclosure/out/*.step and *.3mf
"""
import math
import os
from dataclasses import dataclass, field

import cadquery as cq

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


@dataclass
class Board:
    # Pimoroni spec sheet: board 174.2 × 123.2 mm, active area 160 × 96 mm.
    pcb_w: float = 174.2
    pcb_h: float = 123.2
    pcb_t: float = 1.6
    # 7.3" panel module (glass) outline and thickness incl. adhesive. MEASURE.
    glass_w: float = 170.2
    glass_h: float = 111.2
    glass_t: float = 1.6
    # offset of the glass centre from the board centre (+x right, +y up, seen from the front). MEASURE.
    glass_dx: float = 0.0
    glass_dy: float = 0.0
    # active (image) area and its offset from the board centre. MEASURE.
    active_w: float = 160.0
    active_h: float = 96.0
    active_dx: float = 0.0
    active_dy: float = 0.0
    # M2 corner holes: distance of hole centre from each board edge. MEASURE.
    hole_inset: float = 3.5
    # rear push buttons A-D, centre positions from the board centre seen from the BACK
    # (+x right when looking at the back), and switch height above the PCB. MEASURE.
    buttons: tuple = ((-75.0, 22.5), (-75.0, 7.5), (-75.0, -7.5), (-75.0, -22.5))
    button_h: float = 3.5


@dataclass
class Params:
    board: Board = field(default_factory=Board)
    fit: float = 0.4            # clearance per side around board and glass
    face_t: float = 2.0         # bezel thickness in front of the glass
    side_wall: float = 9.0      # left/right walls; carry the screw bosses
    end_wall: float = 3.0       # top/bottom walls
    corner_r: float = 4.0
    bezel_depth: float = 10.0   # bezel ends here; back shell starts
    back_depth: float = 22.0    # room behind the board for the Pi Zero on its header
    back_t: float = 2.4         # back plate thickness
    insert_d: float = 4.0       # heat-set insert hole
    insert_depth: float = 6.5
    screw_d: float = 3.4
    head_d: float = 6.2
    head_depth: float = 3.2
    lean_deg: float = 15.0      # stand lean
    # flexure button tab
    tab_w: float = 14.0
    tab_h: float = 10.0
    tab_slot: float = 1.0
    tab_t: float = 1.2
    plunger_d: float = 4.5
    plunger_gap: float = 0.6    # free travel before the plunger touches the switch
    # USB cable slot in the bottom wall, centre x seen from the FRONT
    usb_x: float = 0.0
    usb_w: float = 16.0
    usb_h: float = 12.0

    # derived ---------------------------------------------------------------
    @property
    def pocket_w(self):
        return self.board.pcb_w + 2 * self.fit

    @property
    def pocket_h(self):
        return self.board.pcb_h + 2 * self.fit

    @property
    def outer_w(self):
        return self.pocket_w + 2 * self.side_wall

    @property
    def outer_h(self):
        return self.pocket_h + 2 * self.end_wall

    @property
    def pcb_front_z(self):
        return self.face_t + self.board.glass_t

    @property
    def pcb_back_z(self):
        return self.pcb_front_z + self.board.pcb_t

    @property
    def total_depth(self):
        return self.bezel_depth + self.back_depth

    def screw_points(self):
        x = self.pocket_w / 2 + self.side_wall / 2
        y = self.pocket_h / 2 - 12
        return [(sx * x, sy * y) for sx in (-1, 1) for sy in (-1, 1)]

    def hole_points(self):
        b = self.board
        x = b.pcb_w / 2 - b.hole_inset
        y = b.pcb_h / 2 - b.hole_inset
        return [(sx * x, sy * y) for sx in (-1, 1) for sy in (-1, 1)]


def rounded_box(w, h, d, r, z0=0.0):
    return (cq.Workplane("XY").workplane(offset=z0)
            .rect(w, h).extrude(d).edges("|Z").fillet(r))


def bezel(p: Params):
    b = p.board
    body = rounded_box(p.outer_w, p.outer_h, p.bezel_depth, p.corner_r)
    # board pocket from the back
    body = body.cut(cq.Workplane("XY").workplane(offset=p.pcb_front_z)
                    .rect(p.pocket_w, p.pocket_h).extrude(p.bezel_depth))
    # glass recess
    body = body.cut(cq.Workplane("XY").workplane(offset=p.face_t)
                    .center(b.glass_dx, b.glass_dy)
                    .rect(b.glass_w + 2 * p.fit, b.glass_h + 2 * p.fit).extrude(b.glass_t + 0.01))
    # window over the active area, chamfered 45° outwards so the bezel never shades the image
    m = 0.6
    win = (cq.Workplane("XY").center(b.active_dx, b.active_dy)
           .rect(b.active_w + 2 * m + 2 * p.face_t, b.active_h + 2 * m + 2 * p.face_t)
           .workplane(offset=p.face_t).rect(b.active_w + 2 * m, b.active_h + 2 * m)
           .loft())
    body = body.cut(win)
    # heat-set insert holes, from the back face forwards
    body = body.cut(cq.Workplane("XY").workplane(offset=p.bezel_depth - p.insert_depth)
                    .pushPoints(p.screw_points()).circle(p.insert_d / 2).extrude(p.insert_depth))
    # small chamfer on the front edge
    body = body.faces("<Z").edges().chamfer(0.6)
    return body


def _mirror_x(points):
    """Back-view coordinates -> model (front-view) coordinates."""
    return [(-x, y) for x, y in points]


def back(p: Params):
    b = p.board
    z0, z1 = p.bezel_depth, p.total_depth
    plate_in = z1 - p.back_t
    shell = rounded_box(p.outer_w, p.outer_h, p.back_depth, p.corner_r, z0)
    shell = shell.cut(cq.Workplane("XY").workplane(offset=z0)
                      .rect(p.pocket_w, p.pocket_h).extrude(p.back_depth - p.back_t))
    # hollow the thick side walls between the screw bosses to save plastic
    span = 2 * (p.pocket_h / 2 - 12 - 6)
    shell = shell.cut(cq.Workplane("XY").workplane(offset=z0)
                      .pushPoints([(sx * (p.pocket_w / 2 + 2.5), 0) for sx in (-1, 1)])
                      .rect(5.0, span).extrude(p.back_depth - p.back_t))

    # posts press the board's corners into the bezel and locate in its M2 holes
    post_len = plate_in - p.pcb_back_z
    posts = (cq.Workplane("XY").workplane(offset=p.pcb_back_z)
             .pushPoints(p.hole_points()).circle(3.0).extrude(post_len))
    pins = (cq.Workplane("XY").workplane(offset=p.pcb_back_z - 1.2)
            .pushPoints(p.hole_points()).circle(0.85).extrude(1.2))
    shell = shell.union(posts).union(pins)

    # screws: clearance through the side walls, counterbored from the back
    shell = shell.cut(cq.Workplane("XY").workplane(offset=z0)
                      .pushPoints(p.screw_points()).circle(p.screw_d / 2).extrude(p.back_depth))
    shell = shell.cut(cq.Workplane("XY").workplane(offset=z1 - p.head_depth)
                      .pushPoints(p.screw_points()).circle(p.head_d / 2).extrude(p.head_depth))

    # flexure buttons: a U-slot frees a tab hinged on its side towards the middle
    # (so neighbouring tabs can sit close together); the tab is thinned from the
    # inside and carries a plunger, at its free end, down to the switch
    pts = _mirror_x(b.buttons)
    for (x, y) in pts:
        u = (cq.Workplane("XY").workplane(offset=plate_in - 0.01)
             .center(x, y).rect(p.tab_w + 2 * p.tab_slot, p.tab_h + 2 * p.tab_slot)
             .rect(p.tab_w, p.tab_h).extrude(p.back_t + 0.02))
        inward = -math.copysign(1, x)
        hinge = (cq.Workplane("XY").workplane(offset=plate_in - 0.02)
                 .center(x + inward * (p.tab_w / 2 + p.tab_slot / 2), y)
                 .rect(p.tab_slot + 0.02, p.tab_h).extrude(p.back_t + 0.04))
        shell = shell.cut(u.cut(hinge))
        thin = (cq.Workplane("XY").workplane(offset=plate_in - 0.01).center(x, y)
                .rect(p.tab_w, p.tab_h).extrude(p.back_t - p.tab_t + 0.01))
        shell = shell.cut(thin)
        tip_z = p.pcb_back_z + b.button_h + p.plunger_gap
        plunger = (cq.Workplane("XY").workplane(offset=tip_z).center(x, y)
                   .circle(p.plunger_d / 2).extrude(z1 - p.tab_t - tip_z + 0.01))
        shell = shell.union(plunger)

    # keyholes: upper pair for the wall, lower pair for the stand. The slot runs
    # upwards from the entry hole, so the station drops down onto screw or peg.
    for (kx, ky, span) in ((0, p.outer_h / 2 - 32, 100.0), (0, -20.0, 60.0)):
        for sx in (-1, 1):
            cx = kx + sx * span / 2
            key = (cq.Workplane("XY").workplane(offset=plate_in - 0.01)
                   .center(cx, ky).circle(4.1).extrude(p.back_t + 0.02)
                   .union(cq.Workplane("XY").workplane(offset=plate_in - 0.01)
                          .center(cx, ky + 4.5).rect(4.2, 9.0).extrude(p.back_t + 0.02)))
            shell = shell.cut(key)

    # vents in the top and bottom walls, long axis along Z so they print without bridges
    for side in (1, -1):
        y = side * (p.pocket_h / 2 + p.end_wall / 2)
        for i in range(-4, 5):
            x = i * 9.0
            if side == -1 and abs(x - p.usb_x) < p.usb_w / 2 + 4:
                continue
            shell = shell.cut(cq.Workplane("XY").workplane(offset=z0 + 6)
                              .center(x, y).rect(2.2, p.end_wall + 0.2).extrude(p.back_depth - 10))
    # USB cable slot in the bottom wall
    slot_z = z0 + 3
    shell = shell.cut(cq.Workplane("XZ").workplane(offset=p.outer_h / 2)
                      .center(p.usb_x, slot_z + p.usb_h / 2).rect(p.usb_w, p.usb_h)
                      .extrude(p.end_wall + 0.5).edges("|Y").fillet(2.0))

    # labels beside the buttons (towards the middle), debossed into the outside
    # face; text on an XY plane reads correctly when seen from +Z, i.e. from behind
    for label, (x, y) in zip("ABCD", pts):
        lx = x - math.copysign(p.tab_w / 2 + p.tab_slot + 4, x)
        shell = shell.cut(cq.Workplane("XY").workplane(offset=z1 - 0.4).center(lx, y)
                          .text(label, 6, 0.41, kind="bold", halign="center", valign="center"))
    return shell


def stand(p: Params):
    """Desk stand: a base plate with a ledge the station sits on, a lip in front
    of its bottom edge and a back plate whose two pegs hook into the lower
    keyholes. Modelled in a side profile (x towards the back, y up), extruded
    across the width; the base reaches well in front of the station so it
    can't tip forward when the buttons on the back are pressed."""
    th = math.radians(p.lean_deg)
    u = (math.sin(th), math.cos(th))     # up along the station's back face
    n = (math.cos(th), -math.sin(th))    # out of the back face
    D = p.total_depth
    base_t, width, L, plate_t = 5.0, 70.0, 75.0, 4.0
    c = (0.0, base_t)                                     # station's back-bottom corner
    front = (c[0] - D * n[0], c[1] - D * n[1])           # front-bottom corner
    lip_h, lip_t = 8.0, 3.0
    lip_out = (front[0] - lip_t * n[0], front[1] - lip_t * n[1])
    top_in = (c[0] + L * u[0], c[1] + L * u[1])
    top_out = (top_in[0] + plate_t * n[0], top_in[1] + plate_t * n[1])
    foot = 62.0

    def prism(points, z0, w):
        return cq.Workplane("XY").workplane(offset=z0).polyline(points).close().extrude(w)

    half = width / 2
    base = prism([(front[0] - 15, 0), (foot, 0), (foot, base_t), (front[0] - 15, base_t)], -half, width)
    ledge = prism([c, front, (front[0], base_t)], -half, width)
    lip = prism([front, lip_out, (lip_out[0] + lip_h * u[0], lip_out[1] + lip_h * u[1]),
                 (front[0] + lip_h * u[0], front[1] + lip_h * u[1])], -half, width)
    lip_foot = prism([(lip_out[0], base_t), lip_out, front, (front[0], base_t)], -half, width)
    plate = prism([c, top_in, top_out, (c[0] + plate_t * n[0], c[1])], -half, width)
    part = base.union(ledge).union(lip).union(lip_foot).union(plate)
    for z in (-half, -3.0, half - 6):
        part = part.union(prism([(c[0] + plate_t * n[0], base_t), top_out, (foot, base_t)], z, 6))

    # pegs: keyhole entry is 20 mm below the centre, slot 6 mm up from there
    peg_s = p.outer_h / 2 - 20.0 + 6.0
    for zx in (-30.0, 30.0):
        o = cq.Vector(c[0] + peg_s * u[0], c[1] + peg_s * u[1], zx)
        plane = cq.Plane(origin=o, xDir=(0, 0, 1), normal=(-n[0], -n[1], 0))
        neck = cq.Workplane(plane).circle(1.85).extrude(p.back_t + 0.4)
        head = (cq.Workplane(plane).workplane(offset=p.back_t + 0.4).circle(3.7).extrude(2.0)
                .faces(cq.selectors.DirectionMinMaxSelector(cq.Vector(-n[0], -n[1], 0), True))
                .chamfer(0.6))
        part = part.union(neck).union(head)
    return part


def dummy_board(p: Params):
    """Board, glass, rear buttons and a Pi Zero, for clearance checks only."""
    b = p.board
    pcb = (cq.Workplane("XY").workplane(offset=p.pcb_front_z).rect(b.pcb_w, b.pcb_h)
           .extrude(b.pcb_t)
           .cut(cq.Workplane("XY").workplane(offset=p.pcb_front_z).pushPoints(p.hole_points())
                .circle(1.1).extrude(b.pcb_t)))
    glass = (cq.Workplane("XY").workplane(offset=p.face_t).center(b.glass_dx, b.glass_dy)
             .rect(b.glass_w, b.glass_h).extrude(b.glass_t))
    keys = (cq.Workplane("XY").workplane(offset=p.pcb_back_z).pushPoints(_mirror_x(b.buttons))
            .rect(6, 6).extrude(b.button_h))
    # Pi Zero 2 W (65 × 30) on an ~11 mm header stack, parts up to 3 mm tall
    pi = (cq.Workplane("XY").workplane(offset=p.pcb_back_z + 11).rect(65, 30)
          .extrude(1.4 + 3.0))
    return pcb.union(glass).union(keys).union(pi)


def build(p=None):
    p = p or Params()
    return {"bezel": bezel(p), "back": back(p), "stand": stand(p)}, p


def export(parts, p):
    os.makedirs(OUT, exist_ok=True)
    for name, wp in parts.items():
        shape = wp.val()
        # print orientation: bezel face down as modelled; back flipped onto its back plate
        if name == "back":
            shape = shape.rotate((0, 0, 0), (1, 0, 0), 180).translate((0, 0, p.total_depth))
        wp = cq.Workplane().add(shape)
        cq.exporters.export(wp, os.path.join(OUT, "%s.step" % name))
        cq.exporters.export(wp, os.path.join(OUT, "%s.3mf" % name), tolerance=0.05, angularTolerance=0.1)
        bb = shape.BoundingBox()
        print("%-6s %6.1f × %6.1f × %5.1f mm  %6.1f cm³" % (name, bb.xlen, bb.ylen, bb.zlen,
                                                           shape.Volume() / 1000))


def station_on_stand(parts, p, extra=()):
    """Bezel and back (and any `extra` shapes) placed on the stand, in its coordinates."""
    th = p.lean_deg
    D, H = p.total_depth, p.outer_h
    out = []
    for sh in [parts["bezel"].val(), parts["back"].val()] + list(extra):
        # station frame -> stand frame: back-bottom corner to the origin, Y up the face,
        # Z (depth) along the back-face normal, X across becomes the extrude axis
        sh = sh.translate((0, H / 2, -D))
        sh = sh.rotate((0, 0, 0), (0, 1, 0), 90)  # (X, Y, Z) -> (Z, Y, -X)
        sh = sh.rotate((0, 0, 0), (0, 0, 1), -th).translate((0, 5.0, 0))
        out.append(sh)
    return out


def check(parts, p):
    """Fail loudly if printed parts collide with each other or with the board,
    or if neighbouring button tabs leave too little plate between them."""
    board = dummy_board(p).val()
    pairs = [("bezel", "back"), ("bezel", "board"), ("back", "board")]
    solids = {"bezel": parts["bezel"].val(), "back": parts["back"].val(), "board": board}
    bad = []
    for a, b in pairs:
        v = solids[a].intersect(solids[b]).Volume()
        print("overlap %-5s / %-5s %8.3f mm³" % (a, b, v))
        if v > 0.01:
            bad.append((a, b, v))
    st = parts["stand"].val()
    for sh, name in zip(station_on_stand(parts, p), ("bezel", "back")):
        v = st.intersect(sh).Volume()
        print("overlap stand / %-5s %8.3f mm³" % (name, v))
        if v > 0.01:
            bad.append(("stand", name, v))
    ys = sorted(y for _, y in p.board.buttons)
    web = min(b - a for a, b in zip(ys, ys[1:])) - p.tab_h - 2 * p.tab_slot
    print("plate between button tabs: %.1f mm" % web)
    if web < 2:
        bad.append(("buttons", "too close for tab_h", web))
    head_room = p.total_depth - p.back_t - (p.pcb_back_z + 11 + 4.4)
    print("room behind the Pi: %.1f mm" % head_room)
    if bad or head_room < 1:
        raise SystemExit("interference: %s" % bad)


if __name__ == "__main__":
    parts, params = build()
    check(parts, params)
    export(parts, params)
