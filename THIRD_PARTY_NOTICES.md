# Third-party assets and dependencies

The [MIT license](LICENSE), **Copyright (c) 2026 Avinash S**, covers original LifeOS contributions to the extent the licensor holds rights in them. The owner's authorization and commissioned-project record support that attribution; Git configuration is not ownership evidence. Third-party code, photos, fonts and marks retain their separate terms and holders. No ownership of them is assigned to Avinash S.

## Bundled icons

- Lucide 0.468.0 SVGs and derived PNGs: the retained [ISC license and copyright notice](lifeos/assets/LUCIDE-LICENSE.txt) applies, including the notice for portions originating in Feather. Pinned source URLs and integrity hashes are in the [icon manifest](lifeos/assets/icon-manifest.json).
- The grid mark used in the LifeOS application icon is derived from Lucide's `layout-dashboard` icon, as shown in [the asset-generation script](tools/fetch_icon_assets.py). Its Lucide notice remains applicable; it is not claimed as an exclusively original LifeOS symbol.
- The pull-up, push-up and running pictograms are original LifeOS assets, identified separately in that manifest.
- The Python logo files originate from the [official favicon](https://www.python.org/static/favicon.ico), as recorded in the manifest. The source ICO SHA-256 is `39a32ed052ec937b46c40afcc3b87b98ecf2526cf8b6e2cd1698a8b4cd9a6e39`; the current official download matches it. The PNG is the same 48×48 RGBA image decoded from that ICO. Python® and the Python logo™ are Python Software Foundation trademarks. LifeOS is independent, has no PSF affiliation or endorsement, and does not relicense the mark as its own.

## Bundled photography

The nine local application backgrounds and original source images are from Unsplash. Their separate [license notice](lifeos/assets/backgrounds/LICENSE.txt) and [provenance manifest](lifeos/assets/backgrounds/manifest.json) retain source identifiers, URLs, transformations and hashes. These photos are application assets, not an independent stock-photo offering. The selected MIT source license does not replace the separate [Unsplash License](https://unsplash.com/license).

Original downloads remain in the source tree because the asset checks validate their presence and they support reproducible regrading. Runtime and packaged builds use the smaller monochrome WebP versions. The three screenshots in [docs/screenshots/](docs/screenshots/) include these application backgrounds and show synthetic, isolated test records.

## Python dependencies and system fonts

Runtime dependencies are declared in [pyproject.toml](pyproject.toml); the verified development/build/test pins are in [requirements.txt](requirements.txt). Python, Tcl/Tk, CustomTkinter, Matplotlib, psutil, Pygments, Pillow and transitive dependencies retain their own licenses. Consult each dependency's distributed license notices when redistributing a binary; a project source license does not replace them.

The UI uses fonts supplied by Windows, such as Segoe UI and Consolas. Those system font files are not copied into this repository. Dependencies supply their own runtime font assets.

## Nutrition and exercise references

[Nutrition calculations](lifeos/nutrition.py) label typical food composition references and distinguish approximate recipes. [Exercise metadata](lifeos/exercise_library.py) includes its general reference links. These references are not endorsements, and missing measurements or nutrient values are not inferred as known values.

## Python use review - adjacent marking resolved in source

The [PSF FAQ, Logos and Derivatives](https://www.python.org/psf/trademarks-faq/#logos-and-derivatives) permits color-only changes with the outline preserved and illustrates monochrome use. LifeOS's [renderer](lifeos/ui/icons.py) changes RGB to grayscale, retains the alpha channel, and uses the image for Python-language solution rows; it is not the LifeOS product mark. Grayscale alone is therefore not evidence of a prohibited outline modification.

The [formal policy](https://www.python.org/psf/trademarks/) calls for an adjacent unregistered-trademark marker. Python-language solution rows now display a separate small ™ beside the unchanged logo, with space reserved before the row title. The source renderer's stale color description is corrected. Logo assets, grayscale treatment, attribution and non-affiliation notice are preserved. This resolves the identified source UI marking concern for this freely distributed application identifying Python-language solutions; it does not claim an individual PSF approval or authorize unrelated derived/commercial branding. No external permission request was sent. The existing packaged executable and installer predate this marker and remain unchanged; they must not be described as containing the fix.

## Tcl/Tk core notice review — Resolved for the existing installer

The packaged DLL resources and script requirements identify **Tcl 8.6.15 / Tk 8.6.15**. Version-matched upstream [Tcl terms](https://raw.githubusercontent.com/tcltk/tcl/core-8-6-15/license.terms) and [Tk terms](https://raw.githubusercontent.com/tcltk/tk/core-8-6-15/license.terms) require retention of copyright notices and inclusion of the notice text. They do not require a particular standalone filename.

The unchanged installer already delivers **`ThirdParty-Notices/Python-LICENSE.txt`**, containing both upstream notices verbatim after CRLF/LF normalization. Its compiled input's SHA-256 is `62bec384df47b0328307db41455ff6ea2559e5546b394ac69148561b21703120`; the prior successful installer log records that destination file. The separate bundled `_internal/_tk_data/license.terms` also matches the upstream Tk text. Tcl and Tk notices differ, so the Tk notice alone would not have established this result. The earlier filename-only missing-Tcl warning did not inspect the aggregate text and is superseded by this content review.

Preserve the existing aggregate file on redistribution. No invented text, duplicate notice, installer regeneration or application rebuild is needed for this Tcl/Tk core-notice finding. This result is specific to the tested installer and its recorded notice inputs; it is not a blanket clearance of every third-party component or the older portable folder alone.

## Other scope and remaining review

- The installer already supplements the portable folder with notices for its dependencies, Python and PyInstaller. Earlier claims that those copies were absent from the installer are superseded; they concerned the portable payload's original locations. No binary was changed in this review.
- The photo manifest retains service URLs and hashes rather than individual photographer/canonical-page attribution. Keep its separate source/license information; no photo ownership is claimed by the LifeOS copyright holder.
- The repository is not uniformly MIT-licensed. Retain asset/dependency notices and trademark scope. Source UI marking is addressed; existing binaries predate that change. The installer is unsigned, and another-machine/UAC/all-users installation checks remain outside the completed isolated verification.
