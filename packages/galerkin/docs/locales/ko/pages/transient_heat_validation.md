# 과도 열전도 검증 계약

[English](../../../transient_heat_validation.md) · [사용법](transient_heat.md)

## 실행 경계

이 제출에는 구현, producer 계약 시험, 추가 analytic reference와 고정 수렴 프로그램이
있습니다. **새 Python parse/import/compile, 단위·수치·source·전체·설치·플랫폼 검사는
모두 미실행입니다.** 정적 source 검토는 수치 수용이 아닙니다. 이 단계에서 보고할
실제 제품 오차·차수·성공 검사·설치 artifact는 없습니다. 아래 수학적 기대 정답은
결과가 아닙니다. 기존 정상 시험과 이전 소형 설계 진단을 과도 제품 시험으로 인정하지
않습니다. 통합 전 별도 독립 수용과 release 회귀가 필요합니다.

## 정답 경계와 대수

Producer는 기존 형상·조립·미분 helper를 읽기 전용으로 import하며 anchor가 필요한
정상 솔버를 호출하지 않습니다. 새 refsol.transient_heat는 NumPy와 표준 라이브러리
dataclasses만 import하며 engine이나 다른 reference helper는 import하지 않습니다.
소형 dense p1_matrices는 local gradient, consistent mass와 stiffness를 별도
유도합니다. Local 메시 유효성만 검사하며 전체 교차 검사는 하지 않으므로 caller가
유효한 메시를 제공해야 합니다. Dense spectral helper는 작은 reference 메시용이며
대규모 생산 해석용이 아닙니다.

Reference 계열은 uniform_insulated, moving_affine, sine_manufactured,
부모 구현과 무관한 소형 P1 matrix, smallest_dirichlet_mode,
backward_euler_amplitude입니다. Reference field 객체는 temperature_k,
heat_flux_w_m2, heat_source_w_m3, temperature_gradient_k_m를 가집니다.
Semidiscrete mode는 연속 PDE 고유함수와 의도적으로 구분합니다. 별도 독립 수용은
producer/refsol 값을 자기 정답으로 채택하면 안 됩니다.

아래 기준은 모두 producer 실행 전에 고정되었습니다. 실패에 맞춰 메시·시간 grid·부호·
스케일·허용치·제외 사례를 바꾸지 않습니다. 실패 후보와 근거를 보존합니다. 근거가
명시된 정당한 구현 수정은 같은 gate로 검사하며 최초 통과로 바꿔 부르지 않습니다.
Skip/xfail은 수용을 대신할 수 없습니다.

## 정확한 대조

| 대조 | 필요한 관측 |
|---|---|
| 단열 균일 T=T0+(Q0/c)*(t-t0) | 임의의 유한 양의 dt와 부호 있는 Q에서 정확; 인공 anchor 없음, q=0, reaction=0 |
| 분리된 단열 성분 | 개별 초기 상수/source 평형; 정상 nullspace 규칙으로 거절하지 않음 |
| 이동 affine T=290+5*x+3*(t-t0), Q=3*c | 정확한 P1 장/BE 미분, q=(-5*k,0); 양쪽 M_FC 항과 경계 storage |
| 이산 시간 T=300+t+t² | 오른쪽 source c*(1+t_n+t_n-1), 연속 미분 c*(1+2*t_n)이 아님; f0는 표본화하되 진화에는 미사용 |
| 초기/BC/T를 같은 상수로 shift | flux/storage/reaction 불변; H는 선형 shift, V는 불변 아님 |
| 명시적으로 mm 등에서 같은 m로 길이 변환 | 물리 정답 불변; 자동 단위 추론 없음 |
| 32eps 안/밖 초기 데이터 | 수용 초기 장을 정확히 보존; 범위 밖을 projection 없이 거절 |
| Callback/선형 해석/history 실패 | 원래 chained cause, 시간 index/value, 부분 성공 없음 |

등록한 대수 스케일은 Tscale=max(1K, amplitude/change), rate 스케일에
sum(abs(f))+sum(abs(r))+sum(abs(M*dT/dt)) 포함, heat 스케일 c*area*Tscale,
flux k*Tscale/L, mass c*area입니다. 상쇄되는 순하중이나 절대 Tref로 정규화하지
않습니다. 정확한 균일/affine 장, 독립 M/f/storage/reaction, 원래 자유 residual,
성분/전체 평형, H/V와 BE-product 검사 정규화 오차<=1e-10이 필요합니다.
명시적 SI 변환은<=1e-9입니다.

무강제 균질 perturbation에서는 전체 이차 항등식을 검사합니다.

```text
(V_n-V_n-1)/h_n
+ .5*(T_n-T_n-1)^T*M*(T_n-T_n-1)/h_n
+ T_n^T*K*T_n
= T_n·(f_n+r_n)
```

각 항의 단위는 W K/m입니다. 저장 열량 방정식이 아닙니다. 0 Dirichlet 또는 단열인
균질 무강제 조건에서 V는 증가할 수 없습니다. 이동/0이 아닌 경계나 강제 항으로
확장하면 안 됩니다. H 평형은 storage와 outward=-sum reaction을 사용해야 합니다.
독립 복원한 셀 법선 flux와 유한 메시 약형 thermostat rate가 같아야 하는 것은 아닙니다.

