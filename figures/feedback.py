import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# 색상 및 폰트 설정 변수
UNIFIED_COLOR = "#4878D0"  # 파란색 기본값
FONT_FAMILY = "AppleGothic"  # 기본 폰트
BASE_FONT_SIZE = 12  # 기본 폰트 크기
LABEL_FONT_SIZE = BASE_FONT_SIZE + 2  # 라벨 폰트 크기
TITLE_FONT_SIZE = BASE_FONT_SIZE + 4  # 제목 폰트 크기
ANNOTATION_FONT_SIZE = BASE_FONT_SIZE - 1  # 주석 폰트 크기

# --- 데이터 준비 (이전과 동일) ---
# .xlarge 인스턴스 위주로 비교 데이터를 구성합니다.
# 실제 가격은 변동될 수 있으므로 최신 AWS 가격 정보를 참조하는 것이 좋습니다.

# 인스턴스 데이터를 아키텍처별로 구분하여 정의
instances_by_arch = {
    "x86": [
        # Baseline Instances
        {
            "instance": "t3.large",  # Baseline for t4g
            "family": "T",
            "generation": "3 (Intel)",
            "vcpu": 2,
            "memory_gib": 8,
            "hourly_cost_usd": 0.1040,
            "spot_1h_avg_usd": 0.0334,
            "price_perf_gain": None,  # Baseline Perf Gain = 0
        },
        {
            "instance": "m5.xlarge",  # Baseline for m6g/m7g
            "family": "M",
            "generation": "5 (Intel)",
            "vcpu": 4,
            "memory_gib": 16,
            "hourly_cost_usd": 0.2360,
            "spot_1h_avg_usd": 0.0647,
            "price_perf_gain": None,  # Baseline Perf Gain = 0
        },
        {
            "instance": "c5.xlarge",  # Baseline for c6g/c7g
            "family": "C",
            "generation": "5 (Intel)",
            "vcpu": 4,
            "memory_gib": 8,
            "hourly_cost_usd": 0.1920,
            "spot_1h_avg_usd": 0.0764,
            "price_perf_gain": None,  # Baseline Perf Gain = 0
        },
        {
            "instance": "r5.xlarge",  # Baseline for r6g/r7g
            "family": "R",
            "generation": "5 (Intel)",
            "vcpu": 4,
            "memory_gib": 32,
            "hourly_cost_usd": 0.3040,
            "spot_1h_avg_usd": 0.0902,
            "price_perf_gain": None,  # Baseline Perf Gain = 0
        },
        # Newer x86 (can be compared to older x86 if needed, but not baseline for Graviton here)
        {
            "instance": "m6i.xlarge",
            "family": "M",
            "generation": "6 (Intel)",
            "vcpu": 4,
            "memory_gib": 16,
            "hourly_cost_usd": 0.2360,
            "spot_1h_avg_usd": 0.0840,
            "price_perf_gain": 15,  # Vs m5
        },
        {
            "instance": "c6i.xlarge",
            "family": "C",
            "generation": "6 (Intel)",
            "vcpu": 4,
            "memory_gib": 8,
            "hourly_cost_usd": 0.1920,
            "spot_1h_avg_usd": 0.0602,
            "price_perf_gain": 15,  # Vs c5
        },
        {
            "instance": "r6i.xlarge",
            "family": "R",
            "generation": "6 (Intel)",
            "vcpu": 4,
            "memory_gib": 32,
            "hourly_cost_usd": 0.3040,
            "spot_1h_avg_usd": 0.1014,
            "price_perf_gain": 15,  # Vs r5
        },
    ],
    "ARM": [
        {
            "instance": "t4g.large",
            "family": "T",
            "generation": "2 (Graviton2)",
            "vcpu": 2,
            "memory_gib": 8,
            "hourly_cost_usd": 0.0832,
            "spot_1h_avg_usd": 0.0199,
            "price_perf_gain": 40,  # Vs t3
        },
        {
            "instance": "m6g.xlarge",
            "family": "M",
            "generation": "2 (Graviton2)",
            "vcpu": 4,
            "memory_gib": 16,
            "hourly_cost_usd": 0.1880,
            "spot_1h_avg_usd": 0.0371,
            "price_perf_gain": 40,  # Vs m5
        },
        {
            "instance": "m7g.xlarge",
            "family": "M",
            "generation": "3 (Graviton3)",
            "vcpu": 4,
            "memory_gib": 16,
            "hourly_cost_usd": 0.2006,
            "spot_1h_avg_usd": 0.0551,
            "price_perf_gain": 50,  # Vs m5 (Assumed AWS claim basis)
        },
        {
            "instance": "c6g.xlarge",
            "family": "C",
            "generation": "2 (Graviton2)",
            "vcpu": 4,
            "memory_gib": 8,
            "hourly_cost_usd": 0.1540,
            "spot_1h_avg_usd": 0.0469,
            "price_perf_gain": 40,  # Vs c5
        },
        {
            "instance": "c7g.xlarge",
            "family": "C",
            "generation": "3 (Graviton3)",
            "vcpu": 4,
            "memory_gib": 8,
            "hourly_cost_usd": 0.1632,
            "spot_1h_avg_usd": 0.0576,
            "price_perf_gain": 55,  # Vs c5 (Assumed AWS claim basis)
        },
        {
            "instance": "r6g.xlarge",
            "family": "R",
            "generation": "2 (Graviton2)",
            "vcpu": 4,
            "memory_gib": 32,
            "hourly_cost_usd": 0.2440,
            "spot_1h_avg_usd": 0.0586,
            "price_perf_gain": 40,  # Vs r5
        },
        {
            "instance": "r7g.xlarge",
            "family": "R",
            "generation": "3 (Graviton3)",
            "vcpu": 4,
            "memory_gib": 32,
            "hourly_cost_usd": 0.2584,
            "spot_1h_avg_usd": 0.0414,
            "price_perf_gain": 50,  # Vs r5 (Assumed AWS claim basis)
        },
    ],
}

