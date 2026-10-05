import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, date

st.set_page_config(page_title="Historical Daily Temperature Ranking", page_icon="🌡️")

# --- 1. 获取全球历史及预测天气数据 ---
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

# --- 2. 实时联想搜索全球地区 ---
@st.cache_data(ttl=3600)
def fetch_location_suggestions(query, country_code):
    if not query or len(query.strip()) < 2:
        return []
    
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={query}&count=10&language=en"
    if country_code:
        url += f"&countryCode={country_code}"
        
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if "results" in data:
            suggestions = []
            for item in data["results"]:
                name = item.get("name")
                admin1 = item.get("admin1", "")  # 省/州
                country = item.get("country", "")
                lat = item.get("latitude")
                lon = item.get("longitude")
                label_parts = [p for p in [name, admin1, country] if p]
                label = ", ".join(label_parts)
                suggestions.append({"label": label, "lat": lat, "lon": lon, "name": name})
            return suggestions
    except Exception as e:
        print(f"Error fetching suggestions: {e}")
    return []

# --- 初始化 Session State ---
if "searched" not in st.session_state:
    st.session_state.searched = False
if "weather_data" not in st.session_state:
    st.session_state.weather_data = None
if "selected_lat" not in st.session_state:
    st.session_state.selected_lat = None
if "selected_lon" not in st.session_state:
    st.session_state.selected_lon = None
if "city_name" not in st.session_state:
    st.session_state.city_name = ""

# --- UI ---
st.title("🔥 Is Today An All-Time High?")
st.write("Find out if today is making history—or if you're just being dramatic! 🕶️")

# 国家映射字典 (ISO代码)
COUNTRY_MAPPING = {
    "Worldwide": None,
    "United States": "US",
    "China": "CN",
    "France": "FR",
    "United Kingdom": "GB",
    "Germany": "DE",
    "Japan": "JP",
    "Canada": "CA",
    "Australia": "AU",
}

col_c, col_q, col_u = st.columns([1.5, 2, 1])

with col_c:
    selected_country_name = st.selectbox(
        "Country Filter",
        options=list(COUNTRY_MAPPING.keys()),
        index=0,
        on_change=lambda: st.session_state.update(searched=False),
    )
    selected_country_code = COUNTRY_MAPPING[selected_country_name]

with col_q:
    search_query = st.text_input(
        "Search City (Type keyword, e.g. 'West', 'Paris')",
        value="Arcadia",
        placeholder="Type to search...",
        on_change=lambda: st.session_state.update(searched=False),
    )

with col_u:
    temp_unit = st.radio("Unit:", ("°F", "°C"), on_change=lambda: st.session_state.update(searched=False))

# 根据输入和国家过滤获取联想结果
suggestions = fetch_location_suggestions(search_query, selected_country_code)

if suggestions:
    selected_option = st.selectbox(
        "Select specific region from search results:",
        options=suggestions,
        format_func=lambda x: x["label"],
        on_change=lambda: st.session_state.update(searched=False),
    )
    st.session_state.selected_lat = selected_option["lat"]
    st.session_state.selected_lon = selected_option["lon"]
    st.session_state.city_name = selected_option["name"]
else:
    st.warning("No matching regions found. Try typing at least 2 characters or changing the country filter.")
    st.session_state.selected_lat = None
    st.session_state.selected_lon = None

min_allowed_date = date(1950, 1, 1)
max_allowed_date = datetime.today().date()

selected_date = st.date_input(
    "Select Date", 
    value=max_allowed_date,
    min_value=min_allowed_date,
    max_value=max_allowed_date,
    on_change=lambda: st.session_state.update(searched=False)
)

if st.button("Check Ranking"):
    if st.session_state.selected_lat is not None and st.session_state.selected_lon is not None:
        with st.spinner(f"Fetching 70+ years of weather data for {st.session_state.city_name}..."):
            weather_data = fetch_all_weather_data(st.session_state.selected_lat, st.session_state.selected_lon)

            if weather_data and "time" in weather_data:
                st.session_state.weather_data = weather_data
                st.session_state.searched = True
    else:
        st.error("Please select a valid location from the search suggestions first.")

# --- 渲染逻辑 ---
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

            # --- 多维度统计计算 ---
            target_month_name = selected_date.strftime('%B')
            
            # 1. 当月排名 (Month & Year)
            df_month = df[(df["Date"].dt.year == target_year) & (df["Date"].dt.month == target_month)].copy()
            df_month["Rank"] = df_month["MaxTemp"].rank(method="min", ascending=False).astype(int)
            month_rank = df_month[df_month["Date"].dt.date == selected_date]["Rank"].iloc[0]
            
            # 2. 当年排名 (Year)
            df_year = df[df["Date"].dt.year == target_year].copy()
            df_year["Rank"] = df_year["MaxTemp"].rank(method="min", ascending=False).astype(int)
            year_rank = df_year[df_year["Date"].dt.date == selected_date]["Rank"].iloc[0]
            
            # 3. 历史总排名 (All-time ever)
            df_all = df.copy()
            df_all["Rank"] = df_all["MaxTemp"].rank(method="min", ascending=False).astype(int)
            all_time_rank = df_all[df_all["Date"].dt.date == selected_date]["Rank"].iloc[0]
            total_days_ever = len(df_all)
            top_percent = (all_time_rank / total_days_ever) * 100
            
            percent_str = "< 0.01%" if top_percent < 0.01 else f"{top_percent:.2f}%"

            # 润色后的多维度统计文案
            st.markdown(f"""
            **More Heat Stats for this date:**
            - 📅 **#{month_rank} hottest day** in {target_month_name} {target_year}.
            - 📆 **#{year_rank} hottest day** of the entire year in {target_year}.
            - 🌎 **Top {percent_str} hottest day of all time** in {city_name} (Ranked #{all_time_rank:,} out of {total_days_ever:,} total recorded days).
            """)

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
