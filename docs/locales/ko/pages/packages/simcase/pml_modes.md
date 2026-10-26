# PML·누설·일정 반경 모드

[English](../../../../../packages/simcase/pml_modes.md) · [복소 재료 모드](lossy_modes.md) · [좌표 정식화](../galerkin/modal_coordinates.md)

`em.modes2d`는 직사각형 영역에서 scalar/full-vector 복소좌표 PML과 일정
반경 굽힘을 지원합니다. 반환값은 물리 공진으로 인증된 결과가 아닌 **후보**입니다.
PML 인공 모드가 포함될 수 있으므로 메시·물리 창·PML 두께·강도를 각각
변경하여 감쇠의 안정성을 확인해야 합니다. 단일 실행은 항상
`stability: "not_checked"`를 보고합니다.

## 입력과 단위

기존 `physics.em1`에 다음 설정을 추가합니다.

```json
{
  "n_target": 2.85,
  "pml": {
    "thickness": {"bottom": 0.5, "top": 0.5},
    "strength": 3.0,
    "order": 2,
    "min_physical_fraction": 0.1
  },
  "bend": {"radius": 5.0, "axis": "y", "origin": 0.0}
}
```

직선에서는 `bend`를 생략합니다. 두께·반경·원점은 선언한 길이 단위,
strength와 비율은 무차원, order는 정수 2/3/4입니다. 생략한 면의 두께는
0이며 하나 이상은 양수여야 합니다. PML 띠를 제외한 물리 창이 남아야 하고
메시가 두 영역을 모두 분해해야 합니다. 선언한 형상에 PML이 포함되므로
재료를 PML까지 연장합니다. PML 외곽은 PEC, 다른 면은 기존 PEC/PMC입니다.
두 방향 모두 재료 경계·PML·장을 충분히 분해해야 합니다. 요소를 가로지르는
PML/물리창 경계는 요소중심 계수와 소속으로 근사하므로 메시 수렴에 포함합니다.

양수 `n_target`을 명시해야 합니다. 닫힌 도파관의 유전체 구간 대신 목표
근처를 검색합니다. vector `n_cladding`은 설명용이며 열린 후보의 분류 기준이
아닙니다. 금속·흡수 재료는 기존 복소 재료 계약을 따릅니다. 굽힘 축은 바깥
방향이고 origin에서의 양수 radius를 지정합니다. 전체 영역의 반경이 양수여야
하며 전파 거리는 기준 호 길이 `z=R theta`입니다.

## API와 결과

```python
from simcase import Document, run
result = run(Document.load("model.json"), verbose=False)
print(result.neff)                       # 복소수, 점 × 모드
print(result.propagation_loss_db_cm())   # 부호를 보존한 총 전력 감쇠
print(result.bend_loss_db_90deg())       # 직선이면 None
print(result.open_boundary)              # 점별 전체 검색 후보
result.save("results")
```

`simcase.physics_em_modes2d.solve(..., n_target=2.85, pml=..., bend=...)`는
기존 메시에서 같은 설정을 메시 길이 단위로 받습니다. `solve_point`와 `run`의
진단 경계 좌표는 문서 단위입니다. JSON은 `openphysics.modes2d/2`, 실수부
`neff`, `neff_imag`를 유지하고 `open_boundary`, 선택적 `bend_loss_db_90deg`를
추가합니다. NPZ는 pickle 없이 복소 배열과 `open_boundary_json`을 저장합니다.
기능 브랜치 구현이 릴리스를 뜻하지는 않습니다.

각 `openphysics.pml-candidates/1` 점은 전체 후보의 1부터 시작하는 번호,
복소 지수, 원래 pencil 상대잔차, 양의 물리/PML L2 비율, 선택 번호와 이유를
기록합니다. 검색 수는 최소 6개 또는 요청 수의 두 배이며 자유 DOF에 제한됩니다.
적격 기준은 양수 실수부, 잔차<=1e-8, 물리 비율>=설정값(기본0.1, 허용0..1),
허수부<=1e-10 max(1,|Re n|)입니다. 적격 후보 중 목표와 가까운 것을 선택하고
첫 점에서 실수부 내림차순으로 반환합니다. 제외·미선택 후보도 기록합니다.
비유한/0 전파근은 저수준 계산을 중단하며 조용히 삭제하지 않습니다.

