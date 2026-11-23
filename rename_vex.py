# =====================================================================
# rename_vex.py  —  SF Victorian House: readable VEX pass
#
# Rewrites the wrangles in /obj/sf_house_geometry with clear variable
# names and comments. LOGIC IS UNCHANGED: same attribute names, same
# parameter names, same groups, same random streams.
#
# Safety: for each node it records point/prim counts + bounding box,
# swaps the code, re-cooks, and compares. If anything errors or differs,
# that node is reverted automatically. The old code is also kept in the
# node's user data under 'snippet_backup'.
#
# Run in Houdini:  Windows > Python Shell, then
#   exec(open(hou.text.expandString('$HIP/rename_vex.py')).read())
# Save your file first (File > Save As a new version).
# =====================================================================
import hou

GEO = hou.node('/obj/sf_house_geometry')

NEW = {}

# ---------------------------------------------------------------------
NEW['building_params'] = r'''
// =====================================================================
// building_params  —  Attribute Wrangle, Run Over: Detail, no inputs
//
// The "brain" of the house. Runs ONCE and makes every house-level decision:
//   1. random dimensions (width, depth, floor heights, bay + garage widths)
//   2. picks a layout row from the rule table
//   3. works out where the two columns divide on each floor
// Then creates ONE POINT PER SLOT (garage, door, stairs, bay_*, flat).
// Each slot point carries: name, scale, bbmin/bbmax (the slot's box),
//                          col, floor, flat_bottom
// House-level decisions are written as DETAIL attributes at the end.
//
// Axes:  x = along the street (0 = left corner, W = right corner)
//        y = up (0 = street level)
//        z = out of the facade (0 = front wall, negative = inside the house)
// =====================================================================

int forced_row = chi("pattern");   // -1 = pick a layout at random; 0..5 = force that row

// Random number between lo and hi.
// 'stream' gives each random choice its own sequence, so choices don't move
// together, but the same seed always rebuilds the same house.
float rand_range(float lo, hi; int stream) {
    return fit01(rand(chi("seed") * 7919 + stream), lo, hi);
}

// ---------- 1. dimensions ----------
float house_width    = rand_range(chf("w_min"), chf("w_max"), 10);
float house_depth    = rand_range(chf("d_min"), chf("d_max"), 11);
float floor_height[] = array(rand_range(chf("ground_min"), chf("ground_max"), 12),   // [0] ground floor
                             rand_range(chf("f1_min"),     chf("f1_max"),     13),   // [1] first floor
                             rand_range(chf("f2_min"),     chf("f2_max"),     14));  // [2] top floor
float bay_width        = house_width * rand_range(chf("bay_frac_min"),    chf("bay_frac_max"),    15);
float garage_width     = house_width * rand_range(chf("garage_frac_min"), chf("garage_frac_max"), 16);
float wall_inset       = chf("wall_inset");   // assets sink this far into the wall to hide the seam
float entry_width_rand = rand_range(chf("entry_w_min"), chf("entry_w_max"), 17);   // entry width when no bay is above
int   round_bays       = int(rand(chi("seed") + 3) < chf("round_bay_chance"));      // 1 = half-round bays, 0 = angled

// ---------- 2. layout: the rule table ----------
// Each row of 3 numbers is one valid house:
//   { bays in the DOOR column, bays in the GARAGE column, door floor }
//   bays:       0 = none | 1 = top floor only | 2 = both upper floors (stacked)
//   door floor: 0 = ground | 1 = first floor (stairs fill the ground slot)
int rules[] = array(
    2,2,0,   // both columns stacked bays, door at street level
    2,0,0,   // bays over the door, flat windows over the garage
    2,1,0,   // bays over the door, one top bay over the garage
    0,2,0,   // flat windows over the door, bays over the garage
    0,2,1,   // door upstairs (stairs below), bays over the garage
    1,2,0    // one top bay over the door, bays over the garage
);
int num_rows   = len(rules) / 3;
int layout_row = forced_row < 0 ? int(rand(chi("seed") + 2) * num_rows) : min(forced_row, num_rows - 1);

// which side the garage is on; the door goes on the other side
int garage_col = int(rand(chi("seed") + 1) < 0.5);   // 0 = left, 1 = right
int door_col   = 1 - garage_col;

// The rule row speaks in ROLES (door column / garage column); everything after
// this works in SIDES (left = 0, right = 1). Convert here:
int bay_state[] = array(0, 0);
bay_state[door_col]   = rules[3 * layout_row];
bay_state[garage_col] = rules[3 * layout_row + 1];
int door_floor        = rules[3 * layout_row + 2];

// ---------- 3. floors and column splits ----------
// height where each floor starts (running total of the floor heights)
float floor_bottom[] = array(0.0, floor_height[0], floor_height[0] + floor_height[1]);

// column_split[fl] = the x where the LEFT column ends on floor fl.
// Each floor has its own split, so garage width (ground) and bay width (upper) can differ.
float column_split[] = array(0.0, 0.0, 0.0);
column_split[0] = garage_col == 0 ? garage_width : house_width - garage_width;   // ground: the garage decides
for (int fl = 1; fl < 3; fl++) {
    // does each column have a bay on this floor?
    int left_has_bay  = bay_state[0] == 2 || (bay_state[0] == 1 && fl == 2);
    int right_has_bay = bay_state[1] == 2 || (bay_state[1] == 1 && fl == 2);
    if      (left_has_bay && right_has_bay) column_split[fl] = house_width * 0.5;   // two bays share the width
    else if (left_has_bay)                  column_split[fl] = bay_width;
    else if (right_has_bay)                 column_split[fl] = house_width - bay_width;
    else                                    column_split[fl] = house_width * 0.5;
}
// a stacked bay is one tower, so it must be the same width on both upper floors
if (bay_state[0] == 2) column_split[1] = column_split[2] = min(column_split[1], column_split[2]);
if (bay_state[1] == 2) column_split[1] = column_split[2] = max(column_split[1], column_split[2]);

// ---------- 4. one point per slot ----------
for (int column = 0; column < 2; column++) {
    int col_bays = bay_state[column];
    for (int fl = 0; fl < 3; fl++) {

        // --- what goes in this slot ---
        string asset;
        if (fl == 0)
            asset = column == garage_col ? "garage" : (door_floor == 0 ? "door" : "stairs");
        else if (col_bays == 2)
            asset = fl == 1 ? "bay_base" : "bay_cap";      // stacked: lower piece / upper piece
        else if (col_bays == 1 && fl == 2)
            asset = "bay_solo";                            // a single bay on the top floor
        else if (fl == 1 && column == door_col && door_floor == 1)
            asset = "door";                                // upstairs door
        else
            asset = "flat";                                // flat window

        // --- the slot's left/right edges ---
        float slot_left  = column == 0 ? 0.0 : column_split[fl];
        float slot_right = column == 0 ? column_split[fl] : house_width;

        // bays never touch the building corner or each other: leave wall either side
        if (startswith(asset, "bay")) {
            float corner_gap = chf("bay_edge_gap");        // wall left at the building corner
            float middle_gap = chf("bay_mid_gap") * 0.5;   // half the wall between the two columns
            if (column == 0) { slot_left += corner_gap; slot_right -= middle_gap; }
            else             { slot_left += middle_gap; slot_right -= corner_gap; }
        }

        // A slot can be split into several parts (an entry + a flat window beside it).
        // These three arrays list each part's name and left/right edge.
        string part_names[]  = array(asset);
        float  part_lefts[]  = array(slot_left);
        float  part_rights[] = array(slot_right);

        // --- entry strip: where the door/stairs sit inside this column ---
        if (asset == "door" || asset == "stairs") {
            // default: entry_width_rand wide, pushed against the party wall
            float entry_width = min(entry_width_rand, slot_right - slot_left);
            float entry_left  = column == 0 ? slot_left : slot_right - entry_width;

            if (col_bays > 0) {   // a bay above → size and centre the entry under it
                // measure the bay on the floor where it starts: stacked → floor 1, top-only → floor 2
                int bay_floor = col_bays == 2 ? 1 : 2;

                // the column's edges on that floor...
                float bay_left  = column == 0 ? 0.0 : column_split[bay_floor];
                float bay_right = column == 0 ? column_split[bay_floor] : house_width;

                // ...shrunk by the gaps → the bay's actual edges
                float corner_gap = chf("bay_edge_gap");
                float middle_gap = chf("bay_mid_gap") * 0.5;
                if (column == 0) { bay_left += corner_gap; bay_right -= middle_gap; }
                else             { bay_left += middle_gap; bay_right -= corner_gap; }

                // entry width = a fraction of the bay's width (never wider than the slot)
                entry_width = min((bay_right - bay_left) * chf("entry_bay_frac"), slot_right - slot_left);

                // centre it under the bay, then keep it inside the slot
                float bay_centre = (bay_left + bay_right) * 0.5;
                entry_left = clamp(bay_centre - entry_width * 0.5, slot_left, slot_right - entry_width);
            }

            float entry_right = entry_left + entry_width;
            part_lefts[0]  = entry_left;
            part_rights[0] = entry_right;

            // no bay above and enough room left over → a flat window beside the entry
            if (col_bays == 0 && (slot_right - slot_left) - entry_width > chf("min_side_w")) {
                append(part_names,  "flat");
                append(part_lefts,  column == 0 ? entry_right : slot_left);
                append(part_rights, column == 0 ? slot_right  : entry_left);
            }
        }

        // --- create one point per part ---
        float slot_bottom = floor_bottom[fl];
        float slot_top    = slot_bottom + floor_height[fl];
        for (int p = 0; p < len(part_names); p++) {
            string part_name  = part_names[p];
            float  part_left  = part_lefts[p];
            float  part_right = part_rights[p];
            vector part_size  = set(part_right - part_left, slot_top - slot_bottom, 1);

            // scale = how big Copy to Points makes the unit asset
            //   x/y fill the part; z = how far it sticks out of the facade
            vector asset_scale = part_size;
            if (startswith(part_name, "bay"))
                asset_scale.z = round_bays ? part_size.x * 0.5 : chf("bay_depth");   // half-round bays stay circular
            else if (part_name == "stairs")
                asset_scale.z = chf("stair_depth");
            else if (part_name == "flat") {
                float window_size = min(part_size.x, part_size.y) * chf("flat_fill");   // square window, centred
                asset_scale = set(window_size, window_size, chf("trim_depth"));
            }
            else
                asset_scale.z = chf("trim_depth");                                     // door, garage

            // point = bottom-centre of the part, sunk into the wall by wall_inset
            int pt = addpoint(0, set((part_left + part_right) * 0.5, slot_bottom, -wall_inset));
            setpointattrib(0, "name",  pt, part_name);
            setpointattrib(0, "scale", pt, asset_scale);
            // flat_bottom: bays that must not taper (a lower stacked bay, or a bay over an upstairs door)
            setpointattrib(0, "flat_bottom", pt, part_name == "bay_base" ||
                           (part_name == "bay_solo" && column == door_col && door_floor == 1));
            setpointattrib(0, "col",   pt, column);
            setpointattrib(0, "floor", pt, fl);
            setpointattrib(0, "bbmin", pt, set(part_left,  slot_bottom, -wall_inset));
            setpointattrib(0, "bbmax", pt, set(part_right, slot_top,    asset_scale.z - wall_inset));
        }
    }
}

// ---------- 5. house-level decisions for downstream nodes (detail attributes) ----------
f@W          = house_width;
f@D          = house_depth;
f@building_h = floor_height[0] + floor_height[1] + floor_height[2];
f[]@floor_h  = floor_height;
f[]@split    = column_split;
i[]@state    = bay_state;
i@garage_col = garage_col;
i@door_col   = door_col;
i@door_floor = door_floor;
i@bay_round  = round_bays;
'''

