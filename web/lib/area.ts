// Block geometry: circle outlines for the map and sample points for the block analysis.
// Daymet's cells are 1 km, so sample points closer than that would give identical answers;
// we keep at most 9 points at least ~1 km apart, always including the block's center.

const KM_LAT = 111.0;

function kmLon(lat: number) {
  return KM_LAT * Math.cos((lat * Math.PI) / 180);
}

export function circlePolygon(lat: number, lon: number, radiusKm: number, n = 64): [number, number][] {
  const pts: [number, number][] = [];
  for (let i = 0; i <= n; i++) {
    const a = (i / n) * 2 * Math.PI;
    pts.push([lon + (radiusKm * Math.sin(a)) / kmLon(lat), lat + (radiusKm * Math.cos(a)) / KM_LAT]);
  }
  return pts;
}

function insidePolygon(lon: number, lat: number, poly: [number, number][]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi + 1e-12) + xi) inside = !inside;
  }
  return inside;
}

function dedupe(pts: [number, number][], minKm = 0.9, max = 9): [number, number][] {
  const out: [number, number][] = [];
  for (const p of pts) {
    const far = out.every((q) => Math.hypot((p[0] - q[0]) * KM_LAT, (p[1] - q[1]) * kmLon(p[0])) >= minKm);
    if (far) out.push(p);
    if (out.length >= max) break;
  }
  return out;
}

// [lat, lon] sample points across a circle.
export function circleSamples(lat: number, lon: number, radiusKm: number): [number, number][] {
  const pts: [number, number][] = [[lat, lon]];
  for (const frac of [0.55, 1.0]) {
    for (let i = 0; i < 6; i++) {
      const a = (i / 6) * 2 * Math.PI + (frac === 1 ? Math.PI / 6 : 0);
      pts.push([lat + (frac * radiusKm * Math.cos(a)) / KM_LAT, lon + (frac * radiusKm * Math.sin(a)) / kmLon(lat)]);
    }
  }
  return dedupe(pts);
}

// [lat, lon] sample points across a drawn outline ([lon, lat] vertices).
export function outlineSamples(poly: [number, number][], center: [number, number]): [number, number][] {
  const lons = poly.map((p) => p[0]);
  const lats = poly.map((p) => p[1]);
  const [w, e, s, n] = [Math.min(...lons), Math.max(...lons), Math.min(...lats), Math.max(...lats)];
  const midLat = (s + n) / 2;
  const spanKm = Math.max((e - w) * kmLon(midLat), (n - s) * KM_LAT);
  const step = Math.max(1.0, spanKm / 3);
  const pts: [number, number][] = [[center[1], center[0]]];
  for (let la = s + step / KM_LAT / 2; la < n; la += step / KM_LAT) {
    for (let lo = w + step / kmLon(midLat) / 2; lo < e; lo += step / kmLon(midLat)) {
      if (insidePolygon(lo, la, poly)) pts.push([la, lo]);
    }
  }
  return dedupe(pts);
}

export function polygonAreaKm2(poly: [number, number][]): number {
  if (poly.length < 3) return 0;
  const lat0 = poly.reduce((t, p) => t + p[1], 0) / poly.length;
  let a = 0;
  for (let i = 0; i < poly.length; i++) {
    const [x0, y0] = poly[i];
    const [x1, y1] = poly[(i + 1) % poly.length];
    a += x0 * kmLon(lat0) * (y1 * KM_LAT) - x1 * kmLon(lat0) * (y0 * KM_LAT);
  }
  return Math.abs(a) / 2;
}
