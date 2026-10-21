# 튜토리얼: 내 도파관 해석하기

[English](../../../../../packages/simcase/waveguide_tutorial.md) | **한국어**

이 튜토리얼은 제공 예제인 실리콘 strip에서 시작해 내 도파관 단면까지 갑니다.
유효 굴절률 n_eff, 모드장, 파장 sweep의 군굴절률을 얻고, 그 값을 믿어도 되는지
알려 주는 점검을 익힙니다. 아래의 모든 Python 블록과 `python -m simcase` 명령은
`tests/simcase/test_waveguide_tutorial.py`가 설치된 패키지로 실행하며, 출력 숫자가
여기 보인 출력과 마지막 자리 1 이내로 같아야 통과합니다(컴퓨터에 따라 그만큼 다를 수
있습니다).

런타임 패키지가 설치되어 있어야 합니다. 설치 명령은
[패키지 개요](overview.md)를 보세요. Studio(브라우저 편집기, 8단계)에는 `studio`
extra가 필요합니다. 저장소의 `packages/`, `tests/` 폴더 밖의 작업 폴더에서
실행하세요.

## 1. 예제 실행

```bash
python -m simcase example soi_strip > strip.json
python -m simcase run strip.json -o strip_results
```

`strip.json`은 실리카 안의 500 × 220 nm 실리콘 코어를 1.40–1.70 µm의 일곱 파장에서
전체 벡터 모드로 풀도록 기술합니다. 실행하면 파장마다 두 모드의 n_eff를 출력하고
(예: `physics.em1.wavelength = 1.55 um: n_eff = 2.444060, 1.771237`)
`strip_results/`를 씁니다(7단계). 첫 모드는 TE 계열(전기장이 주로 x 방향),
둘째는 TM 계열 모드입니다.

## 2. Python에서 문서를 읽고 바꾸기

JSON 파일과 `simcase.examples.SOI_STRIP`은 같은 문서입니다. 딕셔너리로 고친 뒤
실행합니다. 편집하는 동안에는 단일 파장이 빠릅니다.

```python
import copy
from simcase import Document, examples, run

def solve(doc):
    result = run(Document.from_dict(doc), verbose=False)
    return result.neff[0]

strip = copy.deepcopy(examples.SOI_STRIP)
strip["study"] = {"type": "single"}
print(" ".join(f"{n:.4f}" for n in solve(strip)))
```

```text
2.4441 1.7712
```

길이는 선언한 단위, 여기서는 `"units": {"length": "um"}`를 따릅니다. 사각형을 바꿔
코어 폭을 450 nm로 만듭니다(`x`는 왼쪽 끝, `y`는 아래쪽 끝).

```python
narrow = copy.deepcopy(strip)
narrow["geometry"]["shapes"][0].update(x=-0.225, w=0.45)
print(" ".join(f"{n:.4f}" for n in solve(narrow)))
```

```text
2.3520 1.7341
```

## 3. 형상: strip, rib, 다각형

형상은 `rect`, `circle`, `polygon`입니다. 나중 형상이 앞 형상을 잘라 내고, 나머지
영역은 배경 재료가 채웁니다. rib은 창 전체를 가로지르는 얇은 slab 위에 rib을 얹은
것입니다.

```python
rib = copy.deepcopy(strip)
rib["geometry"]["shapes"] = [
    {"name": "slab", "type": "rect", "x": -1.5, "y": 0.0, "w": 3.0, "h": 0.09,
     "material": "Si", "mesh_size": 0.02},
    {"name": "rib", "type": "rect", "x": -0.25, "y": 0.0, "w": 0.5, "h": 0.22,
     "material": "Si", "mesh_size": 0.02},
]
rib["physics"]["em1"]["num_modes"] = 1
print(f"{solve(rib)[0]:.4f}")
```

```text
2.5669
```

모드를 하나만 요청하는 이유는 6단계에서 설명합니다. 다각형은 꼭짓점을 차례로
받습니다. 다음은 아래 폭 500 nm, 위 폭 440 nm의 기울어진 측벽 strip입니다.

```python
sloped = copy.deepcopy(strip)
sloped["geometry"]["shapes"][0] = {
    "name": "core", "type": "polygon", "material": "Si", "mesh_size": 0.02,
    "points": [[-0.25, 0.0], [0.25, 0.0], [0.22, 0.22], [-0.22, 0.22]],
}
print(" ".join(f"{n:.4f}" for n in solve(sloped)))
```

