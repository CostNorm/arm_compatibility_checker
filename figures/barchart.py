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

# 1. 개별 인스턴스 유형별 비용 비교 (xlarge 기준)
plt.figure(figsize=(14, 7))
# 비교 대상 인스턴스만 필터링 (예: t3 vs t4g, m5 vs m6g, c5 vs c6g, r5 vs r6g)
df_compare_g2 = df[
    df["Instance"].isin(
        [
            "t3.large",
            "t4g.large",
            "m5.xlarge",
            "m6g.xlarge",
            "c5.xlarge",
            "c6g.xlarge",
            "r5.xlarge",
            "r6g.xlarge",
        ]
    )
]
bar1 = sns.barplot(
    data=df_compare_g2,
    x="Family",
    y="Hourly_Cost_USD",
    hue="Instance",
    palette="viridis",
)
plt.title(
    "개별 인스턴스 시간당 비용 비교 (us-east-1, On-Demand, xlarge 기준, Graviton2 vs Prev Gen x86)"
)
plt.ylabel("시간당 비용 (USD)")
plt.xlabel("인스턴스 패밀리")
# 데이터 레이블 추가
for p in bar1.patches:
    bar1.annotate(
        format(p.get_height(), ".4f"),
        (p.get_x() + p.get_width() / 2.0, p.get_height()),
        ha="center",
        va="center",
        xytext=(0, 9),
        textcoords="offset points",
    )
plt.tight_layout()
plt.show()

# 1-2. 개별 인스턴스 비용 비교 (최신 세대 포함)
plt.figure(figsize=(16, 8))
# .xlarge 인스턴스만 사용
df_xlarge = df[
    df["Instance"].str.contains("xlarge") | df["Instance"].str.contains("large")
]  # t시리즈는 large 사용
bar1_all = sns.barplot(
    data=df_xlarge, x="Family", y="Hourly_Cost_USD", hue="Instance", palette="magma"
)
plt.title(
    "개별 인스턴스 시간당 비용 비교 (us-east-1, On-Demand, xlarge/large 기준, 모든 세대)"
)
plt.ylabel("시간당 비용 (USD)")
plt.xlabel("인스턴스 패밀리")
plt.xticks(rotation=10)
# 데이터 레이블 추가 (값이 너무 작으면 겹칠 수 있음)
for p in bar1_all.patches:
    bar1_all.annotate(
        format(p.get_height(), ".4f"),
        (p.get_x() + p.get_width() / 2.0, p.get_height()),
        ha="center",
        va="center",
        size=8,
        xytext=(0, 5),
        textcoords="offset points",
    )
plt.legend(loc="upper right", bbox_to_anchor=(1.15, 1))
plt.tight_layout()
plt.show()


# 2. 상대적 비용 절감률 (Graviton vs 이전 세대 x86)
plt.figure(figsize=(10, 6))
df_graviton_savings = df[
    (df["Architecture"] == "Graviton")
    & (df["Instance"].str.contains("xlarge") | df["Instance"].str.contains("large"))
].copy()
# Graviton 세대별로 분리해서 볼 수도 있음
# df_graviton_savings_g2 = df[(df['Architecture'] == 'Graviton') & df['Generation'].str.contains('Graviton2')]

bar2 = sns.barplot(
    data=df_graviton_savings,
    x="Instance",
    y="Cost_Saving_Percent",
    hue="Instance",
    palette="coolwarm",
    legend=False,
)
plt.title("Graviton 인스턴스 비용 절감률 (vs 이전 세대 x86, us-east-1 On-Demand)")
plt.ylabel("비용 절감률 (%)")
plt.xlabel("Graviton 인스턴스 유형")
plt.ylim(0, 30)  # 절감률 범위 조정 (보고서 기준 ~20%)
# 데이터 레이블 추가
for p in bar2.patches:
    bar2.annotate(
        format(p.get_height(), ".1f") + "%",
        (p.get_x() + p.get_width() / 2.0, p.get_height()),
        ha="center",
        va="center",
        xytext=(0, 9),
        textcoords="offset points",
    )
plt.tight_layout()
plt.show()

# 3. 아키텍처별 평균 비용 비교 (x86 vs Graviton, xlarge/large 기준)
plt.figure(figsize=(7, 5))

# .xlarge 및 .large 인스턴스만 필터링 (df_xlarge는 이전 셀에서 생성됨)
# df_xlarge가 정의되지 않은 경우를 대비하여 재생성 로직 추가 (선택적)
if "df_xlarge" not in locals():
    df_xlarge = df[
        df["Instance"].str.contains("xlarge") | df["Instance"].str.contains("large")
    ].copy()

# 아키텍처별 평균 비용 계산
avg_cost_arch = (
    df_xlarge.groupby("Architecture")["Hourly_Cost_USD"]
    .mean()
    .reset_index()
    .sort_values("Hourly_Cost_USD")
)

bar3_arch = sns.barplot(
    data=avg_cost_arch,
    x="Architecture",
    y="Hourly_Cost_USD",
    hue="Architecture",  # 각 바에 다른 색상 적용
    palette={"x86": "skyblue", "Graviton": "lightcoral"},  # 색상 지정
    legend=False,  # 범례 제거
)

plt.title(
    "평균 시간당 인스턴스 비용 비교 (x86 vs Graviton)\n(us-east-1, On-Demand, xlarge/large 기준)"
)
plt.ylabel("평균 시간당 비용 (USD)")
plt.xlabel("CPU 아키텍처")

