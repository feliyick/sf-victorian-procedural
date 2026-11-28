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
    stoop finishes, lit rooms), `house_number_place`, `doorbell_build` (labelled doorbell beside the front door),
    `semantic_labels` (synthetic-data class/instance ids per build branch).
  - street level (in `/obj/sf_house_geometry`): `house_tag`, `row_layout`, `street_build`, `city_backdrop`,
    `blob_protos` (the 8 foliage blob shapes), `usd_structure` (USD prim paths per object, see USD structure below).
- `vex/include/facade_lib.h` — shared VEX for the HDA (`rand_range`, `place_part`, `add_quad`, `add_box` = chamfered
  box driven by spare parm `bevel`, `bracket_v`/`scroll_bracket`, plan helpers).
  `vex/include/street_lib.h` — shared VEX for street + backdrop (`gy` = ground height on the hill, `face`, `sbox`,
  `lbox`, `cyl`, `hcyl`, `blob`, `wire`). `blob()` emits ONE POINT (pscale, orient, blob_variant, blob_cd) that gets
  an instanced blob shape downstream; `blob_mesh()` is the real-faces version (used by `blob_protos`). **Not yet embedded in the HDA**: the asset needs `vex/include/` beside it.
- `materials/build_materials.py` — generates MaterialX procedural (world-space, no UV) materials →
  `house_materials_vN.mtlx`. Current: **v16**. `/stage/sfh_mtlx` sublayers it (path relative to `$HIP`);
  `/stage/sfh_assign` assigns by prim path `/house/<material>` and `/street/<material>` (geometry carries `s@path`).
- `lights_lop.py`, `street_lights_lop.py`, `semantics_lop.py` — code of the Python LOPs `sfh_lights`,
  `sfh_street_lights`, `sfh_semantics`.
- `usd_publish.py` — hython: writes the street as a payload package to `usd_publish/street/` (see USD structure).
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
      → `city_backdrop` → `OUT_STREET` → `usd_structure` → `OUT_USD` (what Solaris imports).
    - foliage instancing: `street_build` / `city_backdrop` → `*_blob_copy` (Copy to Points, packed, picks the
      `blob_protos` shape by `blob_variant`) → `*_blob_tag` → merged with `*_no_blob_pts` in `*_with_blobs`
      → `synth_labels_street` / `synth_labels_backdrop`.
    - lamp instancing: `street_build` emits one point per lamp (`lamp_pts`, orient, lamp_id) → `lamp_copy` puts
      `lamp_proto` → `lamp_proto_tidy` on them (packed) → `lamp_tag` (group `lamp_inst`) → `street_with_blobs`.
- `/stage`: `sfh_house_import` (OUT_USD) → `sfh_semantics` → merge → `sfh_mtlx` → `sfh_assign` → looks →
  `sfh_look` switch (0 golden, 1 fog, 2 original, 3 dusk, 4 sunny, 5 night) → `sfh_lights` (room/lamp emission per look)
  → cameras (`cam_front`, `cam_wide`, `cam_hero`, `cam_tele`, `cam_street`, `cam_aerial`, `cam_row_up`,
  `cam_row_down`, plus `mcp_cam_*` made by `frame_camera`) → `sfh_karma_render`.

## USD structure (one prim per object, labelled; Replicator / Isaac style)
- `usd_structure` sets `s@path` from the labels: `/World/houses/house_<h>/<class>_<local>/geo` (local =
  instance_id % 1000), parts nest under their parent (`bay_100/window_201`, `door_300/doorbell_350`,
  `window_011/ornament`); street `/World/street/<class>/<material>/geo`, open curves `.../wires`;
  `/World/backdrop/<material>`, sky + clouds `/World/environment/<material>`.
- `sfh_house_import`: partition attribute `material` → per-material GeomSubsets inside each mesh; packed prims →
  PointInstancer (`s@usdinstancerpath`, prototypes under `<instancer>/Prototypes`); only the primvars something
  reads are imported (`P N Cd width base_brick base_top glow_t lamp_on lit skycol semantic_id instance_id
  parent_id house_id`). If a material starts reading a new primvar, add it to that list.
- `sfh_semantics` (Python LOP): class labels on every object prim in both Isaac forms (`SemanticsLabelsAPI:class`
  / `semantics:labels:class`, and legacy `SemanticsAPI:Semantics`), `sfh:instance_id` / `sfh:house_id`, model
  kinds (World assembly, houses group, house component, parts subcomponent), and renames subset family
  `material` → `materialBind` (UsdShade only binds that family).
- Lamp posts: `sfh_lamp_import` (after `sfh_house_import`, which skips group `lamp_inst`) imports them as NATIVE
  instances: `/World/street/street_furniture/lamp_post_NN` (instanceable) sharing `.../Prototypes/lamp_post_00`.
  Foliage = PointInstancer (thousands of unlabelled copies), lamps = native instances (each its own labelled prim).
- `sfh_assign` / `sfh_clay_assign` bind by subset: `/World/**/material_<mat>`, clay `/World/**`, each with
  `^/World/street/street_furniture/lamp_post_*/**` (nothing may be authored inside an instance; the prototype
  under `Prototypes/` gets the binding).
  Old patterns: `backup/sfh_assign_patterns_before_usd_structure.json`.
- `usd_publish.py` → `usd_publish/street/`: `street_scene.usd` (root, payload per house / street part, sublayers
  `looks.usd` = bindings as overs + the .mtlx), `houses/house_<n>.usd` (geometry + labels, opens alone),
  `street.usd`, `backdrop.usd`, `environment.usd`, `metrics.json`. Generated output: git-ignored.

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
`sweep_video`, `usd_export` / `cache_write` (files only under `$HIP`), `hda_edit` / `add_parm` / `hda_save`.
Headless: `houdini-mcp-headless --hip SanFranciscoHouse_v4_hda.hipnc` runs the same tools in hython (never saves over
the scene); use it for exports and batch renders without touching the open GUI session. `auto_save` is on (scene saved after each successful MCP edit); `undo`/`redo` only step through
`MCP: ...` undo groups and refuse at the artist's own edits; `reload_listener` picks up listener code changes.
