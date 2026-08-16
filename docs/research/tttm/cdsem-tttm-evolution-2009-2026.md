# CD-SEM Tool-to-Tool Matching 기법의 발전

## 2009 ABBA에서 Data-driven Fleet Matching과 Virtual Metrology까지

## 1. 개요

CD-SEM Tool-to-Tool Matching(TTTM)의 관점은 지난 15년 이상 크게 변화해왔습니다.

초기의 핵심 문제는 다음과 같았습니다.

> **두 CD-SEM 사이의 실제 measurement bias를 얼마나 정확하게 측정할 수 있는가?**

최근에는 다음과 같은 문제로 확장되고 있습니다.

> **Fleet 전체에서 어떤 tool이 비정상적인가?**
>
> **어떤 recipe parameter를 조정해야 새로운 tool을 fleet에 맞출 수 있는가?**
>
> **Matching degradation을 실제 metrology 결과가 나오기 전에 감지할 수 있는가?**

전체적인 발전 방향은 다음과 같이 정리할 수 있습니다.

```text
2009  ABBA / self-ABBA
      → 정확한 Tool A ↔ Tool B bias 측정

2021~2023  SEM contour / systematic artifact 분석
      → Pattern-dependent / image-level matching

2024  Data-driven CDSEM fleet matching
      → Recipe parameter optimization

2025  Fleet-wide difference score
      → Golden tool 없이 fleet anomaly 분석

2026  Virtual Metrology-driven TTTM
      → Continuous matching monitoring + anomaly detection + RCA
```

## 2. 주요 연구 비교

| 연도 | 연구 | 대상 | 핵심 질문 | 주요 방법 |
| --- | --- | --- | --- | --- |
| 2009 | Kawada et al. | CD-SEM ↔ CD-SEM | 두 SEM의 실제 CD 차이는 얼마인가? | ABBA, self-ABBA |
| 2021 | Mack et al. | CD-SEM | Tool-specific measurement artifact는 무엇인가? | SEM contour / systematic error analysis |
| 2021~2023 | Weisbuch / Pradelles et al. | CD-SEM | Scalar CD가 아닌 contour 수준에서 matching 가능한가? | SEM contour matching |
| 2024 | Baram et al. | CD-SEM Fleet | 어떤 recipe parameter가 fleet matching을 개선하는가? | Data-driven matching model |
| 2025 | Samsung | Semiconductor Tool Fleet | Golden tool 없이 어떤 tool이 다른가? | DBSCAN, Wasserstein, GNN |
| 2026 | Kim / Gauss Labs | Process Chamber Fleet | Matching degradation을 조기에 감지할 수 있는가? | Virtual Metrology + distribution matching |

## 3. 2009: ABBA 기반 CD-SEM Matching

### 3.1 단순 AB 방식의 문제

Tool A에서 측정한 후 Tool B에서 동일 feature를 측정한다고 합시다. 단순하게

```text
ΔCD = CD_B − CD_A
```

를 계산하면 이것이 순수한 tool difference라고 보기 어렵습니다. 두 번째 측정에는
다음 효과가 추가될 수 있습니다.

- Charging
- Carbon contamination
- Carryover
- Sample modification
- Measurement-order effect
- SEM alignment variation

따라서 실제 측정값은 개념적으로 다음과 같이 볼 수 있습니다.

```text
CD_measured = CD_true + Bias_tool + Carryover + Noise
```

### 3.2 ABBA 측정

ABBA에서는 두 개의 equivalent feature set을 이용합니다.

- R1: Tool A → Tool B
- R2: Tool B → Tool A

측정값을 A₁, B₁, B₂, A₂라고 하면 기존 ABBA matching 값은 다음과 같이
계산됩니다.

```text
M_ABBA = (B₁ + B₂) / 2 − (A₁ + A₂) / 2
```

AB와 BA 순서를 모두 사용함으로써 measurement-order / carryover 영향을
최대한 상쇄합니다.

