# openphysics

[English](../../../../../packages/openphysics/overview.md) | **한국어**

[영어·한국어 문서와 번역 상태](https://github.com/fieldalgo/openphysics/blob/main/docs/locales/ko/pages/index.md)

OpenPhysics 완제품을 한 번에 설치하는 배포판입니다. 여섯 패키지와 브라우저 Studio, ParaView용 VTU
내보내기, refractiveindex.info 읽기, `sipi`가 함께 들어옵니다. 자체 코드는 없습니다. 함께 릴리스되는
그 패키지들을 의존성으로 요구하고, Studio 모델 작업 공간을 여는 `openphysics` 명령을 줍니다.

| 패키지 | 역할 |
|---|---|
| `galerkin` | 유한요소 엔진 |
| `galerkin-refsol` | 엔진 검증에 사용하는 해석적 참조해 |
| `meshine` | 2D 품질 메시 생성기 |
| `gmshio` | Gmsh 실행기와 MSH 판독기 |
| `physmat` | 재료 및 광학 분산, refractiveindex.info 읽기(PyYAML) |
| `simcase` | 모델 문서, 헤드리스 실행기, 브라우저 Studio(FastAPI, Uvicorn), VTU 내보내기(meshio) |
| `sipi` | PCB 단면의 신호·전원 무결성 |

**0.0.2는 아직 PyPI에 없습니다.**
- PyPI에는 빈 `0.0.1` 이름 예약만 있습니다. 그래서 지금은 아래 명령이 쓸모 있는 것을 설치하지 않으며, pip가 성공이라고 보고할 수도 있습니다.
- 릴리스 전까지는 [소스 checkout에서 설치](../../overview.md#소스에서-설치)하거나 거기서 만든 wheel로 설치합니다.
- 이때 pip가 `0.0.1`을 고르지 않고 거부하도록 버전을 고정합니다(`"openphysics==0.0.2"`).
- 아래 명령은 릴리스용입니다.

```bash
pip install openphysics        # 완제품
openphysics                    # 브라우저에서 Studio 모델 작업 공간 열기 (Ctrl+C로 종료)
```

- `openphysics --classic`은 예전 광학·열 편집기를 엽니다.
- `--port`, `--host`, `--no-browser`는 `simcase-studio`와 같습니다.
- 예전 extra(`studio`, `export`, `rii`, `sipi`)도 계속 쓸 수 있지만, 이제는 더하는 것이 없습니다.
- Studio 없이 라이브러리만 쓰려면 그 패키지만 따로 설치합니다(예: `pip install simcase`).

어떤 설치도 Gmsh를 넣지 않습니다. `gmshio`는 Gmsh를 별도 프로그램으로 실행하므로, 필요하면 Gmsh 자체 라이선스에 따라 따로 설치하세요(예: `pip install gmsh`). 컴파일된 3D 메셔 `meshloom`은 지금은 따로 설치합니다.

각 패키지는 따로 설치할 수도 있습니다. 모든 이름의 `0.0.1`은 아무것도 설치하지 않는
빈 이름 예약이었습니다.

0.x는 알파입니다. Python API는 마이너 버전 사이에 바뀔 수 있습니다. 릴리스마다 바뀐 점과
안정적으로 유지하는 점은 [변경 기록](../../changelog.md)에 있습니다.

소스: https://github.com/fieldalgo/openphysics
