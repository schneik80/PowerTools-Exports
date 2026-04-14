# PowerTools: Export Tools for Autodesk Fusion

Version 1.0 | Autodesk Fusion Add-in | IMA LLC

Power Tools for Fusion — Exports is an Autodesk Fusion add-in that extends the built-in export capabilities of the platform. It provides commands to export assembly component data and structure to industry-standard formats for use in downstream workflows such as procurement, manufacturing documentation, and architecture visualization.

## Prerequisites

- Autodesk Fusion (any current release)
- Windows 10/11 or macOS 12 or later
- Python runtime included with Autodesk Fusion (no separate installation required)
- (Optional) A Mermaid-compatible viewer to render exported `.mmd` files, such as the [Markdown Preview Mermaid Support](https://marketplace.visualstudio.com/items?itemName=bierner.markdown-mermaid) extension for Visual Studio Code

## Installation

1. Download or clone this repository to a local folder on your computer.
2. In Autodesk Fusion, open the **Scripts and Add-Ins** dialog by selecting **Tools** > **Scripts and Add-Ins**, or by pressing **Shift+S**.
3. On the **Add-Ins** tab, click the **+** icon and browse to the folder where you cloned the repository.
4. Select **PowerTools-Exports** and click **Open**.
5. Click **Run**. The add-in commands become available in the **File** drop-down menu of any open design document.

To load the add-in automatically each time Autodesk Fusion starts, select the **Run on Startup** check box in the Add-Ins dialog.

## Commands

The following commands are available after installation. Each command is accessible from the **File** drop-down menu in the Quick Access Toolbar (QAT) when a Fusion design document is active.

| Command | Output format | Description |
|---|---|---|
| [Export BOM as CSV](./docs/Export%20BOM.md) | `.csv` | Exports a flat bill of materials containing the display name, part number, material, and instance count for each leaf component in the active assembly. |
| [Export Mermaid Diagram](./docs/Export%20Mermaid.md) | `.mmd` | Exports the full hierarchical component relationship tree as a Mermaid left-to-right flowchart file for rendering in Markdown viewers and web tools. |

## Accessing commands

All commands appear in the **File** drop-down menu of the Quick Access Toolbar when a Fusion design document is active. No additional toolbar buttons or panel entries are created.

## Architecture

The following C4 context diagram shows the overall system context for the Power Tools — Exports add-in.

```mermaid
C4Context
    title Power Tools for Fusion — Exports: System Context

    Person(user, "Designer", "Autodesk Fusion user who works with assembly design documents.")

    System(addin, "Power Tools – Exports", "Autodesk Fusion add-in. Provides Export BOM as CSV and Export Mermaid Diagram commands.")

    System_Ext(fusion, "Autodesk Fusion", "CAD platform. Hosts the add-in, provides the design API and component data, and renders the folder browser dialog.")

    System_Ext(fs, "Local File System", "Destination for exported files: .csv and .mmd.")

    System_Ext(downstream, "Downstream Tools", "Spreadsheet applications, Graphviz viewers, Mermaid renderers, and procurement or documentation systems that consume the exported files.")

    Rel(user, fusion, "Opens assembly, invokes export commands")
    Rel(fusion, addin, "Loads add-in on startup, fires command events")
    Rel(addin, fusion, "Reads design component tree via Fusion API")
    Rel(addin, fs, "Writes exported files")
    Rel(user, downstream, "Opens exported files")
    Rel(downstream, fs, "Reads exported files")
```

## Repository structure

```
PowerTools-Exports/
├── PowerTools-Exports.py          # Add-in entry point (run / stop)
├── PowerTools-Exports.manifest    # Autodesk Fusion add-in manifest
├── config.py                      # Add-in configuration constants
├── commands/
│   ├── exportbomcsv/
│   │   └── entry.py               # Export BOM as CSV command
│   └── exportmermaid/
│       └── entry.py               # Export Mermaid Diagram command
├── lib/
│   └── fusionAddInUtils/          # Shared event handler and logging utilities
└── docs/
    ├── Export BOM.md
    └── Export Mermaid.md
```

## License

This project is released under the [GNU General Public License v3.0 or later](LICENSE).

Copyright (C) 2022-2026 IMA LLC.

The vendored library at `lib/fusionAddInUtils` is Autodesk sample code and is distributed under its own license terms; see its source headers for details.

---

*Copyright © 2026 IMA LLC. All rights reserved.*
