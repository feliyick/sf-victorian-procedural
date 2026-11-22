// ===================== facade_lib.h =====================
// Shared helpers for the SF house builders.
// Flat helpers: door, windows, garage.  Bay overloads: bay_shell.

// ---------- Section 0: randomness ----------
// Random number between lo and hi.
// "stream" = a different number for each decision, so decisions don't copy each other.
// Every wrangle that uses this needs a "seed" parameter.
// building_params owns the real seed; every other node links to it.
float rand_range(float lo, hi; int stream) {
    return fit01(rand(chi("seed") * 7919 + stream), lo, hi);
}


// ---------- Section 0b: placing unit-asset parts ----------
// Drops one point for Copy to Points:
//   position = bottom-centre of the box (unit assets have their pivot at the bottom)
//   name     = which asset to copy
//   scale    = box size, which stretches the unit asset to fit
void place_part(string part_name; vector box_min, box_max) {
    int pt = addpoint(0, set((box_min.x + box_max.x) * 0.5,
                             box_min.y,
                             (box_min.z + box_max.z) * 0.5));
    setpointattrib(0, "name",  pt, part_name);
    setpointattrib(0, "scale", pt, box_max - box_min);
}

// --- 1. shapes (from entry_door, copy as-is) ---
//   arch_height_at
//   make_outline

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

// --- 2. flat builders (from entry_door, copy as-is) ---
//   add_quad          (flat version)
//   add_ring
//   add_ring_no_bottom
//   fill_outline
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

// solid box from box_min to box_max: 6 faces, all pointing OUT, tagged with a group
void add_box_sharp(vector box_min, box_max; string group_name) {
    float x0 = box_min.x, y0 = box_min.y, z0 = box_min.z;
    float x1 = box_max.x, y1 = box_max.y, z1 = box_max.z;
    add_quad(set(x0,y1,z1), set(x1,y1,z1), set(x1,y0,z1), set(x0,y0,z1), group_name);   // front  (+z)
    add_quad(set(x1,y1,z0), set(x0,y1,z0), set(x0,y0,z0), set(x1,y0,z0), group_name);   // back   (-z)
    add_quad(set(x1,y1,z1), set(x1,y1,z0), set(x1,y0,z0), set(x1,y0,z1), group_name);   // right  (+x)
    add_quad(set(x0,y1,z0), set(x0,y1,z1), set(x0,y0,z1), set(x0,y0,z0), group_name);   // left   (-x)
    add_quad(set(x0,y1,z0), set(x1,y1,z0), set(x1,y1,z1), set(x0,y1,z1), group_name);   // top    (+y)
    add_quad(set(x0,y0,z1), set(x1,y0,z1), set(x1,y0,z0), set(x0,y0,z0), group_name);   // bottom (-y)
}

// add a polygon from its corners, wound so it faces away from 'centre' (Houdini: clockwise from the front)
void add_poly_out(vector P[]; vector centre; string group_name) {
    vector n = cross(P[1] - P[0], P[2] - P[0]);
    vector avg = {0, 0, 0};
    for (int i = 0; i < len(P); i++) avg += P[i];
    avg /= len(P);
    vector Q[] = P;
    if (dot(n, avg - centre) > 0) Q = reverse(P);
    int pts[];
    for (int i = 0; i < len(Q); i++) { int pt = addpoint(0, Q[i]); append(pts, pt); }
    setprimgroup(0, group_name, addprim(0, "poly", pts), 1);
}

// a box with every edge chamfered by the asset's Edge Bevel (spare parm 'bevel' on the wrangle).
// The chamfer catches a thin highlight on every edge, which is what makes CG trim stop looking like CG.
// Bevel is capped at 30% of the box's smallest side, and skipped when tiny or when 'bevel' is missing.
void add_box(vector box_min, box_max; string group_name) {
    vector mn = min(box_min, box_max), mx = max(box_min, box_max);
    vector sz = mx - mn;
    float b = min(chf("bevel"), 0.3 * min(sz.x, min(sz.y, sz.z)));
    if (b < 0.0015) { add_box_sharp(mn, mx, group_name); return; }
    vector ctr = (mn + mx) * 0.5;
    vector PX[], PY[], PZ[];                     // each corner split into one point per face
    for (int k = 0; k < 8; k++) {
        int ix = k % 2, iy = (k / 2) % 2, iz = k / 4;      // VEX has no bit shifts
        vector c = set(ix ? mx.x : mn.x, iy ? mx.y : mn.y, iz ? mx.z : mn.z);
        vector ins = set(ix ? -b : b, iy ? -b : b, iz ? -b : b);
        append(PX, c + set(0, ins.y, ins.z));
        append(PY, c + set(ins.x, 0, ins.z));
        append(PZ, c + set(ins.x, ins.y, 0));
    }
    // corner index from bits
    for (int s = 0; s < 2; s++) {
        // the six faces
        add_poly_out(array(PX[s + 0], PX[s + 2], PX[s + 6], PX[s + 4]), ctr, group_name);              // x = s
        add_poly_out(array(PY[2*s + 0], PY[2*s + 1], PY[2*s + 5], PY[2*s + 4]), ctr, group_name);      // y = s
        add_poly_out(array(PZ[4*s + 0], PZ[4*s + 1], PZ[4*s + 3], PZ[4*s + 2]), ctr, group_name);      // z = s
    }
    for (int a = 0; a < 2; a++) for (int c2 = 0; c2 < 2; c2++) {
        int k0, k1;
        k0 = 2*a + 4*c2; k1 = k0 + 1;                                                                    // edges along x
        add_poly_out(array(PY[k0], PY[k1], PZ[k1], PZ[k0]), ctr, group_name);
        k0 = a + 4*c2;   k1 = k0 + 2;                                                                    // edges along y
        add_poly_out(array(PX[k0], PX[k1], PZ[k1], PZ[k0]), ctr, group_name);
        k0 = a + 2*c2;   k1 = k0 + 4;                                                                    // edges along z
        add_poly_out(array(PX[k0], PX[k1], PY[k1], PY[k0]), ctr, group_name);
    }
    for (int k = 0; k < 8; k++) add_poly_out(array(PX[k], PY[k], PZ[k]), ctr, group_name);            // corner triangles
}

