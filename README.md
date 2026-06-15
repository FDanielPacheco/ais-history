# History AIS - AIS Data Processing and Visualization Pipeline

This repository contains a set of Python tools designed to process, filter, and visualize marine geolocation data (**AIS - Automatic Identification System**) stored in JSON format. 

The project is structured as a step-by-step pipeline, allowing you to clean large raw data log files, extract smaller subsets for fast testing, and ultimately generate an interactive map featuring a dynamic timeline animation of vessel routes.

The project consists of three main scripts that should be executed in the following sequential order:

### 1. Data Cleanup (`ais_clean.py`)
Raw AIS log files often contain terminal noise, system errors, or empty lines. This script performs a fast text-based string pre-filter and runs a robustness check to validate that each line is a properly formatted JSON object, preserving only valid AIS class entries.

*   **Output:** Generates a file with the suffix `_cleaned.json`.
*   **Usage:**
```bash
    python3 ais_clean.py <path_to_raw_input.json>
```

### 2. Record Slicing (`ais_slice.py`)
Processing massive geospatial datasets can be highly demanding on CPU and memory resources. This script allows you to extract exactly the first $N$ records from a cleaned JSON file, making it ideal for creating lightweight samples for rapid map layout testing.

*   **Output:** Generates a file with the suffix `_sliced.json`.
*   **Usage:**
```bash
    # Example to extract only the first 5000 lines
    python3 ais_slice.py <path_to_cleaned_input.json> 5000
```

### 3. Temporal Map Visualization (`ais_main.py`)
The primary script of this project. It parses the processed data (either cleaned or sliced), converts raw receiver timestamps into proper standard ISO formats, and utilizes the **Folium** library to render an interactive map in your web browser.

**Key Features:**
*   **Persistent Coloring:** Every vessel (uniquely identified by its `MMSI`) is assigned a persistent, dedicated color on the map.
*   **Time-Slider Animation:** Integrates the `TimestampedGeoJson` plugin, adding a time control interface (Play/Pause/Slider) to animate vessel trajectories over time.
*   **WEC C4 Reference Bounds:** Automatically plots a red info marker and its corresponding bounding box ($11.19\text{ km} \times 11.19\text{ km}$ square area) centered around the WEC C4 reference coordinate ($41.458747, -8.842215$).
*   **Auto-Launch:** Automatically compiles the geospatial entries and opens the resulting `.html` file inside your default web browser.

*   **Output:** Generates an interactive map named `_timeline_map.html`.
*   **Usage:**
```bash
    python3 ais_main.py <path_to_cleaned_or_sliced.json>
```