## 4. Self-ABBA

Self-ABBA는 동일 tool에서 ABBA sequence를 수행합니다.

```text
Tool A → Tool A → Tool A → Tool A
```

Tool difference가 존재하지 않기 때문에 이상적인 결과는 다음과 같습니다.

```text
M_self-ABBA = 0
```

따라서 0에서 벗어난 정도는 다음과 같은 요소를 반영합니다.

- Sampling fluctuation
- Carryover
- Measurement repeatability
- Alignment uncertainty
- Short-term stability

2009 연구에서는 self-ABBA uncertainty가 약 ±0.05 nm 수준이었습니다. 또한
sampling 수가 약 50개 이상이면 ABBA 결과의 statistical fluctuation이 약
0.01 nm 이하로 감소하는 결과가 제시되었습니다.

## 5. Carryover를 포함한 ABBA 해석

2009 논문의 중요한 부분 중 하나는 ABBA를 단순한 empirical equation으로만
보지 않았다는 점입니다. Tool difference를 Δ, Tool A/B의 carryover를 각각
d_A, d_B라고 하면 기존 ABBA 결과에는 개념적으로 다음이 포함될 수 있습니다.

```text
Δ + (d_B − d_A) / 2
```

따라서 기존 ABBA가 실제 tool difference를 과소평가할 가능성이 있다고
지적하였습니다. 이는 향후 matching 시스템에서도 중요한 의미를 가집니다.
Observed T2T difference와 intrinsic tool difference는 동일하지 않을 수
있습니다.

## 6. 2021~2023: CD 값에서 SEM Contour로

기존 matching은 주로 `CD_A − CD_B`와 같은 scalar 값을 비교합니다. 하지만
실제 CD-SEM 차이는 pattern에 따라 달라질 수 있습니다. 예를 들어:

- Line / Space / Hole
- 2D pattern
- Dense pattern / Isolated pattern
- Different pitch
- Different orientation

따라서 최근 연구에서는 단일 CD가 아니라 SEM contour 자체를 비교하는
방향으로 발전했습니다.

### 6.1 Tool-specific SEM Artifact

Tool A와 Tool B가 평균 CD는 동일해도 contour 수준에서는 차이가 존재할 수
있습니다. 예:

```text
Tool A        Tool B
│   │          ) (
│   │          ) (
│   │          ) (
```

평균 CD가 비슷하더라도 다음과 같은 차이가 존재할 수 있습니다.

- Scan distortion
- Edge blur
- Beam asymmetry
- Focus
- Stigma
- Detector response
- Pattern-dependent bias

따라서 matching이 scalar CD matching에서 image / contour matching으로
확대되었습니다.

## 7. 2024: Data-driven CDSEM Fleet Matching

2024년 Baram 등의 연구에서는 TTTM을 단순한 평가 문제가 아니라 recipe
parameter optimization 문제로 접근합니다.

기존 방식은 다음과 같습니다.

```text
Recipe 설정 → Wafer 측정 → Tool difference 확인
→ Engineer가 parameter 수정 → 다시 측정 → 반복
```

Data-driven 방식에서는 기존 fleet의 matching history를 이용합니다.

```text
Fleet historical matching data
+ Recipe parameters
+ Layer
+ Pattern
+ Measurement results
→ Matching model
→ Recommended recipe parameters
→ New tool matching
```

## 8. Matching Parameter Optimization

Recipe parameter vector를 다음과 같이 둡니다.

```text
θ = [θ₁, θ₂, …, θ_p]
```

예를 들어 다음 등이 포함될 수 있습니다.

- Magnification
- Focus
- Stigma
- Beam condition
- Scan condition
- Threshold
- Measurement algorithm
- AMP parameters

Matching optimization은 개념적으로 다음 문제로 볼 수 있습니다.

```text
θ* = argmin_θ L(CD_new(θ), CD_fleet)
```

