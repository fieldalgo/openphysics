# Changed

## English

- `meshloom`: **closed triangle surfaces (STL-like inputs) are marked experimental.** They mesh through `builder.triangle_surface` or as one facet per triangle, but the 3D plan's import gate (V20 on the Thingi10K population C14) was not met at milestone M4. Version 1 supports polyhedral inputs and the builder's primitives; closed-surface import is gated again at M8, and V20 stays reported. The README rows that said meshloom had no mesher, and the package README's "no graded sizes", are corrected. [meshloom overview](docs/packages/meshloom/overview.md#limits).

## 한국어

- `meshloom`: **닫힌 삼각형 표면(STL 같은 입력)을 experimental로 표시합니다.** `builder.triangle_surface`나 삼각형마다 facet 하나로 메시가 되지만, 3D 계획의 import 게이트(Thingi10K 모집단 C14의 V20)를 M4에서 충족하지 못했습니다. 버전 1은 다면체 입력과 builder의 primitive를 지원하며, 닫힌 표면 import는 M8에서 다시 게이트하고 V20은 계속 보고합니다. meshloom에 메셔가 없다고 적힌 README 행과, 패키지 README의 "graded 크기 없음"도 바로잡았습니다. [meshloom 개요](packages/meshloom/overview.md#한계).
