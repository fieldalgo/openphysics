# 레퍼런스 도구 비교

[English](../../../reference-comparisons.md) | **한국어**

몇몇 문제를 galerkin과 독립된 유한요소 도구로 두 번 풉니다. 비교 결과는 각 기능의 해석해
수용 기준과 따로 기록하며, 해석해 기준은 그대로 둡니다.

- **같은 이산화**(같은 메시·요소·계수·경계 자료): 두 도구가 같은 이산해를 내야 합니다.
  상대 차이 기준은 `1e-9`로, 반올림 오차보다 훨씬 크고 이산화 오차보다 훨씬 작습니다.
  조립·경계 처리·풀이를 코드끼리 확인합니다.
- **다른 이산화**(다른 요소 차수나 구적): 차이를 보고만 하고 기준을 두지 않습니다.

도구끼리 일치하는 것은 수렴 근거가 아닙니다. 수렴과 정확도 주장은 여전히 해석해와 메시
세분화 연구에서 나옵니다.

## 도구

| 도구 | 버전 | 라이선스 | 쓰는 방식 |
|---|---|---|---|
| [scikit-fem](https://github.com/kinnala/scikit-fem) | `>=12,<13`, CI는 12.0.2 고정 | BSD-3-Clause | 시험 전용 extra `galerkin[crosscheck]`에서 시험 코드가 import |
| [symfem](https://github.com/mscroggs/symfem) | `==2025.12.0`(CI의 sympy는 1.14.0) | MIT(sympy: BSD-3-Clause AND MIT) | 같음. [요소 정의](#요소-정의)에만 사용 |

시험 extra로 설치하고 CI에서 돌리는 도구는 정한 대로 허용형 라이선스 도구뿐입니다
([제3자 소프트웨어](third-party.md) 참고). 약한 copyleft(NGSolve 같은 LGPL)나 GPL 도구는 이
저장소에서 import하거나 설치하지 않습니다. 비교한다면 따로 설치한 수정 없는 프로그램을 자기 환경과
프로세스에서 돌리고, 수치 결과만 보고합니다. AGPL 도구는 쓰지 않습니다.

## 실행

```bash
python -m pip install -e "packages/galerkin[crosscheck]"
OPENPHYSICS_CROSSCHECK_DIR=.validation/crosscheck \
  python -m pytest -q packages/galerkin/tests/test_crosscheck_skfem.py \
    packages/galerkin/tests/test_crosscheck_skfem_lossy_cavity.py \
    packages/galerkin/tests/test_crosscheck_skfem_multimaterial.py \
    packages/galerkin/tests/test_crosscheck_symfem_elements.py
```

도구가 없으면 로컬에서는 시험을 건너뜁니다. CI는 `OPENPHYSICS_REQUIRE_CROSSCHECK=1`을
설정해 도구가 없으면 실패하게 하고, 기록을 Linux job artifact의 `.validation/crosscheck/`에
남깁니다.

## 기록 형식

비교마다 JSON 기록 하나(스키마 `openphysics.crosscheck/1`)를 JUnit 출력에 찍고, 원하면
파일로도 씁니다. 도우미는 `packages/galerkin/tests/crosscheck.py`입니다.

| 필드 | 내용 |
|---|---|
| `case`, `physics` | 사례 식별자와 푼 문제 |
| `openphysics` | 배포판, 설치된 버전, API, 이산화 |
| `reference` | 도구, 설치된 정확한 버전, SPDX 라이선스, 출처 URL, 쓰는 방식, 이산화 |
| `matched` | 똑같이 맞춘 조건(메시·요소·계수·경계 자료·형식) |
| `not_matched` | 알려진 차이(요소 차수·구적·고유값 풀이기) |
| `observables` | 관측량마다 이름, 단위, 지표, 값, 기준(`null`은 보고만), 통과 여부 |
| `analytical_acceptance` | 기능의 해석해 pass/fail이 있는 곳. 비교가 이를 대신하지 않음 |
| `wall_time_s` | 도구별 조립·풀이 시간 |
| `not_measured` | 기록이 다루지 않는 것(현재는 최대 메모리. 한 프로세스를 같이 쓰므로 도구별로 나눌 수 없음) |
| `environment` | Python, 플랫폼, numpy·scipy 버전 |
| `role` | 항상 `code-to-code comparison; not convergence evidence` |

## 현재 사례

로컬 Linux 실행 값입니다(Python 3.12, numpy 2.5.4, scipy 1.18.1, scikit-fem 12.0.2).
커밋마다의 CI 기록이 기준입니다.

| 사례 | galerkin | scikit-fem | 관측량 | 차이 | 기준 |
|---|---|---|---|---|---|
| `heat-p1-slab` | `thermal.solve_steady_heat`, P1 | `ElementTriP1` | 절점 온도, 요소 열유속 | 2.1e-15, 4.0e-14 | 1e-9 |
| `elasticity-p1-plane-strain-cantilever` | `elasticity.solve_elasticity`, P1 | `ElementVector(ElementTriP1)` | 절점 변위 | 4.5e-13 | 1e-9 |
| `elasticity-p1-plane-stress-cantilever` | 같음, 평면응력 | 같음 | 절점 변위 | 8.2e-14 | 1e-9 |
| `waveguide-vector-rect-core` | `waveguide.solve_modes`, Nedelec x P1 | `ElementTriN1 * ElementTriP1` | 유효 굴절률, 도파 모드 4개 | 1.5e-15 | 1e-9 |
| `cavity-pec-box` | `cavity.solve_cavity_box`, Nedelec 사면체 | `ElementTetN0` | 가장 낮은 고유값 k^2 8개 | 1.4e-14 | 1e-9 |
| `cavity-lossy-slab` | `material_cavity.solve_material_cavity_box`, 사면체별 복소 eps/mu | `ElementTetN0`, 재료별 조립 | 복소 k^2 6개; Q | 4.1e-15; 9.2e-14 | 1e-9 |
| `cavity-impedance-walls` | 같음, z1·x0 Leontovich 벽 | `ElementTetN0` + `FacetBasis` 접선 질량, galerkin의 `k0`에서 고정한 `T(k)` | 고정점의 복소 k^2 3개 | 6.8e-13 | 1e-9 |
| `heat-p1-three-region-wall` | `thermal.solve_steady_heat`, P1, 영역별 k·Q | `ElementTriP1`, 삼각형별 k·Q | 절점 온도, 요소 열유속 | 2.0e-15, 3.1e-13 | 1e-9 |
| `elasticity-p1-plane-strain-three-region-bar` | `elasticity.solve_elasticity`, P1, 영역별 E·nu | `ElementVector(ElementTriP1)`, 삼각형별 Lamé 상수 | 절점 변위, 요소 응력 | 3.7e-13, 3.2e-13 | 1e-9 |
| `elasticity-p1-plane-stress-three-region-bar` | 같음, 평면응력 | 같음 | 절점 변위, 요소 응력 | 1.6e-12, 1.0e-12 | 1e-9 |
| `thermoelasticity-p1-plane-strain-three-region-bar` | `thermoelasticity.solve_thermoelasticity`, P1, 영역별 alpha·E·nu | 같음, 열하중 `beta (T_h - Tref) div v` | 절점 변위, 요소 응력 | 4.0e-13, 2.0e-13 | 1e-9 |
| `thermoelasticity-p1-plane-stress-three-region-bar` | 같음, 평면응력 | 같음 | 절점 변위, 요소 응력 | 4.4e-13, 2.7e-13 | 1e-9 |
| `transient-heat-p1-three-region-wall` | `transient_heat.solve_transient_heat`, P1, 영역별 k·c·Q | `ElementTriP1` 강성·일관 질량, 시험 안의 backward Euler | 저장된 모든 시각의 절점 온도 | 1.2e-15 | 1e-9 |
| `heat-p2-reference-slab` | P1 | `ElementTriP2` | 꼭짓점 온도: P1 대 P2, P1 대 해석해, P2 대 해석해 | 3.7e-5, 3.6e-5, 1.5e-6 | 보고만 |
| `elasticity-p2-reference-cantilever` | P1, 평면응력 | `ElementVector(ElementTriP2)` | 끝단 처짐, P1 대 P2 | 1.7e-1 | 보고만 |

P2 행은 성긴 메시에서 요소 차수가 주는 예상된 차이(P1 삼각형은 굽힘에 뻣뻣함)를 보여 줄 뿐,
어느 도구의 정확도 주장도 아닙니다.

## 요소 정의

[symfem](https://github.com/mscroggs/symfem)은 유한요소를 정의 그대로 만들고 정확한 유리수
연산(sympy)으로 적분합니다. DefElement가 다른 라이브러리를 검증할 때 쓰는 기준입니다.
`test_crosscheck_symfem_elements.py`는 유리수 좌표와 뒤섞은 절점 번호를 쓴 작은 메시 두 개에서
galerkin의 요소 정의와 요소 행렬을 symfem과 비교합니다. 삼각형 6개(둔각·가는·시계 방향 삼각형
포함)와, 내부 변 하나를 둘러싼 사면체 4개입니다. 엔진은 symfem을 import하지 않습니다
(`test_independence.py`).

먼저 두 코드와 독립적으로 관례를 정확히 확인합니다. 각 셀의 꼭짓점을 전역 절점 번호 오름차순으로
symfem에 넘기고, symfem Nedelec 함수 각각을 셀의 각 변을 따라 낮은 번호에서 높은 번호 방향으로
선적분한 순환을 여기서 sympy로 계산합니다. 결과가 단위 행렬이므로 symfem의 자유도는 부호나
스케일 변환 없이 galerkin의 자유도(단위 접선 순환, 낮은 절점 번호 → 높은 번호)와 같습니다.
P1 함수는 꼭짓점에서 크로네커 델타와 같습니다. 두 확인 모두 정확한 값(기준 0)입니다. 시험은
galerkin의 전역 변이 낮은 번호에서 높은 번호로 향하는지, 두 지역 방향이 모두 나오는지도
확인합니다.

그다음 전역 행렬을 항목별로 비교합니다(상대 기준 `1e-12`. float64와 정확한 유리수의 차이는
약 `1e-16`). 방향 규칙의 부호 반전, 잘못된 질량 스케일, P1 질량 한 항목의 `1e-7` 변경은 각각
이 시험에서 실패합니다.

| 사례 | 관측량(galerkin API) | 차이 | 기준 |
|---|---|---|---|
| `elements-p1-nedelec-triangles` | 변 순환 - 단위 행렬, P1 꼭짓점 값 - 델타 | 0, 0 | 정확 |
| | P1 기울기(`postprocess.element_gradient`), 강성, 질량 | 1.1e-16, 9.8e-17, 1.0e-16 | 1e-12 |
| | 중심의 Nedelec 값(`edge.eval_edge_field`), curl-curl, 질량, 변 x P1 기울기 결합 | 1.7e-16, 3.6e-16, 1.1e-16, 1.6e-16 | 1e-12 |
| `elements-p1-nedelec-tetrahedra` | 변 순환 - 단위 행렬, P1 꼭짓점 값 - 델타 | 0, 0 | 정확 |
| | P1 기울기(`assembly3d.tet_gradients`), 강성, 질량 | 2.0e-16, 1.6e-16, 7.8e-17 | 1e-12 |
| | 중심의 Nedelec 값(`edge3d.eval_edge_field_3d`), curl-curl, 질량, 변 x P1 기울기 결합 | 2.3e-16, 1.0e-16, 1.2e-16, 1.5e-16 | 1e-12 |

symfem 2025.12.0, sympy 1.14.0으로 로컬 Linux에서 실행한 값입니다. P1 하중 벡터(galerkin은
한 점 중심 구적을 씀)와 P1 경계 질량은 비교하지 않습니다. 기호 적분은 코어 하나에서 약 20초
걸립니다.

## 사례 추가

1. 같은 문제를 galerkin 공개 API와 레퍼런스 도구로 풉니다.
2. 맞출 수 있는 것은 모두 맞추고 `matched`에 적으며, 남은 차이는 모두 `not_matched`에 적습니다.
3. 같은 이산화의 관측량에만 `SAME = 1e-9` 기준을 두고, 나머지는 `gate=None`으로 보고합니다.
4. 새 도구라면 `galerkin[crosscheck]`, CI 고정 버전, 라이선스 목록,
   [제3자 소프트웨어](third-party.md)에 추가합니다.
5. 이 표를 영어·한국어로 함께 고칩니다.