즉, "tool difference를 계산하는 것"에서 "tool difference가 최소화되는
parameter를 찾는 것"으로 목적이 바뀝니다.

## 9. 2025: Fleet Difference Score

2025년 Samsung 연구는 CD-SEM 전용 연구는 아니지만, 다수 semiconductor
tool을 분석하는 방법론 측면에서 매우 흥미롭습니다.

기존 방식은 다음과 같습니다.

```text
D_i = |Tool_i − GoldenTool|
```

하지만 Golden Tool 역시 drift할 수 있습니다. 따라서 fleet 자체에서
consensus를 찾습니다.

```text
D_i = |Tool_i − FleetConsensus|
```

## 10. DBSCAN 기반 Fleet Consensus

하나의 parameter에 대해 Tool 1~18의 데이터를 모두 모은다고 합시다.
DBSCAN을 이용해 distribution을 clustering합니다.

```text
Tool 1  ●●●
Tool 2  ●●●
Tool 3  ●●●
Tool 4             ●●
Tool 5  ●●●
...
```

가장 큰 cluster를 정상 fleet consensus로 정의합니다.

```text
C_ref = Largest DBSCAN Cluster
D_i   = distance(X_i, C_ref)
```

장점은 다음과 같습니다.

- Golden tool이 필요 없음
- Fleet majority를 reference로 사용
- Outlier tool 자동 탐지 가능
- Fleet drift 분석 가능

## 11. Wasserstein Distance 기반 T2T Matching

Mean CD만 비교하는 것에는 한계가 있습니다. 예를 들어 다음과 같은 분포를
생각해 봅시다.

```text
Tool_A ~ N(30.0, 0.05²)
Tool_B ~ N(30.0, 0.15²)
```

평균은 μ_A = μ_B = 30.0이므로 mean matching만 보면 완벽하게 일치합니다.
하지만 Tool B의 variation은 훨씬 큽니다. 이때 distribution 전체를 비교하기
위해 Wasserstein distance를 사용할 수 있습니다.

```text
D_ij = W₁(P_i, P_j)
```

여기서 P_i, P_j는 각각 Tool i, Tool j의 CD distribution입니다.

## 12. Tool-to-Tool Distance Matrix

18개 tool이라면 다음과 같은 matrix를 만들 수 있습니다.

```text
D = [ D_ij ]  (18 × 18, 대각선은 0)
```

각 값은 `D_ij = W₁(P_i, P_j)`입니다. 이 matrix를 이용해 다음 분석을 수행할
수 있습니다.

- Tool clustering
- Hierarchical clustering
- MDS
- PCA-like visualization
- Outlier detection
- Fleet center detection
- Pairwise matching ranking

## 13. Tool-level Difference Score

Tool i가 전체 fleet에서 얼마나 떨어져 있는지를 다음과 같이 정의할 수
있습니다.

```text
Score_i = (1 / (N−1)) · Σ_{j≠i} D_ij
```

Score가 클수록 fleet에서 많이 벗어난 tool입니다.

| Tool | Fleet Distance |
| --- | --- |
| A | 0.05 |
| B | 0.04 |
| C | 0.06 |
| D | 0.31 |
| E | 0.05 |

Tool D를 anomaly candidate로 볼 수 있습니다.

## 14. Multivariate Tool Matching

실제 CD-SEM의 matching은 CD 하나만으로 결정되지 않습니다. 예를 들어 다음과
같은 multivariate 문제입니다.

```text
CD = f(Magnification, Focus, Stigma, Beam, Brightness, Contrast,
       SNR, Pattern, Layer, AMP)
```

따라서 각 parameter를 독립적으로 보는 것만으로는 충분하지 않을 수 있습니다.

## 15. GNN 기반 Parameter Relationship 분석

2025 Samsung 연구에서는 각 sensor를 graph node로 표현하고 parameter 관계를
edge로 학습하는 GNN/GAT 기반 방법도 제안합니다.