# ---------------------------------------------------------------------
NEW['entry_params'] = r'''
// =====================================================================
// entry_params  —  Attribute Wrangle, Run Over: Detail
//   input 1: empty      input 2: building_params
//
// Designs the front entry: finds the door slot, decides porch / pediment,
// sizes the opening, and creates one point per part (name + scale) for
// Copy to Points: recess_cut, column, beam, cap / pediment.
// Also writes detail attributes read by entry_door and stair_params.
// =====================================================================

// random number between lo and hi, from the house seed (see building_params)
float rand_range(float lo, hi; int stream) {
    return fit01(rand(chi("../building_params/seed") * 7919 + stream), lo, hi);
}

// Create one part: a box from box_min to box_max.
// The unit asset sits bottom-centre on its point, so the point goes at the
// box's bottom-centre and 'scale' is the box's size.
void place_part(string part_name; vector box_min, box_max) {
    int pt = addpoint(0, set((box_min.x + box_max.x) * 0.5, box_min.y, (box_min.z + box_max.z) * 0.5));
    setpointattrib(0, "name",  pt, part_name);
    setpointattrib(0, "scale", pt, box_max - box_min);
}

// ---------- read the door slot from building_params ----------
int door_pt = findattribval(1, "point", "name", "door");
if (door_pt < 0) return;                                    // no door → nothing to build

vector slot_min    = point(1, "bbmin", door_pt);
vector slot_max    = point(1, "bbmax", door_pt);
int    door_col    = detail(1, "door_col");
int    door_floor  = detail(1, "door_floor");
int    bay_state[] = detail(1, "state");                   // per column: 0 none, 1 top only, 2 stacked

// ---------- decisions ----------
// is there a bay directly above the door?
int bay_above = (door_floor == 0 && bay_state[door_col] == 2)    // ground door under a stacked bay
             || (door_floor == 1 && bay_state[door_col] == 1);   // upstairs door under a top bay
// upstairs doors always get a porch; ground doors sometimes (never under a bay)
int has_porch    = door_floor == 1 ? 1 : (!bay_above && rand_range(0, 1, 40) < chf("porch_chance_ground"));
int use_pediment = rand_range(0, 1, 41) < chf("gable_chance");    // triangle top vs flat cap

// ---------- sizes ----------
float slot_left      = slot_min.x;
float slot_right     = slot_max.x;
float opening_bottom = slot_min.y;                          // where the opening starts
float floor_height   = slot_max.y - slot_min.y;
if (door_floor == 0) opening_bottom += chf("stoop_h");      // ground-floor door sits one step above the street

float edge_margin = chf("edge_margin");
float porch_width = (slot_right - slot_left) - 2 * edge_margin;   // the entry slot is already sized in building_params
float porch_left  = slot_left + edge_margin;
float porch_right = porch_left + porch_width;

float opening_height = floor_height * chf("opening_frac");
// With a bay above, the top of the opening must stay below:
//   floor line (slot_min.y + floor_height) − clearance (bay skirt + molding + casing)
// Subtract opening_bottom to turn that position into a height.
if (bay_above) {
    opening_height = min(opening_height, slot_min.y + floor_height - chf("bay_clear") - opening_bottom);
}

float recess_depth  = has_porch ? chf("recess_d") : chf("flush_d");     // how deep the door sits in the wall
float column_radius = chf("col_r");
float column_z      = rand_range(chf("col_z_min"), chf("col_z_max"), 44);   // how far the columns stand out
float beam_height   = chf("beam_h");
float overhang      = chf("overhang");

// ---------- opening cut into the wall (subtracted by boolean_recess) ----------
place_part("recess_cut",
           set(porch_left  + 2 * column_radius, opening_bottom,                  -recess_depth),
           set(porch_right - 2 * column_radius, opening_bottom + opening_height,  0.3));

// ---------- porch: columns, beam, flat cap or triangular pediment ----------
if (has_porch) {
    float column_x[] = array(porch_left + column_radius, porch_right - column_radius);
    foreach (float cx; column_x)
        place_part("column",
                   set(cx - column_radius, opening_bottom,                  column_z - column_radius),
                   set(cx + column_radius, opening_bottom + opening_height, column_z + column_radius));

    float beam_front_z = column_z + column_radius + overhang;
    place_part("beam",
               set(porch_left  - overhang, opening_bottom + opening_height,               -0.05),
               set(porch_right + overhang, opening_bottom + opening_height + beam_height, beam_front_z));

    float beam_top_y = opening_bottom + opening_height + beam_height;
    if (use_pediment)
        place_part("pediment",
                   set(porch_left  - overhang, beam_top_y,                               -0.05),
                   set(porch_right + overhang, beam_top_y + porch_width * chf("pitch"),  beam_front_z + overhang));
    else
        place_part("cap",
                   set(porch_left  - 2 * overhang, beam_top_y,        -0.05),
                   set(porch_right + 2 * overhang, beam_top_y + 0.12, beam_front_z + 2 * overhang));
}

// ---------- detail attributes for downstream nodes ----------
// stair_params: the stairs line up with the porch
f@porch_x0 = porch_left;
f@porch_x1 = porch_right;
i@porch    = has_porch;

// entry_door: the opening (same as the recess cut) and door style
f@ox0 = porch_left  + 2 * column_radius;
f@ox1 = porch_right - 2 * column_radius;
f@oy0 = opening_bottom;
f@oy1 = opening_bottom + opening_height;
f@rec = recess_depth;
i@arch   = rand_range(0, 1, 43) < chf("arch_chance");
i@double = (f@ox1 - f@ox0) > chf("double_min_w");      // wide opening → double door

// stair_params: where the landing's front edge is (the stairs start here)
//   with a porch: just past the beam;  without: a small stoop in front of the door
float landing_front_z = has_porch ? (column_z + column_radius + overhang) + chf("land_ext") : chf("stoop_d");
f@door_y = opening_bottom;
f@land_z = landing_front_z;
'''