# 데이터프레임 생성을 위해 리스트로 변환 (이전과 동일)
all_instances = []
for arch, instances in instances_by_arch.items():
    for instance in instances:
        instance_data = {
            "Instance": instance["instance"],
            "Family": instance["family"],
            "Architecture": arch,
            "Generation": instance["generation"],
            "vCPU": instance["vcpu"],
            "Memory_GiB": instance["memory_gib"],
            "Hourly_Cost_USD": instance["hourly_cost_usd"],
            "Spot_1h_avg_USD": instance["spot_1h_avg_usd"],
            "Price_Perf_Gain_vs_Prev_x86 (%)": instance["price_perf_gain"],
        }
        all_instances.append(instance_data)

# 데이터프레임 생성
df = pd.DataFrame(all_instances)

# --- !!! 새로운 계산 방식 !!! ---
# 1. 기준 x86 인스턴스 매핑 정의 (ARM 패밀리별 기준 x86 정의)
baseline_map = {
    "T": "t3.large",
    "M": "m5.xlarge",
    "C": "c5.xlarge",
    "R": "r5.xlarge",
}

# 2. 개별 비교 결과 저장 리스트
comparison_results = []

# 3. ARM 인스턴스별로 순회하며 비교 수행
arm_df = df[df["Architecture"] == "ARM"].copy()
x86_baseline_df = df[
    df["Instance"].isin(baseline_map.values())
].copy()  # 기준 x86만 선택

# 기준 x86 비용/성능을 쉽게 찾기 위한 딕셔너리 생성
baseline_costs = x86_baseline_df.set_index("Instance")["Hourly_Cost_USD"].to_dict()
baseline_spot_costs = x86_baseline_df.set_index("Instance")["Spot_1h_avg_USD"].to_dict()

