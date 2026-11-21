# Added

## English

- `simcase`: **steady heat reads a library material's constant `thermal_conductivity`.** A region of a `thermal.steady2d` document, single- or multiphysics, may name `physmat:<Name>` when physmat gives its conductivity as one constant, its 300 K handbook value (Si 148, SiO2 1.38, GaAs 55, Al2O3 35, Si3N4 20, Au 317, Ag 429 W/(m K)); the conductivity does not follow the temperature, so a large temperature rise calls for a local record with your own value. A library material whose conductivity is a temperature model (Cu, Al) or absent (vacuum, standard_air, …) is `E-PROPERTY-MISSING` by name; transient heat still reads no library material. A heat → modes document can now use `physmat:Si` and `physmat:SiO2` throughout. Checked: a region document and a heat → modes document of `physmat:Si`/`physmat:SiO2` give the temperature of local records of 148 and 1.38 W/(m K) bit for bit, and every shipped example (34, the multiphysics one included) gives hash-identical outputs before and after. [Heat region documents](docs/packages/simcase/thermal_regions2d.md).

## 한국어

- `simcase`: **정상 열전도가 라이브러리 재료의 상수 `thermal_conductivity`를 읽습니다.** 단일 물리든 다중물리든 `thermal.steady2d` 문서의 영역은 physmat이 전도도를 상수 하나, 곧 300 K 핸드북 값으로 주는 `physmat:<Name>`을 쓸 수 있습니다(Si 148, SiO2 1.38, GaAs 55, Al2O3 35, Si3N4 20, Au 317, Ag 429 W/(m K)). 전도도는 온도를 따라 바뀌지 않으므로 온도 상승이 크면 자기 값으로 로컬 기록을 쓰십시오. 전도도를 온도 모델로 주거나(Cu, Al) 주지 않는(vacuum, standard_air, …) 라이브러리 재료는 이름을 밝혀 `E-PROPERTY-MISSING`이고, 과도 열전도는 여전히 라이브러리 재료를 읽지 않습니다. 이제 열 → 모드 문서에서도 `physmat:Si`와 `physmat:SiO2`를 쓸 수 있습니다. 검사: `physmat:Si`/`physmat:SiO2`를 쓴 영역 문서와 열 → 모드 문서는 148과 1.38 W/(m K) 로컬 기록과 비트 단위로 같은 온도를 내고, 배포한 모든 예제(다중물리 예제 포함 34개)는 변경 전후 출력 해시가 같습니다. [열 영역 문서](packages/simcase/thermal_regions2d.md).
