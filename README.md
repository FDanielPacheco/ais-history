# AIS-History: AIS temporal parser and geospatial vessel visualization.

`AIS-History` is a Python-based pipeline for processing raw AIS (Automatic Identification System) maritime data stored as JSON message streams. The project converts large-scale AIS logs into structured Apache Parquet datasets, applies temporal and geospatial filtering, and generates interactive time-based vessel movement visualizations.

The processing architecture is divided into two main stages:

* `parse_ais()`: Parses raw JSON AIS messages, repairs corrupted timestamps, decodes NMEA payloads, and stores canonical structured records in columnar Parquet format.
* `mapit()`: Loads AIS temporal datasets and generates interactive animated vessel trajectory maps using geographic coordinates and timestamp playback.

The pipeline is designed for efficient handling of multi-million message AIS datasets while supporting post-processing spatial filtering and export to multiple formats.

---

## Requirements

Main dependencies:

* Python 3.13+
* `orjson`
* `polars`
* `pyarrow`
* `pyais`
* `folium`
* `tqdm`

Install dependencies:

```bash
pip install orjson polars pyarrow pyais folium tqdm
```

---

## Dataset Structure

All parsed AIS data is stored using a canonical schema in Apache Parquet format.

Main fields:

```text
mmsi
timestamp
lat
lon
speed
course
heading
country
country_code
status_text
signalpower
accuracy
nmea
type
channel
device
...
```

The schema is defined through:

```python
CANONICAL_SCHEMA
ARROW_SCHEMA
```

---

## Usage

### Parsing Raw AIS Data

`parse_ais()` processes line-separated AIS JSON records and stores valid decoded messages in Parquet format.

Function prototype:

```python
parse_ais(infile, outfile, bsize, start, end)
```

Parameters:

* `infile` → Raw AIS JSON input dataset
* `outfile` → Output parquet file
* `bsize` → Batch size used during parquet writing
* `start` → Initial UTC timestamp filter
* `end` → Final UTC timestamp filter

Example:

```python
from datetime import datetime, timezone

parse_ais(
    infile="dataset/feup.json",
    outfile="dataset/ais_d22-23.parquet",
    bsize=500000,
    start=datetime(2026, 5, 22, 0, 0, 0, tzinfo=timezone.utc),
    end=datetime(2026, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
)
```

Returned values:

```python
(saved_records, skipped_records, total_records)
```

Example output:

```text
(428402, 15280259, 15708661)
```

Internal processing stages:

* JSON parsing using `orjson`
* Timestamp extraction from:

  * `timestamp`
  * `rxuxtime`
  * `rxtime`
* Automatic timestamp repair
* AIS NMEA decoding through `pyais`
* Temporal filtering
* Batch writing to parquet

---

### Interactive Vessel Mapping

`mapit()` generates an interactive HTML map containing timestamp-based animated vessel trajectories.

Function prototype:

```python
mapit(path)
```

Parameters:

* `path` → Input parquet AIS dataset

Example:

```python
mapit("dataset/ais_d22-23.parquet")
```

Generated output:

```text
output/ais_d22-23_timeline_map.html
```

Map features:

* Timestamp playback slider
* Vessel trajectory animation
* MMSI identification
* Speed/course/heading metadata
* Country information
* Reference geospatial bounding box

Internally implemented using:

* `folium`
* `TimestampedGeoJson`

---

## Spatial Filtering

Generated parquet datasets can be filtered geographically using latitude and longitude constraints.

Reference coordinate:

```python
coord_center = {
    "lat": 41.458747,
    "lon": -8.842215,
    "half_side_km": 5.59704
}
```

Bounding box conversion:

```python
dlat = half_side_km / 111.0
dlon = half_side_km / (111.0 * cos(latitude))
```

Filter example:

```python
filtered = (
    pl.scan_parquet(path)
    .filter(
        (pl.col("lat") > coord_center["lat"] - dlat) &
        (pl.col("lat") < coord_center["lat"] + dlat) &
        (pl.col("lon") > coord_center["lon"] - dlon) &
        (pl.col("lon") < coord_center["lon"] + dlon)
    )
    .collect()
)
```

---

## Exporting Filtered Data

Filtered datasets can be exported in parquet or CSV format.

Write parquet:

```python
filtered.write_parquet(
    "dataset/ais_d22-23_filtered.parquet"
)
```

Write CSV:

```python
filtered.drop(["nmea"]).write_csv(
    "dataset/ais_d22-23_filtered.csv"
)
```

---

## Full Processing Pipeline

```text
Raw AIS JSON Dataset
        ↓
parse_ais()
        ↓
Temporal AIS Parquet Dataset
        ↓
Geospatial Filtering
        ↓
Filtered Parquet / CSV
        ↓
mapit()
        ↓
Interactive HTML Timeline Map
```

---

## Output Structure

```text
dataset/
 ├── ais_d22-23.parquet
 ├── ais_d31.parquet
 ├── ais_d9-12.parquet
 ├── ais_d22-23_filtered.parquet
 ├── ais_d22-23_filtered.csv

output/
 ├── ais_d22-23_timeline_map.html
 ├── ais_d22-23_filtered_timeline_map.html
```

---

## Author

Fábio D. Pacheco (fabio.d.pacheco@inesctec.pt)
Gonçalo Soares (goncalo.soares@inesctec.pt)

---

## License

MIT License
