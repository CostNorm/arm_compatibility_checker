import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# --- 데이터 준비 (보고서 Phase 3 기반, us-east-1 On-Demand 가격) ---
# .xlarge 인스턴스 위주로 비교 데이터를 구성합니다.
# 실제 가격은 변동될 수 있으므로 최신 AWS 가격 정보를 참조하는 것이 좋습니다.
data = {
    "Instance": [
        "t3.large",
        "t4g.large",
        "m5.xlarge",
        "m6i.xlarge",
        "m6g.xlarge",
        "m7g.xlarge",
        "c5.xlarge",
        "c6i.xlarge",
        "c6g.xlarge",
        "c7g.xlarge",
        "r5.xlarge",
        "r6i.xlarge",
        "r6g.xlarge",
        "r7g.xlarge",
    ],
    "Family": ["T", "T", "M", "M", "M", "M", "C", "C", "C", "C", "R", "R", "R", "R"],
    "Architecture": [
        "x86",
        "Graviton",
        "x86",
        "x86",
        "Graviton",
        "Graviton",
        "x86",
        "x86",
        "Graviton",
        "Graviton",
        "x86",
        "x86",
        "Graviton",
        "Graviton",
    ],
    "Generation": [
        "3 (Intel)",
        "2 (Graviton2)",
        "5 (Intel)",
        "6 (Intel)",
        "2 (Graviton2)",
        "3 (Graviton3)",
        "5 (Intel)",
        "6 (Intel)",
        "2 (Graviton2)",
        "3 (Graviton3)",
        "5 (Intel)",
        "6 (Intel)",
        "2 (Graviton2)",
        "3 (Graviton3)",
    ],
    "vCPU": [2, 2, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4],
    "Memory_GiB": [8, 8, 16, 16, 16, 16, 8, 8, 8, 8, 32, 32, 32, 32],
    # Spot 가격은 AWS Spot 실시간 가격 페이지에서 확인
    "Hourly_Cost_USD": [
        0.1040,
        0.0832,  # t3, t4g
        0.2360,
        0.2360,
        0.1880,
        0.2006,  # m5, m6i, m6g, m7g
        0.1920,
        0.1920,
        0.1540,
        0.1632,  # c5, c6i, c6g, c7g
        0.3040,
        0.3040,
        0.2440,
        0.2584,  # r5, r6i, r6g, r7g
    ],
    "Spot_1h_avg_USD": [
        0.0334,
        0.0199,  # t3, t4g
        0.0647,
        0.0840,
        0.0371,
        0.0551,  # m5, m6i, m6g, m7g
        0.0764,
        0.0602,
        0.0469,
        0.0576,  # c5, c6i, c6g, c7g
        0.0902,
        0.1014,
        0.0586,
        0.0414,  # r5, r6i, r6g, r7g
    ],
    # 보고서 기반 성능 향상 주장 (vs 이전 세대 x86 기준, 예: M6g vs M5)
    # Graviton3는 Graviton2 대비 성능 향상
    "Price_Perf_Gain_vs_Prev_x86 (%)": [
        None,
        40,  # t4g vs t3
        None,
        15,
        40,
        50,  # m6i vs m5, m6g vs m5, m7g vs m5 (추정: m6g 40% + m7g 25% on top?)
        None,
        15,
        40,
        55,  # c6i vs c5, c6g vs c5, c7g vs c5 (추정)
        None,
        15,
        40,
        50,  # r6i vs r5, r6g vs r5, r7g vs r5 (추정)
        # 참고: Graviton3의 성능 향상(vs G2)과 결합하면 Price-Perf 향상은 더 커질 수 있음
    ],
}
df = pd.DataFrame(data)

# 비교를 위한 기준 x86 인스턴스 매핑 (여기서는 단순화를 위해 이전 세대 x86 사용)
# t4g -> t3, m6g/m7g -> m5, c6g/c7g -> c5, r6g/r7g -> r5
baseline_map = {
    ("T", "Graviton"): "t3.large",
    ("M", "Graviton"): "m5.xlarge",  # m6g, m7g 모두 m5와 비교
    ("C", "Graviton"): "c5.xlarge",  # c6g, c7g 모두 c5와 비교
    ("R", "Graviton"): "r5.xlarge",  # r6g, r7g 모두 r5와 비교
}


# 기준 x86 비용 열 추가
def get_baseline_cost(row):
    if row["Architecture"] == "Graviton":
        key = (row["Family"], row["Architecture"])
        baseline_instance = baseline_map.get(key)
        if baseline_instance:
            return df.loc[df["Instance"] == baseline_instance, "Hourly_Cost_USD"].iloc[
                0
            ]
    elif row["Instance"] in [
        "m6i.xlarge",
        "c6i.xlarge",
        "r6i.xlarge",
    ]:  # 최신 x86은 이전 x86과 비교
        key = (row["Family"], "x86")
        baseline_instance = df[
            (df["Family"] == row["Family"]) & (df["Generation"].str.contains("5"))
        ]["Instance"].iloc[0]
        return df.loc[df["Instance"] == baseline_instance, "Hourly_Cost_USD"].iloc[0]
    return np.nan


