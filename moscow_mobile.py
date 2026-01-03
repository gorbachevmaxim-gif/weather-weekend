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
1. **Резюме:** Сверху показаны города, где ожидается **погода без осадков** (или они закончатся до 04:00 утра).
2. **Детали:** Снизу можно посмотреть подробный прогноз по **любому** городу из списка.
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
    """Возвращает список из 4 дат: [Сб1, Вс1, Сб2, Вс2]"""
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
    if num is None: return ""
    val = int((num / 22.5) + 0.5)
    arr = ["С ⬇️", "СВ ↙️", "В ⬅️", "ЮВ ↖️", "Ю ⬆️", "ЮЗ ↗️", "З ➡️", "СЗ ↘️"]
    return arr[(val % 8)]

@st.cache_data(ttl=3600)
def analyze_city_basic(name, lat, lon, target_dates):
    url = "https://api.open-meteo.com/v1/forecast"
    start_str = target_dates[0].strftime("%Y-%m-%d")
    end_str = target_dates[-1].strftime("%Y-%m-%d")
    
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start_str, "end_date": end_str,
        "hourly": ["precipitation", "temperature_2m", "wind_speed_10m", "apparent_temperature", "wind_direction_10m"],
        "daily": ["sunshine_duration"],
        "timezone": "Europe/Moscow"
    }
    
    try:
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        
        hourly = data.get("hourly", {})
        daily = data.get("daily", {})
        
        h_precip = hourly.get("precipitation", [])
        h_temp = hourly.get("temperature_2m", [])
        h_feels = hourly.get("apparent_temperature", [])
        h_wind = hourly.get("wind_speed_10m", [])
        h_wind_dir = hourly.get("wind_direction_10m", [])
        d_sun = daily.get("sunshine_duration", [])
        
        result = {}
        req_start = target_dates[0]
        
        for i, target_date in enumerate(target_dates):
            day_offset = (target_date - req_start).days
            start_h = day_offset * 24
            end_h = start_h + 24
            
            if len(h_precip) < end_h: continue
            
            # 1. Осадки (с 04:00)
            active_precip = h_precip[start_h+4 : end_h]
            total_rain = sum(p for p in active_precip if p is not None)
            wet_hours = [h+4 for h, p in enumerate(active_precip) if p and p > 0.1]
            
            # 2. Активные часы (09-18)
            range_slice = slice(start_h+9, start_h+19)
            
            t_slice = h_temp[range_slice]
            f_slice = h_feels[range_slice]
            w_slice = h_wind[range_slice]
            d_slice = h_wind_dir[range_slice]
            
            t_min = min(t_slice) if t_slice else 0
            t_max = max(t_slice) if t_slice else 0
            f_min = min(f_slice) if f_slice else 0
            f_max = max(f_slice) if f_slice else 0
            w_min = min(w_slice) if w_slice else 0
            w_max = max(w_slice) if w_slice else 0
            
            w_dir_str = ""
            if w_slice and d_slice:
                max_idx = w_slice.index(w_max)
                w_dir_str = deg_to_compass(d_slice[max_idx])
            
            # 3. Солнечные часы
            sun_seconds = (d_sun[day_offset]) if len(d_sun) > day_offset else 0
            s_hours = int(sun_seconds // 3600)
            s_minutes = int((sun_seconds % 3600) / 60)
            sun_str = f"{s_hours} ч {s_minutes} мин"
            
            key = target_date.strftime("%Y-%m-%d")
            
            result[key] = {
                "date_obj": target_date,
                "day_name": "Суббота" if target_date.weekday() == 5 else "Воскресенье",
                "is_dry": total_rain <= 0.2,
                "precip_sum": total_rain,
                "rain_hours": format_rain_hours(wet_hours),
                "temp_range": f"{t_min:.0f}..{t_max:.0f}",
                "feels_range": f"{f_min:.0f}..{f_max:.0f}",
                "wind_range": f"{w_min:.0f}..{w_max:.0f}",
                "wind_max": w_max,
                "wind_dir": w_dir_str,
                "sun_str": sun_str
            }
            
        return result
    except Exception: return None

@st.cache_data(ttl=3600)
def get_accuracy_data(lat, lon, target_dates):
    url = "https://api.open-meteo.com/v1/forecast"
    start_str = target_dates[0].strftime("%Y-%m-%d")
    end_str = target_dates[-1].strftime("%Y-%m-%d")
    
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start_str, "end_date": end_str,
        "daily": "temperature_2m_max",
        "models": "ecmwf_ifs04,gfs_seamless,icon_seamless,gem_global",
        "timezone": "Europe/Moscow"
    }
    
    try:
        r = requests.get(url, params=params)
        data_list = r.json()
        if isinstance(data_list, dict): data_list = [data_list]
        
        accuracy_map = {}
        req_start = target_dates[0]
        
        for target_date in target_dates:
            day_offset = (target_date - req_start).days
            temps = []
            for model in data_list:
                if "daily" in model and "temperature_2m_max" in model["daily"]:
                    t_list = model["daily"]["temperature_2m_max"]
                    if len(t_list) > day_offset:
                        temps.append(t_list[day_offset])
            
            spread = max(temps) - min(temps) if temps else 0
            if spread < 1.5: label, color = "Высокая", "green"
            elif spread < 3.5: label, color = "Средняя", "orange"
            else: label, color = "Низкая", "red"
            
            key = target_date.strftime("%Y-%m-%d")
            accuracy_map[key] = {"label": label, "color": color}
            
        return accuracy_map
    except Exception: return {}

