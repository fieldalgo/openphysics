# Changed

## English

- meshloom: **the PLC check finds the grid cells of a one-triangle facet once**, in its facet step, and the crossing step reuses them. On the fan readiness input at 3e5 faces, whose thin triangles cross many cells, the crossing step falls from 32 to 11 s; the result is unchanged.

## 한국어

- meshloom: **PLC 검사는 삼각형 하나짜리 facet의 격자 칸을 facet 단계에서 한 번만 구하고**, 교차 단계는 그것을 다시 씁니다. 얇은 삼각형이 많은 칸을 지나는 면 3e5개의 fan 사전 점검 입력에서 교차 단계가 32 s에서 11 s로 줄었습니다. 결과는 같습니다.
