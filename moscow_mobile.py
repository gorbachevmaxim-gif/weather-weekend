import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from itertools import groupby, count

# --- НАСТРОЙКИ ---
st.set_page_config(page_title="Анализ выходных ЦФО", layout="wide")

st.title("Поиск идеальных выходных в ЦФО")
st.markdown("""
**Два уровня анализа:**
1. **Резюме:** Сверху показаны города, где ожидается погода без осадков (или они закончатся до 04:00 утра).
2. **Детали:** Снизу можно посмотреть подробный прогноз по любому городу из списка.
""")

# --- СПИСОК ГОРОДОВ ---
CITIES = {
    "Москва": (55.75, 37.61),
    "Истра": (55.91, 36.85),
    "Кубинка": (55.59, 36.72),
    "Можайск": (55.50, 36.03),
    "Волоколамск": (56.04, 35.96),
    "Солнечногорск": (56.18, 36.98),
    "Завидово": (56.52, 36.52),
    "Дубна": (56.73, 37.16),
    "Яхрома": (56.29, 37.48),
    "Сергиев Посад": (56.30, 38.13),
    "Александров": (56.39, 38.71),
    "Павловский Посад": (55.78, 38.65),
    "Воскресенск": (55.32, 38.68),
    "Коломна": (55.08, 38.78),
    "Ступино": (54.89, 38.08),
    "Серпухов": (54.91, 37.41),
    "Калуга": (54.51, 36.26),
    "Обнинск": (55.11, 36.61),
    "Верея": (55.34, 36.18),
    "Жуковский": (55.60, 38.12),
    "Рязань": (54.62, 39.73),
    "Одинцово": (55.67, 37.28),
    "Зеленоград": (55.99, 37.21),
    "Подольск": (55.43, 37.55),
    "Тула": (54.19, 37.61)
}

# --- ФУНКЦИИ ---
def get_weekend_dates():
    today = datetime.now().date()
    if today.weekday() == 5:
        sat1 = today
    else:
        days_until_sat = (5 - today.weekday() + 7) % 7
        sat1 = today + timedelta(days=days_until_sat)
        
    sun1 = sat1 + timedelta(days=1)
    sat2 = sat1 + timedelta(days=7)
    sun2 = sat2 + timedelta(days=1)
    
    return [sat1, sun1, sat2, sun2]

def format_rain_hours(hours_list):
    if not hours_list: return None
    groups = []
    for _, g in groupby(hours_list, lambda x, c=count(): x - next(c)):
        groups.append(list(g))
    parts = []
    for g in groups:
        start, end = g[0], g[-1]
        if start == end: parts.append(f"{start:02d}:00")
        else: parts.append(f"{start:02d}:00–{end+1:02d}:00")
    return ", ".join(parts)

def deg_to_compass(num):
    # Стрелки оставлены намеренно (это данные)
    if num is None: return ""
    val = int((num / 22.5) + 0.5)
    arr = ["С ⬇️", "СВ ↙️", "В ⬅️", "ЮВ ↖️", "Ю ⬆️", "ЮЗ ↗️", "З ➡️", "СЗ ↘️"]
    return arr[(val % 8)]

def format_sun_time(seconds):
    if seconds <= 0: return "0 мин"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) / 60)
    if hours > 0:
        return f"{hours}ч {minutes}мин"
    return f"{minutes}мин"

