# argus-param-i18n

GPL-3.0 data repository for [Argus GCS](https://github.com/L-X-Yao/argus): normalized ArduPilot
parameter metadata and translations.

This repository contains **data only**. It does not run, command or configure a vehicle.

## What it holds

- `meta/<vehicle>/<series>.json`: normalized English metadata from ArduPilot's `apm.pdef.xml`,
  with the `ArduCopter:` / `ArduPlane:` prefixes removed.
- `tm/<locale>.json`: translations keyed by the SHA-256 of the exact English text. The same
  English string is translated once, even when it appears on several parameters, vehicles or
  firmware series.
- `source.json`: hash -> English source text, for translation and provenance.
- `glossary/<locale>.json`: the terms translators must keep consistent.
- `aliases.json`: old parameter name -> name in the selected metadata.
- `overrides/<vehicle>.json`: descriptions for parameters that no upstream pdef documents.
- `manifest.json`: schema, data version, source URLs and hashes, per-locale coverage.

Argus pins a released `tar.gz` by version and SHA-256 in `param_i18n.lock`. The pack is bundled
into the zip and the Windows installer, so the parameter panel works offline.

## Supported sources

`config/sources.json` lists the vehicles and firmware series. The generator takes
`https://autotest.ardupilot.org/Parameters/versioned/<Vehicle>/stable-<version>/apm.pdef.xml`
and falls back to the legacy master URL when a series is absent.

## Translation status

- `r: 0`: machine translation. The Argus panel marks it.
- `r: 1`: reviewed by a person. The reviewer and date are recorded in the commit.
- `s: "generated"`: the English text itself was generated because no upstream description exists.
  The Argus panel marks it separately.

The pack does not claim that machine-translated text is authoritative. Parameter descriptions are
guidance; the ArduPilot documentation and the vehicle's behaviour remain the source of truth.

## Workflow

The scripts are in `tools/`. They are intentionally thin and deterministic:

```bash
python -m tools.fetch_meta       # download pdef XML into cache/
python -m tools.build_catalog    # normalize, hash, write meta/ and source.json
python -m tools.translate --locale zh --provider claude-cli
python -m tools.validate
python -m tools.release --version 2026.11.1
```

The default translation provider uses the local Claude Code CLI in batch mode. A provider
adapter can also import a JSON file produced by another tool, so a translator is not tied to one
vendor.

## License

The repository is GPL-3.0. The English parameter descriptions are derived from ArduPilot, which
is GPL-3.0. Translations are derivative works of those descriptions. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [LICENSE](LICENSE).

The Argus application remains MIT-licensed. This data is an independent work loaded at runtime.
