import streamlit as st
import pandas as pd
import joblib
import requests
import plotly.express as px
from datetime import datetime, timedelta
from supabase import create_client, Client
from PIL import Image
import io
import base64

# ==========================================
# 1. ページ設定
# ==========================================
st.set_page_config(page_title="上天草アジ予測AI & 釣果SNS", layout="wide")

# ==========================================
# 🌟 データベース接続
# ==========================================
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        return None

supabase = init_connection()

# AIモデルの読み込み
@st.cache_resource
def load_model():
    return joblib.load('aji_model.pkl')

try:
    model = load_model()
except FileNotFoundError:
    st.error("AIモデルが見つかりません。先に train_model.py を実行してください。")
    st.stop()

# 釣り場データ
spots = {
    '樋島': {'lat': 32.37974, 'lon': 130.41995},
    '松島': {'lat': 32.51800, 'lon': 130.43800},
    '御所浦島': {'lat': 32.33811, 'lon': 130.33787},
    '大道港': {'lat': 32.38905, 'lon': 130.37089},
    '姫戸港': {'lat': 32.43824, 'lon': 130.41122},
    '永目港': {'lat': 32.45021, 'lon': 130.42099}
}

if 'selected_spot' not in st.session_state:
    st.session_state.selected_spot = '松島'

# ==========================================
# 関数群
# ==========================================
def get_tide_info(date_obj):
    base_date = datetime(2026, 4, 15).date()
    diff_days = (date_obj - base_date).days
    if diff_days < 0: diff_days = (29.53 - (abs(diff_days) % 29.53)) % 29.53
    moon_age = diff_days % 29.53
    
    if moon_age < 2.5 or (13.5 <= moon_age < 17.5) or moon_age >= 28.0: return "大潮 🌊", 1.5
    elif (2.5 <= moon_age < 6.5) or (10.5 <= moon_age < 13.5) or (17.5 <= moon_age < 21.5) or (25.5 <= moon_age < 28.0): return "中潮 〰️", 1.0
    elif (6.5 <= moon_age < 9.5) or (21.5 <= moon_age < 24.5): return "小潮 💧", 0.5
    elif (9.5 <= moon_age < 10.5) or (24.5 <= moon_age < 25.5): return "長潮 🐢", -0.5
    else: return "若潮 🌱", 0.8

@st.cache_data
def run_prediction(avg_t, max_t, min_t, rain, sunshine, wind, lat, lon, tide_bonus):
    features = ['平均気温(℃)', '最高気温(℃)', '最低気温(℃)', '降水量の合計(mm)', '日照時間(時間)', '平均風速(m/s)', '緯度', '経度']
    input_df = pd.DataFrame([[avg_t, max_t, min_t, rain, sunshine, wind, lat, lon]], columns=features)
    pred = model.predict(input_df)[0]
    is_good_tide = tide_bonus >= 1.0
    if '3_爆釣' in pred: return '3_爆釣', '#00FF00'
    elif '2_ぼちぼち' in pred: return ('3_爆釣(潮補正)', '#00FF00') if is_good_tide else ('2_ぼちぼち', '#FFFF00')
    else: return '1_激シブ', '#FF0000'