```text
        Focus
       /     \
  Beam ───── Stigma
    \         /
    Contrast
       |
      SNR
```

Tool별 graph가 만들어지면 두 tool의 graph structure 차이를 계산할 수
있습니다. 개념적으로 다음과 같은 형태입니다.

```text
D_ij^G = Σ_{m,n} |A_i(m,n) − A_j(m,n)| / E_max
```

이 방법의 의미는 "특정 parameter 값이 다른가"뿐 아니라 "parameter 간의
관계가 이 tool에서만 달라졌는가"까지 분석할 수 있다는 점입니다.

## 16. CD-SEM에서는 GNN보다 먼저 고려할 방법

CD-SEM TTTM에서는 처음부터 GNN까지 사용할 필요는 없습니다. 먼저 다음 조합이
상당히 강력합니다.

- Mixed-effect model
- Wasserstein Distance
- Fleet clustering
- Time-series monitoring

특히 explainability 측면에서 유리합니다.

## 17. Mixed-Effect Model 기반 Tool 분석

CD measurement를 다음과 같이 모델링할 수 있습니다.

```text
CD = μ + α_Tool + β_Layer + γ_Pattern + (αβ)_Tool,Layer + u_Wafer + ε
```

각 항의 의미는 다음과 같습니다.

- μ: 전체 평균
- α_Tool: Tool effect
- β_Layer: Layer effect
- γ_Pattern: Pattern effect
- (αβ): Tool × Layer interaction
- u_Wafer: Wafer variation
- ε: measurement noise

**예제 1: Tool 전체 Offset.** Tool A가 거의 모든 layer에서 +0.15 nm 높다면
α_A 문제일 가능성이 높습니다. 즉 global tool bias입니다.

**예제 2: 특정 Layer만 이상.** Tool A가 Layer X에서만 +0.30 nm 높다면
(αβ)_{A,X} 문제일 가능성이 높습니다. 즉 Tool × Layer interaction이며, global
offset correction으로 해결하기 어려울 수 있습니다.

## 18. 2026: Virtual Metrology-driven TTTM

기존 TTTM에는 fundamental limitation이 있습니다. Physical metrology sampling이
sparse하다는 점입니다.

```text
Wafer 1 → Measurement
Wafer 2
Wafer 3
Wafer 4
Wafer 5
Wafer 6 → Measurement
...
```

Tool이 Wafer 2부터 drift하기 시작하면 Wafer 6까지 발견되지 않을 수 있습니다.
Virtual Metrology(VM)를 적용하면 다음과 같이 wafer-level prediction을 생성할
수 있습니다.

```text
Wafer 1 → VM
Wafer 2 → VM
Wafer 3 → VM
Wafer 4 → VM
Wafer 5 → VM
Wafer 6 → VM
```

## 19. VM 기반 Distribution Matching

각 chamber/tool의 VM output을 distribution으로 만듭니다. 예를 들어 P_A(y),
P_B(y)이고, 여러 metric으로 비교합니다.

```text
Mean difference       D_μ = |μ_A − μ_B|
Variance difference   D_σ = |log(σ_A / σ_B)|
Distribution diff.    D_W = W₁(P_A, P_B)
```

이렇게 하면 단순 mean shift뿐 아니라 variation 증가까지 감지할 수 있습니다.

## 20. CD-SEM에 VM을 적용할 때 주의점

Process chamber의 TTTM과 CD-SEM의 TTTM은 구분해야 합니다. CD-SEM
measurement은 다음과 같습니다.

```text
CD_measured = CD_true + Bias_SEM + ε
```

생산 wafer의 raw CD distribution을 Tool A/B 사이에서 바로 비교하면 실제
process variation(CD_true)을 SEM matching error로 잘못 판단할 수 있습니다.
따라서 CD-SEM에서는 raw CD보다 measurement residual을 사용하는 것이 더
적절합니다.

