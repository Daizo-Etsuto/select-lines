
import os
import re
import io
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="CSV 行フィルター & 保存", page_icon="🗂️", layout="wide")

st.title("🗂️ CSV 行フィルター & 保存（大項目・中項目・ページ範囲）")

with st.expander("使い方 / How to use", expanded=False):
    st.markdown("""
1. **CSVファイルを選択**（UTF-8推奨）。  
2. 「大項目」「中項目」の**使用されている文字列の一覧**が出ます。必要なものに**チェック**。  
3. **ページ**列に対して **範囲指定１** と **範囲指定２** を入力（どちらか一方だけでもOK）。  
4. **絞り込み結果を保存**ボタンで、`大項目+中項目+YYYYMMDD+HHMMSS.csv` という名前でダウンロード・保存できます。
    """)

# ---------- 1. ファイル選択 ----------
st.subheader("1) 読み込むファイルを選択")
uploaded = st.file_uploader("CSVファイルを選んでください", type=["csv"])

# オプション: サンプル読み込み（フォルダ内）
sample_csv_path = os.environ.get("SAMPLE_CSV_PATH", "")
if sample_csv_path and os.path.exists(sample_csv_path):
    st.caption(f"📎 サンプル: {sample_csv_path} が利用可能です。未アップロード時はサンプルを使用できます。")
use_sample = False
if uploaded is None and sample_csv_path and os.path.exists(sample_csv_path):
    use_sample = st.toggle("サンプルCSVを使う", value=False)

if uploaded is None and not use_sample:
    st.info("CSVをアップロードすると次のステップに進みます。")
    st.stop()

# 読み込み
if uploaded is not None:
    try:
        df = pd.read_csv(uploaded)
    except UnicodeDecodeError:
        uploaded.seek(0)
        df = pd.read_csv(uploaded, encoding="cp932")  # 日本語Windows想定の代替
elif use_sample:
    df = pd.read_csv(sample_csv_path)
else:
    st.stop()

# 必須列確認
REQUIRED_COLS = ["大項目", "中項目", "ページ"]
missing = [c for c in REQUIRED_COLS if c not in df.columns]
if missing:
    st.error(f"必須列が見つかりません: {missing}\nCSVに『大項目』『中項目』『ページ』列が必要です。")
    st.dataframe(df.head(50))
    st.stop()

# ---------- 2. 大項目・中項目でチェック選択 ----------
st.subheader("2) 大項目・中項目をチェック")

# 重複排除＆表示用
big_values = pd.Series(df["大項目"].astype(str).fillna("")).unique().tolist()
mid_values = pd.Series(df["中項目"].astype(str).fillna("")).unique().tolist()
big_values = sorted([v for v in big_values if v != "" ])
mid_values = sorted([v for v in mid_values if v != "" ])

col1, col2 = st.columns(2)

with col1:
    st.markdown("**大項目**（チェックで選択）")
    select_all_big = st.checkbox("大項目をすべて選択", value=True, key="sel_all_big")
    default_big = big_values if select_all_big else []
    sel_big = st.multiselect("大項目（チェックリスト）", options=big_values, default=default_big, placeholder="大項目を選択")

with col2:
    st.markdown("**中項目**（チェックで選択）")
    select_all_mid = st.checkbox("中項目をすべて選択", value=True, key="sel_all_mid")
    default_mid = mid_values if select_all_mid else []
    sel_mid = st.multiselect("中項目（チェックリスト）", options=mid_values, default=default_mid, placeholder="中項目を選択")

# ---------- 3. ページ範囲（2枠）入力 ----------
st.subheader("3) ページ列の範囲指定（2つまで）")

def range_inputs(prefix: str):
    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        st.caption(f"{prefix}：開始")
        start = st.number_input(f"{prefix} 開始", value=1, step=1, min_value=0, key=f"{prefix}_start")
    with c2:
        st.caption(f"{prefix}：終了")
        end = st.number_input(f"{prefix} 終了", value=1, step=1, min_value=0, key=f"{prefix}_end")
    with c3:
        enabled = st.checkbox(f"{prefix} を有効にする", value=False, key=f"{prefix}_enabled")
    if start > end:
        start, end = end, start
    return enabled, int(start), int(end)

r1_enabled, r1_start, r1_end = range_inputs("範囲指定１")
r2_enabled, r2_start, r2_end = range_inputs("範囲指定２")

# ページ列の数値化（「10-12」「p34」等にもある程度対応）
def extract_first_int(x):
    if pd.isna(x):
        return None
    s = str(x)
    m = re.search(r"\d+", s)
    return int(m.group()) if m else None

pages = df["ページ"].apply(extract_first_int)
df = df.assign(_ページ数値=pages)

# ---------- フィルターの実行 ----------
st.subheader("4) 絞り込み結果")

# 大項目・中項目フィルタ
mask_big = df["大項目"].astype(str).isin(sel_big) if sel_big else pd.Series([False]*len(df))
mask_mid = df["中項目"].astype(str).isin(sel_mid) if sel_mid else pd.Series([False]*len(df))
mask_category = mask_big & mask_mid

# ページ範囲フィルタ
mask_page = pd.Series([False]*len(df))
if r1_enabled:
    mask_page = mask_page | ((df["_ページ数値"].notna()) & (df["_ページ数値"].between(r1_start, r1_end, inclusive="both")))
if r2_enabled:
    mask_page = mask_page | ((df["_ページ数値"].notna()) & (df["_ページ数値"].between(r2_start, r2_end, inclusive="both")))

# 両方適用（カテゴリと範囲）
final_mask = mask_category & (mask_page if (r1_enabled or r2_enabled) else True)
filtered = df.loc[final_mask].drop(columns=["_ページ数値"])

st.write(f"抽出行数: **{len(filtered)}** / {len(df)}")
st.dataframe(filtered, use_container_width=True)

# ---------- 保存 ----------
st.subheader("5) 保存")

def make_filename(big_sel, mid_sel):
    def label(vals):
        if not vals:
            return "未選択"
        if len(vals) == 1:
            return vals[0]
        # 複数選択時は先頭3つ + _他
        head = "_".join(vals[:3])
        return f"{head}_他{len(vals)}件"
    dt = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{label(big_sel)}+{label(mid_sel)}+{dt}.csv"

default_name = make_filename(sel_big, sel_mid)
fn = st.text_input("保存ファイル名", value=default_name)

col_dl, col_save = st.columns([1,1])
with col_dl:
    st.caption("ローカルにダウンロード")
    st.download_button(
        label="⬇️ 絞り込み結果をダウンロード",
        data=filtered.to_csv(index=False).encode("utf-8-sig"),
        file_name=fn,
        mime="text/csv",
        disabled=len(filtered)==0
    )

with col_save:
    st.caption("サーバー側（./outputs）に保存")
    save_clicked = st.button("💾 保存する", disabled=len(filtered)==0)
    if save_clicked:
        os.makedirs("outputs", exist_ok=True)
        path = os.path.join("outputs", fn)
        filtered.to_csv(path, index=False, encoding="utf-8-sig")
        st.success(f"保存しました: {path}")

st.divider()
st.caption("© 2025 CSV Filter App")
