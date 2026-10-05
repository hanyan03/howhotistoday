import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, date

st.set_page_config(page_title="Historical Daily Temperature Ranking", page_icon="🌡️")

@st.cache_data(ttl=86400)
def fetch_all_weather_data(lat, lon):
    today = datetime.today().date()
    archive_end = today - timedelta(days=7)
    forecast_start = archive_end + timedelta(days=1)
    
    archive_url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}&"
        f"start_date=1950-01-01&end_date={archive_end.strftime('%Y-%m-%d')}&"
        f"daily=temperature_2m_max&timezone=auto&temperature_unit=fahrenheit"
    )
    
    forecast_url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"start_date={forecast_start.strftime('%Y-%m-%d')}&end_date={today.strftime('%Y-%m-%d')}&"
        f"daily=temperature_2m_max&timezone=auto&temperature_unit=fahrenheit"
    )
    
    try:
        archive_res = requests.get(archive_url, timeout=15).json()
        forecast_res = requests.get(forecast_url, timeout=15).json()
        
        dates = []
        temps = []
        
        if "daily" in archive_res:
            dates.extend(archive_res["daily"]["time"])
            temps.extend(archive_res["daily"]["temperature_2m_max"])
            
        if "daily" in forecast_res:
            dates.extend(forecast_res["daily"]["time"])
            temps.extend(forecast_res["daily"]["temperature_2m_max"])
            
        return {"time": dates, "temps": temps}
    except Exception as e:
        st.error(f"Network error or API timeout: {e}")
        return None

@st.cache_data(ttl=86400)
def fetch_coordinates(location):
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=en"
    try:
        res = requests.get(geo_url, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        st.error(f"Failed to fetch location coordinates: {e}")
        return None

# --- 初始化 Session State ---
if "searched" not in st.session_state:
    st.session_state.searched = False
if "weather_data" not in st.session_state:
    st.session_state.weather_data = None
if "city_name" not in st.session_state:
    st.session_state.city_name = ""

# --- UI ---
st.title("🔥 Is Today An All-Time High?")
st.write("Select a city and a date to see how its temperature ranks historically for that specific day of the year!")

col1, col2 = st.columns([3, 1])

with col1:
    CITIES = [
        "Arcadia, CA", "Los Angeles, CA", "San Francisco, CA", "New York, NY", 
        "Chicago, IL", "Houston, TX", "Phoenix, AZ", "Philadelphia, PA", 
        "San Antonio, TX", "San Diego, CA", "Dallas, TX", "San Jose, CA", 
        "Austin, TX", "Jacksonville, FL", "Seattle, WA", "Denver, CO", 
        "Washington, DC", "Boston, MA", "Las Vegas, NV", "Miami, FL"
    ]
    # 当用户改变城市时，重置搜索状态
    location = st.selectbox("Select a city (type to search)", CITIES, on_change=lambda: st.session_state.update(searched=False))

with col2:
    # 只要单位改变，Streamlit 就会自动重新运行下方的渲染逻辑，实现实时切换
    temp_unit = st.radio("Temperature Unit:", ("°F", "°C"))

min_allowed_date = date(1950, 1, 1)
max_allowed_date = datetime.today().date()

# 当用户改变日期时，同样重置搜索状态
selected_date = st.date_input(
    "Select Date", 
    value=max_allowed_date,
    min_value=min_allowed_date,
    max_value=max_allowed_date,
    on_change=lambda: st.session_state.update(searched=False)
)

if st.button("Check Ranking"):
    with st.spinner(f"Fetching 70+ years of data for {location}... (Only takes a few seconds the first time)"):
        geo_res = fetch_coordinates(location)
        
        if not geo_res or not geo_res.get("results"):
            st.error(f"Location not found: {location}.")
        else:
            lat = geo_res["results"][0]["latitude"]
            lon = geo_res["results"][0]["longitude"]
            st.session_state.city_name = geo_res["results"][0].get("name", location.split(",")[0])
            
            weather_data = fetch_all_weather_data(lat, lon)
            
            if weather_data and "time" in weather_data:
                # 将获取到的原始数据存入 session_state
                st.session_state.weather_data = weather_data
                st.session_state.searched = True

# --- 渲染逻辑 (与 Check Ranking 按钮解耦) ---
# 只要用户搜索过了，并且缓存里有数据，就会根据当前的单位实时渲染
if st.session_state.searched and st.session_state.weather_data:
    dates = st.session_state.weather_data["time"]
    temps = st.session_state.weather_data["temps"]
    city_name = st.session_state.city_name
    
    df = pd.DataFrame({"Date": pd.to_datetime(dates, format="%Y-%m-%d"), "MaxTemp": temps})
    df = df.dropna() 
    
    # 实时温度转换计算
    if temp_unit == "°C":
        df["MaxTemp"] = (df["MaxTemp"] - 32) * 5.0 / 9.0
    
    target_month = selected_date.month
    target_day = selected_date.day
    
    df_day = df[(df["Date"].dt.month == target_month) & (df["Date"].dt.day == target_day)]
    
    if df_day.empty:
        st.error("No historical data available for this date.")
    else:
        df_day_sorted = df_day.sort_values(by="MaxTemp", ascending=False).reset_index(drop=True)
        df_day_sorted["Rank"] = df_day_sorted["MaxTemp"].rank(method="min", ascending=False).astype(int)
        
        target_year = selected_date.year
        target_record = df_day_sorted[df_day_sorted["Date"].dt.year == target_year]
        
        date_str = selected_date.strftime('%B %d, %Y')
        short_date_str = selected_date.strftime('%b %d')
        
        if target_record.empty:
            st.warning(f"Data for {date_str} is missing. Here are the historical rankings for {short_date_str}:")
            st.dataframe(df_day_sorted.head(10).assign(Date=lambda x: x["Date"].dt.date))
        else:
            rank = target_record.iloc[0]["Rank"]
            temp = target_record.iloc[0]["MaxTemp"]
            total_years = len(df_day_sorted)
            
            st.success(f"### On {date_str}, the maximum temperature in {city_name} was {temp:.1f}{temp_unit}")
            st.write(f"🎉 This day ranks as the **#{rank} hottest** {short_date_str} since 1950 (out of {total_years} years of data).")
            
            st.markdown("---")
            st.subheader(f"🔥 Top 10 Hottest {short_date_str} on Record for {city_name}")
            
            display_df = df_day_sorted.head(10).copy()
            display_df["Date"] = display_df["Date"].dt.date
            display_df = display_df.rename(columns={
                "Date": "Date", 
                "MaxTemp": f"Max Temp ({temp_unit})", 
                "Rank": "Historical Rank"
            })
            
            display_df[f"Max Temp ({temp_unit})"] = display_df[f"Max Temp ({temp_unit})"].map(lambda x: f"{x:.1f}")
            
            st.dataframe(display_df, hide_index=True, use_container_width=True)