```text
r = CD_tool − CD_reference
  = CD_tool − ĈD_true
```

이 residual distribution을 tool 간에 비교합니다.

## 21. 추천 CD-SEM Fleet Matching Architecture

현대적인 CD-SEM TTTM 시스템은 다음과 같이 4개의 layer로 구성할 수 있습니다.

```text
┌──────────────────────────────────────┐
│ 4. Continuous Monitoring / RCA       │
│    Drift / anomaly / image / param   │
├──────────────────────────────────────┤
│ 3. Parameter Optimization            │
│    AMP / Recipe parameter optim.     │
├──────────────────────────────────────┤
│ 2. Fleet Matching                    │
│    Wasserstein / DBSCAN / Clustering │
├──────────────────────────────────────┤
│ 1. Ground Truth / Physics            │
│    ABBA / self-ABBA                  │
└──────────────────────────────────────┘
```

## 22. Layer 1: Ground Truth

ABBA를 버리는 것이 아니라 reference measurement로 유지합니다. 목적은 다음과
같습니다.

- Tool intrinsic bias 확인
- Carryover 제거
- Matching uncertainty 확인
- Fleet algorithm calibration
- Periodic audit

즉 ABBA는 현대적인 fleet 분석에서도 ground-truth layer 역할을 할 수 있습니다.

## 23. Layer 2: Fleet Matching

각 measurement에 대해 다음과 같은 residual dataset을 만듭니다.

```text
r_{i,l,p,r,w}
```

각 index의 의미는 다음과 같습니다.

- i: Tool
- l: Layer
- p: Pattern
- r: Recipe / AMP
- w: Wafer / Site

## 24. 최소 3개의 Matching Metric

단순 mean bias 하나보다 최소 다음 세 가지를 같이 보는 것이 좋습니다.

```text
Mean bias        D_μ,i = |μ_i − μ_fleet|
Variance diff.   D_σ,i = |log(σ_i / σ_fleet)|
Distribution     D_W,i = W₁(P_i, P_fleet)
```

## 25. Composite T2T Matching Score

최종적으로 하나의 score가 필요하다면 다음과 같이 정의할 수 있습니다.

```text
S_i = w_μ·D_μ,i + w_σ·D_σ,i + w_W·D_W,i     (w_μ + w_σ + w_W = 1)
```

예를 들어 w_μ = 0.5, w_σ = 0.2, w_W = 0.3입니다. 단, weight는 실제 matching
requirement와 ABBA ground truth를 이용해 calibration하는 것이 바람직합니다.

## 26. Layer 3: Parameter Optimization

Matching residual과 AMP / recipe parameter 관계를 학습합니다.

```text
Input                    → Matching Model → Predicted T2T Score
 ├─ Tool
 ├─ Layer
 ├─ Pattern
 ├─ Magnification
 ├─ Focus
 ├─ Stigma
 ├─ Threshold
 ├─ Beam condition
 └─ AMP parameters
```

최적화 문제는 다음과 같이 정의할 수 있습니다.

```text
θ* = argmin_θ S(θ)
```

최종 결과는 예를 들어 다음과 같은 형태가 될 수 있습니다.

```text
Tool 17
  Current      AMP1 = 1.03   AMP2 = 0.97    AMP3 = 1.01
  Recommended  AMP1 = 1.01   AMP2 = 0.985   AMP3 = 1.005
  Expected T2T score  0.28 nm → 0.08 nm
```

## 27. Layer 4: Continuous Monitoring

시간축을 추가하면 S_i(t)를 지속적으로 monitoring할 수 있습니다.

```text
Matching Score
0.4 |                        ●
    |                     ●
0.3 |                  ●
    |
0.2 |       ● ● ● ● ●
    | ● ● ●
0.1 |
    +---------------------------
      time
```

이를 이용해 다음을 탐지할 수 있습니다.