# --- ЛОГИКА ---
dates = get_weekend_dates()
date_str_1 = f"{dates[0].strftime('%d.%m')} - {dates[1].strftime('%d.%m')}"
date_str_2 = f"{dates[2].strftime('%d.%m')} - {dates[3].strftime('%d.%m')}"

st.subheader(f"Даты анализа: {date_str_1} (ближайшие) и {date_str_2} (через неделю)")

all_data_cache = {} 
w1_full, w1_sat, w1_sun = [], [], []
w2_full, w2_sat, w2_sun = [], [], []

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
            
        if k3 in res and k4 in res:
            s3, s4 = res[k3]["is_dry"], res[k4]["is_dry"]
            if s3 and s4: w2_full.append(city)
            elif s3: w2_sat.append(city)
            elif s4: w2_sun.append(city)

progress_bar.empty()
status_text.empty()

# --- ФУНКЦИЯ ОТОБРАЖЕНИЯ СПИСКОВ ---
def display_summary_list(full, sat, sun):
    st.markdown("**Весь уикенд (Сб + Вс)**")
    if full:
        st.success(", ".join([f"**{c}**" for c in full]))
    else:
        st.caption("Нет полностью сухих городов.")
    
    st.write("")
    
    st.markdown("**Только Суббота**")
    if sat:
        st.markdown(", ".join(sat))
    elif not full:
        st.caption("Нет подходящих городов")
    else:
        st.caption("Остальные в списке выше")
    
    st.write("")

    st.markdown("**Только Воскресенье**")
    if sun:
        st.markdown(", ".join(sun))
    elif not full:
        st.caption("Нет подходящих городов")
    else:
        st.caption("Остальные в списке выше")

# --- ВЫВОД РЕЗЮМЕ ---
week_tabs = st.tabs([f"Ближайшие ({date_str_1})", f"Через неделю ({date_str_2})"])

with week_tabs[0]:
    display_summary_list(w1_full, w1_sat, w1_sun)

with week_tabs[1]:
    display_summary_list(w2_full, w2_sat, w2_sun)

st.markdown("---")

# --- ПОДРОБНЫЙ ПРОСМОТР (ВЕРТИКАЛЬНО) ---
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
                # ВЕРТИКАЛЬНОЕ РАСПОЛОЖЕНИЕ КАРТОЧЕК
                for key in [k1, k2]:
                    if key not in city_data:
                        st.error("Нет данных")
                        continue
                        
                    d = city_data[key]
                    acc = acc_data.get(key, {"label": "Нет данных", "color": "gray"})
                    
                    status_text = "Без осадков (или до 04:00)" if d["is_dry"] else "Ожидаются осадки"
                    status_color = "green" if d["is_dry"] else "red"
                    
                    with st.container(border=True):
                        st.markdown(f"### {d['day_name']}, {d['date_obj'].strftime('%d.%m')}")
                        
                        m1, m2, m3 = st.columns(3)
                        m1.metric("t° (09-18ч)", f"{d['temp_range']}°C", f"Ощущ: {d['feels_range']}°", delta_color="off")
                        m2.metric("Ветер", f"{d['wind_range']} км/ч", f"Макс: {d['wind_max']} ({d['wind_dir']})", delta_color="inverse")
                        m3.metric("Солнце", d['sun_str'])
                        
                        st.markdown(f"**Статус:** :{status_color}[{status_text}]")
                        if not d["is_dry"]:
                            st.error(f"Сумма: **{d['precip_sum']:.1f} мм**")
                            if d['rain_hours']:
                                st.write(f"**Время:** {d['rain_hours']}")
                            else:
                                st.caption("Незначительные осадки")
                        
                        st.caption(f"Точность прогноза: :{acc['color']}[**{acc['label']}**]")

        draw_weekend_tab(tab1, dates[0], dates[1])
        draw_weekend_tab(tab2, dates[2], dates[3])
    else:
        st.error("Ошибка отображения данных.")