# 물리 공급자

[English](../../../../../packages/simcase/providers.md) | **한국어**

[simcase 개요](overview.md)

*공급자*는 simcase의 [물리 레지스트리](../../../../../../packages/simcase/src/simcase/registry.py)에
물리 종류를 더하는 설치된 배포판이다. simcase 자신의 종류는 내장 공급자 `openphysics-fem`이다.
다른 배포판은 simcase를 고치지 않고 종류를 더할 수 있다. 사용자 화면은 데이터만으로 무엇이
설치됐는지 보여 줄 수 있다. 구현은 [`simcase.providers`](../../../../../../packages/simcase/src/simcase/providers.py)에 있다.

**이 프로토콜은 0.x 동안 불안정하다**(프로토콜 버전 1). 필드, manifest 구성, 목록은 어느
minor 릴리스에서든 바뀔 수 있다. 공급자는 자신이 구현한 버전을 밝히고, simcase는 다른 버전을
이름을 밝혀 거부한다.

## 목적

Studio와 `simcase.run`이 돌릴 수 있는 물리를 모두 찾게 한다. 따로 설치한 패키지의 물리도
포함한다. Studio나 러너가 type 문자열을 직접 비교하지 않게 한다.

## 계약 (D1)

1. **공급자**
   - 공급자는 설치된 Python 배포판이다. entry point 그룹 `openphysics.providers`에 하나를 등록한다.
   - 그 entry point는 공급자 객체를 돌려주는 함수를 가리킨다. 공급자 객체에는 다음이 있다.
     - `name`(예: `"openphysics-fem"`). entry point 이름과 같아야 한다(소문자·숫자·`.`·`_`·`-`).
       `version`(빈 문자열이 아닌 문자열)
     - `protocol`: 구현한 프로토콜 버전, `1`
     - `kinds()`: 더하는 `registry.PhysicsKind`들 (지금 dataclass 그대로, 새 필드 없음).
       러너가 `simcase.run`의 진행 콜백을 받는 종류는 `accepts_on_event=True`로 두고, 그러면
       `run(doc, verbose, on_event=...)`로 불린다. 기본값 `False`(이 필드 전에 만든 모든 종류)이면
       러너는 전과 똑같이 불리고 콜백을 받지 않는다. `run`은 이 필드를 확인하며, 호출해 보고
       `TypeError`를 잡는 방식은 쓰지 않는다. 이벤트는 [simcase 개요](overview.md#python에서-사용)에 있다.
     - `manifest()`: Studio와 검사기가 쓸, 종류별 설명을 담은 JSON 데이터 (아래 4번)
2. **내장 공급자**
   - 내장 종류는 simcase 배포판이 직접 등록하는 공급자 `openphysics-fem`이다
     (`openphysics-fem = simcase.providers:builtin_provider`).
   - `registry.BUILTIN_MODULES`의 모듈이 등록하는 종류(모듈마다 `KIND`로 둠)를 감싸기만 한다.
     문서·결과·숫자는 그대로다.
   - 내장 공급자의 오류는 목록에 적지 않고 그대로 낸다. 내장 종류 없이는 어떤 문서도 돌지 않는다.
3. **발견**
   - 레지스트리를 처음 찾을 때(`registry.kinds()`, `kind_of`, `kind_of_type`, `physics_types`와
     이들을 쓰는 모든 것) 프로세스마다 한 번 불러온다. 내장 공급자를 먼저, 그다음 나머지
     entry point를 이름 순서로 불러온다.
   - 다음 경우 그 공급자는 빠지고, 오류와 함께 "쓸 수 없음"으로 표시된다.
     - entry point를 import하지 못하거나, 함수가 예외를 내거나, 배포판 메타데이터를 읽지 못한다.
     - 이름이 entry point 이름과 다르거나, 이미 불러온 공급자 이름(`openphysics-fem` 포함)과 같다.
     - 프로토콜 버전이 1이 아니다.
     - `kinds()`가 `PhysicsKind`가 아닌 것을 돌려주거나 `manifest()`가 잘못됐다(아래).
     - 종류 하나가 다른 종류가 주장한 type 문자열을 주장한다(두 종류 이름을 밝히는 `register`
       규칙). 또는 다른 공급자의 종류 이름을 쓴다.
     - 모듈이 `kinds()`가 돌려주지 않는 종류를 등록한다.
   - 공급자는 통째로 더해지거나 전혀 더해지지 않는다. 불러오는 동안 등록한 종류는 다시 지우고,
     모듈이 처음 찾기 전에 등록한 `kinds()`의 종류도 지운다. 실패해도 다른 공급자나 내장 종류는
     멈추지 않는다.
   - 두 공급자가 한 type을 주장하면 이름 순서로 앞선 것을 불러오고, 뒤의 것은 쓸 수 없음이 된다.
   - 공급자 밖에서 `registry.register`로 등록한 종류는 어느 공급자의 것도 아니다. 같은 이름의
     공급자 종류가 그 자리를 차지한다.
4. **manifest (데이터만)**
   - `manifest()`는 `{"kinds": {<종류 이름>: {...}}}`를 돌려준다. `kinds()`의 종류를 정확히 설명한다.
     종류마다 다음을 적는다.
     - `types`: 종류가 주장하는 type 문자열
     - `field`: "물리 추가" 목록을 묶을 분야(`electric`, `heat`, `electromagnetics`, `structure` …;
       소문자·숫자·밑줄)
     - `engine`: 푸는 엔진의 표시 이름
     - `process`: `"in_process"` 또는 `"worker"`. Studio와 검사기를 위한 선언이다. simcase는 아직
       worker 프로세스를 띄우지 않는다(D3). `run`은 종류의 러너를 부른 프로세스 안에서 부른다.
     - `ports`: 입력과 출력. 각각 `name`, `direction`(`"input"` 또는 `"output"`), `quantity`(physmat
       [양 레지스트리](../physmat/units.md)의 이름), `unit`(그 양의 SI 단위 기호, 문자열로 비교),
       `location`(`"node"`·`"element"`·`"grid"`·`"scalar"`. `"scalar"`는 메시나 격자 위에 있지 않은
       값으로, 값 하나 또는 모드마다 하나)을 가진다. 입력에는 `combine`(`"single"`
       또는 `"sum"`)도 있다.
     - `ui`(선택): 라벨·묶음·단위·슬라이더 범위 같은 데이터만 담는다. **Studio는 공급자의
       코드(JavaScript나 HTML)를 절대 불러오지 않는다.**
   - 모르는 키는 거부한다. manifest 전체가 JSON 데이터(문자열 키 객체, 목록, 문자열, 유한한 수,
     불리언, null)여야 하고 JSON 왕복 뒤에도 같아야 한다.
     `providers.check_manifest(manifest, kinds)`가 이 규칙을 적용하고, 잘못된 항목을
     (예: `kinds.thermal.steady2d.ports[0].unit`) 밝혀 `ProviderError`를 낸다.
5. **신뢰**
   - 공급자는 일반 설치 Python 코드다. 다른 패키지처럼 사용자 권한으로 돈다.
   - 목록은 공급자마다 이름·버전·배포판을 준다. 무엇이 설치됐는지 사용자가 알 수 있게 하기 위해서다.
6. **안정성**
   - 0.x 동안 불안정하다([changelog](../../changelog.md#0x의-안정성) 참고).
   - 공급자는 자신이 구현한 프로토콜 버전(`protocol = 1`)을 밝힌다. simcase는 다른 버전을 이름을
     밝혀 거부한다.

D1에 넣지 않는 것: worker 프로세스(D3), 저장(D4), 어댑터 배포판(D5).
입력 포트와 `combine`은 [다중물리 문서](multiphysics_document.md)(D2)가 읽는다. 결합은 한 물리의
출력 포트를 다른 물리의 입력 포트로 나른다. 종류는 simcase 내부의 결합 훅으로 결합에 참여하는데,
이 훅은 아직 이 프로토콜의 일부가 아니다. 그래서 공급자의 종류는 입력 포트를 밝힐 수 있지만 아직
결합할 수는 없다.

## 공급자 목록

```python
from simcase import providers

for p in providers.providers():          # 내장 먼저, 그다음 entry point 이름 순서
    print(p.name, p.version, p.distribution, p.status, p.error)

listing = [p.as_dict() for p in providers.providers()]   # JSON 데이터
```

`providers.providers()`의 항목은 `ProviderInfo`다. `name`, `version`, `distribution`, `protocol`,
`status`(`"available"` 또는 `"unavailable"`), `error`(예외 종류와 메시지, 없으면 None), `manifest`,
`kinds`(종류 이름들)를 가진다. `as_dict()`는 `name`, `version`, `distribution`, `protocol`,
`status`, `error`, 그리고 manifest의 종류별 항목인 `kinds`(쓸 수 없는 공급자는 비어 있음)를
돌려준다. 쓸 수 없는 공급자는 entry point 이름으로 표시된다. 공급자가 `version`과 `protocol`을
돌려준 적이 없으면 둘은 None이다.

## 내장 종류와 포트

내장 종류는 모두 프로세스 안에서 돌고 `galerkin`이 푼다. 포트는 그 종류의 모든 문서가 필드를
저장할 때(`results.save_fields`, 기본값 true. false이면 `fields.npz`를 쓰지 않음) 실행의
`fields.npz`에 포트 이름으로 저장하는 출력이다([저장되는 출력](overview.md#저장-출력)). node
포트는 메시 절점마다, element 포트는 요소마다 하나다(과도 이력은 시간 축 다음). 최소 목록이다.
종류는 선언한 것보다 많은 배열을 저장한다. 배포된 예제 문서 전부를 이 목록에 비춰 확인했다.

| 종류 | type | `field` | 출력 포트 (양, 단위, 위치) |
|---|---|---|---|
| `electric_joule` | `electric.steady2d`, `joule.steady2d`, `joule.temperature2d` | `electric` | `electric_potential` (V, node), `electric_field` (V/m, element), `current_density` (A/m^2, element), `joule_power_density` (W/m^3, element) |
| `mechanics` | `mechanics.elasticity2d`, `mechanics.thermoelastic2d` | `structure` | `displacement` (m, node), `strain` (1, element), `stress` (Pa, element) |
| `thermal.transient2d` | `thermal.transient2d` | `heat` | `temperature` (K, node), `heat_flux` (W/m^2, element); 출력 시각마다 한 행 |
| `thermal.steady2d` | `thermal.steady2d` | `heat` | `temperature` (K, node), `heat_flux` (W/m^2, element) |
| `em.cavity3d` | `em.cavity3d` | `electromagnetics` | `resonant_frequency` (Hz, 모드마다 scalar) |
| `em.modes2d` | `em.modes2d` | `electromagnetics` | `effective_index` (1, 모드마다 scalar) |

[다중물리 문서](multiphysics_document.md)에서 내장 입력 포트를 읽습니다.

| 유형 | 입력 포트 (양, 단위, 위치, `combine`) | 사용 |
|---|---|---|
| `thermal.steady2d` | `heat_source_density` (joule_power_density, W/m^3, element, `single`) | `electric.steady2d`의 요소별 줄 발열을 체적 열원으로 적분 |
| `mechanics.thermoelastic2d` | `temperature` (temperature, K, node, `single`) | 절점 온도를 고정해 열팽창을 계산하고 온도도 저장 |
| `em.modes2d` | `temperature` (temperature, K, element, `single`) | 절점 온도를 삼각형마다 평균하고 n = n₀(λ) + (dn/dT)(T − T_ref)로 설정 |

## 공급자 만들기

```toml
# 공급자 배포판의 pyproject.toml
[project.entry-points."openphysics.providers"]
my-physics = "my_physics.provider:provider"
```

```python
# my_physics/provider.py
from simcase import registry

class Provider:
    name, version, protocol = "my-physics", "0.1.0", 1

    def kinds(self):
        return (MY_KIND,)          # "my.type"을 주장하는 registry.PhysicsKind

    def manifest(self):
        return {"kinds": {MY_KIND.name: {
            "types": ["my.type"], "field": "heat", "engine": "my-solver", "process": "in_process",
            "ports": [{"name": "temperature", "direction": "output", "quantity": "temperature",
                       "unit": "K", "location": "node"}]}}}

def provider():
    return Provider()
```

종류에는 모든 종류에 필요한 것(계약 검증, 러너, 요약, 결과 형식, format 0.3 문서를 읽을 slot)이
필요하다. [새 물리 추가하기](../../architecture.md#새-물리-추가하기)를 참고한다.

## 시험

[`tests/simcase/test_providers.py`](../../../../../../tests/simcase/test_providers.py)는 내장 공급자
(같은 종류, 같은 순서, entry point, manifest, physmat 레지스트리와 예제 열두 개의 저장된
`fields.npz`에 비춘 포트, 그대로 내는 오류), 주입한 entry point와 경로 위의 시험 전용 배포판을
통한 가짜 공급자 발견, 위에 적은 실패 하나하나(처음 찾기 전에 등록한 종류 포함), 그리고 manifest
규칙 전부와 JSON 왕복을 확인한다.
