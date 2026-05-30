# Third-party licenses — `lib/interactivehtmlbom`

This directory is a trimmed, wx-free copy of **InteractiveHtmlBom** plus the
third-party components that project bundles. It is used only by the *Export
Interactive HTML BOM* command. Each source file retains its upstream copyright
and license header; this file is a consolidated inventory and the home for the
full license texts.

The enclosing **PowerTools-Exports** project is licensed **GPL-3.0-or-later**
(see the repository-root `LICENSE`). Every component listed below is licensed
under terms that are compatible with GPLv3 — permissive (MIT / WTFPL) or
GPL-2.0-**or-later** (which may be used under GPLv3). The combined work is
therefore distributable under GPL-3.0-or-later, with each component's own
notice preserved as required.

## Inventory

| Component | Files | Copyright | License | Source |
|---|---|---|---|---|
| InteractiveHtmlBom | `core/*.py` (except `lzstring.py`, `newstroke_font.py`), `ecad/common.py`, `ecad/eagle.py`, `web/ibom.{html,css}`, `web/render.js`, `web/ibom.js`, `web/util.js` | © 2016–2026 qu1ck and the InteractiveHtmlBom authors | MIT (see `LICENSE`) | https://github.com/openscopeproject/InteractiveHtmlBom |
| KiCad *newstroke* stroke font | `core/newstroke_font.py` | © 2010 Vladimir Uryvaev; © 1992–2010 KiCad Developers | **GPL-2.0-or-later** (file header) | https://gitlab.com/kicad/code/kicad |
| lz-string (JS) | `web/lz-string.js` | © 2013 Pieroxy | WTFPL-2.0 (below) | http://pieroxy.net/blog/pages/lz-string/ |
| lz-string (Python port) | `core/lzstring.py` | © 2014 Eduard Tomasek | WTFPL-2.0 (below) | https://github.com/eduardalsina/lz-string-python |
| PEP — Pointer Events Polyfill | `web/pep.js` | © jQuery Foundation and contributors | MIT (below) | https://github.com/jquery/PEP |
| Split.js | `web/split.js` | © Nathan Cahill | MIT (below) | https://github.com/nathancahill/split.js |
| svgpathtools (stripped subset) | `ecad/svgpath.py` | © 2015 Andrew Allan Port and contributors | MIT (below) | https://github.com/mathandy/svgpathtools |
| KiBoM `units.py` (adapted) | `core/units.py` | © Oliver Henry Walters (SchrodingersGat) | MIT (below) | https://github.com/SchrodingersGat/KiBoM |

PowerTools-Exports' own additions to this subset — the Fusion Electronics
adapter `ecad/fusion_electronics.py` and the wx-removal edits to `core/ibom.py`
and `core/config.py` — are part of the GPL-3.0-or-later project and are noted in
those files' headers.

---

## MIT License

Applies to InteractiveHtmlBom, PEP, Split.js, svgpathtools, and KiBoM `units.py`
(each under its own copyright as listed above):

```
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

The full InteractiveHtmlBom MIT text (with its copyright line) is also preserved
verbatim at `lib/interactivehtmlbom/LICENSE`.

---

## WTFPL Version 2

Applies to `web/lz-string.js` (© 2013 Pieroxy) and `core/lzstring.py`
(© 2014 Eduard Tomasek):

```
            DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
                    Version 2, December 2004

 Everyone is permitted to copy and distribute verbatim or modified
 copies of this license document, and changing it is allowed as long
 as the name is changed.

            DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE
   TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION

  0. You just DO WHAT THE FUCK YOU WANT TO.
```

---

## GPL-2.0-or-later (KiCad newstroke font)

`core/newstroke_font.py` is taken from the KiCad source tree and is licensed
under the GNU General Public License, version 2 **or (at your option) any later
version** — see the header in that file. Because it is "or later", it is used
here under GPLv3. The full GPLv3 text accompanies this project at the
repository-root `LICENSE`; the GPLv2 text is available at
https://www.gnu.org/licenses/old-licenses/gpl-2.0.html.
