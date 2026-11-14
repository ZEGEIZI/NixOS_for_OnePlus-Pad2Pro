# kShimC protocol snapshot

Authority: https://github.com/ZEGEIZI/kShimC-oneplus-pad2-pro.
`source.json` pins the upstream commit and SHA-256 of the imported protocol,
publisher, license and local patch. The NixOS publisher extension in
`patches/shared-payloads.patch` shares verified immutable payloads through
hardlinks; the loader protocol and default copying behavior remain unchanged.

From the NixOS repository root:

```sh
python3 tools/vendor-kshim.py --check
python3 tools/vendor-kshim.py /path/to/kShimC-oneplus-pad2-pro
# Adopt a reviewed upstream commit:
python3 tools/vendor-kshim.py /path/to/kShimC-oneplus-pad2-pro --revision COMMIT
```

The synchronization reads committed Git objects, never local uncommitted files.
`tools/build-menu.py` uses this same upstream revision; pagination and current
entry labels are already upstream. Old import patches are historical material
under `docs/history/kshim/`. Normal NixOS builds need only this local snapshot.
