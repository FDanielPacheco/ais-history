import os, math, psycopg2, folium, requests, re, uuid, csv, io, platform, time
import streamlit as st
import pandas as pd

from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta, time as dt_time
from zoneinfo import ZoneInfo
from folium.plugins import TimestampedGeoJson, MeasureControl
from pathlib import Path
from vessel_validator import validate_mmsi
from streamlit_autorefresh import st_autorefresh

colorscheme = ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3","#ff7f00", "#ffff33", "#a65628", "#f781bf", "#999999"]
region_dict = {"lat": 41.458747, "lon": -8.842215, "width": 5.59704, "height": 5.59704}
start_dict = {"lat": 41.444261, "lon": -8.778055}
dlat = region_dict["width"] / 111.0
dlon = region_dict["height"] / (111.0 * math.cos(math.radians(region_dict["lat"])))

def to_utc(dt):
        local_tz = ZoneInfo("Europe/Lisbon")
        return dt.replace(tzinfo=local_tz).astimezone(timezone.utc)

def get_shipspotting_image(mmsi):      
        s = requests.Session()
        s.headers.update({"User-Agent": "Mozilla/5.0"})
        res = s.get(f"https://www.vesselfinder.com/vessels/details/{mmsi}")
        img = re.search(r'<img[^>]*class="main-photo"[^>]*src="([^"]+)"|<img[^>]*src="([^"]+)"[^>]*class="main-photo"', res.text)
        return (img.group(1) or img.group(2)) if img else None

def mapit(df, bs, live=False):
        m = folium.Map(location=[bs["lat"], bs["lon"]], zoom_start=6, tiles="CartoDB positron", control_scale=True)

        # Sattelite Map
        satellite_layer = folium.TileLayer(
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                attr='Esri, DigitalGlobe, GeoEye, Earthstar Geographics, CNES/Airbus DS, USDA, USGS, AeroGRID, IGN, and the GIS User Community',
                name='Satellite Imagery',
                overlay=False,
                show=True
        ).add_to(m)
        labels_overlay = folium.TileLayer(
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
                attr='Esri, HERE, Garmin, © OpenStreetMap contributors, and the GIS user community',
                name='City Labels & Boundaries',
                overlay=True,
                show=True
        ).add_to(m)

        # Measurement Feature
        m.add_child(MeasureControl(
                position='topleft',
                primary_length_unit='nauticalmiles',
                secondary_length_unit='kilometers',
                primary_area_unit='sqnm',
                secondary_area_unit='sqkilometers',
                active_color='#e41a1c',
                completed_color='#377eb8'
        ))

        folium.Marker(
                [bs["lat"], bs["lon"]],
                popup="Base Station FEUP",
                icon=folium.Icon(color="gray", icon="info-sign")
        ).add_to(m)
        if df.empty:
                return m
    
        color_map = {}
        features = []
        for idx, rec in df.iterrows():
                mmsi, lat, lon, ts = rec["mmsi"], rec["lat"], rec["lon"], rec["received_at"]
                if mmsi not in color_map:
                        color_map[mmsi] = colorscheme[len(color_map) % len(colorscheme)]
                color = color_map[mmsi]
                iso_time = ts.isoformat()+"Z"

                result = validate_mmsi(str(mmsi))
                if result.valid:
                        country_name = result.info.get("country", "Unknown")
                        vessel_type = result.info.get("type", "Unknown")
                        mid_code = result.info.get("mid", "Unknown")
                popup = (
                        f"<b>MMSI:</b> {mmsi}<br>"
                        f"<b>Callsign:</b> {rec.get('callsign')}<br>"
                        f"<b>Speed:</b> {rec.get('speed')} kn<br>"
                        f"<b>Course:</b> {rec.get('course')}°<br>"
                        f"<b>Heading:</b> {rec.get('heading')}°<br>"
                        f"<b>Country:</b> {country_name}<br>"
                        f"<b>MID:</b> {mid_code}<br>"
                        f"<b>Time:</b> {iso_time}"
                )
                if live == False:
                        features.append({
                                "type": "Feature",
                                "geometry": {
                                        "type": "Point",
                                        "coordinates": [lon, lat]
                                },
                                "properties": {
                                        "time": iso_time,
                                        "popup": popup,
                                        "icon": "circle",
                                        "iconstyle": {
                                                "fillColor": color,
                                                "color": color,
                                                "fillOpacity": 0.4,
                                                "radius": 1.5,
                                                "weight": 1
                                        }
                                }
                        })
                else:
                        folium.CircleMarker(
                                location=[lat, lon],
                                radius=1.5,
                                color=color,
                                fill=True,
                                fillColor=color,
                                fillOpacity=0.4,
                                popup=popup,
                        ).add_to(m)
                        

        if live == False and features:
                timeline = TimestampedGeoJson(
                        {"type": "FeatureCollection", "features": features},
                        period="PT1M",
                        duration="PT5M",
                        transition_time=200,
                        auto_play=False,
                        add_last_point=True,
                        loop=False,
                        max_speed=10        
                )
                timeline.add_to(m)

        # Region of interest
        folium.Rectangle(
                bounds=[
                        [region_dict["lat"] - dlat, region_dict["lon"] - dlon], 
                        [region_dict["lat"] + dlat, region_dict["lon"] + dlon]
                ],
                color="#e41a1c", fill=True, fill_opacity=0.1, weight=2
        ).add_to(m)

        # DAS cable
        folium.PolyLine(
                locations=[
                        [start_dict["lat"], start_dict["lon"]], 
                        [region_dict["lat"], region_dict["lon"]]
                ],
                color="#377eb8", weight=2.5, dash_array="5, 5"
        ).add_to(m)

        folium.LayerControl(position='topright').add_to(m)

        return m

