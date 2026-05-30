# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2022-2026 IMA LLC
#
# Original PowerTools-Exports code. Subclasses InteractiveHtmlBom's MIT-licensed
# EcadParser (see ../../LICENSE and ../../THIRD_PARTY_LICENSES.md); the MIT base
# is GPL-compatible, and this derivative module is GPL-3.0-or-later.
"""Live Fusion Electronics (adsk.electron) board parser.

Reads an open Fusion Electronics PCB directly via the read-only `adsk.electron`
API (Fusion May 2026 release, preview) instead of an exported `.brd` file. This
is the add-in's primary path; `eagle.py` is the file-based fallback / dev harness
(see FUSION_ADDIN_PLAN.md, D3).

The `adsk.electron` object model is EAGLE's ULP model in Python, so this adapter
shares the EAGLE coordinate convention, layer-ID constants, and pcbdata geometry
builders with `eagle.py`. It differs in only three ways:

  1. Coordinates are signed ints in internal units (1/320000 mm per count);
     convert with `adsk.electron.Units.u2mm`.  We wrap that in `fx`/`fy` below.
  2. Rotation is already decomposed on `Element` (`.angle`, `.mirror`, `.spin`),
     so there is no `MR180`-style string to parse.
  3. Layers are live `Layer` objects (`board.layers`, each `.number`) rather than
     XML attributes, but the numeric IDs are identical (Fusion Electronics is
     EAGLE underneath).

Coverage: board outline (incl. arcs), per-element footprints, package + board
silkscreen graphics, reference / value text, copper tracks, vias and polygon
pours (zones), plus the BOM via the linked schematic.

Pad caveat: the current Fusion preview's public adsk.electron API does not
expose pad geometry (Contact.smd / Contact.pad are always None and there is no
dx/drill/shape anywhere reachable from an add-in). Pads are therefore rendered
at each contact's true position and net, sized from the contact pitch — see
_element_pads.
"""

import math
from datetime import datetime

from .common import EcadParser, Component, BoundingBox
from ..core.fontparser import FontParser
# Shared with the file-based parser: EAGLE layer-ID constants. (fx/fy are
# redefined here because the live API gives us integer internal units rather
# than float-mm strings.)
from .eagle import (
    LAYER_TOP_COPPER, LAYER_BOTTOM_COPPER,
    LAYER_DIMENSION,
    LAYER_TOP_PLACE, LAYER_BOTTOM_PLACE,
    LAYER_TOP_NAMES, LAYER_BOTTOM_NAMES,
    LAYER_TOP_VALUES, LAYER_BOTTOM_VALUES,
)


# Silkscreen / documentation text layers that should render with the silk graphics.
_TOP_SILK_LAYERS = (LAYER_TOP_PLACE, LAYER_TOP_NAMES, LAYER_TOP_VALUES)
_BOTTOM_SILK_LAYERS = (LAYER_BOTTOM_PLACE, LAYER_BOTTOM_NAMES, LAYER_BOTTOM_VALUES)


def _units():
    """Return adsk.electron.Units, imported lazily (only exists inside Fusion)."""
    import adsk.electron
    return adsk.electron.Units


def _mm(internal_units):
    """Internal units (int, 1/320000 mm per count) -> mm. No axis flip.

    iBom board coordinates are this value for X and its negative for Y (EAGLE is
    Y-up, iBom is Y-down); callers apply that flip where they build points.
    """
    return float(_units().u2mm(internal_units or 0))


