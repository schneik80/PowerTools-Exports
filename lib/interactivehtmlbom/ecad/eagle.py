"""EAGLE 6+ XML .brd parser.

Targets the XML format used by EAGLE 6 through EAGLE 9.6.2 and the
"EAGLE 9.X brd compatible" export from Autodesk Fusion Electronics.
Earlier (EAGLE <= 5) binary .brd files are NOT supported.

Coordinate conventions:
  EAGLE: bottom-left origin, Y-up, millimetres, angles in degrees CCW.
  iBom : top-left origin (any negative offset is fine), Y-down, mm.
We invert Y (y_ibom = -y_eagle) and rotation (angle_ibom = -angle_eagle).
"""

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime

from .common import EcadParser, Component, BoundingBox


# Canonical EAGLE layer IDs (stable across 6.x - 9.6.2 and Fusion exports).
LAYER_TOP_COPPER = 1
LAYER_BOTTOM_COPPER = 16
LAYER_DIMENSION = 20         # board outline
LAYER_TOP_PLACE = 21         # silkscreen
LAYER_BOTTOM_PLACE = 22
LAYER_TOP_NAMES = 25         # reference designators
LAYER_BOTTOM_NAMES = 26
LAYER_TOP_VALUES = 27
LAYER_BOTTOM_VALUES = 28
LAYER_TOP_DOCU = 51          # fabrication
LAYER_BOTTOM_DOCU = 52


# EAGLE rotation attribute: optional 'S' (spin lock), optional 'M' (mirror /
# bottom side), then 'R' and degrees. Examples: "R0", "R90", "MR180", "SMR270".
_ROT_RE = re.compile(r"^(S?)(M?)R(-?\d+(?:\.\d+)?)$")


def parse_rotation(rot_str):
    """Returns (mirrored, angle_deg). mirrored=True means bottom side."""
    if not rot_str:
        return False, 0.0
    m = _ROT_RE.match(rot_str.strip())
    if not m:
        return False, 0.0
    _spin, mirror, deg = m.groups()
    return bool(mirror), float(deg)


def fy(y):
    """Flip Y from EAGLE (Y-up) to iBom (Y-down). Mm in, mm out."""
    return -float(y)


def fx(x):
    return float(x)


def fa(angle):
    """Flip rotation angle to compensate for Y-axis flip."""
    return -float(angle)


class EagleParser(EcadParser):

    def __init__(self, file_name, config, logger):
        super(EagleParser, self).__init__(file_name, config, logger)
        self._tree = None
        self._board = None
        self._packages = {}   # (library_name, package_name) -> <package> elem

    # ------------------------------------------------------------------
    # Top-level entry point
    # ------------------------------------------------------------------
    def parse(self):
        try:
            self._tree = ET.parse(self.file_name)
        except ET.ParseError as e:
            self.logger.error(
                "Failed to parse %s: %s" % (self.file_name, e))
            return None, None

        root = self._tree.getroot()
        if root.tag != 'eagle':
            self.logger.error(
                "Not an EAGLE XML file (root tag = %s). EAGLE <=5 binary .brd "
                "files are not supported." % root.tag)
            return None, None

        self.logger.info(
            "EAGLE file version %s" % root.get('version', 'unknown'))

        drawing = root.find('drawing')
        if drawing is None:
            self.logger.error("No <drawing> element in EAGLE file.")
            return None, None
        self._board = drawing.find('board')
        if self._board is None:
            self.logger.error(
                "No <board> element. Schematic-only .sch files are not "
                "supported by this parser.")
            return None, None

        self._index_packages()

        edges, edges_bbox = self._parse_edges()
        if not edges_bbox.initialized():
            self.logger.error(
                "No board outline found on layer 20 (Dimension). "
                "Draw the outline before exporting.")
            return None, None

        # TODO(task 6): real element + package + pad extraction.
        # TODO(task 7): tracks / vias / zones from <signals>.
        # TODO(task 8): silkscreen + fabrication from package drawings on
        #               layers 21/22 + 51/52, plus ref/value text from elements.
        modules, components = self._parse_elements_minimal()
        silkscreen = {"F": [], "B": []}
        fabrication = {"F": [], "B": []}
        tracks = {"F": [], "B": []}
        zones = {"F": [], "B": []}

        file_mtime = os.path.getmtime(self.file_name)
        file_date = datetime.fromtimestamp(file_mtime).strftime(
            '%Y-%m-%d %H:%M:%S')
        title = os.path.splitext(os.path.basename(self.file_name))[0]

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
                "date": file_date,
            },
            "bom": {},
            "font_data": {},
        }
        if self.config.include_tracks:
            pcbdata["tracks"] = tracks
            pcbdata["zones"] = zones

        return pcbdata, components

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _index_packages(self):
        libraries = self._board.find('libraries')
        if libraries is None:
            return
        for library in libraries.findall('library'):
            lib_name = library.get('name', '')
            packages = library.find('packages')
            if packages is None:
                continue
            for package in packages.findall('package'):
                pkg_name = package.get('name', '')
                self._packages[(lib_name, pkg_name)] = package

    def _parse_edges(self):
        """Walk <plain> for layer 20 (Dimension) wires only.

        Phase-1 scope: straight segments. Arcs (wire@curve), circles, and
        polygon outlines on layer 20 are deferred to task 8.
        """
        edges = []
        bbox = BoundingBox()
        plain = self._board.find('plain')
        if plain is None:
            return edges, bbox

        for wire in plain.findall('wire'):
            if wire.get('layer') != str(LAYER_DIMENSION):
                continue
            x1, y1 = fx(wire.get('x1')), fy(wire.get('y1'))
            x2, y2 = fx(wire.get('x2')), fy(wire.get('y2'))
            width = float(wire.get('width', '0')) or 0.1
            edges.append({
                "type": "segment",
                "start": [x1, y1],
                "end": [x2, y2],
                "width": width,
            })
            bbox.add_segment(x1, y1, x2, y2, width / 2.0)

        return edges, bbox

    def _parse_elements_minimal(self):
        """Stub element walker.

        Emits one Component + one empty footprint per <element> so the BOM
        pipeline has something to chew on. Geometry (pads, drawings, real
        bbox) is filled in by task 6.
        """
        modules = []
        components = []
        elements = self._board.find('elements')
        if elements is None:
            return modules, components

        for el in elements.findall('element'):
            ref = el.get('name', '')
            val = el.get('value', '')
            pkg_name = el.get('package', '')
            lib_name = el.get('library', '')
            x, y = fx(el.get('x', '0')), fy(el.get('y', '0'))
            mirrored, angle = parse_rotation(el.get('rot', 'R0'))
            layer = 'B' if mirrored else 'F'

            # Placeholder zero-size bbox so the JS doesn't NaN out.
            bbox = BoundingBox()
            bbox.add_point(x, y)
            bbox.pad(0.5)

            modules.append({
                "ref": ref,
                "center": [x, y],
                "bbox": {
                    "pos": [x, y],
                    "relpos": [-0.5, -0.5],
                    "size": [1.0, 1.0],
                    "angle": fa(angle),
                },
                "pads": [],
                "drawings": [],
                "layer": layer,
            })
            components.append(
                Component(ref, val, "%s:%s" % (lib_name, pkg_name), layer))

        return modules, components