# 데이터 레이블 추가
for p in bar3_arch.patches:
    bar3_arch.annotate(
        format(p.get_height(), ".4f"),
        (p.get_x() + p.get_width() / 2.0, p.get_height()),
        ha="center",
        va="center",
        xytext=(0, 9),
        textcoords="offset points",
    )

plt.tight_layout()
plt.show()

# 4. 가격 대비 성능 개념 시각화 (비용 절감 + 성능 향상 주석)
# 여기서는 Graviton2 인스턴스들의 비용 절감률을 보여주고, 성능 향상 주장을 텍스트로 추가합니다.
plt.figure(figsize=(12, 7))
df_g2_savings = df[
    (df["Architecture"] == "Graviton") & (df["Generation"].str.contains("Graviton2"))
].copy()
bar4 = sns.barplot(
    data=df_g2_savings,
    x="Instance",
    y="Cost_Saving_Percent",
    hue="Instance",
    palette="Greens_d",
    legend=False,
)

plt.title("Graviton2 비용 절감률 및 가격 대비 성능 이점 (vs 이전 세대 x86)")
plt.ylabel("비용 절감률 (%)")
plt.xlabel("Graviton2 인스턴스 유형")
plt.ylim(0, 50)  # y축 범위 확장하여 주석 공간 확보

# 데이터 레이블 (비용 절감률)
for p in bar4.patches:
    bar4.annotate(
        f"{p.get_height():.1f}% Cost Saving",
        (p.get_x() + p.get_width() / 2.0, p.get_height()),
        ha="center",
        va="center",
        xytext=(0, 9),
        textcoords="offset points",
    )

# 성능 향상 주석 추가 (텍스트) - 보고서의 "up to 40% better price-performance" 강조
plt.text(
    0.5,
    45,
    '보고서에 따르면, Graviton2 인스턴스는\n유사한 이전 세대 x86 인스턴스 대비\n"최대 40% 더 나은 가격 대비 성능"을 제공합니다.',
    horizontalalignment="center",
    verticalalignment="top",
    fontsize=11,
    color="darkgreen",
    bbox=dict(boxstyle="round,pad=0.5", fc="aliceblue", alpha=0.8),
)

# 개별 인스턴스에 대한 성능 주석 (선택 사항, 그래프 복잡해질 수 있음)
# 예시: t4g.large 위치에 주석 추가
# t4g_index = df_g2_savings[df_g2_savings['Instance'] == 't4g.large'].index[0]
# plt.text(bar4.patches[t4g_index].get_x() + bar4.patches[t4g_index].get_width()/2,
#          bar4.patches[t4g_index].get_height() + 15,
#          'Up to 40%\nbetter price-perf\n(vs T3)', ha='center', va='bottom', fontsize=9, color='green')


plt.tight_layout()
plt.show()


# 4-2. 최신 세대 가격 대비 성능 개념 (Graviton3 vs 최신 x86)
plt.figure(figsize=(12, 7))
df_g3_savings = df[
    (df["Architecture"] == "Graviton") & (df["Generation"].str.contains("Graviton3"))
].copy()
# G3의 비교 기준은 최신 x86 (M6i, C6i, R6i)로 변경
baseline_map_g3 = {
    ("M", "Graviton"): "m6i.xlarge",
    ("C", "Graviton"): "c6i.xlarge",
    ("R", "Graviton"): "r6i.xlarge",
}


def get_baseline_cost_g3(row):
    if row["Architecture"] == "Graviton" and "Graviton3" in row["Generation"]:
        key = (row["Family"], row["Architecture"])
        baseline_instance = baseline_map_g3.get(key)
        if baseline_instance:
            return df.loc[df["Instance"] == baseline_instance, "Hourly_Cost_USD"].iloc[
                0
            ]
    return np.nan


df_g3_savings["Baseline_x86_Cost"] = df_g3_savings.apply(get_baseline_cost_g3, axis=1)
df_g3_savings["Cost_Saving_Percent"] = (
    (df_g3_savings["Baseline_x86_Cost"] - df_g3_savings["Hourly_Cost_USD"])
    / df_g3_savings["Baseline_x86_Cost"]
) * 100

bar5 = sns.barplot(
    data=df_g3_savings,
    x="Instance",
    y="Cost_Saving_Percent",
    hue="Instance",
    palette="Blues_d",
    legend=False,
)
plt.title("Graviton3 비용 절감률 및 가격 대비 성능 이점 (vs 최신 세대 x86)")
plt.ylabel("비용 절감률 (%)")
plt.xlabel("Graviton3 인스턴스 유형")
plt.ylim(0, 50)  # y축 범위 확장

# 데이터 레이블 (비용 절감률)
for p in bar5.patches:
    bar5.annotate(
        f"{p.get_height():.1f}% Cost Saving\n(vs M6i/C6i/R6i)",
        (p.get_x() + p.get_width() / 2.0, p.get_height()),
        ha="center",
        va="center",
        xytext=(0, 15),  # 위치 조정
        textcoords="offset points",
        size=9,
    )

# 성능 향상 주석 추가
plt.text(
    0.5,
    45,
    "보고서에 따르면, Graviton3는 Graviton2 대비\n약 25% 더 높은 컴퓨팅 성능을 제공하며,\n최신 x86 대비 약 15% 저렴합니다.\n결과적으로 가격 대비 성능이 더욱 향상됩니다.",
    horizontalalignment="center",
    verticalalignment="top",
    fontsize=11,
    color="navy",
    bbox=dict(boxstyle="round,pad=0.5", fc="lightcyan", alpha=0.8),
)

plt.tight_layout()
plt.show()
