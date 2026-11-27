# Changed

## English

- meshloom: **segment recovery adds points only on missing pieces, where Si and Gärtner's rules put them.**
  - Before, every segment at an acute vertex was split at a protecting sphere, and other missing pieces were halved. On a triangulated surface nearly every vertex is acute, so recovery added several points per input vertex.
  - Now a missing piece is split at a point fixed by its reference point: the mesh neighbour inside its diametral ball that sees it under the largest angle. The point lies on a sphere about the segment's acute end (rules 2 and 3), at the reference point's distance from the nearer end (rule 1), or at the middle.
  - Meshes change; on the synthetic surfaces of `tests/meshloom/cdt_inputs.py` there are far fewer Steiner points.
  - A piece shorter than 2^-`max_depth` of its segment is the error that ends a run that does not terminate.

## 한국어

- meshloom: **선분 복원이 빠진 조각에만, Si와 Gärtner의 규칙이 정하는 자리에 점을 넣습니다.**
  - 전에는 예각 꼭짓점의 모든 선분을 보호 구에서 나누고, 다른 빠진 조각은 반으로 나눴습니다. 삼각형 곡면에서는 거의 모든 꼭짓점이 예각이라, 입력 꼭짓점마다 점이 여러 개 생겼습니다.
  - 이제 빠진 조각은 기준점이 정하는 점에서 나눕니다. 기준점은 지름 구 안에 있는 메시 이웃 가운데 조각을 가장 큰 각으로 보는 점입니다. 그 점은 선분의 예각 끝을 중심으로 한 구 위(규칙 2와 3), 가까운 끝에서 기준점까지의 거리(규칙 1), 또는 가운데입니다.
  - 메시가 바뀝니다. `tests/meshloom/cdt_inputs.py`의 합성 곡면에서 Steiner 점이 크게 줄었습니다.
  - 선분 길이의 2^-`max_depth`보다 짧은 조각이 생기면 오류를 내어, 끝나지 않는 실행을 멈춥니다.
