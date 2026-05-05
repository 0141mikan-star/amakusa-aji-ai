# 🎣 上天草アジ予測AI ＆ 釣果SNS

**[👉 アプリを実際に触ってみる (Streamlit Cloud)](https://amakusa-aji-ai-efioayzjpjk83ebgrwunkp.streamlit.app/)**

気象データと機械学習を用いて上天草エリアのアジの釣果を予測し、現地のリアルタイムな釣果情報を共有できるハイブリッド型Webアプリケーションです。

「いつ・どこで釣れるか」というアングラーの永遠の課題に対し、データサイエンスに基づく予測（AI）と、現場の一次情報（SNS）の両輪でアプローチし、釣行のUXを最大化することを目指しています。

## ✨ 主な機能 (Features)

*   **🤖 AI予測マップ (AI Prediction Map)**
    *   Open-Meteo APIから取得した15日先までの気象データ（気温、風速、降水量、日照時間）と潮汐情報（月齢計算）を統合。
    *   機械学習モデルを用いて、各ポイント（松島、樋島、御所浦島など）の釣果ポテンシャルを「爆釣 / ぼちぼち / 激シブ」の3段階でヒートマップ表示します。
*   **🐟 リアル釣果マップ ＆ ギャラリー (Real-time SNS Map)**
    *   ユーザーが現場から釣果、時間帯、ヒットパターン、写真をリアルタイムに投稿可能。
    *   投稿データは即座にマップ上のピンとして反映され、他のアングラーと情報を共有できます。
*   **📊 爆釣指数（BI）の時系列分析 (Time-series BI Chart)**
    *   AIの予測スコアに、風速・降水量によるペナルティや「マズメ時（日の出・日の入）」のボーナスを加味した独自の「爆釣指数（BI）」を算出。
    *   1日の釣れるタイミングを可視化するタイムラインチャートを提供します。
*   **📸 画像の自動圧縮・Base64保存 (Image Compression)**
    *   現場からのアップロード負荷とデータベース容量を抑えるため、Pillowを用いて画像をクライアント側でリサイズし、Base64形式でセキュアに保存します。

## 🛠 技術スタック (Tech Stack)

*   **Frontend / Framework:** Streamlit
*   **Data Processing:** Pandas
*   **Machine Learning:** scikit-learn, joblib
*   **API / Network:** Requests
*   **Data Visualization:** Plotly
*   **Database (BaaS):** Supabase (PostgreSQL)
*   **Image Processing:** Pillow

## 🚀 環境構築 (Setup)

### 1. リポジトリのクローンとパッケージのインストール
```bash
git clone [https://github.com/yourusername/amakusa-aji-ai.git](https://github.com/yourusername/amakusa-aji-ai.git)
cd amakusa-aji-ai
pip install -r requirements.txt
