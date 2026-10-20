# 벡터 고유공간 신뢰성

[영문 원문](../../../../../packages/galerkin/eigenspace_reliability.md)

`solve_modes`는 복소수 `et`, `ez` 배열을 반환합니다. 물리장은
`E_t = et`(에지 선적분), `E_z = 1j * ez`(절점값)입니다.
`beta = k0 * n_eff`로 원래 pencil 벡터 `[beta * et; ez]`를 복원하고,
해석 때와 같은 PEC 구속을 적용합니다. 호출자는 허수 계수를 버리면 안 됩니다.
재료와 pencil이 실수라고 해서 축퇴 고유공간의 모든 반환 기저가 실수일 필요는 없습니다.

## 실패와 수정

Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0에서 저장소 루트에서 재현합니다.

```python
import numpy as np
from galerkin import disk_mesh, solve_modes
from galerkin.edge import assemble_edge_mass
from galerkin.assembly import assemble_mass

mesh = disk_mesh((4, 8, 24), (4, 4, 16), 32)
eps = mesh.by_region([1.45**2, 1.44**2, 1.44**2])
neff, space, et, ez = solve_modes(mesh, eps, 2*np.pi/1.50, 1.45, 10)
g = (et[:2].conj() @ (assemble_edge_mass(space, 1.) @ et[:2].T)
     + ez[:2].conj() @ (assemble_mass(mesh, 1.) @ ez[:2].T))
g /= np.sqrt(np.outer(g.diagonal().real, g.diagonal().real))
print(neff[:2], np.linalg.eigvalsh(g))
```

수정 전 두 HE11 장은 같았습니다. 유효굴절률 두 개가 `1.44619559`이고 개별
고유쌍 잔차가 작아도, 정규화한 electric-L2 Gram 고유값은 `[0, 2]`였습니다.
ARPACK은 켤레 shift-invert 고유값 `5.17259007 +/- 8.75e-15j`와 독립적인
복소 방향을 반환했습니다. 각 벡터에 0이 아닌 위상을 곱하면 span은 보존되지만,
그 뒤 실수부를 취하면 보존되지 않습니다. 이전 출력 변환이 한 방향을 잃었습니다.

수정은 각 복소 고유벡터를 유지하고 최대 절댓값 계수로 단위 크기 위상을 정합니다.
위상은 `conj(pivot)/abs(pivot)`이므로 pivot이 음수여도 실수 벡터는 정확히
실수로 남습니다. 정렬, 후보 선택, 고유값, ARPACK 제어, 물리적 스케일은 그대로입니다.
가까운 고유쌍을 혼합하거나 whitening 또는 jitter를 적용하지 않습니다.
양의 실수 beta 추출도 그대로이며 손실 재료 지원을 추가한 수정이 아닙니다.

수정 후 같은 fixture의 정규화 Gram 고유값은 약 `[0.02040816, 1.97959184]`입니다.
full rank이지만 물리적 electric-L2 계량에서 정규직교 기저는 아닙니다.
직교성이나 완전성 보장을 추가하지 않습니다. 개별 잔차만으로 축퇴 쌍의 방향 손실을
검출할 수 없으므로 rank와 물리적 Gram도 검사해야 합니다. 수치적으로 조건이 나쁜
ARPACK 입력 기저도 보존하며 몰래 교체하거나 보정하지 않습니다.

## 기존 소비자

Simcase는 이미 공통 최대 크기 정규화로 복소 횡계수, 물리적 복소 Ez와 복소
centroid 표본을 저장합니다. JSON 표시는 실수/허수 목록을 분리하고 NPZ는
`allow_pickle=False`로 복소 수치 배열을 유지합니다. schema나 추적 변경은 필요 없습니다.
실수 기저에서 Ez는 Et와 직교 위상 관계이지만, 축퇴 공간 안의 임의 복소 조합은
성분별로 그 관계를 가질 필요가 없습니다. 기존 singleton sweep은 여전히 근축퇴
모드를 거절합니다. 이 수정은 부분공간 추적이나 쌍 내부의 개별 식별자를 구현하지 않습니다.

## 회귀 범위

기존 의존성만 사용하여 저장소 루트에서 실행합니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -c pyproject.toml -q -ra \
  tests/galerkin/test_eigenspace_reliability.py \
  tests/simcase/test_vector_eigenspace_reliability.py
```

시험은 1.50/1.55/1.60 um 반복 해석, 반환 rank와 electric-L2 Gram, 원래 각
free-DOF pencil 잔차, 실제 ARPACK 출력의 열별 보존, 지정 복소 위상/순서/정확한
이중 고유값 기저 변환을 다룹니다. 공통 고유값의 벡터를 혼합하는 것은 시험 대역뿐이며
생산 코드는 혼합하지 않습니다. 정규화 Gram 하한 `1e-8`은 이 fixture의 수치 rank
보존을 검사하는 값이지, spectral clustering 허용치나 직교성 요구가 아닙니다.

독립 시험 helper는 Bessel 근에 `refsol.fiber.vector_modes`를 재사용하고, 종방향
J/K 장과 Maxwell 방정식으로 +/-l 전기장을 유도합니다. 시간 의존성 exp(+i omega t),
축 의존성 exp(-i beta z)에서
`Et = (-i beta grad Ez + i k0 zhat cross grad Hz)/(k0^2 n^2-beta^2)`입니다.
Ez=f(r)exp(i l phi), Hz=h f(r)exp(i l phi)로 두고 코어 반경에서 정규화된
J_l/K_l profile이 연속이 되게 합니다. Ephi 연속성이 h를 결정합니다.
시험은 l의 양 부호에 대해 접선 E, 법선 유전 변위, 발산, 성분 Helmholtz 방정식을
계면에서 떨어진 곳에서 독립 검사합니다. 근 oracle은 FEM 장을 제공하지 않습니다.
외부 솔버 소스는 사용하지 않습니다.

FE/해석 cross-Gram은 삼각형마다 직접 요소 다항식과 Duffy tensor Gauss 구적을
사용합니다. 다각형/원 계면 차이는 유지합니다. 1.50 um에서 최악 principal-angle
sine은 scale 1/2/3 mesh에서 약 `0.09903 / 0.04962 / 0.03309`로 감소합니다.
구적 차수 4와 6을 비교하고, 해석 복소 unitary 기저 회전으로 오차가 바뀌지 않아야 합니다.
이 1차 장 수렴 기준은 fixture에 한정됩니다. 기존 2차 굴절률 수렴과 물리적
TE/TM/HE 분리 시험은 유지합니다. 고정 반경 24 um 비교가 무한영역 수렴,
cutoff 완전성 또는 모든 광섬유 계열의 정확성을 입증하지는 않습니다.