## 고정 시간 gate

단위 정사각형 메시의 각 변 분할수는 정확히 n8입니다. M/K를 독립 조립하고 외곽을
모두300K로 고정한 Dirichlet 일반화 문제의 가장 작은 양의 mode를 선택합니다.
max(abs(phi))=1로 정규화하며 진폭1K, t0=0, tau=1/lambda입니다.
tau까지 steps8/16/32/64에서 다음을 사용합니다.

```text
T_F,exact(t) = 300 + exp(-lambda*t)*phi
T_F,BE(t_n) = 300 + product_j(1+lambda*h_j)^(-1)*phi
```

구현과 이산 product를 대수<=1e-10으로 비교하고, 끝점을 exp와 비교해 시간 오차만
측정합니다. 마지막 두 시간 차수는 각각 .9부터1.1이어야 합니다. 연속체 공간 오차를
제거한 것이며 PDE 세분화 결과가 아닙니다. 단열 0-mode 대조는 별개이며 tau=1/0을
사용하지 않습니다. 불규칙 dt product는 추가 재사용/끝점 대조입니다.

## 고정 PDE 공간·분리 gate

단위1m 정사각형, k=2.5W/(m K), c=4J/(m³ K), 진폭1K입니다.

```text
T = 300 + (1+.7*t)*sin(pi*x)*sin(pi*y)
Q = [c*.7 + 2*k*pi^2*(1+.7*t)]*sin(pi*x)*sin(pi*y)
q = -k*(1+.7*t)*grad(sin(pi*x)*sin(pi*y))
```

초기 데이터는 정확한 절점 T이며 외곽은300K입니다. n8/16/32/64와 동일한
dt1/256s로1s까지 해석하고 .25,.5,1s에서 관측합니다. 각 관측 시간의 마지막 두 메시
구간 각각에서 T L2 차수>=1.8, flux L2>=.9가 필요합니다. Norm 구적8/10은 측정한
0이 아닌 오차의1% 이내로 일치해야 합니다. 가장 미세한 n64의 dt1/512 companion은
각 온도/flux 오차를 기본 오차의5% 이내로만 바꿔야 합니다. 분리가 실패하면 실패로
기록하며 조정한 시간 sequence로 대체하지 않습니다. 연속체 시간 의존성이 affine라도
공간 일관성에서 생기는 모든 semidiscrete 시간 transient가 사라지지 않습니다.
초기·시간·공간 오차를 구분해야 합니다.

## 지정한 잘못된 변형과 수명 거절

| 잘못된 구현 | 판별 기준 |
|---|---|
| Lump mass | 정확한 삼각형 비대각/generalized mode; 양수성 대체 금지 |
| Old/new/양쪽 M_FC 생략 | 이동 affine 내부 값과 전체 residual |
| 왼쪽/평균 source 또는 f0 재사용 | 비상수 이산 시간 source 대조 |
| Residual=K*T-f만 사용 | Storage를 포함한 약형 절점 reaction과 평형 |
| 정상 평형 또는 outward 부호 오류 | 단열 가열/이동 BC의 content 평형 |
| V를 J/m 열량으로 표기 | H 선형성/shift, V 이차 항등식/단위 |
| 잘못된 dt factorization 재사용 | 비균일 step mode product |
| 인공 anchor 또는 clamp | 단열/분리 성분과 부호 있는 음의 K 사례 |
| 초기 projection 또는 가짜 t0 rate | 정확한 초기 보존, Nt-1 rate shape |
| 실패 context 누락/부분 성공 | t0/후속 BC/source/solve/최종 복사 fault 사례 |

Producer 계약 파일은 기본 계약, 원래 계 감사와 소형 reference 검사를 다룹니다.
모든 독립 wrong variant를 이미 주입·거절했다는 주장이 아닙니다. 지정 mutation 실행과
독립 물리 증명은 미완료입니다. 기존 gate는 변경하지 않습니다.

## 향후 재현과 배포 경계

기존 의존성을 사용할 수 있는 저장소 루트에서 실행합니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m pytest -q packages/galerkin/tests/test_transient_heat.py packages/galerkin-refsol/tests/test_transient_heat_reference.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python packages/galerkin/examples/transient_heat_convergence.py
python -m pytest -q
```

수렴 프로그램은 고정 시간/공간/분리 gate를 assert한 뒤 성공한 결합 JSON 보고서를
만들며 정해 놓은 통과를 출력하지 않습니다. 요청 history를 모두 보존하므로 n64
companion에 상당한 메모리가 필요합니다. 실행 시간은 전용 호스트 성능 기준선이 아닙니다.

후속 설치 검사는 실제 sdist->wheel artifact를 만들고 설치 패키지 출처/source 바이트와
EN/KO·예제 포함을 확인한 뒤 source 밖 계약/물리 consumer를 실행해야 합니다.
현재 build/install 또는 배포 포함을 검증하지 않았습니다. 공유 release helper/manifest를
변경하지 않았습니다. Windows, 독립 수용, 전체 회귀와 release 통합에는 각각 실제
근거가 필요합니다. Actions나 배포 결과를 의미하지 않습니다.