```text
2.3922 1.7495
```

## 4. 재료

재료 이름은 먼저 문서 자체의 `materials` 표에서, 그다음 내장 재료 18종에서
찾습니다. 내장 재료에는 `Si`, `SiO2`, `Si3N4`, `LiNbO3`, `vacuum` 등이 있습니다.
내장 재료는 분산을 담고 있어 sweep의 각 파장이 자기 굴절률을 씁니다. 내 재료는
상수 굴절률이나 Sellmeier 계수로 줍니다. Sellmeier `C` 값의 단위는 문서 길이
단위의 제곱입니다.

```python
import physmat

print(len(physmat.names()), "built-in materials")
nitride = copy.deepcopy(strip)
nitride["materials"] = {
    "my_sin": {"n": 2.0},
    "my_glass": {"sellmeier": {"B": [0.6961663, 0.4079426, 0.8974794],
                               "C": [0.0684043**2, 0.1162414**2, 9.896161**2]}},
}
nitride["geometry"]["background"]["material"] = "my_glass"
nitride["geometry"]["shapes"][0].update(material="my_sin", x=-0.6, w=1.2, h=0.4)
nitride["physics"]["em1"].update(n_cladding=1.45, num_modes=1)
print(f"{solve(nitride)[0]:.4f}")
```

```text
18 built-in materials
1.6658
```

모드 솔버는 무손실입니다. 내장 금속 `Au`, `Ag`, `Cu`, `Al`처럼 흡수가 있는 재료는
손실을 버리고 풀지 않고 오류로 거절합니다. `physmat`이 읽을 수 있는
refractiveindex.info 데이터베이스는 문서에서 쓸 수 없습니다.

## 5. 창과 메시 점검

영역 가장자리는 열린 공간이 아니라 완전 전기 도체(`"pec"`)이고, 메시는
유한합니다. 둘 다 자동으로 점검되지 않습니다. 하나씩 바꿔 n_eff가 얼마나
움직이는지 보세요.

```python
def changed(edit):
    doc = copy.deepcopy(strip)
    edit(doc)
    return f"{solve(doc)[0]:.5f}"

def wider_window(doc):
    doc["geometry"]["domain"] = {"xmin": -3.0, "xmax": 3.0, "ymin": -2.4, "ymax": 2.4}

def finer_core(doc):
    doc["geometry"]["shapes"][0]["mesh_size"] = 0.01

def finer_outside(doc):
    doc["mesh"]["size"] = 0.125
    doc["mesh"]["grading"].update(near=0.01, far=0.08)

def finer_both(doc):
    finer_core(doc)
    finer_outside(doc)

print("as supplied  ", changed(lambda doc: None))
print("window x2    ", changed(wider_window))
print("core mesh /2 ", changed(finer_core))
print("outside /2   ", changed(finer_outside))
print("both /2      ", changed(finer_both))
```

```text
as supplied   2.44406
window x2     2.44377
core mesh /2  2.44459
outside /2    2.44614
both /2       2.44634
```

이 strip에서 창은 충분히 큽니다(3e-4). 하지만 제공 메시는 n_eff가 적어도 2e-3 낮고
(둘 다 세분화해도 n_eff가 아직 오름), 그 오차 대부분은 코어 바깥에 있습니다. 형상의
`mesh_size`는 그 형상 안의 요소 크기를, `mesh.size`와 `mesh.grading`은 형상 주변의
요소 크기를 정하는데, 모서리 근처에서는 장이 여전히 빠르게 변합니다. 필요한
정밀도에서 n_eff가 더 바뀌지 않을 때까지 둘을 함께 세분화하세요. 장이 창
가장자리에 닿으면 창을 키워야 합니다. 이 두 점검은 새 형상마다 직접 해야 합니다.

## 6. rib 함정: slab 모드

rib의 slab은 자체 모드를 안내하며, 창 가장자리가 전기 벽이면 이 모드가 추가 해로
나타납니다. `n_cladding`은 n_eff 탐색의 하한이고, strip 예제의 1.45는 이 모드들을
들여보냅니다. rib에 모드 넷을 요청하고 창을 넓혀 보세요.