for index, row in arm_df.iterrows():
    family = row["Family"]
    baseline_instance_name = baseline_map.get(family)

    if baseline_instance_name and baseline_instance_name in baseline_costs:
        baseline_od_cost = baseline_costs[baseline_instance_name]
        baseline_spot_cost = baseline_spot_costs[baseline_instance_name]

        # ARM 인스턴스 정보
        arm_instance = row["Instance"]
        arm_od_cost = row["Hourly_Cost_USD"]
        arm_spot_cost = row["Spot_1h_avg_USD"]
        # price_perf_gain이 NaN이거나 0일 경우 0으로 처리
        arm_perf_gain = (
            row["Price_Perf_Gain_vs_Prev_x86 (%)"]
            if pd.notna(row["Price_Perf_Gain_vs_Prev_x86 (%)"])
            else 0
        )

        # 상대 값 계산 (기준: 해당 패밀리의 baseline x86 On-Demand = 100%)
        relative_od_cost_percent = (arm_od_cost / baseline_od_cost) * 100
        relative_spot_cost_percent = (
            arm_spot_cost / baseline_od_cost
        ) * 100  # 스팟 비용도 x86 OD 기준
        relative_perf_percent = 100.0 + arm_perf_gain  # 기준 x86 대비 성능

        comparison_results.append(
            {
                "ARM_Instance": arm_instance,
                "Baseline_x86_Instance": baseline_instance_name,
                "Relative_OD_Cost_%": relative_od_cost_percent,
                "Relative_Spot_Cost_%": relative_spot_cost_percent,
                "Relative_Perf_%": relative_perf_percent,
                "Original_Perf_Gain_%": arm_perf_gain,  # 평균 계산 시 사용
            }
        )

# 4. 비교 결과 데이터프레임 생성 및 평균 계산
comparison_df = pd.DataFrame(comparison_results)

# 각 상대 값들의 평균 계산 (NaN 값 제외)
avg_relative_arm_od_cost = np.nanmean(comparison_df["Relative_OD_Cost_%"])
avg_relative_arm_spot_cost = np.nanmean(comparison_df["Relative_Spot_Cost_%"])
avg_relative_arm_perf = np.nanmean(comparison_df["Relative_Perf_%"])
avg_arm_perf_gain = np.nanmean(
    comparison_df["Original_Perf_Gain_%"]
)  # 순수 성능 향상률 평균

# 5. x86 스팟 비용의 상대 평균 계산 (기준: 모든 baseline x86의 평균 On-Demand 비용)
avg_baseline_x86_od_cost = np.nanmean(list(baseline_costs.values()))
avg_baseline_x86_spot_cost = np.nanmean(list(baseline_spot_costs.values()))
avg_relative_x86_spot_cost = (
    avg_baseline_x86_spot_cost / avg_baseline_x86_od_cost
) * 100

# 6. 최종 플롯 데이터 준비
plot_data_avg = []

# x86 On-Demand (기준)
plot_data_avg.append(
    {
        "Category": "x86",
        "Avg_Relative_Cost_Percent": 100.0,
        "Avg_Relative_Perf_Percent": 100.0,
        "Avg_Raw_Cost": avg_baseline_x86_od_cost,
    }
)
# ARM On-Demand (평균 상대 값)
plot_data_avg.append(
    {
        "Category": "ARM",
        "Avg_Relative_Cost_Percent": avg_relative_arm_od_cost,
        "Avg_Relative_Perf_Percent": avg_relative_arm_perf,
        "Avg_Raw_Cost": np.nanmean(arm_df["Hourly_Cost_USD"]),
    }
)
# x86 Spot (평균 상대 값)
plot_data_avg.append(
    {
        "Category": "x86 - Spot",
        "Avg_Relative_Cost_Percent": avg_relative_x86_spot_cost,
        "Avg_Relative_Perf_Percent": 100.0,  # 성능은 OD와 동일 가정
        "Avg_Raw_Cost": avg_baseline_x86_spot_cost,
    }
)
# ARM Spot (평균 상대 값)
plot_data_avg.append(
    {
        "Category": "ARM - Spot",
        "Avg_Relative_Cost_Percent": avg_relative_arm_spot_cost,
        "Avg_Relative_Perf_Percent": avg_relative_arm_perf,  # 성능은 OD와 동일 가정
        "Avg_Raw_Cost": np.nanmean(arm_df["Spot_1h_avg_USD"]),
    }
)

