# AIS-History

AIS-History is a Python-based pipeline for processing raw AIS (Automatic Identification System) maritime data stored as JSON message streams, output obtained by logging the JSON console output of AIS-Catcher project by Jasper. The project converts large-scale AIS logs into structured Apache Parquet datasets, applies temporal and geospatial filtering, and generates interactive time-based vessel movement visualizations.

The processing architecture is divided into two main stages:

* `parse_ais()`: Parses raw JSON AIS messages, repairs corrupted timestamps, decodes NMEA payloads, and stores canonical structured records in columnar Parquet format.
* `mapit()`: Loads AIS temporal datasets and generates interactive animated vessel trajectory maps using geographic coordinates and timestamp playback.

The pipeline is designed for efficient handling of multi-million message AIS datasets while supporting post-processing spatial filtering and export to multiple formats.

---

## Dataset Structure

### Metadata about Reception / Decoder

| Field      | Meaning                                                                   | Example             |
| ---------- | ------------------------------------------------------------------------- | ------------------- |
| `class`    | AIS transmitter class (usually vessel transponder type)                   | A, B                |
| `device`   | Receiver device identifier that captured the AIS signal                   | SDR-01              |
| `version`  | AIS-Catcher software version                                              | 3.1.0               |
| `driver`   | SDR driver used by receiver                                               | RTLSDR              |
| `hardware` | Hardware used for reception                                               | RTL-SDR v3          |
| `rxtime`   | Human-readable timestamp when message was received                        | 2026-06-22 14:32:10 |
| `rxuxtime` | Unix timestamp of reception                                               | 1782138730          |
| `channel`  | VHF AIS channel used                                                      | A / B               |
| `scaled`   | Indicates whether numeric fields were already scaled to engineering units | true/false          |
| `nmea`     | Raw NMEA AIS sentence                                                     | !AIVDM,...          |

### Radio Signal Quality / Receiver Parameters

| Field         | Meaning                                                          | Example |
| ------------- | ---------------------------------------------------------------- | ------- |
| `signalpower` | Received signal strength / power level                           | -42 dBm |
| `ppm`         | Frequency correction error (Parts Per Million) of SDR oscillator | 2.3     |

### AIS Message Header Fields

| Field      | Meaning                                             | Example         |
| ---------- | --------------------------------------------------- | --------------- |
| `type`     | AIS message type number                             | 1               |
| `msg_type` | Human-readable message category                     | Position Report |
| `repeat`   | Number of retransmissions                           | 0–3             |
| `mmsi`     | Maritime Mobile Service Identity (unique vessel ID) | 235123456       |

### Vessel Identity / Registration

| Field          | Meaning                           | Example  |
| -------------- | --------------------------------- | -------- |
| `country`      | Country inferred from MMSI prefix | Portugal |
| `country_code` | Maritime country code (MID)       | 255      |

Example countries:

* 235 = United Kingdom
* 255 = Portugal
* 366 = United States

### Navigation Status

| Field         | Meaning                                       | Example   |
| ------------- | --------------------------------------------- | --------- |
| `status`      | Numeric navigation status code                | 0         |
| `status_text` | Human-readable vessel status                  | Under way |
| `maneuver`    | Special maneuver indicator                    | Turning   |
| `raim`        | Receiver Autonomous Integrity Monitoring flag | 0/1       |

Common `status` values:

| Code | Meaning                |
| ---- | ---------------------- |
| 0    | Under way using engine |
| 1    | At anchor              |
| 5    | Moored                 |
| 6    | Aground                |

### Vessel Motion / Navigation Data

| Field      | Meaning                    | Unit            |
| ---------- | -------------------------- | --------------- |
| `speed`    | Speed Over Ground (SOG)    | knots           |
| `course`   | Course Over Ground (COG)   | degrees         |
| `heading`  | True heading of vessel     | degrees         |
| `lon`      | Longitude                  | decimal degrees |
| `lat`      | Latitude                   | decimal degrees |
| `accuracy` | GPS position accuracy flag | high/low        |

### Rate of Turn Information

| Field           | Meaning                    | Example   |
| --------------- | -------------------------- | --------- |
| `turn_unscaled` | Raw AIS encoded turn value | 45        |
| `turn`          | Converted rate of turn     | 8.3 °/min |

AIS stores turn in compressed form, so:
```text
turn = pyais.decoded(turn_unscaled)
```

### Time Information Embedded in AIS Message

| Field        | Meaning                            | Example    |
| ------------ | ---------------------------------- | ---------- |
| `second`     | UTC second when GPS fix was taken  | 37         |
| `utc_hour`   | UTC hour                           | 14         |
| `utc_minute` | UTC minute                         | 52         |
| `timestamp`  | Timestamp field inside AIS payload | 1718712352 |

### TDMA Radio Communication Fields

AIS uses Self-Organizing Time Division Multiple Access (SOTDMA):

| Field          | Meaning                           | Example         |
| -------------- | --------------------------------- | --------------- |
| `radio`        | Raw radio state information       | encoded integer |
| `sync_state`   | TDMA synchronization method       | UTC Direct      |
| `slot_timeout` | Frames until new slot reservation | 3               |
| `slot_offset`  | Reserved transmission slot offset | 124             |

---

## Requirements

Library Requirements:

* Python 3.13+
* `orjson`
* `polars`
* `pyarrow`
* `pyais`
* `folium`
* `tqdm`

```bash
pip install orjson polars pyarrow pyais folium tqdm
```

## Usage

### Parsing Raw AIS Data

```python
parse_ais(infile, outfile, bsize, start, end)
```

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

### Interactive Vessel Mapping

```python
mapit(path)
```

* `path` → Input parquet AIS dataset

Example:

```python
mapit("dataset/ais_d22-23.parquet")
```

Generated output:

```text
output/ais_d22-23_timeline_map.html
```

### Spatial Filtering

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

### Exporting Filtered Data

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

[MIT License](https://mit-license.org/)
