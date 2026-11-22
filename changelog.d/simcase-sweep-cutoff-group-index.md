# Fixed

## English

- `simcase`: **a wavelength sweep no longer reports n_g = 0 for a cut-off scalar mode.** Where β² ≤ 0 the scalar solve reports the fill value n_eff = 0 (its square root is clipped), and the sweep's difference turned it into n_g = 0. That n_g is now null (NaN) at every point whose difference uses a cut-off value, `log.txt` says *n_g undefined at …: n_eff^2 <= 0 (cut off)*, and every other value is unchanged; no result key is added and `effective_index` keeps its value. Checked (C1–C3, pre-registered): the cut-off 220 nm Si film gives null at all three points, NaN falls exactly on the difference stencil in first and second order with the other values equal bit for bit, and a guided sweep is unchanged. [Overview](docs/packages/simcase/overview.md).

## 한국어

- `simcase`: **파장 sweep이 차단된 스칼라 모드에 n_g = 0을 내지 않습니다.** β² ≤ 0이면 스칼라 풀이가 채움 값 n_eff = 0(제곱근을 0에서 자름)을 내고, sweep의 차분이 그것을 n_g = 0으로 만들었습니다. 이제 차단된 값을 쓰는 차분의 모든 지점에서 n_g는 null(NaN)이고 `log.txt`가 *n_g undefined at …: n_eff^2 <= 0 (cut off)*라고 밝히며, 다른 값은 모두 그대로입니다. 결과 키는 늘지 않고 `effective_index`도 값을 유지합니다. 검사(C1–C3, 사전 등록): 차단된 220 nm Si 막은 세 지점 모두 null, NaN은 1차·2차 모두 정확히 차분 스텐실에만 놓이고 다른 값은 비트 단위로 같으며, 안내되는 sweep은 그대로입니다. [개요](packages/simcase/overview.md).
