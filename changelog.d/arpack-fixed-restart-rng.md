# Fixed

## English

- `galerkin`, `simcase`: **an ARPACK search that reaches a degenerate cluster is reproducible on one build.** When its Krylov space breaks down, ARPACK asks for a random start vector, which SciPy took from operating-system entropy. A vector mode search that reaches the static β² = 0 family therefore differed from run to run: the 8-root search of `test_pml_additional_searches.py::test_the_record_with_and_without_the_key` took 5 to 611 ARPACK restarts on one machine and code (2 of 12 runs took 79–94 s instead of 6–7 s). Every ARPACK call (galerkin's mode, coordinate and cavity solves and gap checks, simcase's scalar `em.modes2d` solve) now passes `rng=np.random.default_rng(0)`, created per call, when SciPy's `eigs` or `eigsh` takes it (SciPy 1.17 and later, checked once by signature). Calls that draw no restart vector, including Studio's searches, give the same bits as before. Below SciPy 1.17 nothing changes. [PML modes](docs/packages/simcase/pml_modes.md#signs-attenuation-and-limitations).

## 한국어

- `galerkin`, `simcase`: **겹친 무리에 닿는 ARPACK 탐색이 한 빌드에서 재현됩니다.** Krylov 공간이 무너지면 ARPACK이 무작위 시작 벡터를 요구하고, SciPy는 이를 운영체제 엔트로피에서 가져왔습니다. 그래서 정적 β² = 0 무리에 닿는 벡터 모드 탐색이 실행마다 달랐습니다. `test_pml_additional_searches.py::test_the_record_with_and_without_the_key`의 8개 근 탐색은 같은 기계와 코드에서 ARPACK 재시작이 5번에서 611번까지 걸렸습니다(12번 중 2번이 6–7초 대신 79–94초). 이제 모든 ARPACK 호출(galerkin의 모드·좌표·공진기 풀이와 간격 확인, simcase의 스칼라 `em.modes2d` 풀이)이 SciPy의 `eigs`나 `eigsh`가 받으면(SciPy 1.17 이상, 시그니처로 한 번 확인) 호출마다 새로 만든 `rng=np.random.default_rng(0)`을 넘깁니다. 재시작 벡터를 뽑지 않는 호출은 Studio의 탐색을 포함해 예전과 같은 비트를 줍니다. SciPy 1.17 미만에서는 바뀌는 것이 없습니다. [PML 모드](packages/simcase/pml_modes.md#부호감쇠한계).
