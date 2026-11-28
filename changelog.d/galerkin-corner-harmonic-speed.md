# Changed

## English

- `galerkin`: **separated and far static wedge-harmonic interaction blocks are evaluated about 1.7–2.1 times faster, with the same formula.** The constant mode carries weight only on the first half of each rule's nodes, so its logarithm arrays are formed only there, and the real log-modulus identity runs in place with the same IEEE operations in the same order. Measured on Linux with one thread: the centered block at order 32/64 went from 275/609 µs to 129/367 µs, and the two-active guard-field solve at 32/48 panels from 220/584 s to 170/425 s. Checked: the log-modulus helper is bit-identical; over 3000 random blocks orders 4, 32, 64 and 128 are bit-identical and orders 8 and 16 differ by at most 3.1e-15 relative (shorter BLAS dot products); 922 public far/separated results and every array of those guard solves are bit-identical; the harmonic and quadratic-far galerkin tests pass with unchanged tolerances and stored values. Not checked: bit identity on macOS or Windows BLAS. [Harmonic interaction blocks](docs/packages/galerkin/laplace_corner_harmonic_interactions.md).

## 한국어

- `galerkin`: **떨어진·먼 정적 쐐기 조화 상호작용 블록을 같은 수식으로 약 1.7–2.1배 빠르게 계산합니다.** 상수 모드는 각 규칙 노드의 앞 절반에만 가중치를 가지므로 그 로그 배열을 거기서만 만들고, 실수 로그 모듈러스 항등식은 같은 IEEE 연산을 같은 순서로 제자리에서 계산합니다. Linux 1스레드 측정: 차수 32/64의 중심 블록이 275/609 µs에서 129/367 µs, 두 활성 guard 장 풀이가 32/48패널에서 220/584 s에서 170/425 s가 되었습니다. 검사: 로그 모듈러스 보조 함수는 비트 동일하고, 무작위 블록 3000개에서 차수 4, 32, 64, 128은 비트 동일, 차수 8과 16은 상대 차이 최대 3.1e-15입니다(짧아진 BLAS 내적). 공개 far/separated 결과 922개와 그 guard 풀이의 모든 배열이 비트 동일하며, harmonic·quadratic-far galerkin 시험이 허용오차와 저장값을 바꾸지 않고 통과합니다. 미검증: macOS·Windows BLAS에서의 비트 동일성. [조화 상호작용 블록](packages/galerkin/laplace_corner_harmonic_interactions.md).
