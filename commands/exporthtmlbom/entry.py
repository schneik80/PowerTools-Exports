# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2022-2026 IMA LLC

import os
import tempfile
import traceback

import adsk.core

from ...lib import fusionAddInUtils as futil
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface


def _fusion_theme() -> str:
    """Return 'dark' or 'light' matching Fusion's currently applied UI theme.

    Uses ``activeUserInterfaceTheme`` so the "follow device OS theme" setting is
    resolved to the actually rendered theme. Mirrors the Version Diff command so
    our exports follow the same convention. Defaults to 'dark' (Fusion's default)
    on any failure.
    """
    try:
        theme = app.preferences.generalPreferences.activeUserInterfaceTheme
        dark_set = {
            adsk.core.UserInterfaceThemes.DarkBlueUserInterfaceTheme,
            adsk.core.UserInterfaceThemes.DarkGrayUserInterfaceTheme,
        }
        return "dark" if theme in dark_set else "light"
    except Exception:
        return "dark"

CMD_NAME = "Export Interactive HTML BOM"
CMD_ID = "PTE-exporthtmlbom"
CMD_Description = (
    "Generate a self-contained interactive HTML BOM from the active "
    "Fusion Electronics PCB (read-only adsk.electron API)."
)
IS_PROMOTED = False

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []


class _IbomLogger(object):
    """Logger that bridges the vendored ibom pipeline to futil + the UI."""

    def info(self, msg, *args):
        try:
            futil.log(str(msg) % args if args else str(msg))
        except Exception:
            futil.log(str(msg))

    def warn(self, msg):
        futil.log("WARNING: " + str(msg))

    def error(self, msg):
        futil.log("ERROR: " + str(msg))
        ui.messageBox(str(msg), CMD_NAME)


# Executed when add-in is run.
def start():
    cmd_def = ui.commandDefinitions.addButtonDefinition(
        CMD_ID, CMD_NAME, CMD_Description
    )
    futil.add_handler(cmd_def.commandCreated, command_created)

    # Add a button into the File drop-down of the Quick Access Toolbar,
    # matching the other PowerTools export commands.
    file_dd = futil.get_qat_file_dropdown()
    if file_dd:
        file_dd.controls.addCommand(cmd_def, "ExportCommand", False)


# Executed when add-in is stopped.
def stop():
    futil.remove_from_qat_file_dropdown(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)
    if command_definition:
        command_definition.deleteMe()


def command_created(args: adsk.core.CommandCreatedEventArgs):
    futil.add_handler(
        args.command.execute, command_execute, local_handlers=local_handlers
    )
    futil.add_handler(
        args.command.destroy, command_destroy, local_handlers=local_handlers
    )


def _resolve_board():
    """Return an adsk.electron.Board for the active product, or None.

    Accepts an active PCB (Board) directly, or an active Schematic with a
    linked board.
    """
    import adsk.electron

    product = app.activeProduct
    board = adsk.electron.Board.cast(product)
    if board:
        return board

    schematic = adsk.electron.Schematic.cast(product)
    if schematic and schematic.linkedBoard:
        return schematic.linkedBoard

    return None


def command_execute(args: adsk.core.CommandEventArgs):
    try:
        # adsk.electron requires the Fusion May 2026 release or newer.
        try:
            import adsk.electron  # noqa: F401
        except ImportError:
            ui.messageBox(
                "This command requires the Fusion Electronics API "
                "(adsk.electron), available in the May 2026 release or newer.",
                CMD_NAME,
            )
            return

        board = _resolve_board()
        if not board:
            ui.messageBox(
                "Open an Electronics PCB (or a schematic linked to one) "
                "before running this command.",
                CMD_NAME,
            )
            return

        # Vendored, wx-free InteractiveHtmlBom pipeline.
        from ...lib.interactivehtmlbom.core import ibom
        from ...lib.interactivehtmlbom.core.config import Config
        from ...lib.interactivehtmlbom.ecad.fusion_electronics import (
            FusionElectronicsParser,
        )

        # The version string is surfaced as pcbdata.ibom_version and the web UI
        # parses it with /^v\d+\.\d+/ for the footer link; if it does NOT start
        # with "v<major>.<minor>" that regex returns null and populateMetadata()
        # throws, which silently aborts BOM-table + component/pad rendering
        # (leaving only the board outline). Keep the leading vN.N.
        cfg = Config(version="v1.0 PowerTools-Exports / Fusion Electronics")
        # Write to the OS temp folder and display it in Fusion's built-in web
        # panel (QTWebBrowser) rather than prompting for a folder / launching an
        # external browser, matching the Version Diff command's report flow.
        cfg.bom_dest_dir = tempfile.gettempdir()   # absolute -> used directly
        # Timestamp the name (%D date, %T time) so every export is a fresh file:
        # the iBOM viewer persists the dark-mode toggle in localStorage keyed by
        # URL, so reusing one name would let a stale manual toggle override the
        # Fusion-theme default below — and it avoids re-opening a locked file.
        cfg.bom_name_format = "%f_%D_%T"
        cfg.open_browser = False          # we display in the Fusion web panel
        cfg.include_tracks = True         # emit copper tracks/vias/zones
        # Follow Fusion's active light/dark theme so the report matches the UI.
        cfg.dark_mode = (_fusion_theme() == "dark")

        logger = _IbomLogger()
        parser = FusionElectronicsParser(board, cfg, logger)
        bom_file = ibom.main(parser, cfg, logger)

        if bom_file:
            # Fusion's embedded Qt web browser; file:/// + absolute path mirrors
            # the Version Diff report display.
            app.executeTextCommand(f"QTWebBrowser.Display file:///{bom_file}")
            futil.log(f"{CMD_NAME}: displayed {bom_file}")
        # On failure the logger already surfaced an error message box.

    except Exception:
        futil.log(traceback.format_exc())
        futil.handle_error(CMD_NAME, show_message_box=True)


def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    local_handlers = []
    futil.log(f"{CMD_NAME} Command Destroy Event")
