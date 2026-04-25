"""
build_dashboard.py
------------------
Standalone script that reads precinct GeoPackages and produces a
self-contained HTML choropleth dashboard — no server or internet
connection required to open the output file.

Architecture
------------
A single Plotly choroplethmapbox trace is rendered once against a
unified precinct roster (the union of all years' composite_prec_id
values). Layer switching calls Plotly.restyle() to update only the
z-values and hover text, so transitions are near-instant rather than
requiring a full re-render.

Views
-----
  2016 / 2020 / 2024 — Precinct-level actual turnout %
  Model Predictions  — 2024 need score + priority flag

Usage
-----
  Run from the project root:
      python scripts/build_dashboard.py

  Optional flags:
      --geo-dir   PATH   Directory containing precinct_features_*.gpkg
                         (default: data/geo/output)
      --out       PATH   Output HTML file path
                         (default: data/geo/output/mo_precinct_dashboard.html)

Dependencies
------------
  geopandas  (already required by the main pipeline)
  Plotly JS  is loaded from CDN on first open; the browser caches it
             for subsequent offline use.
"""

import argparse
import json
import os
import sys

import geopandas as gpd
import pandas as pd


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Build Missouri precinct turnout choropleth dashboard"
    )
    parser.add_argument(
        "--geo-dir",
        default="data/geo/output",
        help="Directory containing GeoPackage files (default: data/geo/output)",
    )
    parser.add_argument(
        "--out",
        default="data/geo/output/mo_precinct_dashboard.html",
        help="Output HTML path (default: data/geo/output/mo_precinct_dashboard.html)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def repair_and_reproject(gdf):
    """
    Two-pass geometry repair + reproject to EPSG:4326.
    make_valid() fixes structural issues; buffer(0) closes any remaining
    open rings before to_crs() runs.
    """
    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.make_valid()
    gdf["geometry"] = gdf.geometry.buffer(0)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    return gdf.to_crs(epsg=4326)


def load_gpkg(path, cols):
    """Reads a GeoPackage and returns a repaired, reprojected GeoDataFrame."""
    if not os.path.exists(path):
        print(f"  ERROR: {path} not found.", file=sys.stderr)
        sys.exit(1)
    gdf = gpd.read_file(path)
    gdf = repair_and_reproject(gdf)
    keep = [c for c in cols if c in gdf.columns] + ["geometry"]
    return gdf[keep].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Unified roster builder
# ---------------------------------------------------------------------------

FEATURE_COLS = [
    "composite_prec_id", "COUNTYFP",
    "turnout_pct", "dem_pct", "rep_pct", "total_votes", "apportioned_vap",
]

PRED_COLS = [
    "composite_prec_id", "COUNTYFP",
    "predicted_turnout_pct", "priority_flag",
    "priority_proba", "need_score", "predicted_uncasted_votes",
]


def build_unified_roster(year_gdfs):
    """
    Builds a single GeoDataFrame containing one row per unique
    composite_prec_id across all election years.

    When a precinct appears in multiple years, the most recent year's
    geometry is used (2024 > 2020 > 2016) since boundaries are most
    current. Non-geometry attributes are not carried over — they are
    stored separately per-view.

    Returns
    -------
    GeoDataFrame with columns: composite_prec_id, COUNTYFP, geometry
    """
    # Process years oldest-first so newer entries overwrite older ones
    seen = {}
    for year in [2016, 2020, 2024]:
        gdf = year_gdfs[year]
        for _, row in gdf.iterrows():
            pid = row["composite_prec_id"]
            seen[pid] = {
                "composite_prec_id": pid,
                "COUNTYFP": row.get("COUNTYFP", ""),
                "geometry": row.geometry,
            }

    roster = gpd.GeoDataFrame(
        list(seen.values()),
        geometry="geometry",
        crs="EPSG:4326",
    ).sort_values("composite_prec_id").reset_index(drop=True)

    print(f"  Unified roster: {len(roster):,} unique precincts across all years")
    return roster


# ---------------------------------------------------------------------------
# Per-view array builders
# ---------------------------------------------------------------------------

def _safe_round(val, decimals=2):
    """Round a value for JSON output; return None for NaN/None."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if f != f else round(f, decimals)  # NaN check
    except (TypeError, ValueError):
        return None


def build_turnout_arrays(roster, gdf, year):
    """
    Builds z-values and hover strings for a turnout view, aligned to
    the roster order. Precincts absent in this year get z=None (shown
    as grey on the map).
    """
    lookup = {
        row["composite_prec_id"]: row
        for _, row in gdf.iterrows()
    }

    z, hover = [], []
    for pid in roster["composite_prec_id"]:
        row = lookup.get(pid)
        if row is None:
            z.append(None)
            hover.append(f"<b>{pid}</b><br>No data for {year}")
            continue

        prec  = pid.split("_", 1)[1] if "_" in pid else pid
        to    = _safe_round(row.get("turnout_pct"), 1)
        dem   = _safe_round(row.get("dem_pct"),     1)
        rep   = _safe_round(row.get("rep_pct"),     1)
        tv    = row.get("total_votes")

        z.append(to)
        hover.append(
            f"<b>{prec}</b><br>"
            f"County FIPS: {row.get('COUNTYFP', '')}<br>"
            f"Turnout: <b>{to if to is not None else 'N/A'}%</b><br>"
            f"Dem%: {dem if dem is not None else 'N/A'}% &nbsp;|&nbsp; "
            f"Rep%: {rep if rep is not None else 'N/A'}%<br>"
            f"Total votes: {int(tv):,}" if tv is not None else "Total votes: N/A"
        )

    return z, hover


def build_pred_arrays(roster, pred_gdf):
    """
    Builds z-values (need_score) and hover strings for the model
    predictions view, aligned to the roster order.
    """
    lookup = {
        row["composite_prec_id"]: row
        for _, row in pred_gdf.iterrows()
    }

    z, hover = [], []
    for pid in roster["composite_prec_id"]:
        row = lookup.get(pid)
        if row is None:
            z.append(None)
            hover.append(f"<b>{pid.split('_', 1)[-1]}</b><br>No prediction available")
            continue

        prec = pid.split("_", 1)[1] if "_" in pid else pid
        pto  = _safe_round(row.get("predicted_turnout_pct"), 1)
        ns   = _safe_round(row.get("need_score"), 0)
        prob = _safe_round(row.get("priority_proba"), 4)
        flag = row.get("priority_flag")
        unc  = row.get("predicted_uncasted_votes")

        flag_str = "&#9873; HIGH PRIORITY" if flag == 1 else "Normal"
        prob_pct = f"{round(prob * 100, 1)}%" if prob is not None else "N/A"
        unc_str  = f"{int(unc):,}" if unc is not None else "N/A"

        z.append(ns)
        hover.append(
            f"<b>{prec}</b><br>"
            f"County FIPS: {row.get('COUNTYFP', '')}<br>"
            f"{flag_str}<br>"
            f"Predicted turnout: <b>{pto if pto is not None else 'N/A'}%</b><br>"
            f"Need score: <b>{int(ns):,}" if ns is not None else "Need score: <b>N/A"
            f"</b><br>"
            f"Priority probability: {prob_pct}<br>"
            f"Est. uncasted votes: {unc_str}"
        )

    return z, hover


def build_pred_turnout_arrays(roster, pred_gdf):
    """
    Builds z-values (predicted_turnout_pct, 0-100 scale) and hover strings
    for the predicted turnout view, aligned to the roster order.
    Uses the same colour scale as historical turnout views so the comparison
    is direct.
    """
    lookup = {
        row["composite_prec_id"]: row
        for _, row in pred_gdf.iterrows()
    }

    z, hover = [], []
    for pid in roster["composite_prec_id"]:
        row = lookup.get(pid)
        if row is None:
            z.append(None)
            hover.append(f"<b>{pid.split('_', 1)[-1]}</b><br>No prediction available")
            continue

        prec = pid.split("_", 1)[1] if "_" in pid else pid
        pto  = _safe_round(row.get("predicted_turnout_pct"), 1)
        ns   = _safe_round(row.get("need_score"), 0)
        prob = _safe_round(row.get("priority_proba"), 4)
        flag = row.get("priority_flag")
        unc  = row.get("predicted_uncasted_votes")

        flag_str = "&#9873; HIGH PRIORITY" if flag == 1 else "Normal"
        prob_pct = f"{round(prob * 100, 1)}%" if prob is not None else "N/A"
        unc_str  = f"{int(unc):,}" if unc is not None else "N/A"
        ns_str   = f"{int(ns):,}" if ns is not None else "N/A"

        z.append(pto)
        hover.append(
            f"<b>{prec}</b><br>"
            f"County FIPS: {row.get('COUNTYFP', '')}<br>"
            f"{flag_str}<br>"
            f"Predicted turnout: <b>{pto if pto is not None else 'N/A'}%</b><br>"
            f"Need score: {ns_str} (not a %)<br>"
            f"Priority probability: {prob_pct}<br>"
            f"Est. uncasted votes: {unc_str}"
        )

    return z, hover


def build_county_outlines(roster):
    """
    Dissolves the unified precinct roster by COUNTYFP to produce county
    polygons, then extracts exterior ring coordinates as flat lon/lat arrays
    suitable for a Plotly Scattermapbox lines trace.

    Polygons are separated by None sentinels so Plotly draws discrete
    closed shapes rather than connecting counties to each other.
    """
    county_gdf = (
        roster[["COUNTYFP", "geometry"]]
        .dissolve(by="COUNTYFP")
        .reset_index()
    )
    county_gdf["geometry"] = county_gdf.geometry.make_valid()
    county_gdf["geometry"] = county_gdf.geometry.buffer(0)
    county_gdf = county_gdf[
        county_gdf.geometry.notna() & ~county_gdf.geometry.is_empty
    ]

    lons, lats = [], []
    for geom in county_gdf.geometry:
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        for poly in polys:
            xs, ys = poly.exterior.xy
            lons.extend(list(xs) + [None])
            lats.extend(list(ys) + [None])

    print(f"  County outlines: {len(county_gdf)} counties extracted")
    return lons, lats


def percentile_95(z_list):
    """Returns the 95th percentile of non-null values for colorscale capping."""
    vals = sorted(v for v in z_list if v is not None)
    if not vals:
        return 1
    return vals[int(0.95 * (len(vals) - 1))]


# ---------------------------------------------------------------------------
# Colour scales
# ---------------------------------------------------------------------------

TURNOUT_CS = [
    [0.0,  "#d73027"],
    [0.25, "#fc8d59"],
    [0.5,  "#fee090"],
    [0.75, "#91bfdb"],
    [1.0,  "#4575b4"],
]

NEED_CS = [
    [0.0,  "#f7f7f7"],
    [0.5,  "#fb6a4a"],
    [1.0,  "#67000d"],
]


# ---------------------------------------------------------------------------
# GeoDataFrame → compact GeoJSON string
# ---------------------------------------------------------------------------

def gdf_to_geojson_str(gdf):
    """
    Serialises a GeoDataFrame to a compact GeoJSON string.
    Only composite_prec_id is included as a property (the map
    only needs it for featureidkey matching — all other data
    lives in the pre-built z / hover arrays).
    """
    features = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        features.append({
            "type": "Feature",
            "geometry": geom.__geo_interface__,
            "properties": {"composite_prec_id": row["composite_prec_id"]},
        })
    fc = {"type": "FeatureCollection", "features": features}
    return json.dumps(fc, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_dashboard(geo_dir, out_path):
    print("Loading GeoPackages...")

    year_gdfs = {}
    for year in [2016, 2020, 2024]:
        path = os.path.join(geo_dir, f"precinct_features_{year}.gpkg")
        print(f"  Reading {year}...")
        year_gdfs[year] = load_gpkg(path, FEATURE_COLS)
        print(f"    → {len(year_gdfs[year]):,} precincts")

    pred_path = os.path.join(geo_dir, "precinct_model_predictions.gpkg")
    print("  Reading model predictions...")
    pred_gdf = load_gpkg(pred_path, PRED_COLS)
    print(f"    → {len(pred_gdf):,} precincts")

    # Build unified roster (one geometry per unique precinct)
    print("\nBuilding unified precinct roster...")
    roster = build_unified_roster(year_gdfs)

    # Build per-view arrays aligned to roster order
    print("Pre-computing view arrays...")
    z16, h16 = build_turnout_arrays(roster, year_gdfs[2016], 2016)
    z20, h20 = build_turnout_arrays(roster, year_gdfs[2020], 2020)
    z24, h24 = build_turnout_arrays(roster, year_gdfs[2024], 2024)
    zpr, hpr = build_pred_arrays(roster, pred_gdf)
    zpt, hpt = build_pred_turnout_arrays(roster, pred_gdf)

    need_zmax = percentile_95(zpr)

    # County outline coordinates for permanent overlay trace
    print("Building county outlines...")
    county_lons, county_lats = build_county_outlines(roster)

    # Serialise GeoJSON (geometry + id only — keeps file lean)
    print("Serialising GeoJSON...")
    geojson_str = gdf_to_geojson_str(roster)
    geojson_size_mb = len(geojson_str.encode()) / 1_048_576
    print(f"  GeoJSON size: {geojson_size_mb:.1f} MB  "
          f"({len(roster):,} features)")

    # Embed view data as JS
    views_js = f"""
const COUNTY_LONS = {json.dumps(county_lons, separators=(',', ':'))};
const COUNTY_LATS = {json.dumps(county_lats, separators=(',', ':'))};

const VIEWS = {{
  '2016': {{
    z:           {json.dumps(z16, separators=(',', ':'))},
    hover:       {json.dumps(h16, separators=(',', ':'))},
    colorscale:  {json.dumps(TURNOUT_CS)},
    zmin: 0, zmax: 100,
    colorbarTitle: 'Turnout %',
    legend: 'Actual precinct turnout % \u00b7 2016 presidential election'
  }},
  '2020': {{
    z:           {json.dumps(z20, separators=(',', ':'))},
    hover:       {json.dumps(h20, separators=(',', ':'))},
    colorscale:  {json.dumps(TURNOUT_CS)},
    zmin: 0, zmax: 100,
    colorbarTitle: 'Turnout %',
    legend: 'Actual precinct turnout % \u00b7 2020 presidential election'
  }},
  '2024': {{
    z:           {json.dumps(z24, separators=(',', ':'))},
    hover:       {json.dumps(h24, separators=(',', ':'))},
    colorscale:  {json.dumps(TURNOUT_CS)},
    zmin: 0, zmax: 100,
    colorbarTitle: 'Turnout %',
    legend: 'Actual precinct turnout % \u00b7 2024 presidential election'
  }},
  'pred': {{
    z:           {json.dumps(zpr, separators=(',', ':'))},
    hover:       {json.dumps(hpr, separators=(',', ':'))},
    colorscale:  {json.dumps(NEED_CS)},
    zmin: 0, zmax: {need_zmax},
    colorbarTitle: 'Need Score',
    legend: '2024 model predictions \u00b7 Need score = priority probability \u00d7 estimated uncasted votes \u00b7 Not a percentage \u2014 higher = greater resource need'
  }},
  'pred-turnout': {{
    z:           {json.dumps(zpt, separators=(',', ':'))},
    hover:       {json.dumps(hpt, separators=(',', ':'))},
    colorscale:  {json.dumps(TURNOUT_CS)},
    zmin: 0, zmax: 100,
    colorbarTitle: 'Predicted Turnout %',
    legend: '2024 model predictions \u00b7 Predicted precinct turnout % \u00b7 Same scale as historical views \u2014 compare directly with 2024 actual'
  }}
}};
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Missouri Precinct Turnout Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js" charset="utf-8"></script>
<style>
  *      {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body   {{ font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; color: #e0e0e0; }}

  header {{
    padding: 14px 28px 10px;
    background: #16213e;
    border-bottom: 2px solid #0f3460;
    display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap;
  }}
  header h1 {{ font-size: 1.2rem; font-weight: 700; color: #e2e8f0; }}
  header p  {{ font-size: 0.78rem; color: #94a3b8; }}

  #controls {{
    display: flex; gap: 8px; padding: 9px 28px;
    background: #16213e; border-bottom: 1px solid #0f3460;
    flex-wrap: wrap; align-items: center;
  }}
  #controls span {{ font-size: 0.78rem; color: #94a3b8; margin-right: 2px; }}

  .btn {{
    padding: 5px 15px; border: 1.5px solid #4a90d9; border-radius: 5px;
    background: transparent; color: #93c5fd; font-size: 0.80rem; cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }}
  .btn:hover  {{ background: #1e3a5f; }}
  .btn.active {{ background: #1d4ed8; color: #fff; border-color: #1d4ed8; }}

  #legend-bar {{
    padding: 4px 28px; background: #16213e;
    border-bottom: 1px solid #0f3460;
    font-size: 0.73rem; color: #94a3b8; min-height: 24px;
  }}

  #map {{ width: 100%; height: calc(100vh - 128px); }}
</style>
</head>
<body>

<header>
  <h1>Missouri Precinct Turnout &amp; Resource Need Dashboard</h1>
  <p>CAPS 5576 &middot; Group 1 &middot; Missouri Voter Resource Allocation &middot; April 2026</p>
</header>

<div id="controls">
  <span>View:</span>
  <button class="btn"        id="btn-2016"         onclick="showLayer('2016')">2016 Turnout</button>
  <button class="btn"        id="btn-2020"         onclick="showLayer('2020')">2020 Turnout</button>
  <button class="btn"        id="btn-2024"         onclick="showLayer('2024')">2024 Turnout</button>
  <button class="btn active" id="btn-pred-turnout" onclick="showLayer('pred-turnout')">2024 Predicted Turnout</button>
  <button class="btn"        id="btn-pred"         onclick="showLayer('pred')">2024 Precinct Need Score</button>
</div>

<div id="legend-bar">
  <span id="legend-text">2024 model predictions &middot; Predicted precinct turnout % &middot; Same scale as historical views &mdash; compare directly with 2024 actual</span>
</div>

<div id="map"></div>

<script>
// ── Embedded GeoJSON (geometry + composite_prec_id only) ──────────────────
const GEOJSON = {geojson_str};

// ── Per-view z / hover / style data ──────────────────────────────────────
{views_js}

// ── Initial render — 2024 predicted turnout view ─────────────────────────
const init = VIEWS['pred-turnout'];
const PREC_IDS = GEOJSON.features.map(f => f.properties.composite_prec_id);

Plotly.newPlot('map',
  [
    // Trace 0 — main choropleth (switches view on layer change)
    {{
      type: 'choroplethmapbox',
      geojson: GEOJSON,
      locations: PREC_IDS,
      featureidkey: 'properties.composite_prec_id',
      z:    init.z,
      text: init.hover,
      hovertemplate: '%{{text}}<extra></extra>',
      colorscale: init.colorscale,
      zmin: init.zmin,
      zmax: init.zmax,
      marker: {{opacity: 0.78, line: {{width: 0.3, color: '#555'}}}},
      colorbar: {{
        title: {{text: init.colorbarTitle, side: 'right'}},
        thickness: 14, len: 0.55, y: 0.5
      }}
    }},
    // Trace 1 — county outlines (permanent overlay on all views)
    {{
      type: 'scattermapbox',
      lon: COUNTY_LONS,
      lat: COUNTY_LATS,
      mode: 'lines',
      line: {{color: '#cccccc', width: 0.6}},
      hoverinfo: 'skip',
      showlegend: false
    }}
  ],
  {{
    mapbox: {{
      style: 'carto-darkmatter',
      center: {{lat: 38.5, lon: -92.5}},
      zoom: 6.2
    }},
    margin: {{t: 0, b: 0, l: 0, r: 0}},
    paper_bgcolor: '#1a1a2e',
    hoverlabel: {{
      bgcolor: '#16213e', bordercolor: '#4a90d9',
      font: {{color: '#e0e0e0', size: 12}},
      align: 'left'
    }},
    showlegend: false
  }},
  {{responsive: true, displaylogo: false}}
);

// ── Layer switcher — updates z/hover/colorscale only, no re-render ────────
const BTN_IDS = {{
  '2016':         'btn-2016',
  '2020':         'btn-2020',
  '2024':         'btn-2024',
  'pred-turnout': 'btn-pred-turnout',
  'pred':         'btn-pred'
}};

function showLayer(key) {{
  const v = VIEWS[key];
  Plotly.restyle('map', {{
    z:                    [v.z],
    text:                 [v.hover],
    colorscale:           [v.colorscale],
    zmin:                 [v.zmin],
    zmax:                 [v.zmax],
    'colorbar.title.text': [v.colorbarTitle]
  }}, [0]);

  document.getElementById('legend-text').textContent = v.legend;
  Object.keys(BTN_IDS).forEach(k =>
    document.getElementById(BTN_IDS[k]).classList.toggle('active', k === key)
  );
}}
</script>

</body>
</html>
"""

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)

    size_mb = os.path.getsize(out_path) / 1_048_576
    print(f"\nDashboard written → {out_path}  ({size_mb:.1f} MB)")
    print("Open in any browser. No internet needed after first load.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = parse_args()
    build_dashboard(geo_dir=args.geo_dir, out_path=args.out)
