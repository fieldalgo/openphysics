# Changed

## English

- Studio: **the closed-window search checks K2 and K13 on the same mesh.** As first registered they compared n_eff with absolute values to 1e-8, and failed on a CI runner without AVX-512 (K2 −1.93e-5, K13 +3e-8): meshine orders refinement points of equal circumradius with NumPy's quicksort, whose tie order depends on the CPU dispatch, so the default mesh differs between CPUs. Re-registered after that result (not blind): the targeted modes equal an untargeted closed run of the same document in the same process within 1e-8, and the absolute values are references within 2e-4. The limitation is documented. [Closed-window search document](docs/packages/simcase/workspace.md#closed-window-search-document-optical-shapes-v10).

## 한국어

- Studio: **닫힌 창 탐색의 K2와 K13을 같은 메시에서 검사합니다.** 처음 등록한 대로는 n_eff를 절대값과 1e-8로 비교했고, AVX-512가 없는 CI 러너에서 실패했습니다(K2 −1.93e-5, K13 +3e-8). meshine은 외접원 반지름이 같은 세분 점을 NumPy의 quicksort로 정렬하는데, 같은 값의 순서가 CPU 디스패치에 따라 달라 기본 메시가 CPU마다 다릅니다. 그 결과 뒤 다시 등록했습니다(사전 아님): 목표 모드는 같은 프로세스에서 같은 문서의 목표 없는 닫힌 실행과 1e-8 안에서 같고, 절대값은 2e-4 안의 기준값입니다. 이 한계를 문서에 적었습니다. [닫힌 창 탐색 문서](packages/simcase/workspace.md#닫힌-창-탐색-문서optical-shapes-v10).
