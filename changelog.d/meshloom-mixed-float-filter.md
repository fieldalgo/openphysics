# Changed

## English

- meshloom: **faster exact predicates on points placed on segments during boundary recovery.** An error-bounded float filter now runs before the interval filter. orient3d and the projected orient2d are decided from their values on segment ends when those agree, since a segment point is a positive-weight combination of the ends. Coplanar and collinear configurations then no longer need big-integer arithmetic. Signs, and so meshes, are unchanged.

## 한국어

- meshloom: **경계 복원에서 선분 위에 놓인 점에 대한 정확한 판정식이 빨라졌습니다.** 이제 오차 한계를 가진 부동소수점 필터가 구간 필터보다 먼저 돕니다. 선분 위의 점은 양 끝점의 양의 가중 결합이므로, orient3d와 투영 orient2d는 끝점에서의 값들이 일치하면 그 값으로 정해집니다. 그래서 같은 평면이나 같은 직선 위의 배치에 더 이상 큰 정수 연산이 필요하지 않습니다. 부호와 메시는 바뀌지 않습니다.