# ---------------------------------------------------------------------
NEW['stair_params'] = r'''
// =====================================================================
// stair_params  —  Attribute Wrangle, Run Over: Detail
//   input 1: empty      input 2: entry_params
//
// Lays out the front stairs from the street up to the door. Creates:
//   - one point per part for Copy to Points (name + scale):
//       landing, step, newel, newel_cap, baluster, cheek
//   - two 'rail' polylines (left/right handrail paths) for rail_sweep
//   - detail attributes bal_style / newel_style for the asset Switches
//
// Steps are counted from the TOP: step 1 is just below the landing,
// step num_steps is at street level.
// =====================================================================

float rand_range(float lo, hi; int stream) {
    return fit01(rand(chi("../building_params/seed") * 7919 + stream), lo, hi);
}

// same helper as entry_params: one box from box_min to box_max
void place_part(string part_name; vector box_min, box_max) {
    int pt = addpoint(0, set((box_min.x + box_max.x) * 0.5, box_min.y, (box_min.z + box_max.z) * 0.5));
    setpointattrib(0, "name",  pt, part_name);
    setpointattrib(0, "scale", pt, box_max - box_min);
}

// Extra width on EACH side of a step (the flare).
// 0 above the flare zone, growing to flare_width at the bottom step; squared so it eases in.
float flare_extra(int step_num, num_steps, flare_steps; float flare_width) {
    if (flare_steps <= 0) return 0;
    float into_flare = clamp(float(step_num - (num_steps - flare_steps)) / flare_steps, 0, 1);   // 0 → 1 through the flare zone
    return flare_width * into_flare * into_flare;
}

// ---------- A. read the entry ----------
float climb_height  = detail(1, "door_y");     // how high the door is above the street
float stair_left    = detail(1, "porch_x0");   // the stairs are as wide as the porch
float stair_right   = detail(1, "porch_x1");
float stair_start_z = detail(1, "land_z");     // front edge of the landing: the steps start here
if (climb_height <= 0 || stair_right <= stair_left) return;

// ---------- B. style choices ----------
int has_flare      = rand_range(0, 1, 50) < chf("flare_chance");   // bottom steps get wider
int has_cheek_base = rand_range(0, 1, 51) < chf("base_chance");    // solid walls beside the bottom steps
i@bal_style   = rand_range(0, 1, 52) < 0.5;    // read by the baluster Switch: 0 turned, 1 square
i@newel_style = rand_range(0, 1, 53) < 0.5;    // read by the newel + cap Switches: 0 round, 1 square

// ---------- C. how many steps ----------
int   num_risers   = max(1, int(ceil(climb_height / chf("riser_max"))));   // round UP so no riser is too tall
float riser_height = climb_height / num_risers;                          // every riser the same height
float tread_depth  = chf("tread");
int   num_steps    = num_risers - 1;                                     // the landing is the top tread

// ---------- D. landing + steps ----------
place_part("landing", set(stair_left, 0, 0), set(stair_right, climb_height + 0.01, stair_start_z));

int   flare_steps = has_flare ? min(chi("flare_n"), num_steps) : 0;
float flare_width = chf("flare_w");
for (int step_num = 1; step_num <= num_steps; step_num++) {
    float extra = flare_extra(step_num, num_steps, flare_steps, flare_width);
    place_part("step",
               set(stair_left  - extra, 0,                                      stair_start_z + (step_num - 1) * tread_depth),
               set(stair_right + extra, climb_height - step_num * riser_height, stair_start_z + step_num * tread_depth));
}

// ---------- E. balustrade: newel posts + caps, rail paths, balusters ----------
int   base_steps         = has_cheek_base ? min(chi("base_n"), num_steps) : 0;
int   last_baluster_step = num_steps - max(flare_steps, base_steps);   // balustrade stops where flare / cheek walls start
float side_inset         = chf("side_inset");    // balustrade line, in from the stair edge
float newel_width        = chf("newel_w");
float rail_height        = chf("rail_h");        // handrail height above the treads
float baluster_width     = chf("bal_w");
int   balusters_per_step = chi("bal_per_step");
float post_height        = rail_height + chf("newel_extra");   // newel post height above its tread
float cap_size           = newel_width * chf("cap_scale");     // ball / cap: same size in x, y, z (never stretched)

if (last_baluster_step >= 1) {
    float top_newel_z    = stair_start_z - newel_width * 0.5;                          // on the landing's front edge
    float bottom_newel_z = stair_start_z + (last_baluster_step - 0.5) * tread_depth;   // middle of the last baluster step
    float bottom_newel_y = climb_height - last_baluster_step * riser_height;
    float rail_lines_x[] = array(stair_left + side_inset, stair_right - side_inset);   // left / right balustrade

    foreach (float rail_x; rail_lines_x) {
        // newel posts: these stretch to any height
        place_part("newel",
                   set(rail_x - newel_width/2, climb_height,               top_newel_z - newel_width/2),
                   set(rail_x + newel_width/2, climb_height + post_height, top_newel_z + newel_width/2));
        place_part("newel",
                   set(rail_x - newel_width/2, bottom_newel_y,               bottom_newel_z - newel_width/2),
                   set(rail_x + newel_width/2, bottom_newel_y + post_height, bottom_newel_z + newel_width/2));
        // caps sit on top of each post (a separate part, so they stay round)
        place_part("newel_cap",
                   set(rail_x - cap_size/2, climb_height + post_height,            top_newel_z - cap_size/2),
                   set(rail_x + cap_size/2, climb_height + post_height + cap_size, top_newel_z + cap_size/2));
        place_part("newel_cap",
                   set(rail_x - cap_size/2, bottom_newel_y + post_height,            bottom_newel_z - cap_size/2),
                   set(rail_x + cap_size/2, bottom_newel_y + post_height + cap_size, bottom_newel_z + cap_size/2));

        // handrail path: a straight line between the newels, rail_height above the treads
        int rail_top    = addpoint(0, set(rail_x, climb_height   + rail_height, top_newel_z));
        int rail_bottom = addpoint(0, set(rail_x, bottom_newel_y + rail_height, bottom_newel_z));
        setprimgroup(0, "rail", addprim(0, "polyline", array(rail_top, rail_bottom)), 1);

        // balusters: several per step, standing on the tread and reaching up to the rail
        for (int step_num = 1; step_num <= last_baluster_step; step_num++)
            for (int b = 0; b < balusters_per_step; b++) {
                float baluster_z = stair_start_z + (step_num - 1 + (b + 0.5) / balusters_per_step) * tread_depth;
                if (baluster_z > bottom_newel_z - newel_width * 0.5) continue;    // stop before the bottom newel
                float tread_y = climb_height - step_num * riser_height;
                // the rail slopes, so read its height at this z
                float rail_y  = lerp(climb_height + rail_height, bottom_newel_y + rail_height,
                                     (baluster_z - top_newel_z) / (bottom_newel_z - top_newel_z));
                place_part("baluster",
                           set(rail_x - baluster_width/2, tread_y, baluster_z - baluster_width/2),
                           set(rail_x + baluster_width/2, rail_y,  baluster_z + baluster_width/2));
            }
    }
}

// ---------- F. cheek walls: solid stepped blocks beside the bottom steps ----------
float cheek_width  = chf("cheek_w");
float cheek_height = chf("cheek_h");     // how far the wall rises above each tread
for (int step_num = num_steps - base_steps + 1; step_num <= num_steps; step_num++) {
    float extra       = flare_extra(step_num, num_steps, flare_steps, flare_width);   // follow the flare
    float cheek_top_y = climb_height - step_num * riser_height + cheek_height;
    place_part("cheek",
               set(stair_left - extra - cheek_width, 0,           stair_start_z + (step_num - 1) * tread_depth),
               set(stair_left - extra,               cheek_top_y, stair_start_z + step_num * tread_depth));
    place_part("cheek",
               set(stair_right + extra,               0,           stair_start_z + (step_num - 1) * tread_depth),
               set(stair_right + extra + cheek_width, cheek_top_y, stair_start_z + step_num * tread_depth));
}
'''

