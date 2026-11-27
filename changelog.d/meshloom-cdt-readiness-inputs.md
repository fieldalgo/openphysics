# Added

## English

- meshloom: **synthetic inputs for the boundary-recovery readiness set.** `tests/meshloom/cdt_inputs.py` builds seeded closed triangle surfaces with float32 coordinates (1e5 to 2e6 faces) in six categories: coplanar terraces, near-flat dihedrals (179.9–180 degrees), needles and caps (angles down to about 0.01 degree), fan caps, near-touching vertices and faces (gaps down to 1e-6 of the bounding-box diagonal), and all of them mixed. `test_cdt_inputs.py` checks small builds with the exact PLC check. Setting `MESHLOOM_PROFILE` prints the stage times of `mesh_plc` on stderr.

## 한국어

- meshloom: **경계 복원 준비 집합의 합성 입력.** `tests/meshloom/cdt_inputs.py`가 float32 좌표의 닫힌 삼각형 곡면을 시드로 정해 만듭니다(면 1e5–2e6개). 범주는 여섯 가지입니다: 같은 평면의 계단면, 거의 평평한 이면각(179.9–180도), 바늘과 캡 삼각형(약 0.01도까지의 각), 부채꼴 뚜껑, 거의 닿는 꼭짓점과 면(경계 상자 대각선의 1e-6까지의 간격), 그리고 이 모두를 섞은 것. `test_cdt_inputs.py`가 작은 입력을 정확한 PLC 검사로 확인합니다. `MESHLOOM_PROFILE`을 설정하면 `mesh_plc`의 단계별 시간이 stderr에 출력됩니다.