df["Baseline_x86_Cost"] = df.apply(get_baseline_cost, axis=1)

# 비용 절감률 계산
df["Cost_Saving_Percent"] = (
    (df["Baseline_x86_Cost"] - df["Hourly_Cost_USD"]) / df["Baseline_x86_Cost"]
) * 100


# --- 시각화 ---
sns.set_style("whitegrid")
plt.rcParams["font.family"] = "AppleGothic"  # Mac 사용자
# plt.rcParams['font.family'] = 'NanumGothic' # Windows/Linux 사용자 (나눔고딕 설치 필요)
plt.rcParams["axes.unicode_minus"] = False  # 마이너스 기호 깨짐 방지


# 1. 아키텍처/구매 옵션별 상대적 비용 및 성능 비교 (x86 On-Demand = 100% 기준, xlarge/large 기준)
# Filter relevant instances (.xlarge and .large)
df_relevant = df[
    df["Instance"].str.contains("xlarge") | df["Instance"].str.contains("large")
].copy()

# Prepare data for the new plot
plot_data = []

# --- Calculate Performance Gain (needed for the first plot now) ---
avg_cost_arch_perf = (
    df_relevant.groupby("Architecture")["Hourly_Cost_USD"].mean().reset_index()
)
valid_gains_perf = df_relevant.loc[
    (df_relevant["Architecture"] == "Graviton")
    & df_relevant["Price_Perf_Gain_vs_Prev_x86 (%)"].notna(),
    "Price_Perf_Gain_vs_Prev_x86 (%)",
]
avg_perf_gain_graviton_calc = (
    valid_gains_perf.mean() if not valid_gains_perf.empty else 0
)
# --- End Performance Gain Calculation ---

# Calculate average costs for each category
avg_costs = df_relevant.groupby("Architecture")[
    ["Hourly_Cost_USD", "Spot_1h_avg_USD"]
].mean()

# Handle potential KeyError if 'Graviton' or 'x86' isn't present after filtering
x86_ondemand_avg = (
    avg_costs.loc["x86", "Hourly_Cost_USD"] if "x86" in avg_costs.index else np.nan
)
graviton_ondemand_avg = (
    avg_costs.loc["Graviton", "Hourly_Cost_USD"]
    if "Graviton" in avg_costs.index
    else np.nan
)
x86_spot_avg = (
    avg_costs.loc["x86", "Spot_1h_avg_USD"] if "x86" in avg_costs.index else np.nan
)
graviton_spot_avg = (
    avg_costs.loc["Graviton", "Spot_1h_avg_USD"]
    if "Graviton" in avg_costs.index
    else np.nan
)


# Use x86 On-Demand as the baseline (100%)
baseline_cost = x86_ondemand_avg

# Add data points only if cost is available
if not pd.isna(x86_ondemand_avg):
    plot_data.append(
        {
            "Category": "x86 - OnDemand",
            "Avg_Cost": x86_ondemand_avg,
            "Relative_Cost_Percent": 100.0,
            "Relative_Perf_Percent": 100.0,
        }
    )
if not pd.isna(graviton_ondemand_avg) and not pd.isna(baseline_cost):
    plot_data.append(
        {
            "Category": "Graviton - OnDemand",
            "Avg_Cost": graviton_ondemand_avg,
            "Relative_Cost_Percent": (graviton_ondemand_avg / baseline_cost) * 100,
            "Relative_Perf_Percent": 100.0 + avg_perf_gain_graviton_calc,
        }
    )
if not pd.isna(x86_spot_avg) and not pd.isna(baseline_cost):
    plot_data.append(
        {
            "Category": "x86 - Spot",
            "Avg_Cost": x86_spot_avg,
            "Relative_Cost_Percent": (x86_spot_avg / baseline_cost) * 100,
            "Relative_Perf_Percent": 100.0,
        }
    )
if not pd.isna(graviton_spot_avg) and not pd.isna(baseline_cost):
    plot_data.append(
        {
            "Category": "Graviton - Spot",
            "Avg_Cost": graviton_spot_avg,
            "Relative_Cost_Percent": (graviton_spot_avg / baseline_cost) * 100,
            "Relative_Perf_Percent": 100.0 + avg_perf_gain_graviton_calc,
        }
    )


plot_df = pd.DataFrame(plot_data)


# --- Plotting: Cost Bars with Performance Gain Indicators ---
fig, ax1 = plt.subplots(figsize=(12, 8))  # Keep figure size

# Define colors for each specific category
category_order = [
    "x86 - OnDemand",
    "Graviton - OnDemand",
    "x86 - Spot",
    "Graviton - Spot",
]
colors = {
    "x86 - OnDemand": "skyblue",
    "Graviton - OnDemand": "lightcoral",
    "x86 - Spot": "lightblue",
    "Graviton - Spot": "salmon",
}
palette = [
    colors.get(cat, "gray")
    for cat in category_order
    if cat in plot_df["Category"].values
]  # Ensure palette matches available data