@st.cache_data(ttl=3600)
def analyze_city_basic(name, lat, lon, target_dates):
    url = "https://api.open-meteo.com/v1/forecast"
    start_str = target_dates[0].strftime("%Y-%m-%d")
    end_str = target_dates[-1].strftime("%Y-%m-%d")
    
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start_str, "end_date": end_str,
        "hourly": ["precipitation", "temperature_2m", "wind_speed_10m", "apparent_temperature", "wind_direction_10m", "sunshine_duration"],
        "timezone": "Europe/Moscow"
    }
    
    try:
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        
        hourly = data.get("hourly", {})
        h_precip = hourly.get("precipitation", [])
        h_temp = hourly.get("temperature_2m", [])
        h_feels = hourly.get("apparent_temperature", [])
        h_wind = hourly.get("wind_speed_10m", [])
        h_wind_dir = hourly.get("wind_direction_10m", [])
        h_sun = hourly.get("sunshine_duration", [])
        
        final_result = {}
        start_date_obj = target_dates[0]
        
        for i, target_date in enumerate(target_dates):
            day_offset = (target_date - start_date_obj).days
            s_idx = day_offset * 24
            e_idx = s_idx + 24
            
            if len(h_precip) < e_idx: continue
            
            # Осадки (с 04:00)
            p_slice = h_precip[s_idx+4 : e_idx]
            total_rain = sum(x for x in p_slice if x)
            wet_hours = [h+4 for h, x in enumerate(p_slice) if x and x > 0.1]
            
            # Активные часы (09-18)
            act_slice = slice(s_idx+9, s_idx+19)
            
            # Солнце (09-18)
            sun_val = sum(x for x in h_sun[act_slice] if x)
            
            # Температура
            temps = h_temp[act_slice]
            feels = h_feels[act_slice]
            
            t_min = min(temps) if temps else 0
            t_max = max(temps) if temps else 0
            f_min = min(feels) if feels else 0
            f_max = max(feels) if feels else 0
            
            # Ветер
            winds = h_wind[act_slice]
            wd = h_wind_dir[act_slice]
            w_min = min(winds) if winds else 0
            w_max = max(winds) if winds else 0
            w_d_str = ""
            if winds:
                w_d_str = deg_to_compass(wd[winds.index(w_max)])
                
            key = target_date.strftime("%Y-%m-%d")
            final_result[key] = {
                "date_obj": target_date,
                "day_name": "Суббота" if target_date.weekday() == 5 else "Воскресенье",
                "is_dry": total_rain <= 0.2,
                "precip_sum": total_rain,
                "rain_hours": format_rain_hours(wet_hours),
                "temp_range": f"{t_min:.0f}..{t_max:.0f}",
                "feels_range": f"{f_min:.0f}..{f_max:.0f}",
                "wind_range": f"{w_min:.0f}..{w_max:.0f}",
                "wind_max": w_max,
                "wind_dir": w_d_str,
                "sun_seconds": sun_val, 
                "sun_str": format_sun_time(sun_val)
            }
            
        return final_result
    except Exception: return None

@st.cache_data(ttl=3600)
def get_accuracy_data(lat, lon, target_dates):
    url = "https://api.open-meteo.com/v1/forecast"
    start_str = target_dates[0].strftime("%Y-%m-%d")
    end_str = target_dates[-1].strftime("%Y-%m-%d")
    try:
        r = requests.get(url, params={
            "latitude": lat, "longitude": lon,
            "start_date": start_str, "end_date": end_str,
            "daily": "temperature_2m_max",
            "models": "ecmwf_ifs04,gfs_seamless,icon_seamless,gem_global",
            "timezone": "Europe/Moscow"
        })
        data_list = r.json()
        if isinstance(data_list, dict): data_list = [data_list]
        accuracy_map = {}
        req_start = target_dates[0]
        for target_date in target_dates:
            day_offset = (target_date - req_start).days
            temps = []
            for model in data_list:
                if "daily" in model:
                    t_list = model["daily"]["temperature_2m_max"]
                    if len(t_list) > day_offset: temps.append(t_list[day_offset])
            spread = max(temps) - min(temps) if temps else 0
            if spread < 1.5: label, color = "Высокая", "green"
            elif spread < 3.5: label, color = "Средняя", "orange"
            else: label, color = "Низкая", "red"
            accuracy_map[target_date.strftime("%Y-%m-%d")] = {"label": label, "color": color}
        return accuracy_map
    except: return {}

# --- ЛОГИКА ---
dates = get_weekend_dates()
date_str_1 = f"{dates[0].strftime('%d.%m')} - {dates[1].strftime('%d.%m')}"
date_str_2 = f"{dates[2].strftime('%d.%m')} - {dates[3].strftime('%d.%m')}"

st.subheader(f"Даты анализа: {date_str_1} (ближайшие) и {date_str_2} (через неделю)")

all_data_cache = {} 
w1_full, w1_sat, w1_sun = [], [], []
w2_full, w2_sat, w2_sun = [], [], []

sun_ranking_sat = []
sun_ranking_sun = []

progress_bar = st.progress(0)
status_text = st.empty()
sorted_cities = sorted(list(CITIES.keys()))

for i, city in enumerate(sorted_cities):
    coords = CITIES[city]
    status_text.text(f"Анализ погоды: {city}...")
    progress_bar.progress((i + 1) / len(sorted_cities))
    
    res = analyze_city_basic(city, coords[0], coords[1], dates)
    
    if res:
        all_data_cache[city] = res
        
        k1 = dates[0].strftime("%Y-%m-%d")
        k2 = dates[1].strftime("%Y-%m-%d")
        k3 = dates[2].strftime("%Y-%m-%d")
        k4 = dates[3].strftime("%Y-%m-%d")
        
        if k1 in res and k2 in res:
            s1, s2 = res[k1]["is_dry"], res[k2]["is_dry"]
            if s1 and s2: w1_full.append(city)
            elif s1: w1_sat.append(city)
            elif s2: w1_sun.append(city)
            
            # Солнце
            sun_ranking_sat.append((city, res[k1]["sun_seconds"], res[k1]["sun_str"]))
            sun_ranking_sun.append((city, res[k2]["sun_seconds"], res[k2]["sun_str"]))

        if k3 in res and k4 in res:
            s3, s4 = res[k3]["is_dry"], res[k4]["is_dry"]
            if s3 and s4: w2_full.append(city)
            elif s3: w2_sat.append(city)
            elif s4: w2_sun.append(city)

