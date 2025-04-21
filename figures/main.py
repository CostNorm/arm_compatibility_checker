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
    "Hourly_Cost_USD": [
        0.0832,
        0.0672,  # t3 vs t4g
        0.192,
        0.192,
        0.154,
        0.1632,  # m5, m6i vs m6g, m7g
        0.1700,
        0.1700,
        0.1360,
        0.1450,  # c5, c6i vs c6g, c7g
        0.252,
        0.252,
        0.2016,
        0.2142,  # r5, r6i vs r6g, r7g
    ],
    "Spot_3m_avg_USD": [
        0.0832,
        0.0672,  # t3 vs t4g
        0.192,
        0.192,
        0.154,
        0.1632,  # m5, m6i vs m6g, m7g
        0.1700,
        0.1700,
        0.1360,
        0.1450,  # c5, c6i vs c6g, c7g
        0.252,
        0.252,
        0.2016,
        0.2142,  # r5, r6i vs r6g, r7g
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


# 1. 아키텍처별 상대적 비용 및 성능 비교 (x86=100% 기준, xlarge/large 기준)
# Filter relevant instances (.xlarge and .large)
df_relevant = df[
    df["Instance"].str.contains("xlarge") | df["Instance"].str.contains("large")
].copy()

# Calculate average cost per architecture
avg_cost_arch = (
    df_relevant.groupby("Architecture")["Hourly_Cost_USD"].mean().reset_index()
)

# Calculate average performance gain for Graviton vs baseline x86
valid_gains = df_relevant.loc[
    (df_relevant["Architecture"] == "Graviton")
    & df_relevant["Price_Perf_Gain_vs_Prev_x86 (%)"].notna(),
    "Price_Perf_Gain_vs_Prev_x86 (%)",
]
avg_perf_gain_graviton = valid_gains.mean() if not valid_gains.empty else 0

# Get x86 average cost as baseline
x86_avg_cost = avg_cost_arch.loc[
    avg_cost_arch["Architecture"] == "x86", "Hourly_Cost_USD"
].iloc[0]

# Create relative data
relative_data = []
for arch in ["x86", "Graviton"]:
    cost_row = avg_cost_arch[avg_cost_arch["Architecture"] == arch]
    if not cost_row.empty:
        current_cost = cost_row["Hourly_Cost_USD"].iloc[0]
        relative_cost = (current_cost / x86_avg_cost) * 100
        if arch == "x86":
            relative_perf = 100.0
        else:  # Graviton
            relative_perf = 100.0 + avg_perf_gain_graviton
        relative_data.append(
            {
                "Architecture": arch,
                "Relative_Cost_Percent": relative_cost,
                "Relative_Perf_Percent": relative_perf,
            }
        )

relative_df = pd.DataFrame(relative_data)


# --- Plotting ---
fig, ax1 = plt.subplots(figsize=(8, 6))

plot_order = ["x86", "Graviton"]
colors = {"x86": "skyblue", "Graviton": "lightcoral"}

# Plot Relative Cost bars (ax1)
sns.barplot(
    data=relative_df,
    x="Architecture",
    y="Relative_Cost_Percent",
    hue="Architecture",
    palette=colors,
    order=plot_order,
    ax=ax1,
    legend=False,
)
ax1.set_ylabel("상대적 비용 (x86 = 100%)", color="black")
ax1.set_xlabel("CPU 아키텍처")
ax1.tick_params(axis="y", labelcolor="black")

# Create secondary axis (ax2) for Relative Performance
ax2 = ax1.twinx()

# Plot Relative Performance points (ax2)
sns.pointplot(
    data=relative_df,
    x="Architecture",
    y="Relative_Perf_Percent",
    order=plot_order,
    ax=ax2,
    color="green",
    markers="D",
    linestyles="",
    label="상대적 성능 (%)",
)
ax2.set_ylabel("상대적 성능 (x86 = 100%)", color="green")
ax2.tick_params(axis="y", labelcolor="green")
ax2.grid(False)

# --- Y-axis limits starting from 0 ---
# Find max values for both axes
max_cost = relative_df["Relative_Cost_Percent"].max()
max_perf = relative_df["Relative_Perf_Percent"].max()
overall_max = max(max_cost, max_perf)

# Set limits from 0 to overall max + padding
padding_top = overall_max * 0.10  # 10% padding at the top
y_lim_bottom = 0
y_lim_top = overall_max + padding_top

ax1.set_ylim(y_lim_bottom, y_lim_top)
ax2.set_ylim(y_lim_bottom, y_lim_top)

# Add horizontal line at 100% AFTER setting limits (only on primary axis)
ax1.axhline(100, color="gray", linestyle="--", linewidth=0.8)

# --- Annotations ---
# Add relative cost values on bars, combining x86 info
for i, container in enumerate(ax1.containers):
    arch = plot_order[i]
    original_cost = avg_cost_arch.loc[
        avg_cost_arch["Architecture"] == arch, "Hourly_Cost_USD"
    ].iloc[0]

    labels = []
    for v in container.datavalues:  # v is Relative_Cost_Percent
        if arch == "x86":
            # Combine cost and performance for x86 baseline
            label_text = f"{v:.1f}%\n(${original_cost:.4f})\n(+0.0% gain)"
        else:  # Graviton
            label_text = f"{v:.1f}%\n(${original_cost:.4f})"
        labels.append(label_text)

    ax1.bar_label(container, labels=labels, padding=3)

# Add relative performance values as text annotations (Graviton only)
for i, arch in enumerate(plot_order):
    if arch == "Graviton":  # Only annotate Graviton performance point
        row = relative_df[relative_df["Architecture"] == arch]
        if not row.empty:
            perf_value = row["Relative_Perf_Percent"].iloc[0]
            original_gain = avg_perf_gain_graviton

            # Adjust y position slightly above the point
            y_offset = (
                y_lim_top - y_lim_bottom
            ) * 0.02  # 2% of the axis range works fine here too
            y_pos = perf_value + y_offset
            # Create annotation text
            annotation_text = f"{perf_value:.1f}%\n({original_gain:+.1f}% gain)"
            ax2.text(i, y_pos, annotation_text, color="green", ha="center", va="bottom")

# Final adjustments
plt.title(
    "x86 대비 Graviton: 상대적 비용 및 성능 비교\n(us-east-1, On-Demand, xlarge/large 기준, x86=100%)"
)
plt.tight_layout()
plt.show()