ax1 = sns.barplot(  # Assign to ax1
    data=plot_df,
    x="Category",
    y="Relative_Cost_Percent",
    order=[
        cat for cat in category_order if cat in plot_df["Category"].values
    ],  # Ensure order matches available data
    palette=palette,
    hue="Category",  # Still use hue to ensure categories are distinct if needed, map colors via palette
    dodge=False,  # Ensure bars are not dodged
    legend=False,  # Turn off default legend
)

ax1.set_ylabel("상대적 비용 (x86 On-Demand = 100%)", color="black")
ax1.set_xlabel("아키텍처 및 구매 옵션")
ax1.tick_params(axis="x", rotation=15)  # Rotate labels slightly
ax1.tick_params(axis="y", labelcolor="black")

# Add horizontal line at 100%
if not pd.isna(baseline_cost):  # Only add line if baseline is valid
    ax1.axhline(100, color="gray", linestyle="--", linewidth=0.8)

# --- Annotations ---
# Recalculate containers based on the actual plot generated
containers = ax1.containers
if containers and not plot_df.empty:
    for i, bar in enumerate(ax1.patches):
        height = bar.get_height()  # Relative_Cost_Percent
        # Get category name from x-tick labels (more robust than assuming container order)
        category = ax1.get_xticklabels()[i].get_text()
        if not pd.isna(height):
            # --- Bar Top Label (Cost %) ---
            original_cost_series = plot_df.loc[
                plot_df["Category"] == category, "Avg_Cost"
            ]
            if not original_cost_series.empty:
                original_cost = original_cost_series.iloc[0]
                label_text = f"{height:.1f}%\n(${original_cost:.4f})"
                ax1.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height,
                    label_text,  # Position near top of bar
                    ha="center",
                    va="bottom",
                    color="black",
                    fontsize=9,
                )

        x_pos = bar.get_x() + bar.get_width() / 2.0

        # --- Add Cost Saving Indicator (If bar is below 100%) ---
        if height < 100.0:
            y_cost_top = height
            ax1.plot(
                [x_pos, x_pos],
                [y_cost_top, 100.0],
                color="blue",
                linestyle="-",
                linewidth=1.5,
                marker="_",
                markersize=6,
            )  # Small caps at ends

            # Add text annotation for the saving %
            cost_saving_percent = 100.0 - height
            # Adjust text position based on category to avoid overlap
            ha_cost = (
                "right" if "Graviton" in category else "left"
            )  # Place left for x86 Spot
            x_offset_cost = -0.05 if "Graviton" in category else 0.05
            ax1.text(
                x_pos + x_offset_cost,
                (y_cost_top + 100.0) / 2,  # Position text vertically in the middle
                f"-{cost_saving_percent:.1f}%\nCost Save",
                color="blue",
                ha=ha_cost,
                va="center",
                fontsize=8,
            )

        # --- Add Performance Gain Indicator (Only for Graviton) ---
        if "Graviton" in category:
            # 1. Performance Gain (Green Line - Above 100%)
            y_perf_top = 100.0 + avg_perf_gain_graviton_calc
            # Draw vertical line from 100% level to performance level
            ax1.plot(
                [x_pos, x_pos],
                [100.0, y_perf_top],
                color="green",
                linestyle="-",
                linewidth=1.5,
                marker="_",
                markersize=6,
            )  # Small caps at ends

            # Add text annotation for the AVG GAIN % next to the line
            ax1.text(
                x_pos + 0.05,  # Slight horizontal offset from line (right)
                (100.0 + y_perf_top)
                / 2,  # Position text vertically in the middle of the line
                f"{avg_perf_gain_graviton_calc:+.1f}%\nAvg. Perf.\nGain (G2/G3 Est.)",
                color="green",
                ha="left",
                va="center",
                fontsize=8,
            )

            # Add text annotation for the TOTAL performance % near the top marker
            ax1.text(
                x_pos,
                y_perf_top
                + 2.0,  # Position slightly above the top marker (adjust offset)
                f"{y_perf_top:.1f}%",
                color="green",
                ha="center",  # Center horizontally
                va="bottom",  # Place text above the coordinate
                fontsize=8,
            )

# Adjust Y-axis limit to start from 0 and add padding
if not plot_df.empty:
    max_rel_cost = plot_df["Relative_Cost_Percent"].max()
    # Consider performance indicator height for padding
    potential_max_y = max(
        max_rel_cost if not pd.isna(max_rel_cost) else 0,
        100.0 + avg_perf_gain_graviton_calc,
    )
    padding_top = potential_max_y * 0.18  # Increase padding slightly more for text
    top_limit = potential_max_y + padding_top if potential_max_y > 0 else 150

    ax1.set_ylim(0, top_limit)
else:
    ax1.set_ylim(0, 150)  # Default limits if no data

# Final adjustments
plt.title(
    "x86 vs Graviton: 비용(막대), 평균 성능향상(녹색선, 추정치 기반), 비용절감(파란선)\n(us-east-1, On-Demand & Spot, xlarge/large, x86 OD Cost/Perf = 100%)"
)
plt.tight_layout()
plt.show()
