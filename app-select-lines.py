import os
import re
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="CSV 行フィルター & 保存", page_icon="🗂️", layout="wide")

st.title("🗂️ CSV 行フィルター & 保存（大項目・中項目・ページ範囲対応）")

with st.expander("使い方 / How to use", expanded=False):
    st.markdown("""
1. **CSVファイルを選択**（UTF-8推奨）。  
2. 「大項目」「中項目」の**使用されている文字列の一覧**が出ます。必要なものに**チェック**。  
3. **ページ**列に対して **範囲指定１** と **範囲指定２** を入力（どちらか一方だけでもOK）。  
4. **絞り込み結果をダウンロード**ボタンで、`大項目+中項目+YYYYMMDD_HHMMSS.csv` という名前で保存できます。
    """)

# ---------- 1. ファイル選択 ----------
st.subheader("1) 読み込むファイルを選択")
uploaded = st.file_uploader("CSVファイルを選んでください", type=["csv"])

if uploaded is None:
    st.info("CSVをアップロードすると次のステップに進みます。")
    st.stop()

# CSV読み込み（UTF-8 → cp932フォールバック）
try:
    df = pd.read_csv(uploaded)
except UnicodeDecodeError:
    uploaded.seek(0)
    df = pd.read_csv(uploaded, encoding="cp932")

# ---------- 必須列確認 ----------
REQUIRED_COLS = ["大項目", "中項目", "ページ"]
missing = [c for c in REQUIRED_COLS if c not in df.columns]
if missing:
    st.error(f"必須列が見つかりません: {missing}\nCSVに『大項目』『中項目』『ページ』列が必要です。")
    st.dataframe(df.head(50))
    st.stop()

# ---------- 2. 大項目・中項目選択 ----------
st.subheader("2) 大項目・中項目をチェック")

big_values = sorted(df["大項目"].dropna().astype(str).unique().tolist())
mid_values = sorted(df["中項目"].dropna().astype(str).unique().tolist())

col1, col2 = st.columns(2)

with col1:
    st.markdown("**大項目**（チェックで選択）")
    select_all_big = st.checkbox("大項目をすべて選択", value=True)
    sel_big = st.multiselect("大項目", options=big_values,
                             default=big_values if select_all_big else [])

with col2:
    st.markdown("**中項目**（チェックで選択）")
    select_all_mid = st.checkbox("中項目をすべて選択", value=True)
    sel_mid = st.multiselect("中項目", options=mid_values,
                             default=mid_values if select_all_mid else [])

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

# ---------- ページ列の範囲表記対応 ----------
def extract_page_numbers(x):
    """ページ列からページ番号リストを返す（例: '10-12' → [10,11,12]）"""
    if pd.isna(x):
        return []
    s = str(x)
    # "10-12" / "10～12" / "p10-12" / "p10～12"
    m = re.match(r"[pＰ]?\s*(\d+)\s*[-〜~]\s*(\d+)", s)
    if m:
        start, end = map(int, m.groups())
        return list(range(start, end + 1))
    # 単一ページ
    m2 = re.search(r"\d+", s)
    if m2:
        return [int(m2.group())]
    return []

df["_ページリスト"] = df["ページ"].apply(extract_page_numbers)

def in_any_range(page_list, ranges):
    """ページリストのいずれかが範囲内にあればTrue"""
    for p in page_list:
        for (rstart, rend) in ranges:
            if rstart <= p <= rend:
                return True
    return False

ranges = []
if r1_enabled: ranges.append((r1_start, r1_end))
if r2_enabled: ranges.append((r2_start, r2_end))

# ---------- 4. 絞り込み実行 ----------
st.subheader("4) 絞り込み結果")

mask_big = df["大項目"].astype(str).isin(sel_big) if sel_big else pd.Series([False]*len(df))
mask_mid = df["中項目"].astype(str).isin(sel_mid) if sel_mid else pd.Series([False]*len(df))
mask_category = mask_big & mask_mid

if ranges:
    mask_page = df["_ページリスト"].apply(lambda lst: in_any_range(lst, ranges))
else:
    mask_page = True

final_mask = mask_category & mask_page
filtered = df.loc[final_mask].drop(columns=["_ページリスト"])

st.write(f"抽出行数: **{len(filtered)}** / {len(df)}")
st.dataframe(filtered, use_container_width=True)

# ---------- 5. ダウンロード ----------
st.subheader("5) ダウンロード")

def make_filename(big_sel, mid_sel):
    def label(vals):
        if not vals:
            return "未選択"
        if len(vals) == 1:
            return vals[0]
        head = "_".join(vals[:3])
        return f"{head}_他{len(vals)}件"
    dt = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{label(big_sel)}+{label(mid_sel)}+{dt}.csv"

default_name = make_filename(sel_big, sel_mid)

st.download_button(
    label="⬇️ 絞り込み結果をダウンロード",
    data=filtered.to_csv(index=False).encode("utf-8-sig"),
    file_name=default_name,
    mime="text/csv",
    disabled=len(filtered)==0
)

st.caption("© 2025 CSV Filter App – ページ範囲表記完全対応版")