# ---------------------------------------------------------------------
NEW['entry_door'] = r'''
// =====================================================================
// entry_door  —  Attribute Wrangle, Run Over: Detail
//   input 1: empty      input 2: entry_params
//
// Builds the visible entry around the recess cut:
//   wall infill above an arch, casing (trim frame), reveal (recess walls),
//   threshold (recess floor), and the door: frame, transom, 1 or 2 leaves.
//
// Method: everything is made from OUTLINES of an opening — a list of points:
// the bottom row left→right, then the top row right→left (flat or arched).
//   add_ring()     joins two outlines with a strip of faces, at two depths
//   fill_outline() caps an outline with faces
// Depth (z) is passed separately; outlines are made at z = 0.
// =====================================================================

// Height of a segmental arch at position x.
// arch_top = the peak; rise = how far the peak is above the ends (0 = flat top).
float arch_height_at(float x, left, right, arch_top, rise) {
    if (rise < 1e-4) return arch_top;
    float half_span = 0.5 * (right - left), centre = 0.5 * (left + right);
    float radius = (half_span * half_span + rise * rise) / (2 * rise);   // circle through both ends and the peak
    return arch_top - radius + sqrt(max(radius * radius - (x - centre) * (x - centre), 0.0));
}

// Outline of an opening: segments+1 points along the bottom (left→right),
// then segments+1 points along the top (right→left).
function vector[] make_outline(float left, right, bottom, arch_top, rise; int segments) {
    vector pts[];
    for (int k = 0; k <= segments; k++)
        append(pts, set(lerp(left, right, float(k) / segments), bottom, 0));
    for (int k = segments; k >= 0; k--) {
        float x = lerp(left, right, float(k) / segments);
        append(pts, set(x, arch_height_at(x, left, right, arch_top, rise), 0));
    }
    return pts;
}

// one 4-sided face, tagged with a group (used later for materials)
void add_quad(vector a, b, c, d; string group_name) {
    int pts[] = array(addpoint(0, a), addpoint(0, b), addpoint(0, c), addpoint(0, d));
    setprimgroup(0, group_name, addprim(0, "poly", pts), 1);
}

// join outline A (at depth za) to outline B (at depth zb) with faces, all the way round
void add_ring(vector A[]; float za; vector B[]; float zb; string group_name) {
    int m = len(A);
    for (int k = 0; k < m; k++) {
        int next = (k + 1) % m;
        add_quad(A[k] + set(0,0,za), B[k] + set(0,0,zb), B[next] + set(0,0,zb), A[next] + set(0,0,za), group_name);
    }
}

// same as add_ring, but skips the bottom edge (parts standing on the floor; avoids z-fighting)
void add_ring_no_bottom(vector A[]; float za; vector B[]; float zb; string group_name) {
    int m = len(A), bottom_segs = m / 2 - 1;     // the first bottom_segs segments are the bottom row
    for (int k = bottom_segs; k < m; k++) {
        int next = (k + 1) % m;
        add_quad(A[k] + set(0,0,za), B[k] + set(0,0,zb), B[next] + set(0,0,zb), A[next] + set(0,0,za), group_name);
    }
}

// fill the inside of an outline at depth z (strips from the bottom row to the top row)
void fill_outline(vector C[]; float z; string group_name) {
    int segments = len(C) / 2 - 1;
    vector dz = set(0, 0, z);
    for (int k = 0; k < segments; k++)
        add_quad(C[k] + dz, C[2*segments+1-k] + dz, C[2*segments-k] + dz, C[k+1] + dz, group_name);
}

// ---------- read the opening from entry_params ----------
float open_left    = detail(1, "ox0");
float open_right   = detail(1, "ox1");
float open_bottom  = detail(1, "oy0");
float open_top     = detail(1, "oy1");
float recess_depth = detail(1, "rec");
int   is_arched    = detail(1, "arch");
int   is_double    = detail(1, "double");
if (open_right - open_left < 0.1) return;

int   arch_segments = chi("arch_n");                                   // smoothness of the curves
float open_width    = open_right - open_left;
float arch_rise     = is_arched ? open_width * chf("arch_frac") : 0.0;
float casing_width  = chf("casing_w");
float casing_depth  = chf("casing_d");

// ---------- wall face: infill above the arch, casing around the opening ----------
vector cut_edge[]     = make_outline(open_left, open_right, open_bottom, open_top, 0,         arch_segments);   // rectangular wall cut
vector opening_edge[] = make_outline(open_left, open_right, open_bottom, open_top, arch_rise, arch_segments);   // visible opening
vector casing_outer[] = make_outline(open_left - casing_width, open_right + casing_width, open_bottom,
                                     open_top + casing_width, arch_rise, arch_segments);
if (is_arched) add_ring_no_bottom(cut_edge, 0.001, opening_edge, 0.001, "wall");   // fill the corners above the arch
add_ring_no_bottom(opening_edge, casing_depth, opening_edge, 0,            "casing");   // casing inner side
add_ring(casing_outer,           casing_depth, opening_edge, casing_depth, "casing");   // casing front face
add_ring(casing_outer,           0,            casing_outer, casing_depth, "casing");   // casing outer side

// ---------- reveal: lines the recess so the arch carries back to the door ----------
vector reveal_edge[] = make_outline(open_left + 0.01, open_right - 0.01, open_bottom, open_top - 0.01, arch_rise, arch_segments);
add_ring_no_bottom(reveal_edge, 0, reveal_edge, -recess_depth, "reveal");

// ---------- threshold: floor of the recess, 5 mm up so it never fights the wall Boolean or the ground ----------
float threshold_y = open_bottom + 0.005;
add_quad(set(open_left,  threshold_y, 0),             set(open_left,  threshold_y, -recess_depth),
         set(open_right, threshold_y, -recess_depth), set(open_right, threshold_y, 0), "threshold");

// ---------- door assembly at the back of the recess ----------
float door_z       = -recess_depth + 0.02;
float door_width   = min(chf("door_w"), open_width - 0.3);
float door_left    = 0.5 * (open_left + open_right) - 0.5 * door_width;
float door_right   = door_left + door_width;
float door_top     = open_top - 0.05;
float transom_rise = is_arched ? door_width * chf("arch_frac") : 0.0;
float frame_width  = chf("frame_w");
float leaf_height  = (door_top - open_bottom) * chf("door_frac");   // the doors; the transom fills the space above

// frame + (arched) transom window above the doors
vector frame_outer[]  = make_outline(door_left - frame_width, door_right + frame_width, open_bottom, door_top, transom_rise, arch_segments);
vector transom_edge[] = make_outline(door_left, door_right, open_bottom + leaf_height + frame_width, door_top - frame_width, transom_rise, arch_segments);
add_ring(frame_outer,  door_z, transom_edge, door_z,        "door_frame");
add_ring(transom_edge, door_z, transom_edge, door_z - 0.03, "door_frame");
fill_outline(transom_edge, door_z - 0.03, "glass");

// door leaves: glass panel on top, raised panel below
int   num_leaves   = is_double ? 2 : 1;
float leaf_width   = door_width / num_leaves;
float stile_width  = chf("stile_w");      // the leaf's frame around its panels
float leaf_front_z = door_z + 0.05;
for (int leaf = 0; leaf < num_leaves; leaf++) {
    float leaf_left  = door_left + leaf * leaf_width + 0.005;
    float leaf_right = door_left + (leaf + 1) * leaf_width - 0.005;
    vector leaf_edge[] = make_outline(leaf_left, leaf_right, open_bottom, open_bottom + leaf_height, 0, 1);
    add_ring_no_bottom(leaf_edge, door_z, leaf_edge, leaf_front_z, "door");
    fill_outline(leaf_edge, leaf_front_z, "door");

    float leaf_mid_y = open_bottom + leaf_height * 0.45;     // split between glass (above) and panel (below)

    // glass panel with a bead around it
    vector glass_edge[] = make_outline(leaf_left + stile_width, leaf_right - stile_width,
                                       leaf_mid_y + stile_width * 0.5, open_bottom + leaf_height - stile_width, 0, 1);
    vector bead_edge[]  = make_outline(leaf_left + stile_width - 0.03, leaf_right - stile_width + 0.03,
                                       leaf_mid_y + stile_width * 0.5 - 0.03, open_bottom + leaf_height - stile_width + 0.03, 0, 1);
    add_ring(bead_edge, leaf_front_z, glass_edge, leaf_front_z + 0.02, "door");
    fill_outline(glass_edge, leaf_front_z + 0.002, "glass");

    // raised panel
    vector panel_edge[]  = make_outline(leaf_left + stile_width, leaf_right - stile_width,
                                        open_bottom + stile_width * 1.5, leaf_mid_y - stile_width * 0.5, 0, 1);
    vector panel_inner[] = make_outline(leaf_left + stile_width + 0.04, leaf_right - stile_width - 0.04,
                                        open_bottom + stile_width * 1.5 + 0.04, leaf_mid_y - stile_width * 0.5 - 0.04, 0, 1);
    add_ring(panel_edge, leaf_front_z, panel_inner, leaf_front_z + 0.015, "door");
    fill_outline(panel_inner, leaf_front_z + 0.015, "door");
}
'''