@st.cache_data(ttl=3600)
def get_weather_data(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,precipitation,wind_speed_10m,weather_code&daily=sunrise,sunset,sunshine_duration&timezone=Asia%2FTokyo&past_days=90&forecast_days=16&wind_speed_unit=ms"
    try:
        data = requests.get(url).json()
        df_h = pd.DataFrame({'日時': pd.to_datetime(data['hourly']['time']), '気温(℃)': data['hourly']['temperature_2m'], '風速(m/s)': data['hourly']['wind_speed_10m'], '降水量(mm)': data['hourly']['precipitation'], '天気コード': data['hourly']['weather_code']})
        df_d = pd.DataFrame({'日付': pd.to_datetime(pd.Series(data['daily']['time'])).dt.date, '日の出': pd.to_datetime(pd.Series(data['daily']['sunrise'])), '日の入': pd.to_datetime(pd.Series(data['daily']['sunset'])), '日照時間': [s/3600 if s else 0 for s in data['daily']['sunshine_duration']]})
        return df_h, df_d
    except: return None, None

def find_next_bakucho(lat, lon, df_h, df_d):
    today = datetime.now().date()
    future_dates = df_d[df_d['日付'] > today]['日付'].unique()
    for d in future_dates:
        h_sub = df_h[df_h['日時'].dt.date == d]
        d_sub = df_d[df_d['日付'] == d].iloc[0]
        rep = h_sub[h_sub['日時'].dt.hour == 12].iloc[0] if len(h_sub) > 12 else h_sub.iloc[0]
        tide_name, tide_bonus = get_tide_info(d)
        r, _ = run_prediction(rep['気温(℃)'], rep['気温(℃)']+5, rep['気温(℃)']-5, rep['降水量(mm)'], d_sub['日照時間'], rep['風速(m/s)'], lat, lon, tide_bonus)
        if '3_爆釣' in r: return f"{d.strftime('%Y年%m月%d日')} ({tide_name})"
    return "15日以内に爆釣予測なし（厳しい時期です…）"

# 写真を圧縮して文字(Base64)に変換する関数
def process_image(uploaded_file):
    if uploaded_file is None: return None
    img = Image.open(uploaded_file)
    img.thumbnail((500, 500)) # サーバーを圧迫しないように縮小
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

# 釣果データの取得
def get_catch_data():
    if supabase is None: return pd.DataFrame()
    try:
        res = supabase.table("catches").select("*").order("created_at", desc=True).execute()
        return pd.DataFrame(res.data)
    except:
        return pd.DataFrame()

with st.spinner('システム起動中... 全ポイントの気象データを先読みしています🎣'):
    for c in spots.values():
        get_weather_data(c['lat'], c['lon'])

# ==========================================
# メイン UI
# ==========================================
st.title('🎣 上天草アジ予測AI ＆ 釣果SNS (Ver.8.0)')

st.markdown("### 📍 ポイントを素早く切り替え")
selected_name = st.radio(
    label="場所を選択",
    options=list(spots.keys()),
    index=list(spots.keys()).index(st.session_state.selected_spot),
    horizontal=True,
    label_visibility="collapsed"
)

if selected_name != st.session_state.selected_spot:
    st.session_state.selected_spot = selected_name
    st.rerun()

st.markdown('---')

spot_cfg = spots[st.session_state.selected_spot]
selected_date = st.sidebar.date_input("予測日", value=datetime.now().date(), min_value=datetime.now().date()-timedelta(days=90), max_value=datetime.now().date()+timedelta(days=15))

df_h, df_d = get_weather_data(spot_cfg['lat'], spot_cfg['lon'])
df_catches = get_catch_data() # データベースからみんなの釣果を取得

if df_h is not None and df_d is not None:
    target_h = df_h[df_h['日時'].dt.date == selected_date].copy()
    target_d = df_d[df_d['日付'] == selected_date].iloc[0]
    w_rep = target_h[target_h['日時'].dt.hour == 12].iloc[0] if len(target_h) > 12 else target_h.iloc[0]

    current_tide_name, current_tide_bonus = get_tide_info(selected_date)
    next_bakucho = find_next_bakucho(spot_cfg['lat'], spot_cfg['lon'], df_h, df_d)

    # ==========================================
    # 🌟 マップのタブ切り替え（AI予測 vs リアル釣果）
    # ==========================================
    c1, c2 = st.columns([2, 1])
    
    with c1:
        map_tab1, map_tab2 = st.tabs(["🤖 AI予測マップ", "🐟 みんなのリアル釣果マップ"])
        
        with map_tab1:
            # AI予測マップデータの作成
            ai_map_list = []
            for n, c in spots.items():
                _, tb = get_tide_info(selected_date)
                r, col = run_prediction(w_rep['気温(℃)'], w_rep['気温(℃)']+5, w_rep['気温(℃)']-5, w_rep['降水量(mm)'], target_d['日照時間'], w_rep['風速(m/s)'], c['lat'], c['lon'], tb)
                ai_map_list.append({'name': n, 'lat': c['lat'], 'lon': c['lon'], 'color': col, 'rank': r, 'size': 35})
            df_ai_map = pd.DataFrame(ai_map_list)

            fig_ai = px.scatter_mapbox(df_ai_map, lat="lat", lon="lon", color="rank", text="name", custom_data=["name"],
                                        color_discrete_map={'3_爆釣': '#00FF00', '3_爆釣(潮補正)': '#00FF00', '2_ぼちぼち': '#FFFF00', '1_激シブ': '#FF0000'},
                                        zoom=11.5, size="size", mapbox_style="carto-darkmatter")
            fig_ai.update_traces(mode='markers+text', textposition='top right', textfont=dict(color='white', size=15, family="Arial Black"), marker=dict(opacity=0.9))
            fig_ai.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, showlegend=False, mapbox_center={"lat": spot_cfg['lat'], "lon": spot_cfg['lon']})
            
            try:
                event_ai = st.plotly_chart(fig_ai, on_select="rerun", selection_mode="points", key="ai_map_click", use_container_width=True)
                if hasattr(event_ai, "selection") and event_ai.selection:
                    pts = event_ai.selection.get("points", [])
                    if pts and pts[0].get("customdata", [""])[0] != st.session_state.selected_spot:
                        st.session_state.selected_spot = pts[0].get("customdata", [""])[0]
                        st.rerun()
            except Exception: st.plotly_chart(fig_ai, use_container_width=True)

        with map_tab2:
            # 🌟 リアル釣果マップデータの作成
            catch_map_list = []
            for n, c in spots.items():
                if not df_catches.empty:
                    # その場所の最新の釣果データを取得
                    spot_catches = df_catches[df_catches['spot'] == n]
                    if not spot_catches.empty:
                        latest_catch = spot_catches.iloc[0]['catch_count']
                        # 釣果数に応じて記号を変える！
                        if latest_catch == 0: symbol = "✖"
                        elif latest_catch < 10: symbol = "〇"
                        else: symbol = "⭐"
                        
                        display_text = f"{n} {symbol}({latest_catch}匹)"
                        catch_map_list.append({'name': n, 'lat': c['lat'], 'lon': c['lon'], 'text': display_text, 'size': 35, 'color': '釣果あり'})
                    else:
                        catch_map_list.append({'name': n, 'lat': c['lat'], 'lon': c['lon'], 'text': f"{n} (報告なし)", 'size': 15, 'color': '報告なし'})
                else:
                    catch_map_list.append({'name': n, 'lat': c['lat'], 'lon': c['lon'], 'text': f"{n} (報告なし)", 'size': 15, 'color': '報告なし'})
            
            df_catch_map = pd.DataFrame(catch_map_list)

            fig_catch = px.scatter_mapbox(df_catch_map, lat="lat", lon="lon", color="color", text="text", custom_data=["name"],
                                        color_discrete_map={'釣果あり': '#FFD700', '報告なし': '#555555'},
                                        zoom=11.5, size="size", mapbox_style="carto-darkmatter")
            fig_catch.update_traces(mode='markers+text', textposition='top right', textfont=dict(color='white', size=16, family="Arial Black"), marker=dict(opacity=0.9))
            fig_catch.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, showlegend=False, mapbox_center={"lat": spot_cfg['lat'], "lon": spot_cfg['lon']})
            
            try:
                event_ca = st.plotly_chart(fig_catch, on_select="rerun", selection_mode="points", key="ca_map_click", use_container_width=True)
                if hasattr(event_ca, "selection") and event_ca.selection:
                    pts = event_ca.selection.get("points", [])
                    if pts and pts[0].get("customdata", [""])[0] != st.session_state.selected_spot:
                        st.session_state.selected_spot = pts[0].get("customdata", [""])[0]
                        st.rerun()
            except Exception: st.plotly_chart(fig_catch, use_container_width=True)

    with c2:
        # 右側も「予測」と「釣果ギャラリー」のタブに分ける
        info_tab1, info_tab2 = st.tabs(["🎯 予測データ", "📸 みんなの釣果ギャラリー"])
        
        with info_tab1:
            st.write(f"📍 **場所**: {st.session_state.selected_spot}")
            st.write(f"🌕 **潮回り**: `{current_tide_name}`")
            st.write(f"🚀 **次の爆釣日**: `{next_bakucho}`")
            
            my_r = df_ai_map[df_ai_map['name'] == st.session_state.selected_spot].iloc[0]['rank']
            if '3_爆釣' in my_r: st.success(f"✨【爆釣】✨\n\n大漁フラグ成立！これで釣れなかったら道具のせいじゃなくて君の腕のせいだね😀")
            elif '2_ぼちぼち' in my_r: st.info(f"👍【ぼちぼち】\n\n潮の流れを読み切れば釣果は伸びる！頑張り損にならないようにね😒")
            else: st.warning(f"⚠️【激シブ】\n\n潮も天気も味方してくれない最悪の日。大人しく家に引き籠って仕掛けでも作りましょう。")

        with info_tab2:
            st.write(f"📍 **{st.session_state.selected_spot} の最新釣果**")
            if not df_catches.empty:
                spot_history = df_catches[df_catches['spot'] == st.session_state.selected_spot].head(3)
                if spot_history.empty:
                    st.info("まだこの場所の釣果報告はありません。最初の報告者になりましょう！")
                else:
                    for _, row in spot_history.iterrows():
                        date_str = pd.to_datetime(row['created_at']).strftime('%m/%d %H:%M')
                        with st.container(border=True):
                            st.markdown(f"**🐟 {row['catch_count']}匹** ⏰ {row['catch_time'][:5]}ごろ ({date_str})")
                            if row['memo']: st.caption(f"📝 {row['memo']}")
                            # 写真があれば表示！
                            if 'image_b64' in row and row['image_b64']:
                                try:
                                    image_bytes = base64.b64decode(row['image_b64'])
                                    st.image(image_bytes, use_container_width=True)
                                except: pass
            else:
                st.info("まだデータベースに釣果がありません。")

    # ハイブリッドBI計算
    if '3_爆釣' in my_r: base_score = 3.8
    elif '2_ぼちぼち' in my_r: base_score = 2.2
    else: base_score = 0.5

    def calculate_hybrid_bi(row):
        wind_penalty = max(-1.0, row['風速(m/s)'] * -0.15)
        rain_penalty = max(-1.0, row['降水量(mm)'] * -0.3)
        bi = base_score + current_tide_bonus + wind_penalty + rain_penalty
        curr = row['日時']
        if abs((curr - target_d['日の出']).total_seconds()) <= 7200 or abs((curr - target_d['日の入']).total_seconds()) <= 7200:
            bi += 1.2
        return max(0.1, min(5.0, bi))

    target_h['BI'] = target_h.apply(calculate_hybrid_bi, axis=1)

    st.markdown('---')
    st.subheader(f'📅 時間ごとの爆釣指数（BI）')
    
    fig_bi = px.bar(target_h, x='日時', y='BI', color='BI', color_continuous_scale='YlGnBu', range_y=[0, 5.5], range_color=[0, 5.0])
    
    sr_str = target_d['日の出'].strftime("%Y-%m-%d %H:%M:%S")
    ss_str = target_d['日の入'].strftime("%Y-%m-%d %H:%M:%S")
    
    fig_bi.add_vline(x=sr_str, line_dash="dash", line_color="green")
    fig_bi.add_vline(x=ss_str, line_dash="dash", line_color="red")
    fig_bi.add_annotation(x=sr_str, y=5.2, text="日の出", showarrow=False, font=dict(color="green", size=14), xanchor="right")
    fig_bi.add_annotation(x=ss_str, y=5.2, text="日の入", showarrow=False, font=dict(color="red", size=14), xanchor="left")
    
    fig_bi.update_xaxes(range=[f"{selected_date} 00:00:00", f"{selected_date} 23:59:59"], tickformat="%H:%M")
    st.plotly_chart(fig_bi, use_container_width=True)

    # ==========================================
    # 🌟 究極の機能：写真付き釣果報告フォーム
    # ==========================================
    st.markdown('---')
    st.subheader('📸 今日の釣果を報告してマップを更新しよう！')
    st.caption("ここで投稿されたデータは、上の「リアル釣果マップ」に即座に反映され、来月のAIの学習にも使われます。")

    with st.form("report_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            report_spot = st.selectbox("📍 釣れた場所", list(spots.keys()), index=list(spots.keys()).index(st.session_state.selected_spot))
            report_count = st.number_input("🐟 釣れた数（匹）", min_value=0, max_value=500, value=0, step=1)
        with c2:
            report_time = st.time_input("⏰ 一番釣れた時間帯", value=datetime.now().time())
            report_memo = st.text_input("📝 ヒットルアーや潮の動き")
        with c3:
            # 🌟 新機能：カメラ/写真アップローダー
            uploaded_file = st.file_uploader("📸 釣果写真（任意）", type=['png', 'jpg', 'jpeg'])
            
        submitted = st.form_submit_button("🚀 写真とデータをマップに送信！", use_container_width=True)
        
        if submitted:
            if supabase is None:
                st.error("⚠️ データベース連携設定が完了していません！")
            else:
                try:
                    # 写真を圧縮して文字(Base64)に変換
                    img_b64 = process_image(uploaded_file)
                    
                    data, count = supabase.table("catches").insert({
                        "spot": report_spot,
                        "catch_count": report_count,
                        "catch_time": str(report_time),
                        "memo": report_memo,
                        "image_b64": img_b64 # 圧縮した写真をデータベースに保存！
                    }).execute()
                    
                    st.success(f"🎉 報告完了！上の「みんなのリアル釣果マップ」タブを見てください！")
                    st.balloons()
                except Exception as e:
                    st.error(f"送信エラー: {e}\n(Supabaseに 'image_b64' という列を追加したか確認してください)")