```python
def rib_modes(half_width, n_cladding=1.45, modes=4):
    doc = copy.deepcopy(rib)
    doc["geometry"]["domain"].update(xmin=-half_width, xmax=half_width)
    doc["geometry"]["shapes"][0].update(x=-half_width, w=2 * half_width)
    doc["physics"]["em1"].update(num_modes=modes, n_cladding=n_cladding)
    return " ".join(f"{n:.4f}" for n in solve(doc))

print("half width 1.5:", rib_modes(1.5))
print("half width 3.0:", rib_modes(3.0))
print("n_cladding 2.2:", rib_modes(1.5, n_cladding=2.2))
```

```text
half width 1.5: 2.5669 2.1157 2.0798 2.0422
half width 3.0: 2.5668 2.1124 2.0952 2.0904
n_cladding 2.2: 2.5669
```

rib 모드 2.5669는 창이 바뀌어도 거의 움직이지 않습니다. 나머지는 90 nm 맨 slab의
TE 모드(n_eff 2.104) 근처에 있고 창 폭에 따라 바뀝니다. 내 rib의 모드가 아니라 벽
사이를 오가는 slab 모드입니다. `n_cladding`을 slab 자체의 n_eff보다 높이면
제외됩니다. 2.2로 같은 네 모드를 요청하면 rib 모드만 돌아오고, 로그에 더 적게
찾았다고 남습니다. rib에서는 장도 보세요. slab 모드는 slab 전체로 퍼집니다.

## 7. 파장 sweep과 군굴절률

파장 sweep은 지점마다 각 모드를 추적하고, sweep 전체의 유한차분으로 군굴절률
`n_g = n_eff - λ dn_eff/dλ`도 줍니다.

```python
result = run(Document.from_dict(examples.SOI_STRIP), verbose=False)
i = result.values.index(1.55)
print(f"n_eff {result.neff[i, 0]:.4f}  n_g {result.group_index()[i, 0]:.4f}")
```

```text
n_eff 2.4441  n_g 4.1923
```

군굴절률에도 n_eff와 같은 메시 점검이 필요하고, 유한차분에 충분히 촘촘한 파장
간격도 필요합니다.

`result.save("strip_results")`(또는 `python -m simcase run`)는 1단계의 폴더를
씁니다.

| 파일 | 내용 |
|---|---|
| `summary.json` | study 지점·모드별 n_eff, 군굴절률, 선언 단위, 메시 통계, 시간, 모드 추적 |
| `fields.npz` | 메시 절점·삼각형, 원시 벡터장 계수, 삼각형 중심의 전기장(Ex, Ey, Ez). `numpy.load(..., allow_pickle=False)`로 읽음 |
| `results.png` | 메시, 첫 모드의 \|E\|, sweep |
| `log.txt`, `model.json` | 실행 로그와 실행한 문서 그대로 |

장 진폭은 상대값(가장 큰 중심 \|E\|가 1)이며 와트나 V/m가 아닙니다. 배열은
[패키지 개요](overview.md#벡터-장과-단일-지점-study)에 있습니다.

## 8. Studio에서 같은 모델

[패키지 개요](overview.md#브라우저-ui)대로 `studio` extra를 설치한 뒤 실행합니다.

```bash
simcase-studio
```

Studio는 이 strip 예제로 열립니다. 내 JSON 파일을 열고, 형상·재료·메시를 고치고,
실행해 n_eff, sweep, \|E\|·\|Ex\|·\|Ey\|·\|Ez\| 장을 봅니다. 위 명령과 같은 엔진을
씁니다.

## 한계

- 무손실 유전체만: 금속, 흡수 재료, 이득, 누설 모드는 없습니다.
- 창 가장자리는 열린 경계가 아니라 벽(PEC 또는 PMC)입니다. 완전 정합층(PML)이 없어
  굽힘·누설 손실은 계산하지 않습니다.
- 곧은 도파관만: 굽힘도, 도파관을 따른 전파도 없습니다.
- 창·메시 수렴 자동 점검이 없습니다. 5단계를 직접 하세요.
- `n_cladding`은 직접 고르는 탐색 경계이며, 솔버가 모든 유도 모드를 찾았음을
  증명하지 않습니다.
- 스칼라 정식화(`"formulation": "scalar"`)는 고대비 코어에 근사입니다. 이 strip에서
  2.444 대신 2.611입니다.
