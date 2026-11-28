// street_lib.h: shared helpers for street_build + city_backdrop (ground on the hill, tagged faces, boxes, cylinders, blobs, wires)
#ifndef STREET_LIB_H
#define STREET_LIB_H
float gy(float x) { return -chf("slope") * (x - chf("xcentre")); }      // ground height at x (sidewalk top)
float rnd(int s) { return rand(chi("seed") * 7919 + 90000 + s); }

// ---------------- primitives ----------------
void tag(int pr; string mat; vector srgb) {
    setprimattrib(0, "path", pr, "/street/" + mat);
    setprimattrib(0, "material", pr, mat);
    setprimattrib(0, "paint", pr, "street");
    setprimattrib(0, "Cd", pr, pow(srgb, 2.2));
}
// a polygon facing 'outdir' (Houdini: clockwise seen from the front)
void face(vector P[]; vector outdir; string mat; vector srgb) {
    vector n = cross(P[1] - P[0], P[2] - P[0]);
    vector Q[] = P;
    if (dot(n, outdir) > 0) Q = reverse(P);
    int pts[];
    for (int i = 0; i < len(Q); i++) { int pt = addpoint(0, Q[i]); append(pts, pt); }
    tag(addprim(0, "poly", pts), mat, srgb);
}
// a box that follows the hill: top at gy(x) + t, bottom at gy(x) + b
void sbox(float x0, x1, z0, z1, b, t; string mat; vector srgb) {
    vector p[];
    float xs[] = array(x0, x1, x1, x0), zs[] = array(z0, z0, z1, z1);
    vector T[], B[];
    for (int i = 0; i < 4; i++) {
        append(T, set(xs[i], gy(xs[i]) + t, zs[i]));
        append(B, set(xs[i], gy(xs[i]) + b, zs[i]));
    }
    face(T, {0, 1, 0}, mat, srgb);
    face(reverse(B), {0, -1, 0}, mat, srgb);
    face(array(B[0], B[1], T[1], T[0]), {0, 0, -1}, mat, srgb);
    face(array(B[2], B[3], T[3], T[2]), {0, 0, 1}, mat, srgb);
    face(array(B[3], B[0], T[0], T[3]), {-1, 0, 0}, mat, srgb);
    face(array(B[1], B[2], T[2], T[1]), {1, 0, 0}, mat, srgb);
}
// a level box (absolute heights)
void lbox(vector mn, mx; string mat; vector srgb) {
    vector c[];
    for (int i = 0; i < 8; i++) append(c, set(i % 2 ? mx.x : mn.x, (i / 2) % 2 ? mx.y : mn.y, i / 4 ? mx.z : mn.z));
    face(array(c[2], c[3], c[7], c[6]), {0, 1, 0}, mat, srgb);
    face(array(c[0], c[1], c[5], c[4]), {0, -1, 0}, mat, srgb);
    face(array(c[0], c[1], c[3], c[2]), {0, 0, -1}, mat, srgb);
    face(array(c[4], c[5], c[7], c[6]), {0, 0, 1}, mat, srgb);
    face(array(c[0], c[2], c[6], c[4]), {-1, 0, 0}, mat, srgb);
    face(array(c[1], c[3], c[7], c[5]), {1, 0, 0}, mat, srgb);
}
// vertical tapered cylinder with caps
void cyl(vector base; float r0, r1, h; int n; string mat; vector srgb) {
    vector lo[], hi[];
    for (int i = 0; i < n; i++) {
        float a = 2 * PI * i / n;
        append(lo, base + set(cos(a) * r0, 0, sin(a) * r0));
        append(hi, base + set(cos(a) * r1, h, sin(a) * r1));
    }
    for (int i = 0; i < n; i++) {
        int j = (i + 1) % n;
        float a = 2 * PI * (i + 0.5) / n;
        face(array(lo[i], lo[j], hi[j], hi[i]), set(cos(a), 0, sin(a)), mat, srgb);
    }
    face(hi, {0, 1, 0}, mat, srgb);
    face(lo, {0, -1, 0}, mat, srgb);
}
// horizontal cylinder from a to b (pole arms, hydrant nozzles)
void hcyl(vector a, b; float r; int n; string mat; vector srgb) {
    vector ax = normalize(b - a);
    vector u = normalize(cross(ax, abs(ax.y) > 0.9 ? set(1, 0, 0) : set(0, 1, 0)));
    vector v = cross(ax, u);
    vector A[], B[];
    for (int i = 0; i < n; i++) {
        float t = 2 * PI * i / n;
        vector o = (u * cos(t) + v * sin(t)) * r;
        append(A, a + o); append(B, b + o);
    }
    for (int i = 0; i < n; i++) {
        int j = (i + 1) % n;
        face(array(A[i], A[j], B[j], B[i]), ((A[i] + A[j]) * 0.5) - a, mat, srgb);
    }
    face(B, ax, mat, srgb);
    face(A, -ax, mat, srgb);
}
// a foliage blob (tree crown lump, hedge, shrub): ONE POINT, not a mesh. Downstream, Copy to Points puts one of
// 8 prebuilt blob shapes (blob_protos, built with blob_mesh) on it as a packed instance, and the SOP Import turns
// those into a USD PointInstancer: ~3,000 blobs share 8 x 54 faces instead of 160k unique faces.
// Point attributes: pscale (radius), blob_variant 0-7, blob_cd (linear colour), blob_mat, orient (random spin
// about Y so the 8 shapes don't read as repeats); group blob_pts.
void blob(vector c; float r; int seed_s; string mat; vector srgb) {
    int pt = addpoint(0, c);
    setpointattrib(0, "pscale", pt, r);
    setpointattrib(0, "blob_variant", pt, abs(seed_s) % 8);
    setpointattrib(0, "blob_cd", pt, pow(srgb, 2.2));
    setpointattrib(0, "blob_mat", pt, mat);
    setpointattrib(0, "orient", pt, quaternion(2 * PI * rand(seed_s * 7 + 3), {0, 1, 0}));
    setpointgroup(0, "blob_pts", pt, 1);
}
// the blob as real faces (the original): blob_protos builds the 8 instance shapes with it (c = 0, r = 1)
void blob_mesh(vector c; float r; int seed_s; string mat; vector srgb) {
    int nu = 9, nv = 6;
    vector g[];
    for (int j = 0; j <= nv; j++)
        for (int i = 0; i < nu; i++) {
            float th = PI * j / nv, ph = 2 * PI * i / nu;
            float rr = r * (0.85 + 0.3 * rand(seed_s * 131 + j * 17 + i));
            if (j == 0 || j == nv) rr = r;
            append(g, c + set(sin(th) * cos(ph), cos(th) * 0.8, sin(th) * sin(ph)) * rr);
        }
    for (int j = 0; j < nv; j++)
        for (int i = 0; i < nu; i++) {
            int i2 = (i + 1) % nu;
            vector a = g[j * nu + i], b = g[j * nu + i2], cc = g[(j + 1) * nu + i2], d = g[(j + 1) * nu + i];
            face(array(a, b, cc, d), (a + cc) * 0.5 - c, mat, srgb);
        }
}
// an open curve with a width (wires) -> Karma renders it as a curve
void wire(vector P[]; float w; string mat; vector srgb) {
    int pts[];
    for (int i = 0; i < len(P); i++) { int pt = addpoint(0, P[i]); setpointattrib(0, "width", pt, w); append(pts, pt); }
    tag(addprim(0, "polyline", pts), mat, srgb);
}
// a sagging wire between two points
void span(vector a, b; float sag; float w) {
    vector P[];
    for (int i = 0; i <= 12; i++) {
        float t = i / 12.0;
        append(P, lerp(a, b, t) - set(0, sag * 4 * t * (1 - t), 0));
    }
    wire(P, w, "metal", {0.05, 0.05, 0.05});
}


#endif