plot_df_avg = pd.DataFrame(plot_data_avg)


# --- 시각화 (개선된 평균 데이터 사용) ---
# 논문 스타일의 시각화 설정
plt.style.use("default")  # Changed from seaborn-v0_8-whitegrid to remove grid lines
plt.rcParams["font.family"] = FONT_FAMILY  # 설정된 폰트 사용
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams.update({"font.size": BASE_FONT_SIZE})
plt.rcParams.update({"axes.labelsize": LABEL_FONT_SIZE})
plt.rcParams.update({"axes.titlesize": TITLE_FONT_SIZE})
plt.rcParams.update({"xtick.labelsize": BASE_FONT_SIZE})
plt.rcParams.update({"ytick.labelsize": BASE_FONT_SIZE})
plt.rcParams["axes.grid"] = False  # Explicitly disable grid

fig, ax1 = plt.subplots(figsize=(10, 6), dpi=150)

# 카테고리 순서 정의
category_order = [
    "x86",
    "ARM",
    "x86 - Spot",
    "ARM - Spot",
]
# 단일 색상 사용
palette = [UNIFIED_COLOR] * len(
    [cat for cat in category_order if cat in plot_df_avg["Category"].values]
)

ax1 = sns.barplot(
    data=plot_df_avg,
    x="Category",
    y="Avg_Relative_Cost_Percent",
    order=[cat for cat in category_order if cat in plot_df_avg["Category"].values],
    palette=palette,
    hue="Category",
    dodge=False,
    legend=False,
)

ax1.set_ylabel("Relative Cost (%)", color="black")
ax1.set_xlabel("")
ax1.tick_params(axis="x", rotation=0)
ax1.tick_params(axis="y", labelcolor="black")
ax1.grid(False)  # Explicitly turn off the grid

# 100% 기준선 - 남기기
ax1.axhline(100, color="gray", linestyle="--", linewidth=0.8)

# --- Annotations (평균값 기반) ---
if not plot_df_avg.empty:
    for i, bar in enumerate(ax1.patches):
        height = bar.get_height()  # Avg_Relative_Cost_Percent
        category = ax1.get_xticklabels()[i].get_text()

        if not pd.isna(height):
            # 막대 상단 레이블 (평균 상대 비용 %)
            label_text = f"{height:.1f}%"
            ax1.text(
                bar.get_x() + bar.get_width() / 2.0,
                height + 1,  # 약간 위로 이동
                label_text,
                ha="center",
                va="bottom",
                color="black",
                fontsize=ANNOTATION_FONT_SIZE,
                bbox=dict(
                    facecolor="white", alpha=0.7, pad=1, edgecolor="none"
                ),  # 배경 추가
            )

        x_pos = bar.get_x() + bar.get_width() / 2.0

# Y축 범위 조정
if not plot_df_avg.empty:
    max_rel_cost = plot_df_avg["Avg_Relative_Cost_Percent"].max()
    padding_top = max_rel_cost * 0.15 if not pd.isna(max_rel_cost) else 15
    top_limit = max(max_rel_cost + padding_top if not pd.isna(max_rel_cost) else 0, 120)
    ax1.set_ylim(0, top_limit)
else:
    ax1.set_ylim(0, 120)

# 최종 조정
plt.tight_layout()
plt.savefig("x86_vs_arm_comparison.pdf", bbox_inches="tight")
plt.savefig("x86_vs_arm_comparison.png", bbox_inches="tight", dpi=300)
plt.show()

# 비교 결과 상세 출력 (옵션)
print("--- 패밀리별 비교 결과 상세 ---")
print(comparison_df.to_string())
print("\n--- 최종 평균 플롯 데이터 ---")
print(plot_df_avg.to_string())