- Sudden shift
- Gradual drift
- Variance increase
- Pattern-specific degradation
- Layer-specific degradation
- Tool-specific anomaly

## 28. 최종적으로 추천하는 분석 구조

18개 CD-SEM을 가정하면 다음 분석 pipeline이 실용적입니다.

```text
Raw CD Data
    ↓
Condition normalization
    ↓
Tool / Layer / Pattern / Recipe grouping
    ↓
Residual calculation
    ↓
┌─────────────────────────────┐
│ Mean Bias                   │
│ Variance                    │
│ Wasserstein Distance        │
│ Pairwise Distance           │
└─────────────────────────────┘
    ↓
18 × 18 Distance Matrix
    ↓
┌──────────────┬──────────────┐
│ Clustering   │ MDS / PCA    │
└──────────────┴──────────────┘
    ↓
Fleet Consensus
    ↓
Tool Difference Score
    ↓
Mixed-effect Analysis
    ↓
Tool × Layer / Pattern RCA
    ↓
AMP / Recipe Optimization
    ↓
Continuous Monitoring
```

## 29. TTTM 발전의 핵심 변화

| 시기 | 질문 | 핵심 기법 |
| --- | --- | --- |
| 2009 | How accurately can I measure Tool A-B? | ABBA, carryover correction, measurement uncertainty |
| 2024 | Which recipe parameters make the new tool match the fleet? | Historical matching data, recipe parameters, optimization |
| 2025 | Without trusting one golden tool, which member of the fleet is different? | Fleet consensus, DBSCAN, Wasserstein distance, multivariate analysis |
| 2026 | Can I detect matching degradation before sparse physical metrology catches it? | Virtual Metrology, distribution matching, continuous monitoring, anomaly detection, RCA |

## 30. 결론

현대적인 CD-SEM Tool-to-Tool Matching은 단순히 `CD_ToolB − CD_ToolA`를
계산하는 문제가 아닙니다. 보다 일반적으로 다음과 같은 conditional
multivariate problem으로 볼 수 있습니다.

```text
TTTM = f(Tool, Layer, Pattern, Recipe, AMP, ImageQuality,
         BeamSampleInteraction, Time)
```

따라서 새로운 TTTM 시스템을 구축한다면 다음 구조가 적합합니다.

```text
ABBA Ground Truth
  + Fleet Distribution Matching
  + Tool-to-Tool Distance Matrix
  + Mixed-effect / Interaction Analysis
  + Recipe Parameter Optimization
  + Time-series Anomaly Detection
```

핵심적인 변화는 다음과 같이 정리할 수 있습니다.

```text
Pairwise matching → Fleet matching → Data-driven matching
→ Continuous predictive matching
```

ABBA는 오래된 방법이지만 버려지는 것이 아니라, 현대적인 fleet matching
algorithm을 검증하기 위한 physics-based ground truth로 활용하는 것이 가장
적절합니다.

## 구현 관점 참고

본 문서의 기법을 현재 저장소의 TTTM 페이지에 적용하는 방안은
`tttm-page-implementation-review.md`(동일 폴더)를 참고하십시오.

## References

1. Kawada, H. et al. (2009), Methodologies for Evaluating CD-matching of CD-SEM
2. Weisbuch et al. (2021), Investigating SEM-contour to CD-SEM matching
3. Mack et al. (2021), Diagnosing and removing CD-SEM metrology artifacts
4. Pradelles et al. (2023), Can remote SEM contours be used to match various SEM tools in fabs?
5. Baram et al. (2024), Data driven CDSEM fleet matching in sub-Å era
6. Samsung Semiconductor India Research / Samsung Electronics (2025), Tool-to-Tool Matching Analysis Based Difference Score Computation Methods for Semiconductor Manufacturing
7. Kim et al. / Gauss Labs (2026), A virtual metrology-driven tool-to-tool matching: toward early anomaly detection and diagnosis
