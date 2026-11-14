# Board audio sources

This directory is maintained by the NixOS project. `source.json` records the
original board import and the pinned upstream AudioReach archive. The m4
recipes, TDM/MFC helpers and UCM carry their original BSD-3-Clause notices.
No external distribution checkout is needed to build them.

`../audio.nix` compiles and decodes the topology, merges the board UCM with
nixpkgs' generic UCM, and applies the accepted amplifier limit of 270
(-22.5 dB) during installation. Keep that gain policy when updating recipes.
See `docs/AUDIO.md` from the repository root for hardware scope and validation.
