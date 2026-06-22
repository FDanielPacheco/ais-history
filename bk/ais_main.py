import sys, json, webbrowser, os, math
from collections import defaultdict
import folium
from folium.plugins import TimestampedGeoJson

def safe_float(v):
    try: return float(v)
    except: return None

def format_iso_time(rxtime):
    # converts YYYYMMDDHHMMSS string to ISO format YYYY-MM-DDTHH:MM:SS
    if rxtime and len(rxtime) == 14:
        return f"{rxtime[0:4]}-{rxtime[4:6]}-{rxtime[6:8]}T{rxtime[8:10]}:{rxtime[10:12]}:{rxtime[12:14]}"
    return rxtime

def main(path):
    print(f"Processing temporal database from: {path}...")
    
    mmsi_names = {}
    features = []
    all_points = []
    
    colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33', '#a65628', '#f781bf', '#999999']
    mmsi_color_map = {}
    color_index = 0

    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                mmsi = rec.get("mmsi")
                if not mmsi: continue
                
                if rec.get("shipname"):
                    mmsi_names[mmsi] = rec.get("shipname").strip()
                
                lat = safe_float(rec.get("lat"))
                lon = safe_float(rec.get("lon"))
                
                if lat is not None and lon is not None:
                    all_points.append((lat, lon))
                    
                    # assign a persistent color to each unique MMSI
                    if mmsi not in mmsi_color_map:
                        mmsi_color_map[mmsi] = colors[color_index % len(colors)]
                        color_index += 1
                    
                    ship_color = mmsi_color_map[mmsi]
                    ship_name = mmsi_names.get(mmsi, "-")
                    iso_time = format_iso_time(rec.get("rxtime"))
                    
                    popup_content = f"MMSI: {mmsi}<br>Name: {ship_name}<br>Time: {iso_time}"
                    
                    # construct a GeoJSON Feature for each point over time
                    feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [lon, lat] # GeoJSON uses [lon, lat] order
                        },
                        "properties": {
                            "time": iso_time,
                            "popup": popup_content,
                            "icon": "circle",
                            "iconstyle": {
                                "fillColor": ship_color,
                                "fillOpacity": 0.6,
                                "color": ship_color,
                                "radius": 2.5,
                                "weight": 1
                            }
                        }
                    }
                    features.append(feature)
                    
    except FileNotFoundError:
        print("Error: Input file not found.", file=sys.stderr); sys.exit(2)

    if not features:
        print("No geographical data found to plot.", file=sys.stderr); sys.exit(1)

    print(f"Loaded {len(features):,} timeline points across {len(mmsi_color_map)} targets.")

    # calculate global center map location
    mean_lat = sum(p[0] for p in all_points) / len(all_points)
    mean_lon = sum(p[1] for p in all_points) / len(all_points)
    
    m = folium.Map(location=[mean_lat, mean_lon], zoom_start=6, tiles=None)

    # add WEC C4 reference point
    WEC_C4_lat = 41.458747  
    WEC_C4_lon = -8.842215 
    half_side_km = 5.59704
    
    delta_lat = half_side_km / 111.0
    delta_lon = half_side_km / (111.0 * math.cos(math.radians(WEC_C4_lat)))
    
    lat_min, lat_max = WEC_C4_lat - delta_lat, WEC_C4_lat + delta_lat
    lon_min, lon_max = WEC_C4_lon - delta_lon, WEC_C4_lon + delta_lon
    
    folium.Marker(
        location=[WEC_C4_lat, WEC_C4_lon],
        popup=f"WEC_C4<br>Lat: {WEC_C4_lat}<br>Lon: {WEC_C4_lon}",
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)

    # add square area around the reference point
    folium.Rectangle(
        bounds=[[lat_min, lon_min], [lat_max, lon_max]],
        color="#e41a1c",
        fill=True,
        fill_color="#e41a1c",
        fill_opacity=0.1,
        weight=2,
        popup=f"Area: {half_side_km * 2}km x {half_side_km * 2}km"
    ).add_to(m)
    
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attr="&copy; OpenStreetMap contributors &copy; CARTO",
        name="CartoDB Positron",
        max_zoom=19,
        subdomains=["a","b","c","d"],
    ).add_to(m)

    # wrap features inside a GeoJSON FeatureCollection structure
    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }

    # apply the TimestampedGeoJson plugin to create the time slider animation
    TimestampedGeoJson(
        geojson_data,
        period="PT1M", # time step granularity
        duration="PT5M", # how long points stay visible on screen
        transition_time=200,
        auto_play=False,
        add_last_point=True,
        loop=False,
        max_speed=10
    ).add_to(m)

    out_name = os.path.splitext(os.path.basename(path))[0] + "_timeline_map.html"
    m.save(out_name)
    print(f"Timebar Map rendered successfully: {out_name}")
    webbrowser.open('file://' + os.path.abspath(out_name))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 ais_main.py <cleaned_data.json>", file=sys.stderr); sys.exit(1)
    main(sys.argv[1])