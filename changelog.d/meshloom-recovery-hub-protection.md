# Changed

## English

- meshloom: **segment recovery protects a vertex with many segments (a fan's centre) on common shells.** When a piece is missing at an input vertex with more than 32 segments, every segment there is first split at one distance from it. Later points about it lie at that distance divided by powers of two. Before, the lazy rules left the thin wedges of a large fan encroaching each other without end. With `MESHLOOM_PROFILE`, recovery prints one line per round.

## 한국어

- meshloom: **선분 복원이 선분이 많은 꼭짓점(부채꼴 중심)을 공통 껍질로 보호합니다.** 선분이 32개보다 많은 입력 꼭짓점에서 조각이 빠지면, 그 꼭짓점의 모든 선분을 먼저 꼭짓점에서 같은 거리에서 나눕니다. 그 둘레의 이후 점은 그 거리를 2의 거듭제곱으로 나눈 거리에 놓입니다. 전에는 필요할 때만 쓰는 규칙 때문에 큰 부채꼴의 얇은 쐐기들이 서로를 끝없이 침범했습니다. `MESHLOOM_PROFILE`을 설정하면 복원이 라운드마다 한 줄씩 출력합니다.