def validateTime(time_dict):
        if not isinstance(time_dict, dict):
                raise ValueError("Time filter must be a dictionary.")
        if "ini" not in time_dict or "fin" not in time_dict:
                raise ValueError("Time filter must contain both 'ini' and 'fin' keys.")
        if not isinstance(time_dict["ini"], datetime) or not isinstance(time_dict["fin"], datetime):
                raise ValueError("'ini' and 'fin' values must be datetime objects.")
        if time_dict["ini"] >= time_dict["fin"]:
                raise ValueError("Start time ('ini') must be strictly before end time ('fin').")
        return True

def fetchDB(time_dict, region=None, live=False, mmsi=None):
        load_dotenv()
        conn = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                port=5432,
                database=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD")
        )
        bs = requests.get(f'http://{os.getenv("DB_HOST")}:8888').json()

        if False == live:
                validateTime(time_dict)
                if region is None:
                        query = (
                                "SELECT pos.*, v.shipname, v.callsign, v.shiptype, v.destination " 
                                "FROM ais_vessel_pos pos "
                                "LEFT JOIN ais_vessel v ON pos.mmsi = v.mmsi "
                                "WHERE pos.received_at >= %s AND pos.received_at < %s "
                                "  AND pos.lat IS NOT NULL AND pos.lon IS NOT NULL "
                                "  AND (%s IS NULL OR pos.mmsi = %s);"
                        )
                        params = (time_dict["ini"], time_dict["fin"], mmsi, mmsi)
                else:
                        query = (
                                "SELECT pos.*, v.shipname, v.callsign, v.shiptype, v.destination " 
                                "FROM ais_vessel_pos pos "
                                "LEFT JOIN ais_vessel v ON pos.mmsi = v.mmsi "
                                "WHERE pos.received_at >= %s AND pos.received_at < %s "
                                "  AND pos.lat IS NOT NULL AND pos.lon IS NOT NULL "
                                "  AND pos.lat BETWEEN %s AND %s AND pos.lon BETWEEN %s AND %s "
                                "  AND (%s IS NULL OR pos.mmsi = %s);"
                        )
                        params = (
                                time_dict["ini"], time_dict["fin"], 
                                region_dict["lat"] - dlat, region_dict["lat"] + dlat, 
                                region_dict["lon"] - dlon, region_dict["lon"] + dlon,
                                mmsi, mmsi
                        )
            
        else:
                query = (
                        "SELECT pos.*, v.shipname, v.callsign, v.shiptype, v.destination " 
                        "FROM ais_vessel_pos pos "
                        "LEFT JOIN ais_vessel v ON pos.mmsi = v.mmsi "
                        "WHERE pos.received_at >= %s "
                        "  AND pos.lat IS NOT NULL AND pos.lon IS NOT NULL "
                        "  AND (%s IS NULL OR pos.mmsi = %s);"
                )
                params = (datetime.now(timezone.utc) - timedelta(minutes=30), mmsi, mmsi)

        df = pd.read_sql_query(query, conn, params=params)           
        conn.close()
        return df, bs 
    