# ---------------------------------------------------------------------
NEW['attribwrangle2'] = r'''
// =====================================================================
// bay_shell  —  Attribute Wrangle, Run Over: Detail
//   inside the For-Each loop.  input 1: empty   input 2: foreach_begin (ONE bay point)
//
// Builds one bay window at its real size from its slot (bbmin / bbmax).
// Output groups:
//   post, trim, casing, reveal, frame, sash, glass, panel_mold, panel_field  — the shell
//   skirt, soffit — the underside (flat or tapered)
//   cap           — top/bottom caps (removed after the loop)
//   trim_curve    — horizontal curves for the swept moldings (prim attrib 'trim')
//   footprint     — top outline, extruded after the loop into a solid for the roof Boolean
//
// Method — "design flat, then wrap":
//   1. the bay's PLAN is a polyline across the wall (half-round or 3-sided)
//   2. everything is laid out flat: x = distance along the plan, y = height,
//      z = out of (+) or into (−) the surface
//   3. layout_to_world() wraps each flat point onto the plan
// So the same layout code works for round and angled bays.
// =====================================================================

// ---------- plan helpers ----------
// plan[]      = the plan's points
// plan_dist[] = running distance along the plan at each point

// position on the plan at distance 'dist' along it
vector point_on_plan(float dist; vector plan[]; float plan_dist[]) {
    for (int i = 1; i < len(plan); i++)
        if (dist <= plan_dist[i] || i == len(plan) - 1) {
            float t = (dist - plan_dist[i-1]) / max(plan_dist[i] - plan_dist[i-1], 1e-6);
            return lerp(plan[i-1], plan[i], t);
        }
    return plan[-1];
}
// outward direction of the plan at distance 'dist'
vector plan_normal_at(float dist; vector plan[]; float plan_dist[]) {
    for (int i = 1; i < len(plan); i++)
        if (dist <= plan_dist[i] || i == len(plan) - 1)
            return normalize(cross(plan[i] - plan[i-1], {0,1,0}));
    return {0,0,1};
}
// flat layout point (x = along plan, y = height, z = out of surface) → world position
vector layout_to_world(vector lp; vector origin; vector plan[]; float plan_dist[]) {
    return origin + point_on_plan(lp.x, plan, plan_dist) + set(0, lp.y, 0)
                  + plan_normal_at(lp.x, plan, plan_dist) * lp.z;
}

// ---------- shape helpers (all in flat layout space) ----------
// height of a segmental arch at x; arch_top = the peak, rise = peak above the ends (0 = flat)
float arch_height_at(float x, left, right, arch_top, rise) {
    if (rise < 1e-4) return arch_top;
    float half_span = 0.5 * (right - left), centre = 0.5 * (left + right);
    float radius = (half_span * half_span + rise * rise) / (2 * rise);
    return arch_top - radius + sqrt(max(radius * radius - (x - centre) * (x - centre), 0.0));
}
// outline of an opening: bottom row left→right, then top row right→left
function vector[] make_outline(float left, right, bottom, arch_top, rise; int segments) {
    vector pts[];
    for (int k = 0; k <= segments; k++)
        append(pts, set(lerp(left, right, float(k) / segments), bottom, 0));
    for (int k = segments; k >= 0; k--) {
        float x = lerp(left, right, float(k) / segments);
        append(pts, set(x, arch_height_at(x, left, right, arch_top, rise), 0));
    }
    return pts;
}
// one 4-sided face, wrapped onto the bay and tagged with a group
void add_quad(vector a, b, c, d; string group_name; vector origin; vector plan[]; float plan_dist[]) {
    int pts[] = array(addpoint(0, layout_to_world(a, origin, plan, plan_dist)),
                      addpoint(0, layout_to_world(b, origin, plan, plan_dist)),
                      addpoint(0, layout_to_world(c, origin, plan, plan_dist)),
                      addpoint(0, layout_to_world(d, origin, plan, plan_dist)));
    setprimgroup(0, group_name, addprim(0, "poly", pts), 1);
}
// join two outlines (same point count) at depths za / zb with a strip of faces
void add_ring(vector A[]; float za; vector B[]; float zb; string group_name; vector origin; vector plan[]; float plan_dist[]) {
    int m = len(A);
    for (int k = 0; k < m; k++) {
        int next = (k + 1) % m;
        add_quad(A[k] + set(0,0,za), B[k] + set(0,0,zb), B[next] + set(0,0,zb), A[next] + set(0,0,za),
                 group_name, origin, plan, plan_dist);
    }
}
// fill the inside of an outline at depth z
void fill_outline(vector C[]; float z; string group_name; vector origin; vector plan[]; float plan_dist[]) {
    int segments = len(C) / 2 - 1;
    vector dz = set(0, 0, z);
    for (int k = 0; k < segments; k++)
        add_quad(C[k] + dz, C[2*segments+1-k] + dz, C[2*segments-k] + dz, C[k+1] + dz,
                 group_name, origin, plan, plan_dist);
}

// =================== main ===================
// ---------- read this bay's slot ----------
vector slot_min = point(1, "bbmin", 0);
vector slot_max = point(1, "bbmax", 0);
string bay_type = point(1, "name", 0);     // bay_base, bay_cap or bay_solo
int    is_round = chi("round");            // driven by building_params' bay_round

float  bay_width  = slot_max.x - slot_min.x;
float  bay_height = slot_max.y - slot_min.y;
float  bay_depth  = slot_max.z - slot_min.z;                                     // how far it sticks out
vector origin     = set((slot_min.x + slot_max.x) * 0.5, slot_min.y, slot_min.z);   // back-centre-bottom of the slot

// ---------- plan: left wall → right wall, back edge on the wall ----------
vector plan[];
if (is_round) {
    for (int i = 0; i <= 48; i++) {                       // half circle, 48 segments
        float angle = PI * (1.0 - float(i) / 48);
        append(plan, set(0.5 * bay_width * cos(angle), 0, bay_depth * sin(angle)));
    }
} else {                                                  // 3-sided: wide back, narrower front
    float front_half = 0.5 * bay_width * chf("front_ratio");
    plan = array(set(-0.5 * bay_width, 0, 0), set(-front_half, 0, bay_depth),
                 set( front_half, 0, bay_depth), set(0.5 * bay_width, 0, 0));
}
// running distance along the plan at each plan point
float plan_dist[] = array(0.0);
for (int i = 1; i < len(plan); i++) append(plan_dist, plan_dist[-1] + length(plan[i] - plan[i-1]));
float plan_length = plan_dist[-1];

// where the three faces (left side | front | right side) start and end along the plan
float face_bounds[];
if (is_round) { float side_len = chf("side_frac") * plan_length; face_bounds = array(0.0, side_len, plan_length - side_len, plan_length); }
else            face_bounds = array(0.0, plan_dist[1], plan_dist[2], plan_length);

// heights of the three bands: skirt | windows | frieze
float band_bounds[] = array(0.0, chf("sill") * bay_height, chf("head") * bay_height, bay_height);
float post_width    = chf("post_w");     // plain strip at each face edge
float max_seg_len   = chf("seg_len");    // longest quad along a curve (smoothness)

// window settings
float win_margin    = chf("win_margin"), casing_width = chf("casing_w"), casing_depth = chf("casing_d");
float reveal_depth  = chf("reveal_d"),   frame_width  = chf("frame_w");
float sash_width    = chf("sash_w"),     sash_depth   = chf("sash_d");
float arch_frac     = chf("arch_frac"),  meet_frac    = chf("meet");   // meet = where the two sashes meet (0–1)
int   arch_segments = chi("arch_n");
// panel settings
float panel_margin     = chf("panel_margin"), panel_mold_width  = chf("panel_mold_w");
float panel_mold_depth = chf("panel_mold_d"), panel_field_depth = chf("panel_field_d");

// ---------- cells: 3 faces × 3 columns (post | middle | post) × 3 bands ----------
for (int face = 0; face < 3; face++) {
    float col_bounds[] = array(face_bounds[face], face_bounds[face] + post_width,
                               face_bounds[face+1] - post_width, face_bounds[face+1]);
    for (int cell_col = 0; cell_col < 3; cell_col++) {
        for (int band = 0; band < 3; band++) {
            float cell_left   = col_bounds[cell_col],  cell_right = col_bounds[cell_col+1];
            float cell_bottom = band_bounds[band],     cell_top   = band_bounds[band+1];
            int   segments    = max(1, int(ceil((cell_right - cell_left) / max_seg_len)));

            if (cell_col == 1 && band == 1) {
                // ----- arched double-hung window (middle column, window band) -----
                segments = max(segments, arch_segments);
                float rise = arch_frac * (cell_right - cell_left);
                // nested outlines, each further in from the cell edge
                float to_casing_out = win_margin;
                float to_casing_in  = win_margin + casing_width;
                float to_frame_in   = win_margin + casing_width + frame_width;
                vector cell_edge[]    = make_outline(cell_left,               cell_right,               cell_bottom,               cell_top,               0,    segments);
                vector casing_outer[] = make_outline(cell_left+to_casing_out, cell_right-to_casing_out, cell_bottom+to_casing_out, cell_top-to_casing_out, rise, segments);
                vector casing_inner[] = make_outline(cell_left+to_casing_in,  cell_right-to_casing_in,  cell_bottom+to_casing_in,  cell_top-to_casing_in,  rise, segments);
                vector frame_inner[]  = make_outline(cell_left+to_frame_in,   cell_right-to_frame_in,   cell_bottom+to_frame_in,   cell_top-to_frame_in,   rise, segments);
                add_ring(cell_edge,    0,             casing_outer, 0,             "trim",   origin, plan, plan_dist);   // wall around the arch
                add_ring(casing_outer, 0,             casing_outer, casing_depth,  "casing", origin, plan, plan_dist);   // casing outer side
                add_ring(casing_outer, casing_depth,  casing_inner, casing_depth,  "casing", origin, plan, plan_dist);   // casing face
                add_ring(casing_inner, casing_depth,  casing_inner, -reveal_depth, "reveal", origin, plan, plan_dist);   // casing inner side + reveal
                add_ring(casing_inner, -reveal_depth, frame_inner,  -reveal_depth, "frame",  origin, plan, plan_dist);   // frame face

                // two sashes: lower (square top) and upper (arched)
                float sash_left   = cell_left   + to_frame_in, sash_right = cell_right - to_frame_in;
                float sash_bottom = cell_bottom + to_frame_in, sash_top   = cell_top   - to_frame_in;
                float meet_y      = lerp(sash_bottom, sash_top - rise, meet_frac);
                for (int sash = 0; sash < 2; sash++) {
                    float lo        = sash == 0 ? sash_bottom : meet_y;
                    float hi        = sash == 0 ? meet_y      : sash_top;
                    float sash_rise = sash == 0 ? 0.0         : rise;
                    vector sash_outer[] = make_outline(sash_left,              sash_right,              lo,              hi,              sash_rise, segments);
                    vector sash_inner[] = make_outline(sash_left + sash_width, sash_right - sash_width, lo + sash_width, hi - sash_width, sash_rise, segments);
                    add_ring(sash_outer, -reveal_depth,              sash_outer, -reveal_depth + sash_depth, "sash", origin, plan, plan_dist);
                    add_ring(sash_outer, -reveal_depth + sash_depth, sash_inner, -reveal_depth + sash_depth, "sash", origin, plan, plan_dist);
                    add_ring(sash_inner, -reveal_depth + sash_depth, sash_inner, -reveal_depth,              "sash", origin, plan, plan_dist);
                    fill_outline(sash_inner, -reveal_depth, "glass", origin, plan, plan_dist);
                }
                continue;
            }

            if (cell_col == 1) {
                // ----- recessed panel (middle column, skirt or frieze band) -----
                float max_margin = 0.2 * min(cell_right - cell_left, cell_top - cell_bottom);   // keep margins sane on small cells
                float mold_out   = min(panel_margin, max_margin);
                float mold_in    = min(panel_margin + panel_mold_width, 2 * max_margin);
                vector panel_cell[] = make_outline(cell_left,          cell_right,          cell_bottom,          cell_top,          0, segments);
                vector mold_outer[] = make_outline(cell_left+mold_out, cell_right-mold_out, cell_bottom+mold_out, cell_top-mold_out, 0, segments);
                vector field_edge[] = make_outline(cell_left+mold_in,  cell_right-mold_in,  cell_bottom+mold_in,  cell_top-mold_in,  0, segments);
                add_ring(panel_cell, 0,                mold_outer, 0,                  "trim",       origin, plan, plan_dist);
                add_ring(mold_outer, 0,                mold_outer, panel_mold_depth,   "panel_mold", origin, plan, plan_dist);
                add_ring(mold_outer, panel_mold_depth, field_edge, panel_mold_depth,   "panel_mold", origin, plan, plan_dist);
                add_ring(field_edge, panel_mold_depth, field_edge, -panel_field_depth, "panel_mold", origin, plan, plan_dist);
                fill_outline(field_edge, -panel_field_depth, "panel_field", origin, plan, plan_dist);
                continue;
            }

            // ----- posts: plain strips (outer columns) -----
            for (int seg = 0; seg < segments; seg++) {
                float seg_left  = lerp(cell_left, cell_right, float(seg) / segments);
                float seg_right = lerp(cell_left, cell_right, float(seg + 1) / segments);
                add_quad(set(seg_left,  cell_bottom, 0), set(seg_left,  cell_top,    0),
                         set(seg_right, cell_top,    0), set(seg_right, cell_bottom, 0),
                         "post", origin, plan, plan_dist);
            }
        }
    }
}

// ---------- top and bottom caps (deleted after the loop) ----------
int bottom_cap[], top_cap[];
foreach (vector q; plan) {
    append(bottom_cap, addpoint(0, origin + q));
    append(top_cap,    addpoint(0, origin + q + set(0, bay_height, 0)));
}
reverse(bottom_cap);   // NOTE: reverse() returns a reversed COPY, so this line does nothing (harmless: caps are removed later)
setprimgroup(0, "cap", addprim(0, "poly", top_cap), 1);
setprimgroup(0, "cap", addprim(0, "poly", bottom_cap), 1);

// ---------- underside: close the bottom of a bay with nothing below it ----------
if (bay_type != "bay_cap") {
    int   bottom_style = chi("bottom_style");             // 0 = flat, 1 = tapered
    if (point(1, "flat_bottom", 0)) bottom_style = 0;     // building_params says this bay must be flat
    float skirt_height = chf("skirt_h");                  // vertical band below the bay before the taper starts
    float taper_height = chf("taper_h");                  // how far the taper drops below that band
    float taper_width  = chf("taper_w");                  // width left where it meets the wall (0 = a point)
    int edge_pts[], skirt_pts[], taper_pts[];
    foreach (vector q; plan) {
        append(edge_pts,  addpoint(0, origin + q));                                   // the bay's bottom edge
        append(skirt_pts, addpoint(0, origin + q - set(0, skirt_height, 0)));         // bottom of the vertical band
        if (bottom_style == 1)
            append(taper_pts, addpoint(0, origin + set(q.x * taper_width, -skirt_height - taper_height, 0)));   // where the taper meets the wall
    }
    int num_plan_pts = len(plan);
    if (skirt_height > 0)
        for (int k = 0; k < num_plan_pts - 1; k++)
            setprimgroup(0, "skirt", addprim(0, "poly", array(skirt_pts[k], edge_pts[k], edge_pts[k+1], skirt_pts[k+1])), 1);
    if (bottom_style == 0)
        setprimgroup(0, "soffit", addprim(0, "poly", skirt_pts), 1);                 // flat underside
    else
        for (int k = 0; k < num_plan_pts - 1; k++)
            setprimgroup(0, "soffit", addprim(0, "poly", array(taper_pts[k], skirt_pts[k], skirt_pts[k+1], taper_pts[k+1])), 1);
}

// ---------- trim curves for the swept moldings ----------
float  trim_heights[];
string trim_names[];
append(trim_heights, band_bounds[1]); append(trim_names, "sill");    // under the windows
append(trim_heights, band_bounds[2]); append(trim_names, "head");    // above the windows
if (bay_type != "bay_cap")  { append(trim_heights, 0.0);        append(trim_names, "base"); }   // bottom edge
if (bay_type == "bay_base") { append(trim_heights, bay_height); append(trim_names, "belt"); }   // where it meets the bay above
// bay_cap / bay_solo reach the roof: the roof cornice wraps them, so no top molding of their own
for (int i = 0; i < len(trim_heights); i++) {
    int curve_pts[];
    foreach (vector q; plan) append(curve_pts, addpoint(0, origin + q + set(0, trim_heights[i], 0)));
    int curve_prim = addprim(0, "polyline", curve_pts);
    setprimgroup(0, "trim_curve", curve_prim, 1);
    setprimattrib(0, "trim", curve_prim, trim_names[i]);
}

// ---------- footprint: top outline, pushed down into a solid after the loop (for the roof Boolean) ----------
float footprint_inset = chf("footprint_inset");                     // must be deeper than reveal_d
float shrink_x = max(0.5 * bay_width - footprint_inset, 0.01) / (0.5 * bay_width);
float shrink_z = max(bay_depth - footprint_inset, 0.01) / bay_depth;
int footprint_pts[];
foreach (vector q; plan) append(footprint_pts, addpoint(0, origin + set(q.x * shrink_x, bay_height, q.z * shrink_z)));
int footprint_prim = addprim(0, "poly", footprint_pts);
setprimgroup(0, "footprint", footprint_prim, 1);
setprimattrib(0, "zscale", footprint_prim, bay_height);             // how far to push it down
'''

