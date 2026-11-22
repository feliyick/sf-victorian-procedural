# SF Victorian House — procedural Houdini street

A procedural San Francisco Victorian ("Painted Ladies") house as a Houdini digital asset (HDA), plus a street
system around it, rendered in Karma/Solaris. Houdini **20.5.370**, **Apprentice / non-commercial** licence
(`.hipnc`, `.hdanc`, renders capped at 1280x720). This file is the context an AI agent works from in this project.

## Files
- `SanFranciscoHouse_v4_hda.hipnc` — **the working scene**.
- `otls/sfh_victorian_house.hdanc` — the house HDA (type used by `victorian_house`, `row_house`, `house_L*/R*`).
- `*.vfl` — VEX source for every code node (the HDA's wrangle snippets are loaded from these files):
  - inside the HDA: `openings_build` (windows, hoods, garage doors), `roof_build` (cornice, gables, brackets),
    `ornament` (carved scrolls/sprays/sunbursts from `orn_slot` points), `porch_detail` (columns, beam, newels),
    `window_dressing` (rooms, curtains, blinds, plants per window), `paint` (paint roles, palettes, materials,
    stoop finishes, lit rooms), `house_number_place`.
  - street level (in `/obj/sf_house_geometry`): `house_tag`, `row_layout`, `street_build`, `city_backdrop`.
- `vex/include/facade_lib.h` — shared VEX for the HDA (`rand_range`, `place_part`, `add_quad`, `add_box` = chamfered
  box driven by spare parm `bevel`, `bracket_v`/`scroll_bracket`, plan helpers).
  `vex/include/street_lib.h` — shared VEX for street + backdrop (`gy` = ground height on the hill, `face`, `sbox`,
  `lbox`, `cyl`, `hcyl`, `blob`, `wire`). **Not yet embedded in the HDA**: the asset needs `vex/include/` beside it.
- `materials/build_materials.py` — generates MaterialX procedural (world-space, no UV) materials →
  `house_materials_vN.mtlx`. Current: **v16**. `/stage/sfh_mtlx` sublayers it (path relative to `$HIP`);
  `/stage/sfh_assign` assigns by prim path `/house/<material>` and `/street/<material>` (geometry carries `s@path`).
- `lights_lop.py`, `street_lights_lop.py` — code of the Python LOPs `sfh_lights` and `sfh_street_lights`.
- `check_errors.py` — read-only: re-cooks the asset and `/stage`, prints every node with an error.
- `capture_portfolio.py`, `exr2web.py`, `make_contact_sheet.py` — unattended Karma renders and web conversion.
- `houdini_mcp_config.json` — this project's settings for [houdini-mcp](https://github.com/feliyick/houdini-mcp).

## Scene layout
- `/obj/sf_house_geometry`
  - `victorian_house` — the **hero** house (house_id 0) → `OUT_RENDER` → `hero_tag`.
  - Row: `STREET_CONTROLS` null holds all street parms (Row Count, Slope, Gap, Street Seed, trees, leaves,
    cars, Street Extends, Clouds, Night Sky, **Editable Houses**).
    - procedural: `row_begin`/`row_house`/`row_tag`/`row_end` For-Each (seed = hero seed + 101·n). Row Count only
      drives this mode.
    - editable: `house_L1..3`, `house_R1..3` real HDA nodes with the same live random expressions; typing a value overrides.
    - `row_mode` switch → `row_layout` (lays houses down the hill, writes detail arrays hx0/hx1/hb/hd/bay_x0/bay_x1)
      → `row_move` (the row of houses only) → `street_build` (reads everything from geometry, no node names)
      → `city_backdrop` → `OUT_STREET`.
- `/stage`: `sfh_house_import` (OUT_STREET) → merge → `sfh_mtlx` → `sfh_assign` → looks →
  `sfh_look` switch (0 golden, 1 fog, 2 original, 3 dusk, 4 sunny, 5 night) → `sfh_lights` (room/lamp emission per look)
  → cameras (`cam_front`, `cam_wide`, `cam_hero`, `cam_tele`, `cam_street`, `cam_aerial`, `cam_row_up`,
  `cam_row_down`, plus `mcp_cam_*` made by `frame_camera`) → `sfh_karma_render`.

## Conventions / rules that came from real failures
- **Back up before writing, save after.** A crash once lost work because the save happened before the changes.
- Changes must be **re-runnable** and must **never overwrite the artist's manual edits** (check for existing
  nodes / expressions / non-default values before setting).
- After any change: cook and check for errors. Verify geometry with real data, not assumptions.
- **Never hot-reload a .mtlx** (USD layer cache breaks MaterialX → flat colours). Write a new `vN` file and repoint.
- Editing `facade_lib.h`/`street_lib.h` doesn't recompile nodes: append/replace a `// facade_lib reload <time>`
  comment in each including snippet.
- Menus on the HDA default to Auto/Random; artist overrides are menu choices.
- Paint colours are sRGB in code, written as linear `v@Cd = pow(srgb, 2.2)`.
- Code that runs on cook (Python LOPs `sfh_lights`, `sfh_street_lights`) must not add undo steps: set node comments
  only when they change, inside `hou.undos.disabler()`.
- Any forced cook marks the .hip as unsaved even when nothing changed; that's Houdini, not a bug.
- Cameras: always through `frame_camera` (see the MCP's camera guide); judge framing with `quick_render`, not GL.

## VEX pitfalls hit in this project
- No bit shifts (`>>`, `<<`); use `/` and `%`.
- Always bounded loops (an open `while` hung Houdini for 20 min). Prefer `for (...; i < N && cond; ...)`.
- `append(arr, point(...))` is ambiguous — assign to a typed temp first.
- `len()`/`foreach` on `array()` literals can be ambiguous — use typed array variables.
- Functions can't modify their parameters (read-only) — copy to locals.
- Functions can't see snippet globals — pass arrays in.
- `(name) - x` parses as a cast — drop the brackets.
- Define functions before the snippet's statements.

## Working through houdini-mcp
The agent drives the open Houdini session through [houdini-mcp](https://github.com/feliyick/houdini-mcp)
(settings in `houdini_mcp_config.json`). Prefer its tools over ad-hoc scripts: `scene_info`, `get_parms`,
`set_parms` (dry run first), `cook_and_check`, `viewport_snapshot`, `quick_render`, `frame_camera`,
`sweep_video`. `auto_save` is on (scene saved after each successful MCP edit); `undo`/`redo` only step through
`MCP: ...` undo groups and refuse at the artist's own edits; `reload_listener` picks up listener code changes.