// --- 3. plan helpers (from bay_shell, copy as-is) ---
//   point_on_plan
//   plan_normal_at
//   layout_to_world

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
// wraps each flat-layout corner onto the bay’s curved plan, which gives its world position
vector layout_to_world(vector lp; vector origin; vector plan[]; float plan_dist[]) {
    return origin + point_on_plan(lp.x, plan, plan_dist) + set(0, lp.y, 0)
                  + plan_normal_at(lp.x, plan, plan_dist) * lp.z;
}

// --- 4. bay overloads ---
//   add_quad      → YOUR new one-liner version

void add_quad(vector a, b, c, d; string group_name; vector origin; vector plan[]; float plan_dist[]) {
    add_quad(layout_to_world(a, origin, plan, plan_dist),
             layout_to_world(b, origin, plan, plan_dist),
             layout_to_world(c, origin, plan, plan_dist),
             layout_to_world(d, origin, plan, plan_dist), group_name);
}
//   add_ring      → bay_shell's version (unchanged)
//   fill_outline  → bay_shell's version (unchanged)

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

// ---------- Section 5: ornament ----------
// Scroll bracket (corbel): an S-curved (ogee) side profile, extruded across its width.
//   o      = point on the wall at the bracket's TOP centre
//   across = along the wall, out = away from the wall (both horizontal unit vectors)
//   w = width, h = height (hangs down from o), d = depth out from the wall
// a bracket: a profile (out, up) extruded 'w' wide along 'across'. 'o' is the TOP of the bracket
// on the wall; it hangs down 'h' and reaches out 'd'.
//   style 0 SCROLL   S-curve with a toe            (the classic)
//   style 1 CONSOLE  concave neck + round volute   (Italianate)
//   style 2 BLOCK    stepped square blocks         (Stick / false fronts)
//   style 3 QUARTER  concave quarter sweep         (Queen Anne)
void bracket_v(vector o, across, out; float w, h, d; int style; string grp) {
    vector up = {0, 1, 0};
    int flip = dot(cross(across, out), up) < 0;         // keep faces pointing out whatever the frame
    float po[], pu[];                                   // profile: (out, up) measured from the bracket bottom
    append(po, 0.0); append(pu, h);
    append(po, d);   append(pu, h);
    if (style == 1) {
        append(po, d); append(pu, h * 0.9);
        for (int i = 1; i <= 8; i++) {                  // concave neck down to the volute
            float v = float(i) / 8;
            append(po, d * (0.3 + 0.7 * (1 - v) * (1 - v))); append(pu, h * (0.9 - 0.45 * v));
        }
        float rr = h * 0.17, ro = d * 0.2;
        for (int i = 1; i <= 10; i++) {                 // the round volute at the foot
            float a = radians(90 - 24 * i);
            append(po, d * 0.3 + ro * cos(a)); append(pu, h * 0.28 + rr * sin(a));
        }
        append(po, d * 0.12); append(pu, 0.0);
    }
    else if (style == 2) {
        float sx[] = array(1.0, 0.75, 0.75, 0.5, 0.5, 0.3, 0.3);
        float sy[] = array(0.7, 0.7, 0.45, 0.45, 0.2, 0.2, 0.0);
        for (int i = 0; i < 7; i++) { append(po, d * sx[i]); append(pu, h * sy[i]); }
    }
    else if (style == 3) {
        append(po, d); append(pu, h * 0.92);
        for (int i = 1; i <= 10; i++) {
            float t = float(i) / 10 * PI * 0.5;
            append(po, d - d * 0.82 * sin(t)); append(pu, h * 0.05 + h * 0.87 * cos(t));
        }
        append(po, d * 0.18); append(pu, 0.0);
    }
    else {
        append(po, d);   append(pu, h * 0.85);
        int n = 10;
        for (int i = 1; i <= n; i++) {
            float v = float(i) / n;
            append(po, d * (0.22 + 0.78 * 0.5 * (1 + cos(PI * v))));
            append(pu, h * 0.85 - v * h * 0.7);
        }
        append(po, d * 0.30); append(pu, h * 0.10);
        append(po, d * 0.22); append(pu, 0.0);
    }
    append(po, 0.0); append(pu, 0.0);
    int m = len(po);
    int L[], R[];
    for (int i = 0; i < m; i++) {
        vector base = o + out * po[i] + up * (pu[i] - h);
        int pl = addpoint(0, base - across * (w * 0.5)); append(L, pl);
        int pr = addpoint(0, base + across * (w * 0.5)); append(R, pr);
    }
    int lf[] = reverse(L), rf[] = R;
    if (flip) { lf = L; rf = reverse(R); }
    setprimgroup(0, grp, addprim(0, "poly", lf), 1);
    setprimgroup(0, grp, addprim(0, "poly", rf), 1);
    for (int i = 0; i < m; i++) {
        int j = (i + 1) % m;
        int q[] = flip ? array(R[i], R[j], L[j], L[i]) : array(L[i], L[j], R[j], R[i]);
        setprimgroup(0, grp, addprim(0, "poly", q), 1);
    }
}

void scroll_bracket(vector o, across, out; float w, h, d; string grp) {
    bracket_v(o, across, out, w, h, d, 0, grp);
}
