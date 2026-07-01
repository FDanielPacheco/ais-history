import os, math, psycopg2, folium, requests, re, uuid
import streamlit as st
import pandas as pd

from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta, time as dt_time
from zoneinfo import ZoneInfo
from folium.plugins import TimestampedGeoJson
from pathlib import Path
from vessel_validator import validate_mmsi

colorscheme = ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3","#ff7f00", "#ffff33", "#a65628", "#f781bf", "#999999"]
mapfile = f"/tmp/ais-history/{uuid.uuid4().hex}.map.html"                        
region_dict = {"lat": 41.458747, "lon": -8.842215, "width": 5.59704, "height": 5.59704}
dlat = region_dict["width"] / 111.0
dlon = region_dict["height"] / (111.0 * math.cos(math.radians(region_dict["lat"])))

def to_utc(dt):
        local_tz = ZoneInfo("Europe/Lisbon")
        return dt.replace(tzinfo=local_tz).astimezone(timezone.utc)

def mapit(df, bs, live=False):
        df = df.dropna(subset=["lat", "lon"])               
        m = folium.Map(location=[bs["lat"], bs["lon"]], zoom_start=6, tiles="CartoDB positron")
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
                                "  AND (%s IS NULL OR pos.mmsi = %s);"
                        )
                        df = pd.read_sql_query(
                                query, conn, 
                                params=(
                                        time_dict["ini"], time_dict["fin"], 
                                        mmsi, mmsi
                                )
                        )
                else:
                        query = (
                                "SELECT pos.*, v.shipname, v.callsign, v.shiptype, v.destination " 
                                "FROM ais_vessel_pos pos "
                                "LEFT JOIN ais_vessel v ON pos.mmsi = v.mmsi "
                                "WHERE pos.received_at >= %s AND pos.received_at < %s "
                                "  AND pos.lat BETWEEN %s AND %s AND pos.lon BETWEEN %s AND %s "
                                "  AND (%s IS NULL OR pos.mmsi = %s);"
                        )
                        df = pd.read_sql_query(
                                query, conn, 
                                params=(
                                        time_dict["ini"], time_dict["fin"], 
                                        region_dict["lat"] - dlat, region_dict["lat"] + dlat, 
                                        region_dict["lon"] - dlon, region_dict["lon"] + dlon,
                                        mmsi, mmsi
                                )
                        )
        else:
                query = (
                        "SELECT pos.*, v.shipname, v.callsign, v.shiptype, v.destination " 
                        "FROM ais_vessel_pos pos "
                        "LEFT JOIN ais_vessel v ON pos.mmsi = v.mmsi "
                        "WHERE pos.received_at >= %s "
                        "  AND (%s IS NULL OR pos.mmsi = %s);"
                )
                df = pd.read_sql_query(query, conn, params=(datetime.now(timezone.utc) - timedelta(minutes=30), mmsi, mmsi))
       
        conn.close()
        return df, bs 


def get_shipspotting_image(mmsi):      
        s = requests.Session()
        s.headers.update({"User-Agent": "Mozilla/5.0"})

        res1 = s.get(f"https://maritime-database.com/search?q={mmsi}")
        paths = re.findall(r'href="([^"]*/vessel/[^"]*)"', res1.text)
        if not paths: 
                return None

        res2 = s.get(f"https://maritime-database.com{paths[0]}" if not paths[0].startswith("http") else paths[0])
        img = re.search(r'src="(https://www\.myshiptracking\.com/requests/getimage-[^"]+)"', res2.text)
        return img.group(1) if img else f"https://www.myshiptracking.com/requests/getimage-normal/{mmsi}.jpg"
    
def winlayout():
        st.set_page_config(page_title="AIS-History", layout="wide")
        with st.sidebar:
                st.title("AIS-History")

                c1, c2 = st.columns(2)
                time_dict = {
                        "ini": to_utc(c1.datetime_input("From")),
                        "fin": to_utc(c2.datetime_input("To"))
                }
                st.subheader("Geographic and Time Filters")
                segfilter = st.segmented_control("Filter", ["Live", "Aguça Doura"], selection_mode="multi")

                mmsi = st.text_input("MMSI")                                

                c1, c2 = st.columns(2)
                if c1.button("Load Data", use_container_width=True):
                        with st.spinner(text="Please wait..."):
                                df, bs = fetchDB(
                                        time_dict, 
                                        region=region_dict if "Aguça Doura" in segfilter else None, 
                                        live=True if "Live" in segfilter else False,
                                        mmsi=mmsi if validate_mmsi(str(mmsi)).valid else None
                                )
                                mapit(df, bs, live=True if "Live" in segfilter else False).save(mapfile)
                                st.session_state.data2save = df.to_csv(index=False)
                                st.session_state.loaded = True

                        
                if "data2save" not in st.session_state:
                        c2.button("CSV", use_container_width=True, icon=":material/download:")
                else:
                        c2.download_button(
                                "CSV", st.session_state.data2save, 
                                file_name=f"ais_{datetime.now().date()}.csv", 
                                mime="text/csv", use_container_width=True, 
                                type="primary", icon=":material/download:",
                        )

                if "mmsi" not in st.session_state:
                        st.session_state.mmsi = ""
                if mmsi != st.session_state.mmsi:
                        result = validate_mmsi(str(mmsi))
                        if result.valid:
                                url = get_shipspotting_image(mmsi)
                                if url is not None:
                                        st.image(url, caption=f"Vessel Photo (MMSI: {mmsi})", use_container_width=True)
def loop():
        winlayout()
        if "loaded" not in st.session_state:
                if os.path.exists(mapfile):
                        st.session_state.loaded = True
                else:
                        st.session_state.loaded = False
        if st.session_state.loaded:
                st.iframe(mapfile, height=1400)
        if os.path.exists(mapfile):
                os.remove(mapfile)

loop()    