class FusionElectronicsParser(EcadParser):

    def __init__(self, board, config, logger):
        """
        :param board: an adsk.electron.Board (already cast from activeProduct)
        :param config: Config instance
        :param logger: logging object
        """
        # Give the base class a synthetic "file name" derived from the document
        # so downstream code (which expects a path) keeps working unchanged.
        #
        # NOTE: these are live API properties whose getters can raise (e.g.
        # Board.parentDocument throws InternalValidationError in some Fusion
        # builds), so getattr's default is not enough — a missing attribute
        # raises AttributeError but a failing getter raises RuntimeError. Probe
        # each one defensively and fall back to a constant name.
        name = (self._safe_attr(self._safe_attr(board, "parentDocument"), "name")
                or self._safe_attr(board, "name")
                or "fusion_board")
        super(FusionElectronicsParser, self).__init__(name, config, logger)
        self.board = board
        # Collects the glyphs for every string we emit; the rendered output is
        # placed in pcbdata["font_data"] so the web viewer can stroke the text.
        self._font = FontParser()

    @staticmethod
    def _safe_attr(obj, attr):
        """getattr that also tolerates a property getter raising.

        Returns None if `obj` is None, the attribute is absent, or its live
        API getter raises (RuntimeError on some Fusion builds)."""
        if obj is None:
            return None
        try:
            return getattr(obj, attr, None)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Top-level entry point — same (pcbdata, components) contract as eagle.py
    # ------------------------------------------------------------------
    def parse(self):
        board = self.board
        if board is None:
            self.logger.error("No board supplied to FusionElectronicsParser.")
            return None, None

        edges, edges_bbox = self._parse_edges()
        if not edges_bbox.initialized():
            self.logger.error(
                "No board outline found on layer %d (Dimension). "
                "Define the board outline before generating the BOM."
                % LAYER_DIMENSION)
            return None, None

        modules, components, silkscreen = self._parse_elements()
        # Free-standing board text (titles, labels) on the silk layers.
        for side, drawings in self._parse_board_text().items():
            silkscreen[side].extend(drawings)
        tracks, zones = self._parse_signals()
        fabrication = {"F": [], "B": []}

        # Diagnostic: how much the web UI is expected to render. If these counts
        # are non-zero but the page shows only the board outline, the failure is
        # downstream in the browser (e.g. a JS exception in populateMetadata),
        # not here in parsing.
        pad_count = sum(len(m["pads"]) for m in modules)
        self.logger.info(
            "Parsed %d element(s): %d module(s), %d pad(s), %d/%d silk (F/B), "
            "%d/%d tracks, %d/%d zones, %d BOM component(s) expected."
            % (len(components), len(modules), pad_count,
               len(silkscreen["F"]), len(silkscreen["B"]),
               len(tracks["F"]), len(tracks["B"]),
               len(zones["F"]), len(zones["B"]), len(components)))

        title = self.file_name
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        pcbdata = {
            "edges_bbox": edges_bbox.to_dict(),
            "edges": edges,
            "silkscreen": silkscreen,
            "fabrication": fabrication,
            "modules": modules,
            "metadata": {
                "title": title,
                "revision": "",
                "company": "",
                "date": date,
            },
            "bom": {},
            # Glyph strokes for every string emitted above (refs, values, text).
            "font_data": self._font.get_parsed_font(),
        }
        if self.config.include_tracks:
            pcbdata["tracks"] = tracks
            pcbdata["zones"] = zones

        return pcbdata, components

    # ------------------------------------------------------------------
    # Helpers (the .count / .item(i) collection pattern is used throughout)
    # ------------------------------------------------------------------
    def _parse_edges(self):
        """Board outline from wires on layer 20 (Dimension).

        Curved wires (rounded corners, cutouts) are subdivided into short
        segments by _wire_points so the outline closes correctly.
        """
        edges = []
        bbox = BoundingBox()
        for w in self._iter(self._safe_attr(self.board, "wires")):
            if self._layer_number(w) != LAYER_DIMENSION:
                continue
            width = _mm(self._safe_attr(w, "width")) or 0.1
            pts = [[x, -y] for x, y in self._wire_points(w)]
            for a, b in zip(pts, pts[1:]):
                edges.append({
                    "type": "segment",
                    "start": a,
                    "end": b,
                    "width": width,
                })
                bbox.add_segment(a[0], a[1], b[0], b[1], width / 2.0)
        return edges, bbox

    def _parse_elements(self):
        """Build a footprint (module) + Component + silk drawings per Element.

        Returns (modules, components, silkscreen) where silkscreen is
        {"F": [...], "B": [...]} of board-space drawing dicts collected from
        every element's package graphics.
        """
        modules = []
        components = []
        silkscreen = {"F": [], "B": []}

        for el in self._iter(self._safe_attr(self.board, "elements")):
            ref = self._safe_attr(el, "name") or ""
            val = self._safe_attr(el, "value") or ""
            mirror = bool(self._safe_attr(el, "mirror"))
            layer = 'B' if mirror else 'F'

            pkg = self._safe_attr(el, "package")
            footprint = self._safe_attr(pkg, "name") or ""

            to_board = self._placement(el)
            center = to_board(0.0, 0.0)

            pads = self._element_pads(pkg, to_board, layer)
            silk = self._element_silk(pkg, to_board, mirror)
            text = self._element_text(el, pkg, to_board, mirror)
            for side in ("F", "B"):
                silkscreen[side].extend(silk[side])
                silkscreen[side].extend(text[side])

            modules.append({
                "ref": ref,
                "center": center,
                "bbox": self._module_bbox(pads, center),
                "pads": pads,
                "drawings": [],   # footprint silk lives in top-level silkscreen
                "layer": layer,
            })
            components.append(Component(ref, val, footprint, layer))

        return modules, components, silkscreen

    # ------------------------------------------------------------------
    # Placement transform (EAGLE local -> iBom board coordinates)
    # ------------------------------------------------------------------
    def _placement(self, el):
        """Return a to_board(lx_mm, ly_mm) closure for one placed Element.

        It maps a package-local point (mm, EAGLE Y-up) to an iBom board point
        [x, y] (mm, Y-down). EAGLE places an element by (optionally) mirroring
        the footprint across its local Y axis, rotating CCW by `angle`, then
        translating to (x, y); iBom then flips Y. Validated to 0 mm against a
        placed part's known pad coordinates.
        """
        ex = _mm(self._safe_attr(el, "x"))
        ey = _mm(self._safe_attr(el, "y"))
        ang = float(self._safe_attr(el, "angle") or 0.0)
        mirror = bool(self._safe_attr(el, "mirror"))
        a = math.radians(ang)
        cos_a, sin_a = math.cos(a), math.sin(a)

        def to_board(lx_mm, ly_mm):
            if mirror:
                lx_mm = -lx_mm
            rx = lx_mm * cos_a - ly_mm * sin_a
            ry = lx_mm * sin_a + ly_mm * cos_a
            return [ex + rx, -(ey + ry)]

        return to_board

    # ------------------------------------------------------------------
    # Pad extraction (package contacts -> iBom pad dicts)
    # ------------------------------------------------------------------
    #
    # LIMITATION: the public adsk.electron API in the current Fusion preview
    # does NOT expose pad geometry. Every Contact reports a position, name and
    # signal, but Contact.smd / Contact.pad are always None, there is no
    # dx/drill/shape on the contact, and Package has no .smds / .pads
    # collection. (The Fusion MCP can read it via Autodesk-internal access, but
    # an add-in cannot.) So we render each contact as a position- and
    # net-accurate pad whose size is estimated from the contact pitch; shape and
    # the SMD/TH distinction are not recoverable. Swap in real geometry once the
    # API exposes it.
    def _element_pads(self, pkg, to_board, side):
        locs = []
        for c in self._iter(self._safe_attr(pkg, "contacts")):
            cx = self._safe_attr(c, "x")
            cy = self._safe_attr(c, "y")
            if cx is None or cy is None:
                continue
            locs.append((c, _mm(cx), _mm(cy)))

        size = self._estimate_pad_size([(x, y) for _, x, y in locs])
        pads = []
        for c, lx, ly in locs:
            pad = {
                "layers": [side],
                "pos": to_board(lx, ly),
                "size": [size, size],
                "angle": 0.0,
                "shape": "circle",
                "type": "smd",
                "net": self._safe_attr(c, "signal") or "",
            }
            if (self._safe_attr(c, "name") or "") == "1":
                pad["pin1"] = 1
            pads.append(pad)
        return pads

    @staticmethod
    def _estimate_pad_size(points):
        """Approximate a pad size (mm) from the closest spacing of contacts."""
        n = len(points)
        if n < 2:
            return 1.0
        best = None
        m = min(n, 60)   # cap the O(n^2) scan on large footprints
        for i in range(m):
            xi, yi = points[i]
            for j in range(i + 1, m):
                xj, yj = points[j]
                d = math.hypot(xi - xj, yi - yj)
                if d > 1e-6 and (best is None or d < best):
                    best = d
        if best is None:
            return 1.0
        return max(0.4, min(best * 0.55, 2.0))

    # ------------------------------------------------------------------
    # Silkscreen extraction (package wires / circles / rectangles)
    # ------------------------------------------------------------------
    def _element_silk(self, pkg, to_board, mirror):
        out = {"F": [], "B": []}

        for w in self._iter(self._safe_attr(pkg, "wires")):
            side = self._silk_side(self._layer_number(w), mirror)
            if side is None:
                continue
            width = max(_mm(self._safe_attr(w, "width")), 0.05)
            pts = [to_board(x, y) for x, y in self._wire_points(w)]
            for a, b in zip(pts, pts[1:]):
                out[side].append({
                    "type": "segment", "start": a, "end": b, "width": width,
                })

        for c in self._iter(self._safe_attr(pkg, "circles")):
            side = self._silk_side(self._layer_number(c), mirror)
            if side is None:
                continue
            out[side].append({
                "type": "circle",
                "start": to_board(_mm(c.x), _mm(c.y)),
                "radius": _mm(self._safe_attr(c, "radius")),
                "width": max(_mm(self._safe_attr(c, "width")), 0.05),
            })

        for r in self._iter(self._safe_attr(pkg, "rectangles")):
            side = self._silk_side(self._layer_number(r), mirror)
            if side is None:
                continue
            x1, y1 = _mm(r.x1), _mm(r.y1)
            x2, y2 = _mm(r.x2), _mm(r.y2)
            corners = [to_board(x1, y1), to_board(x2, y1),
                       to_board(x2, y2), to_board(x1, y2)]
            out[side].append({
                "type": "polygon",
                "pos": [0.0, 0.0],
                "angle": 0.0,
                "polygons": [corners],
            })

        return out

    # ------------------------------------------------------------------
    # Footprint bounding box (axis-aligned over transformed pad corners)
    # ------------------------------------------------------------------
    @staticmethod
    def _module_bbox(pads, center):
        bb = BoundingBox()
        for p in pads:
            cx, cy = p["pos"]
            hw, hh = p["size"][0] / 2.0, p["size"][1] / 2.0
            a = math.radians(p.get("angle", 0.0))
            cos_a, sin_a = math.cos(a), math.sin(a)
            for sx, sy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
                bb.add_point(cx + sx * cos_a - sy * sin_a,
                             cy + sx * sin_a + sy * cos_a)
        if not bb.initialized():
            bb.add_point(center[0], center[1])
            bb.pad(0.5)
        return bb.to_component_dict()

    # ------------------------------------------------------------------
    # Copper routing: tracks, vias and polygon pours (zones)
    # ------------------------------------------------------------------
    def _parse_signals(self):
        """Tracks/zones for the F.Cu and B.Cu layers from Board.signals.

        Inner-layer copper is dropped (iBom renders only outer layers). Vias
        are drawn as round dots on both outer layers (the vendored web has no
        dedicated via primitive, but a zero-length round-capped track renders
        as a filled circle)."""
        tracks = {"F": [], "B": []}
        zones = {"F": [], "B": []}

        for sig in self._iter(self._safe_attr(self.board, "signals")):
            net = self._safe_attr(sig, "name") or ""

            for w in self._iter(self._safe_attr(sig, "wires")):
                side = self._copper_side_strict(self._layer_number(w))
                if side is None:
                    continue
                width = max(_mm(self._safe_attr(w, "width")), 0.05)
                pts = [[x, -y] for x, y in self._wire_points(w)]
                for a, b in zip(pts, pts[1:]):
                    tracks[side].append(
                        {"start": a, "end": b, "width": width, "net": net})

            for v in self._iter(self._safe_attr(sig, "vias")):
                vx, vy = self._safe_attr(v, "x"), self._safe_attr(v, "y")
                if vx is None or vy is None:
                    continue
                d = _mm(self._safe_attr(v, "diameter"))
                if d <= 0:
                    drill = _mm(self._safe_attr(v, "drill"))
                    d = drill * 1.5 if drill > 0 else 0.6
                pos = [_mm(vx), -_mm(vy)]
                tracks["F"].append(
                    {"start": pos, "end": list(pos), "width": d, "net": net})
                tracks["B"].append(
                    {"start": list(pos), "end": list(pos), "width": d, "net": net})

            for pour in self._iter(self._safe_attr(sig, "polyPours")):
                side = self._copper_side_strict(self._layer_number(pour))
                if side is None:
                    continue
                ring = self._poly_ring(pour)
                if len(ring) >= 3:
                    zones[side].append(
                        {"net": net, "width": 0, "polygons": [ring]})

        return tracks, zones

    def _poly_ring(self, pour):
        """Ordered boundary of a PolyPour as a list of [x, y] iBom points.

        Uses the pour's outline wires; the inner cutouts / thermal reliefs are
        not subtracted (the fill is an approximation of the copper region)."""
        ring = []
        for w in self._iter(self._safe_attr(pour, "wires")):
            # Drop each wire's last point: it coincides with the next wire's
            # start, so the ring stays free of duplicate vertices.
            for x, y in self._wire_points(w)[:-1]:
                ring.append([x, -y])
        return ring

    # ------------------------------------------------------------------
    # Text: free board labels and per-element reference / value
    # ------------------------------------------------------------------
    def _parse_board_text(self):
        out = {"F": [], "B": []}
        for t in self._iter(self._safe_attr(self.board, "texts")):
            side = self._text_side(self._layer_number(t))
            if side is None:
                continue
            pos = [_mm(self._safe_attr(t, "x")), -_mm(self._safe_attr(t, "y"))]
            d = self._text_drawing(
                t, pos, float(self._safe_attr(t, "angle") or 0.0),
                self._safe_attr(t, "value") or "")
            if d:
                out[side].append(d)
        return out

    def _element_text(self, el, pkg, to_board, mirror):
        """Reference / value (and any literal package text) on the silk layers.

        Package text uses EAGLE's >NAME / >VALUE placeholders; we substitute the
        element's reference and value and tag them so the viewer's
        References / Values toggles work."""
        out = {"F": [], "B": []}
        ref = self._safe_attr(el, "name") or ""
        val = self._safe_attr(el, "value") or ""
        ang_el = float(self._safe_attr(el, "angle") or 0.0)

        for t in self._iter(self._safe_attr(pkg, "texts")):
            side = self._text_side(self._layer_number(t))
            if side is None:
                continue
            if mirror:
                side = 'B' if side == 'F' else 'F'
            raw = self._safe_attr(t, "value") or ""
            if raw == ">NAME":
                content, kind = ref, "ref"
            elif raw == ">VALUE":
                content, kind = val, "val"
            else:
                content, kind = raw, None
            if not content:
                continue
            local_ang = float(self._safe_attr(t, "angle") or 0.0)
            angle = ang_el - local_ang if mirror else ang_el + local_ang
            pos = to_board(_mm(self._safe_attr(t, "x")),
                           _mm(self._safe_attr(t, "y")))
            d = self._text_drawing(t, pos, angle, content, kind)
            if d:
                out[side].append(d)
        return out

    def _text_drawing(self, t, pos, angle, content, kind=None):
        """Build an iBom stroke-text drawing and register its glyphs.

        `angle` is the EAGLE (Y-up, CCW) angle; the web renderer negates it to
        compensate for the Y flip baked into every coordinate."""
        if not content:
            return None
        size = _mm(self._safe_attr(t, "size")) or 1.0
        ratio = self._safe_attr(t, "ratio") or 8
        self._font.parse_font_for_string(content)
        d = {
            "pos": pos,
            "text": content,
            "height": size,
            "width": size,
            "thickness": max(size * ratio / 100.0, 0.02),
            "angle": angle,
            "attr": [],
            "horiz_justify": -1,
        }
        if kind == "ref":
            d["ref"] = 1
        elif kind == "val":
            d["val"] = 1
        return d

    # ------------------------------------------------------------------
    # Wire geometry (straight segment or subdivided arc)
    # ------------------------------------------------------------------
    def _wire_points(self, w):
        """Trace a wire as EAGLE-space (mm, Y-up) points.

        Straight wires give their two endpoints; curved wires (curve != 0) are
        flattened into a short polyline approximating the arc."""
        x1, y1 = _mm(self._safe_attr(w, "x1")), _mm(self._safe_attr(w, "y1"))
        x2, y2 = _mm(self._safe_attr(w, "x2")), _mm(self._safe_attr(w, "y2"))
        curve = float(self._safe_attr(w, "curve") or 0.0)
        if abs(curve) < 1e-9:
            return [(x1, y1), (x2, y2)]
        arc = self._safe_attr(w, "arc")
        xc, yc = self._safe_attr(arc, "xc"), self._safe_attr(arc, "yc")
        radius = self._safe_attr(arc, "radius")
        if xc is None or yc is None or radius is None:
            return [(x1, y1), (x2, y2)]
        xc, yc, radius = _mm(xc), _mm(yc), _mm(radius)
        a1 = math.atan2(y1 - yc, x1 - xc)
        sweep = math.radians(curve)
        n = max(2, int(abs(curve) / 12.0) + 1)
        return [(xc + radius * math.cos(a1 + sweep * i / n),
                 yc + radius * math.sin(a1 + sweep * i / n))
                for i in range(n + 1)]

    # ------------------------------------------------------------------
    # Collection / layer helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _iter(collection):
        """Yield items from an adsk.electron .count/.item(i) collection.

        Tolerant of None and of getters that raise on individual items."""
        if collection is None:
            return
        try:
            n = collection.count
        except Exception:
            return
        for i in range(n):
            try:
                item = collection.item(i)
            except Exception:
                continue
            if item is not None:
                yield item

    @staticmethod
    def _layer_number(obj):
        """Layer id for a geometry object: an int `.layer`, or `.layer.number`."""
        layer = FusionElectronicsParser._safe_attr(obj, "layer")
        if layer is None:
            return None
        num = FusionElectronicsParser._safe_attr(layer, "number")
        return num if num is not None else layer

    @staticmethod
    def _copper_side_strict(layer_num):
        """Map an outer copper-layer id to 'F'/'B'; None for inner layers."""
        if layer_num == LAYER_TOP_COPPER:
            return 'F'
        if layer_num == LAYER_BOTTOM_COPPER:
            return 'B'
        return None

    @staticmethod
    def _text_side(layer_num):
        """Map a silk/name/value layer id to 'F'/'B', or None if not silk."""
        if layer_num in _TOP_SILK_LAYERS:
            return 'F'
        if layer_num in _BOTTOM_SILK_LAYERS:
            return 'B'
        return None

    @staticmethod
    def _silk_side(layer_num, mirror):
        """Map a silk-layer id (21/22, + mirror) to 'F'/'B', or None if not silk."""
        if layer_num == LAYER_TOP_PLACE:
            top = True
        elif layer_num == LAYER_BOTTOM_PLACE:
            top = False
        else:
            return None
        if mirror:
            top = not top
        return 'F' if top else 'B'