progress_bar.empty()
status_text.empty()

# --- БЛОК 1: ОСАДКИ ---
st.info(f"Сводка городов без осадков: **Ближайшие выходные ({date_str_1})**")
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("**Весь уикенд**")
    if w1_full: st.markdown(", ".join([f"**{c}**" for c in w1_full]))
    else: st.write("Нет городов.")
with c2:
    st.markdown("**Только Суббота**")
    if w1_sat: st.write(", ".join(w1_sat))
    else: st.caption("Пусто")
with c3:
    st.markdown("**Только Воскресенье**")
    if w1_sun: st.write(", ".join(w1_sun))
    else: st.caption("Пусто")

# --- БЛОК 2: СОЛНЦЕ (КОМПАКТНО ДЛЯ МОБИЛЬНЫХ) ---
st.markdown("---")
st.info("Самые солнечные города (09:00–18:00)")

top_sat = sorted(sun_ranking_sat, key=lambda x: x[1], reverse=True)[:5]
top_sun = sorted(sun_ranking_sun, key=lambda x: x[1], reverse=True)[:5]

# Используем компактный вывод: одна строка для всех городов
if top_sat:
    sat_str = "  |  ".join([f"**{c}**: {t}" for c, _, t in top_sat])
    st.markdown(f"**Суббота:** {sat_str}")
else:
    st.caption("Суббота: Нет данных")

st.write("") # Отступ

if top_sun:
    sun_str = "  |  ".join([f"**{c}**: {t}" for c, _, t in top_sun])
    st.markdown(f"**Воскресенье:** {sun_str}")
else:
    st.caption("Воскресенье: Нет данных")

st.markdown("---")

# --- БЛОК 3: ОСАДКИ ЧЕРЕЗ НЕДЕЛЮ ---
st.info(f"Сводка городов без осадков: **Через неделю ({date_str_2})**")
c4, c5, c6 = st.columns(3)
with c4:
    st.markdown("**Весь уикенд**")
    if w2_full: st.markdown(", ".join([f"**{c}**" for c in w2_full]))
    else: st.write("Нет городов.")
with c5:
    st.markdown("**Только Суббота**")
    if w2_sat: st.write(", ".join(w2_sat))
    else: st.caption("Пусто")
with c6:
    st.markdown("**Только Воскресенье**")
    if w2_sun: st.write(", ".join(w2_sun))
    else: st.caption("Пусто")

st.markdown("---")

# --- БЛОК 4: ДЕТАЛИ ---
st.header("Подробный прогноз")
selected_city = st.selectbox("Выберите город:", sorted_cities)

if selected_city:
    city_data = all_data_cache.get(selected_city)
    coords = CITIES[selected_city]
    acc_data = get_accuracy_data(coords[0], coords[1], dates)
    
    if city_data:
        tab1, tab2 = st.tabs(["Ближайшие выходные", "Через неделю"])
        
        def draw_weekend_tab(tab, day1_date, day2_date):
            k1 = day1_date.strftime("%Y-%m-%d")
            k2 = day2_date.strftime("%Y-%m-%d")
            with tab:
                for key in [k1, k2]:
                    if key not in city_data: continue
                    d = city_data[key]
                    acc = acc_data.get(key, {"label": "Нет данных", "color": "gray"})
                    
                    status_text = "Без осадков (или до 04:00)" if d["is_dry"] else "Ожидаются осадки"
                    status_color = "green" if d["is_dry"] else "red"
                    
                    with st.container():
                        st.markdown(f"### {d['day_name']}, {d['date_obj'].strftime('%d.%m')}")
                        m1, m2, m3 = st.columns(3)
                        m1.metric("t° (09-18ч)", f"{d['temp_range']}°", f"Ощущ: {d['feels_range']}°", delta_color="off")
                        m2.metric("Ветер", f"{d['wind_range']} км/ч", f"Макс: {d['wind_max']} ({d['wind_dir']})", delta_color="inverse")
                        m3.metric("Солнце (09-18ч)", d['sun_str'])
                        
                        st.markdown(f"**Статус:** :{status_color}[{status_text}]")
                        if not d["is_dry"]:
                            st.error(f"Сумма: **{d['precip_sum']:.1f} мм**")
                            if d['rain_hours']:
                                st.write(f"**Время:** {d['rain_hours']}")
                            else:
                                st.caption("Незначительные осадки")
                        
                        st.caption(f"Точность прогноза: :{acc['color']}[**{acc['label']}**]")
                        st.markdown("---")

        draw_weekend_tab(tab1, dates[0], dates[1])
        draw_weekend_tab(tab2, dates[2], dates[3])
    else:
        st.error("Ошибка отображения данных.")