"""Config object.

Vendored from InteractiveHtmlBom (MIT, see ../LICENSE), trimmed to remove the
wx dependency: the FileConfig (config.ini) load/save and the wx settings-dialog
transfer methods are dropped. Callers construct Config(version) and set fields
directly. argparse helpers (add_options/set_from_args) are kept but unused by
the Fusion command.
"""

import argparse  # noqa: F401  (kept for add_options/set_from_args)
import os
import re


class Config:
    FILE_NAME_FORMAT_HINT = (
        'Output file name format supports substitutions:\n'
        '\n'
        '    %f : original pcb file name without extension.\n'
        '    %p : pcb/project title from pcb metadata.\n'
        '    %c : company from pcb metadata.\n'
        '    %r : revision from pcb metadata.\n'
        '    %d : pcb date from metadata if available, '
        'file modification date otherwise.\n'
        '    %D : bom generation date.\n'
        '    %T : bom generation time.\n'
        '\n'
        'Extension .html will be added automatically.'
    )  # type: str

    # Helper constants
    bom_view_choices = ['bom-only', 'left-right', 'top-bottom']
    layer_view_choices = ['F', 'FB', 'B']
    default_sort_order = [
        'C', 'R', 'L', 'D', 'U', 'Y', 'X', 'F', 'SW', 'A',
        '~',
        'HS', 'CNN', 'J', 'P', 'NT', 'MH',
    ]
    default_checkboxes = ['Sourced', 'Placed']
    html_config_fields = [
        'dark_mode', 'show_pads', 'show_fabrication', 'show_silkscreen',
        'highlight_pin1', 'redraw_on_drag', 'board_rotation', 'checkboxes',
        'bom_view', 'layer_view', 'extra_fields'
    ]

    # Defaults

    # HTML section
    dark_mode = False
    show_pads = True
    show_fabrication = False
    show_silkscreen = True
    highlight_pin1 = False
    redraw_on_drag = True
    board_rotation = 0
    checkboxes = ','.join(default_checkboxes)
    bom_view = bom_view_choices[1]
    layer_view = layer_view_choices[1]
    open_browser = True

    # General section
    bom_dest_dir = 'bom/'  # This is relative to pcb file directory
    bom_name_format = 'ibom'
    component_sort_order = default_sort_order
    component_blacklist = []
    blacklist_virtual = True
    blacklist_empty_val = False
    include_tracks = False
    include_nets = False

    # Extra fields section
    netlist_file = None
    netlist_initial_directory = ''  # This is relative to pcb file directory
    extra_fields = []
    normalize_field_case = False
    board_variant_field = ''
    board_variant_whitelist = []
    board_variant_blacklist = []
    dnp_field = ''

    @staticmethod
    def _split(s):
        """Splits string by ',' and drops empty strings from resulting array."""
        return [a.replace('\\,', ',') for a in re.split(r'(?<!\\),', s) if a]

    @staticmethod
    def _join(lst):
        return ','.join([s.replace(',', '\\,') for s in lst])

    def __init__(self, version):
        """Init with built-in defaults (no config.ini persistence)."""
        self.version = version

    # noinspection PyTypeChecker
    def add_options(self, parser, file_name_format_hint):
        # type: (argparse.ArgumentParser, str) -> None
        parser.add_argument('--dark-mode', help='Default to dark mode.',
                            action='store_true')
        parser.add_argument('--hide-pads',
                            help='Hide footprint pads by default.',
                            action='store_true')
        parser.add_argument('--show-fabrication',
                            help='Show fabrication layer by default.',
                            action='store_true')
        parser.add_argument('--hide-silkscreen',
                            help='Hide silkscreen by default.',
                            action='store_true')
        parser.add_argument('--highlight-pin1',
                            help='Highlight pin1 by default.',
                            action='store_true')
        parser.add_argument('--no-redraw-on-drag',
                            help='Do not redraw pcb on drag by default.',
                            action='store_true')
        parser.add_argument('--board-rotation', type=int,
                            default=self.board_rotation * 5,
                            help='Board rotation in degrees (-180 to 180). '
                                 'Will be rounded to multiple of 5.')
        parser.add_argument('--checkboxes',
                            default=self.checkboxes,
                            help='Comma separated list of checkbox columns.')
        parser.add_argument('--bom-view', default=self.bom_view,
                            choices=self.bom_view_choices,
                            help='Default BOM view.')
        parser.add_argument('--layer-view', default=self.layer_view,
                            choices=self.layer_view_choices,
                            help='Default layer view.')
        parser.add_argument('--no-browser', help='Do not launch browser.',
                            action='store_true')
        parser.add_argument('--dest-dir', default=self.bom_dest_dir,
                            help='Destination directory for bom file '
                                 'relative to pcb file directory.')
        parser.add_argument('--name-format', default=self.bom_name_format,
                            help=file_name_format_hint.replace('%', '%%'))
        parser.add_argument('--include-tracks', action='store_true',
                            help='Include track/zone information in output. '
                                 'F.Cu and B.Cu layers only.')
        parser.add_argument('--include-nets', action='store_true',
                            help='Include netlist information in output.')

    def set_from_args(self, args):
        # type: (argparse.Namespace) -> None
        import math

        self.dark_mode = args.dark_mode
        self.show_pads = not args.hide_pads
        self.show_fabrication = args.show_fabrication
        self.show_silkscreen = not args.hide_silkscreen
        self.highlight_pin1 = args.highlight_pin1
        self.redraw_on_drag = not args.no_redraw_on_drag
        self.board_rotation = math.fmod(args.board_rotation // 5, 37)
        self.checkboxes = args.checkboxes
        self.bom_view = args.bom_view
        self.layer_view = args.layer_view
        self.open_browser = not args.no_browser
        self.bom_dest_dir = args.dest_dir
        self.bom_name_format = args.name_format
        self.include_tracks = args.include_tracks
        self.include_nets = args.include_nets

    def get_html_config(self):
        import json
        d = {f: getattr(self, f) for f in self.html_config_fields}
        return json.dumps(d)
