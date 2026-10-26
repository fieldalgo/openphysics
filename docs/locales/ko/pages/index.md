# OpenPhysics 문서

[English](../../../README.md) | **한국어**

OpenPhysics는 유한요소 엔진, 메시, 물성, 모델 실행기와 독립 기준해를 함께 제공하는
물리 해석 도구입니다. **모델을 구성하고 → 물리를 선택하고 → 실행하고 → 결과를 검증하는**
순서로 문서를 읽을 수 있습니다. API는 패키지별로, 물리 설명과 검증은 문제별로 찾아갑니다.

<a id="시작하기"></a>

## 해석을 시작하는 순서

| 단계 | 읽을 문서 |
|---|---|
| 1 | [설치·첫 예제](getting-started/index.md) |
| 2 | [형상·재료·메시](modeling/index.md) |
| 3 | [물리 문제·연계 방향](physics/index.md) |
| 4 | [Python·JSON/CLI·Studio 실행](guide/index.md) |
| 5 | [저장된 장·내보내기·물리 검사](results/index.md) |


## 물리 문제로 찾기

- [전자기](physics/electromagnetics.md)
- [열전도](physics/heat.md)
- [전기전도·Joule 발열](physics/electric-joule.md)
- [역학·열탄성 연계](physics/mechanics.md)

Python 엔진, JSON/CLI와 Studio의 지원 범위는 서로 다릅니다. 각 물리 안내에서 가능한
인터페이스와 한계를 먼저 확인하세요. 열→역학은 단방향이며, 온도 의존 Joule 반복은
별도 계약을 가진 제한된 연계 문제입니다.

<a id="현재-구현의-사용-계약과-검증-근거"></a>

## API·수식·근거·개발

- <a id="패키지-개요"></a>[패키지 API·문서 계약](reference/index.md)
- [수식·수치 방법](theory/index.md)
- <a id="벤치마크와-자원-관측"></a>[독립 검증·벤치마크](validation/index.md)
- [개발·CI·기여](development/index.md)

[패키지 구조](architecture.md) · [예제 갤러리](gallery.md) · [문서 배치·번역 규칙](development/documentation.md)

영어를 기준으로 한국어 대응 문서를 함께 관리합니다. 기존 패키지 원문은
`packages/<package>/`에 유지하며, 각 읽기 경로는 같은 원문을 연결합니다.