# ---------------------------------------------------------------------
NEW['baluster_profile'] = r'''
// =====================================================================
// baluster_profile  —  Attribute Wrangle, Run Over: Detail, no inputs → revolve1
// Builds a baluster's half-profile from the 'profile' ramp:
//   ramp x-axis = height up the baluster (0 = bottom, 1 = top)
//   ramp y-axis = radius at that height (0–1, scaled by max_radius)
// revolve1 spins it around Y; the MatchSize after the Switch normalises the size.
// =====================================================================
int   samples    = chi("samples");        // points along the profile (smoothness)
float max_radius = chf("max_radius");
int profile_pts[];
for (int i = 0; i <= samples; i++) {
    float height_frac = float(i) / samples;               // 0 → 1 going up
    float radius_frac = chramp("profile", height_frac);   // the ramp's value at this height
    append(profile_pts, addpoint(0, set(radius_frac * max_radius, height_frac, 0)));
}
addprim(0, "polyline", profile_pts);
'''

# ---------------------------------------------------------------------
PROFILE = r'''
// =====================================================================
// molding profile  —  Attribute Wrangle, Run Over: Detail, no inputs
//   → second input (cross-section) of a molding Sweep
// A cross-section that steps out from the wall and back in.
// Stored normalised (0–1), then scaled by this node's parameters:
//   depth  : how far it projects from the wall (x)
//   height : how tall it is (y)
//   anchor : where it sits on its curve (0 = above, 0.5 = centred, 1 = hangs below)
// =====================================================================
float profile_xy[] = array(   // pairs of (projection, height)
    0.00, 0.00,   // wall, bottom
    0.20, 0.00,
    0.20, 0.10,   // small fillet
    0.45, 0.20,   // bed molding stepping out
    0.60, 0.32,
    0.85, 0.36,   // underside of the shelf
    0.85, 0.45,
    1.00, 0.50,   // front face (fascia)
    1.00, 0.70,
    0.90, 0.74,   // drip edge
    0.55, 0.90,   // sloped top running back in
    0.30, 0.93,
    0.30, 1.00,
    0.00, 1.00);  // wall, top
float depth  = chf("depth");
float height = chf("height");
float anchor = chf("anchor");
int profile_pts[];
for (int i = 0; i < len(profile_xy); i += 2)
    append(profile_pts, addpoint(0, set(profile_xy[i] * depth, (profile_xy[i+1] - anchor) * height, 0)));
addprim(0, "polyline", profile_pts);
'''
NEW['profile_small'] = PROFILE
NEW['profile_mid']   = PROFILE
NEW['profile_big']   = PROFILE