`abs(Im n)<=1e-10 max(1,|Re n|)`이면 `numerically_unresolved`로 표시하고
부호 있는 값과 감쇠를 보존합니다. 0으로 고치지 않습니다. 이 문턱은 수치적
부호 진단이지 정확도 보증이 아닙니다. 요청보다 적게 찾으면 개수를 명시하며
0개면 `.diagnostics`가 있는 `ModeSelectionError`를 냅니다. 유한 검색은 완전성을
보장하지 않고 비율 문턱만으로 모든 인공 모드를 구분할 수도 없습니다.

## 모드장·정규화·추적

scalar는 물리 절점 peak=1, vector는 물리 요소중심의 최대 |E|=1입니다.
둘 다 상대진폭이며 단위 전력이 아닙니다. 요소 소속은 중심으로 판단합니다.
`pml-vector-edge-nodal-v1`에서 transverse는 계산 좌표의 공변 edge 선적분
(늘림 없는 물리창에서는 실제 Et), longitudinal은 h로 나눈 실제 Ez 절점값,
electric은 각 Jacobian 성분으로 나눈 요소중심 장입니다. PML 내부 장은
인공적입니다. scalar 표현은 `pml-scalar-nodal-v1`입니다.

양의 L2 진단은 transverse 계산좌표 edge mass와 실제 Ez의 절점보간을 씁니다.
물리창에서 sx=sy=1입니다. PML 기여는 이 지표를 확장한 진단값이며 전자기
에너지·biorthogonal 내적·모드 직교성 주장이 아닙니다. 동일한 양의 지표를
물리 영역에 제한해 파장 추적에 사용합니다.

형상/PML/굽힘을 고정한 파장 sweep만 지원합니다. scalar/vector 모두 양수의
엄격히 단조로운 파장 3개 이상이 필요합니다. 모드 부족·모호한 매칭·거의 축퇴한
매칭이면 중단합니다. resolved assignment는 개별 고유장을 보존하고 후보
선택 번호를 갱신하며 서로 다른 고유값의 장을 섞지 않습니다.
`electric-l2-subspace-v1`은 이 복소 스펙트럼에서 지원하지 않습니다. 복소 군지수는
스펙트럼 미분이며 에너지 속도가 아닙니다. 파장 간격과 후보 수도 검증해야 합니다.

## 부호·감쇠·한계

`exp(+i omega t-i beta z)`, `beta=k0 n_eff`입니다. 수동 재료는 Im epsilon<=0,
수동 순방향 감쇠는 Im n_eff<0입니다. 전력 손실은
`-40 pi Im(n_eff)/(100 ln(10) wavelength_m)` dB/cm입니다. 굽힘은 기준 반경에서
`loss_db_90deg=loss_db_cm pi R_cm/2`입니다. 모두 흡수와 방사가 포함된 **총**
감쇠입니다. 서로 다른 계산을 빼는 것으로 재료·누설·굽힘 손실이 유일하게
분리되지는 않습니다.

Studio에서 PML 면·강도·차수·비율·목표 및 굽힘을 입력합니다. 결과는 모든
후보 이유와 잔차를 표시하며 인공 PML 장은 회색으로 가립니다. scalar는 불변축
TE slab 편광의 정확식이고 일반 2D 고대비 도파관에서는 근사입니다. 가변곡률,
3D 열린 모드, 자동 PML 수렴 인증, 비Hermitian 축퇴 부분공간 추적은 범위 밖입니다.

검증은 독립 outgoing slab 전달식, 복소차수 원통 J/Y/Hankel 매칭, 3개 메시,
독립 PML/창 변화, bound 무손실·큰 반경 극한, 별도 scikit-fem 조립+dense QZ를
사용합니다. 관련 시험은 `tests/galerkin/test_pml_modes.py`,
`tests/galerkin/test_crosscheck_skfem_pml_modes.py`,
`tests/simcase/test_pml_contract.py`이며 기존 무손실 기준과 golden을 바꾸지 않습니다.

실행 예제: [기판 누설 slab](../../../../../../examples/simcase/pml_leaky_slab.json), [일정 반경 slab](../../../../../../examples/simcase/pml_bent_slab.json).