def winlayout():
        st.set_page_config(page_title="AIS-History", layout="wide")

        with st.sidebar:
                st.title("AIS-History")

                c1, c2 = st.columns(2)
                time_dict = {
                        "ini": c1.datetime_input("From"),
                        "fin": c2.datetime_input("To")
                }
                st.subheader("Geographic and Time Filters")
                segfilter = st.segmented_control("Filter", ["Live", "Aguça Doura"], selection_mode="multi")

                st.session_state.is_live = True if "Live" in segfilter else False
                auto_refresh_triggered = st.session_state.get("auto_refresh_triggered", False)

                if st.session_state.is_live:
                        options = {"1m": 60, "5m": 300, "10m": 600, "30m": 1800, "1h": 3600}
                        selected_option = st.selectbox("Auto-Refresh Interval", options=list(options.keys()), index=2)
                        st.session_state.refresh_interval_ms = options[selected_option] * 1000
                
                mmsi = st.text_input("MMSI")                                
                c1, c2 = st.columns(2)
                if c1.button("Load Data", width="stretch") or auto_refresh_triggered:
                        st.session_state.auto_refresh_triggered = False

                        with st.spinner(text="Please wait..."):
                                df, bs = fetchDB(
                                        {"ini": to_utc(time_dict["ini"]), "fin": to_utc(time_dict["fin"])}, 
                                        region=region_dict if "Aguça Doura" in segfilter else None, 
                                        live=True if "Live" in segfilter else False,
                                        mmsi=mmsi if validate_mmsi(str(mmsi)).valid else None
                                )
                                st.session_state.df = df.copy()
                                if platform.system() == "Windows" or platform.system() == "Linux":
                                        st.session_state.mapfile = f"{uuid.uuid4().hex}.map.html"
                                else:
                                        st.session_state.mapfile = f"/tmp/ais-history/{uuid.uuid4().hex}.map.html"
                                mapit(df, bs, live=True if "Live" in segfilter else False).save(st.session_state.mapfile)

                                st.session_state.data2save = df.to_csv(index=False)
                                st.session_state.loaded = True

                if "data2save" not in st.session_state:
                        c2.button("CSV", width="stretch", icon=":material/download:")
                else:
                        c2.download_button(
                                "CSV", st.session_state.data2save, 
                                file_name = f"ais_{time_dict['ini']:%Y-%m-%d_%H-%M}-{time_dict['fin']:%Y-%m-%d_%H-%M}.csv",
                                mime="text/csv", width="stretch", 
                                type="primary", icon=":material/download:",
                        )

                if "mmsi" not in st.session_state:
                        st.session_state.mmsi = ""
                if mmsi != st.session_state.mmsi:
                        result = validate_mmsi(str(mmsi))
                        if result.valid:
                                url = get_shipspotting_image(mmsi)
                                if url is not None and "df" in st.session_state and not st.session_state.df.empty:
                                        matches = st.session_state.df[st.session_state.df["mmsi"].astype(str) == str(mmsi)]
                                        shipname = matches["shipname"].iloc[0]

                                        st.image(url, caption=f"Vessel Photo (MMSI: {mmsi})", width="stretch")
                                        st.caption(f"Country: {result.info.get("country", "Unknown")}")
                                        destination = matches["destination"].iloc[0]
                                        st.caption(f"Ship Name: {shipname}")
                                        st.caption(f"Destination: {destination}")
                                else:
                                        st.text("No picture found")

with st.bottom:
        st.caption("© 2026 INESC TEC - MIT License | fabio.d.pacheco@inesctec.pt")

def loop():
        st.logo("https://www.inesctec.pt/INESCTECcomb_EN_mail.png")
        winlayout()

        if st.session_state.get("loaded", False) and st.session_state.get("is_live", False):
                interval_ms = st.session_state.get("refresh_interval_ms", 60000)
                refresh = st_autorefresh(interval=interval_ms, key=f"ais_refresh{interval_ms}")
                if refresh >= 0:
                        st.session_state.auto_refresh_triggered = True

        if "loaded" not in st.session_state:
                st.session_state.loaded = False
        if st.session_state.loaded:
                st.iframe(st.session_state.mapfile, height=1400)

loop()    