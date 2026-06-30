# MEMORY

## 2026-06-30

- Analysed full structure of `src/catchy/` (14 modules): pipeline order, dependencies, and module roles documented.
- Classified all scripts for idempotency: `setup_svg` is intentionally one-pass (overwrites SVGs for stand-by notes unconditionally, write-gate does not apply). `publish_src` and `publish_main` have no safe mode. All others are safe to re-run.
- Upgraded `README.md` with: overview, pipeline execution order, general warnings, CLI conventions, and a per-module micro reference (intent, run command, re-run safety, caveats).
- Notable bug flagged: `reformat_svg_sizes.py` class is named `ScriptReformatFonts` (copy-paste artifact, should be `ScriptReformatSizes`).
