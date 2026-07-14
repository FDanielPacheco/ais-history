import math, os, psycopg2, sqlite3, warnings, time
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

warnings.filterwarnings("ignore", category=UserWarning)
load_dotenv()

region_dict = {"lat": 41.458747, "lon": -8.842215, "width": 5.59704, "height": 5.59704}
dlat = region_dict["width"] / 111.0
dlon = region_dict["height"] / (111.0 * math.cos(math.radians(region_dict["lat"])))

def create_database():
    with sqlite3.connect("ais_notifications.db") as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS vessel_alerts(datetime, mmsi)")

def fetchGlobalDB(lookback=10):
    time_threshold = datetime.now(timezone.utc) - timedelta(minutes=lookback)

    with psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=5432,
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    ) as conn:
        query = """
            SELECT pos.mmsi, pos.received_at, pos.lat, pos.lon
            FROM ais_vessel_pos pos
            WHERE pos.received_at >= %s
            AND pos.lat BETWEEN %s AND %s
            AND pos.lon BETWEEN %s AND %s;
        """
        params = (
            time_threshold,       
            region_dict["lat"] - dlat,
            region_dict["lat"] + dlat,
            region_dict["lon"] - dlon,
            region_dict["lon"] + dlon
        )
        return pd.read_sql_query(query, conn, params=params)

def fetchLocalDB(lookback=1):
    time_threshold_str = (datetime.now(timezone.utc) - timedelta(hours=lookback)).strftime("%Y-%m-%d %H:%M:%S")
    query = "SELECT mmsi, datetime FROM vessel_alerts WHERE datetime >= ?;"
    
    with sqlite3.connect("ais_notifications.db", timeout=30) as conn:
        return pd.read_sql_query(query, conn, params=[time_threshold_str])

def saveLocalDB(global_df, local_df):
    if global_df.empty:
        return
    
    recent_local_mmsis = set(local_df['mmsi'])
    latest_global_positions = global_df.sort_values('received_at').groupby('mmsi').first().reset_index()

    with sqlite3.connect("ais_notifications.db", timeout=30) as conn:
        for _, row in latest_global_positions.iterrows():
            vessel_mmsi = int(row['mmsi'])
            timestamp_str = row['received_at'].strftime('%Y-%m-%d %H:%M:%S')

            if vessel_mmsi not in recent_local_mmsis:
                query = "INSERT INTO vessel_alerts (mmsi, datetime) VALUES (?, ?);"
                conn.execute(query, (vessel_mmsi, timestamp_str))
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Vessel {vessel_mmsi} entered region.")
    
if __name__ == "__main__":
    if not os.path.exists("ais_notifications.db"):
        create_database()

    while True:
        try:
            saveLocalDB(fetchGlobalDB(10), fetchLocalDB(1))
        except Exception as error:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {error}")
    
        time.sleep(600)