# 처방 온도장 열탄성: 2D 기계 단계

[영문 원문](../../../prescribed_temperature_thermoelasticity.md)

현재 브랜치에 영문 파일이 아직 없는 경우에는 [고정 영문판](https://github.com/fieldalgo/openphysics/blob/0c9237b2dfcfabd59fa0d14091bbb1e7165eda80/packages/galerkin/docs/prescribed_temperature_thermoelasticity.md)을 참조합니다. 이 링크는 번역 원본이며 새 검증 결과가 아닙니다.

아래 실행 수치·실패·미검증 서술은 영문 원문의 해당 후보 시점 기록이며 새 수용 결과를 뜻하지 않습니다.

이 재사용 가능한 정적 기계 단계는 사용자가 명시한 절점 P1 절대 온도장을 받습니다. 열전도 solver를 호출하거나 열 결과를 자동 연결하거나 온도 출처를 인증하거나 완전한 순차 heat-to-mechanics workflow를 검증하지 않습니다. `galerkin.thermoelasticity`와 `refsol.thermoelasticity`에서 import하며 공용 package export는 필요하지 않습니다.

## API와 SI 계약

```python
snapshot = freeze_temperature(mesh, temperature_k)
result = solve_thermoelasticity(
    mesh, snapshot, reference_temperature_k=293.15,
    thermal_expansion_per_k=12e-6, young_modulus=70e9,
    poisson_ratio=0.3, plane="strain",
    dirichlet={(0, 0): 0., (0, 1): 0., (nx, 1): 0.})
```

이 예제의 지지는 원래 절점 순서를 유지한 `rectangle_mesh(1., 1., nx, ny)`를 가정합니다. 완전한 실행 예제는 `examples/prescribed_temperature_thermoelasticity.py`입니다. 좌표·변위는 m, Young 계수·응력은 Pa, 변형률은 무차원이고 alpha는 부호를 가질 수 있는 1/K입니다. T는 K 단위의 유한 비음수 실수 `(N,)` 배열, Tref는 유한 비음수 실수 스칼라 K입니다. 냉각, alpha=0과 음수 alpha를 허용합니다. 유한한 E>0, -1<nu<0.5와 명시적 plane=`"stress"` 또는 `"strain"`이 필요합니다. 섭씨 변환, 스칼라 온도 broadcast 또는 단위 추론은 없습니다.

체적력은 유한한 2성분 벡터 또는 `(Q,2)` 좌표를 받아 `(Q,2)` 힘 밀도 N/m^3를 반환하는 callable입니다. 탄성 체적 하중과 같은 축당 6점 Duffy 구적법으로 적분합니다. 메시는 벡터 절점 변위를 갖는 삼각형이며 DOF 순서는 `[ux0, uy0, ux1, uy1, ...]`입니다. Dirichlet는 외곽 `(node, component)`를 변위 m에 대응시킵니다. 성분은 0=x, 1=y입니다. 적용한 traction 매핑이 없으면 나머지 성분에는 **총 열탄성 natural traction이 0**입니다. 선택적인 전역 Cartesian total-traction 매핑은 [traction 계약](thermoelastic_traction.md)을 참고하세요. 스칼라 pressure 전용·로컬 프레임·follower API는 없지만 고정 경계에서 전역 Pa callback `lambda points_m, normals: -p * normals`는 유효합니다.

하중·반력은 면외 두께당 선하중 N/m입니다. 실제 두께(m)를 곱하면 N입니다. 물리적 탄성에너지는 J/m이며 두께를 곱하면 J입니다. 이 힘의 모멘트는 N, 즉 두께당 모멘트입니다. 열 등가 하중은 약형의 기여 항이며 추가적인 물리적 외력이 아닙니다. 체적 하중과 지지 반력을 구분해 보고합니다.

## 동결 장의 식별

`TemperatureSnapshot`은 좌표, connectivity, 절점·요소 순서와 T를 canonical little-endian float64/int64의 immutable bytes-backed 배열로 복사합니다. schema1, `length_unit="m"`, `temperature_unit="K"`와 mesh·temperature·combined 재현 fingerprint를 저장합니다. fingerprint는 version tag와 length framing을 갖는 FNV-1a64 checksum이며 암호학적 서명이나 출처 인증이 아닙니다. 실제 메시 배열도 정확히 비교하므로 checksum 충돌로 다른 기하를 허용할 수 없습니다. 동일 배열을 복사한 메시는 허용하지만 좌표, scale, 순서, connectivity, schema, 단위나 동결 데이터를 바꾸면 거절합니다. 원래 온도 입력 배열을 변이해도 snapshot은 유지되며 온도를 바꾸려면 다시 freeze해야 합니다. 이 API는 잘못 표시한 단위를 탐지하거나 직접 입력의 취득 경위를 인증하지 못합니다. Python의 의도적인 저수준 객체 변이는 불변성 계약 밖이며 검출한 metadata·배열·checksum 손상은 거절합니다.

## 구성식 축약과 약형

 e=(exx,eyy,gamma_xy), gamma_xy=2epsilon_xy, m=(1,1,0), a=alpha(T-Tref)로 둡니다. 응력 순서는 (sigma_xx,sigma_yy,tau_xy)이므로 e dot sigma는 텐서 수축입니다. D는 통상적인 등방 축약 engineering-shear 행렬이며 D33=mu=E/[2(1+nu)]입니다. 법선 성분 block은 평면응력에서 `E/(1-nu^2) * [[1,nu],[nu,1]]`, 평면변형률에서 `E/((1+nu)(1-2nu)) * [[1-nu,nu],[nu,1-nu]]`입니다.

총 면내 응력은 sigma=D e-q m이며 다음을 사용합니다.

| 축약 | q | 면외 총 변형률·응력 |
|---|---|---|
| 평면응력 | E a/(1-nu) | sigma_zz=0; epsilon_zz=((1+nu)a-nu(exx+eyy))/(1-nu) |
| 평면변형률 | E a/(1-2nu) | epsilon_zz=0; sigma_zz=lambda(exx+eyy)-q |

lambda=E nu/[(1+nu)(1-2nu)]는 원래 3D Lamé 상수입니다. 물리적 열변형률은 3D에서 aI이며 각 법선 성분이 3a인 것이 아닙니다. 두 축약 모두 물리적 면내 탄성 변형률은 e-a m입니다.

정적 평형은 -div(sigma)=b입니다. P1 벡터 B와 단위 두께 면적에 대해 K=integral B^T D B dA는 선형탄성과 같으며 다음과 같습니다.

`K u = f_body + g_thermal`, `g_thermal = +integral B^T q m dA`.

양의 부호와 경계 기여가 중요합니다. 이 항을 열 체적력만으로 대체하면 균일 온도의 자유 팽창을 잃습니다. B는 상수이고 각 삼각형의 q는 선형이므로 centroid 온도로 g를 정확히 적분합니다. Dirichlet 소거는 성분별 지지를 유지하고 분리된 각 연결 성분에 남는 강체 모드를 거절합니다.

## 결과 위치, 재구성과 에너지

`displacement`의 shape은 `(N,2)`입니다. `total_strain`은 요소별 상수 `(M,3)`입니다. `thermal_strain`, `elastic_strain`, `stress`는 centroid의 `(M,3)`, `sigma_zz`와 `epsilon_zz`는 centroid의 `(M,)`입니다. `load_external`, `load_thermal`, `reaction`, `residual`은 별개의 `(N,2)` 배열입니다. `load_total`은 앞의 두 하중을 더한 값입니다. 반력은 처방 DOF에서만 `Ku-f_body-g`이며 나머지에서 0입니다. residual은 모든 DOF의 값을 유지합니다.

요소의 barycentric 좌표 l에서 T(l)=sum l_i T_i, a(l)=alpha(T(l)-Tref)로 재구성합니다. 열변형률=a(l)m, 탄성 변형률=e-a(l)m, sigma(l)=D e-q(l)m이며 sigma_zz/epsilon_zz는 표의 식을 사용합니다. 따라서 응력은 일반적으로 요소 내부에서 선형입니다. centroid 응력을 완전한 조각별 상수 응력장으로 해석해서는 안 됩니다. 응력 smoothing이나 절점 recovery는 사용하지 않습니다.

`physical_elastic_energy`는 선택한 축약을 적용한 원래 3D 탄성에너지를 적분합니다. 요소 에너지 밀도는 다음과 같습니다.

- PS: `.5 (e-a m)^T D (e-a m)`;
- PE: `.5 (e-(1+nu)a m)^T D (e-(1+nu)a m) + .5 E a^2`.

차수 2에 정확한 3점 삼각형 구적법으로 P1 T의 에너지 밀도를 적분합니다. centroid T의 제곱만 쓰면 과소 적분합니다. 균일한 자유 PE 팽창은 u=(1+nu)a(x,y), 면내 응력 0, sigma_zz=-Ea이며 잔여 에너지 밀도는 `.5 E a^2`입니다. 이 잔여량은 solver 오차가 아니라 물리적 값입니다. 음의 에너지를 0으로 잘라내지 않습니다. 고정 온도 상수 CT를 PS의 `E a^2/(1-nu)` 또는 PE의 `1.5 E a^2/(1-2nu)` 적분으로 정의하면 다음 종점 항등식이 성립합니다.

`U=.5 u^T K u-u^T g+CT`,
`u^T K u=u^T(f+g+r)`,
`integral sigma:e = u^T f+u_D^T r`,
`2U=u^T f+u_D^T r-u^T g+2CT`.

0이 아닌 처방 변위에서도 지지부의 일을 유지합니다. 이들은 고정 온도의 기계 항등식이며 열수지나 열 하중 경로에 따른 일 계산이 아닙니다.

## 독립 검증과 사전 등록 기준

독립 참조 모듈은 생산 구성식·메시 helper·solver를 import하지 않고 원래 3D 법칙을 사용합니다. 네 군은 균일 자유 팽창, 균일 구속, 선형 T 아래의 적합한 2차 변위, 매끄러운 sine MMS입니다. 단위 정사각형의 sine 사례는 S=sin(pi x)sin(pi y), u=(1e-4,0.6e-4)S, T=Tref+20S입니다. 독립 체적력은 `-mu Laplacian(u)-(lambda_eff+mu) grad(div u)+beta grad T`이며 lambda_eff는 PS에서 E nu/(1-nu^2), PE에서 lambda이고 beta는 PS에서 E alpha/(1-nu), PE에서 E alpha/(1-2nu)입니다. 정확한 절점 T를 주입합니다. 이는 보간한 처방 온도장 아래의 기계 수렴이며 열전도 FEM 수렴이 아닙니다.

구현 전에 원래 n=8,16,32와 양쪽 인접 구간의 L2u>=1.8, H1u·응력·기계 에너지 norm>=0.9 기준을 고정했습니다. 독립 8x8 대 10x10 구적 오차 차이는 각 측정 오차의 1% 미만, 해석적 물리 에너지 12x12 대 16x16 일치는 에너지 scale의 1e-8 이내여야 합니다. 정규화 에너지 오차는 단조 감소하고 최종값 <=0.02여야 합니다. 적합 변위 사례는 consistent-mass 강체 평행이동·회전 맞춤만 허용하며 strain·scale·shear를 맞추지 않습니다.

대표 자동 시험 결과는 E=2GPa, nu=.27, alpha12e-6/K, 단위 정사각형입니다. 추가 독립 3D 법칙 검사와 예제는 E70GPa/nu.3을 사용합니다.

| 군 / 축약 | L2u 인접 차수 | H1u 차수 | 응력 차수 | 최종 정규화 에너지 오차 |
|---|---|---|---|---|
| Sine PS | 1.978,1.994 | .993,.998 | 1.007,1.002 | .00177 |
| Sine PE | 1.975,1.993 | .995,.999 | 1.028,1.007 | .00240 |
| Compatible PS | 1.881,1.957 | 1.018,1.012 | .980,.993 | 0을 향해 감소 |
| Compatible PE | 1.879,1.958 | 1.017,1.012 | .982,.994 | 해석적 PE 잔여량을 향해 감소 |

사전 등록한 주 재료값 E70GPa/nu.3도 통과합니다. sine PS의 L2u는 1.978/1.994, H1u는 .993/.998, 응력은 1.007/1.002이고 PE는 각각 1.972/1.992, .996/.999, 1.031/1.008입니다. 최종 정규화 물리 에너지 오차는 PS .001802, PE .002376입니다. Compatible L2u 차수는 PS 1.881/1.958, PE 1.875/1.958이며 H1u·응력·변형률 차수는 모두 .96보다 큽니다. 기준은 조정하지 않았습니다.

나머지 검사는 물리적 3D 에너지·일, 지지부 일, 힘·모멘트 평형, 변·모서리 half-edge 반력, 온도·기준 온도 동시 이동, alpha0에서 기존 탄성과 일치, 냉각·음수 alpha, 중첩, 동결·stale·변조 snapshot, 잘못된 입력·메시와 분리 성분 강체 모드를 다룹니다. 실행 가능한 negative control은 잘못된 열 하중 부호, 체적력만으로의 대체·누락, 세 배 alpha, 잘못된 PE 자유 팽창, 누락되거나 비연성으로 계산한 sigma_zz, centroid-T 제곱 에너지를 거절합니다. 참조 MMS 체적력은 응력 발산의 유한차분과 대조합니다. 실행 기준은 전용 시험을 참조하며 열전도·완전 순차 연성 수용을 주장하지 않습니다.

## 한계와 배포 통합

등방 선형 소변형, 정적 삼각형 P1 변위, 상수 재료·alpha 하나 또는 이름 있는 영역별 구간 상수 alpha·E·nu([multimaterial](multimaterial.md)), 명시적으로 처방한 같은 메시의 절점 P1 T만 지원합니다. 위 기준은 균질 재료를 설명합니다. 근접 비압축성 평면변형률은 locking이 생길 수 있으며 nu가 .5에 접근할 때 입력 검증만으로 해결되지 않습니다. 비선형·대변형·접촉·동적·3D·열전도, 스칼라 pressure 전용·로컬 프레임·follower API, 온도 의존 재료, 교차 메시 전달, simcase·Studio 통합은 포함하지 않습니다. 경계 태그는 단위나 출처를 인증하지 않습니다. callable 체적력은 수치 적분하므로 강하게 진동하는 입력에는 적절한 메시·구적을 독립적으로 확인해야 합니다.

이 문서와 영어 예제는 sdist manifest 및 필수 byte 자산 검사에 포함되어 있습니다. 설치 wheel 소비자 검사는 검증한 archive의 예제를 격리된 Python으로 실행하도록 설정되어 있습니다. 포함 여부와 검사 설정은 실행 결과가 아니므로 정확한 후보의 실제 빌드·설치·검증 결과를 별도로 확인해야 합니다.