# ---------------------------------------------------------------------
NEW['attribwrangle1'] = r'''
// Debug colours (Run Over: Primitives): tint each placeholder asset by its name.
string asset_name = s@name;
if      (startswith(asset_name, "bay")) @Cd = {1.0, 0.0, 0.5};   // pink
else if (asset_name == "door")          @Cd = {0.0, 1.0, 0.5};   // green
else if (asset_name == "garage")        @Cd = {1.0, 1.0, 0.0};   // yellow
else if (asset_name == "flat")          @Cd = {0.5, 0.0, 1.0};   // purple
else if (asset_name == "stairs")        @Cd = {1.0, 0.6, 0.0};   // orange
'''

NEW['attribwrangle3'] = r'''
// Bracket orientation (Run Over: Points), on the resampled cornice curve:
// N  = horizontal direction perpendicular to the curve → brackets face outward
// up = world up, so Copy to Points keeps them upright
v@N  = normalize(cross(v@tangentu, {0,1,0}));
v@up = {0,1,0};
'''

# =====================================================================
# apply with verification
# =====================================================================
def stats(node):
    node.cook(force=True)
    geo = node.geometry()
    if geo is None:
        return None
    bb = geo.boundingBox()
    return (len(geo.points()), len(geo.prims()),
            tuple(round(v, 4) for v in tuple(bb.minvec()) + tuple(bb.maxvec())))

def errs(node):
    try:
        node.cook(force=True)
    except hou.OperationFailed:
        pass
    return list(node.errors())

display = GEO.displayNode()
final_before = stats(display)
report = []

for name, code in NEW.items():
    node = GEO.node(name)
    if node is None:
        report.append('SKIP   %-18s (node not found)' % name)
        continue
    parm = node.parm('snippet')
    old_code = parm.eval()
    try:
        before = stats(node)
    except hou.OperationFailed:
        before = 'error'
    node.setUserData('snippet_backup', old_code)
    parm.set(code.strip() + '\n')
    problems = errs(node)
    try:
        after = stats(node)
    except hou.OperationFailed:
        after = 'error'
    if problems or after != before:
        parm.set(old_code)
        node.cook(force=True)
        report.append('REVERT %-18s %s | before %s | after %s' % (name, problems, before, after))
    else:
        report.append('OK     %-18s %s' % (name, before))

final_after = stats(display)
report.append('')
report.append('display node %s: before %s | after %s -> %s' % (
    display.name(), final_before, final_after,
    'IDENTICAL' if final_before == final_after else 'DIFFERENT - check above'))
print('\n'.join(report))
