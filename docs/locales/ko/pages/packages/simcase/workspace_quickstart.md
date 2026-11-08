# 작업 공간 빠른 시작

[English](../../../../../packages/simcase/workspace_quickstart.md) | **한국어**

Studio 작업 공간을 설치하고, 실리콘 도파관 설계 두 개를 만들어 비교한 뒤, 재시작해도
작업이 남게 합니다. 전체 설명은 [작업 공간 안내](workspace.md)에 있습니다.

OpenPhysics 0.1.0은 아직 PyPI에 없습니다(빈 `0.0.1` 이름 예약만 있음). 그래서 저장소에서
만든 wheel 파일 폴더(*wheelhouse*)로 설치합니다. NumPy·FastAPI 같은 다른 패키지는 PyPI에서
받으므로 설치하는 동안 인터넷이 필요합니다.

## 1. wheelhouse 받기

저장소가 있는 사람이 안내받은 커밋에서 한 번 만듭니다.

```sh
git clone https://github.com/fieldalgo/openphysics.git
cd openphysics
git checkout <commit>
python3.12 -m venv ../op-build
../op-build/bin/python -m pip wheel --no-deps -w ../wheelhouse packages/galerkin packages/meshine packages/physmat packages/simcase packages/gmshio packages/galerkin-refsol packages/sipi packages/openphysics
```

`wheelhouse` 폴더를 홈 폴더로 복사합니다.

## 2. 설치

[python.org](https://www.python.org/downloads/)의 Python 3.12 이상이 필요합니다(macOS는
`brew install python@3.12`도 됩니다). 버전 확인을 먼저 하는 이유는, 낮은 Python이면 빈 `0.0.1`
패키지를 조용히 설치하기 때문입니다.

Linux와 macOS:

```sh
python3.12 -c "import sys; assert sys.version_info >= (3, 12), sys.version"
python3.12 -m venv ~/op-studio
~/op-studio/bin/python -m pip install --find-links ~/wheelhouse "openphysics[studio]==0.1.0"
~/op-studio/bin/simcase-studio --help
```

Windows(PowerShell. 환경의 프로그램을 직접 부르므로 활성화 스크립트나 실행 정책 변경이
필요 없습니다):

```powershell
py -3.12 -c "import sys; assert sys.version_info >= (3, 12), sys.version"
py -3.12 -m venv "$HOME\op-studio"
& "$HOME\op-studio\Scripts\python.exe" -m pip install --find-links "$HOME\wheelhouse" "openphysics[studio]==0.1.0"
& "$HOME\op-studio\Scripts\simcase-studio.exe" --help
```

`--help`가 Studio 옵션을 보여 주면 설치가 끝난 것입니다.

## 3. Studio 켜고 끄기

```sh
~/op-studio/bin/simcase-studio --workspace                # Linux, macOS
```

```powershell
& "$HOME\op-studio\Scripts\simcase-studio.exe" --workspace  # Windows
```

브라우저가 `http://127.0.0.1:8765/workspace`를 엽니다. 최신 Chrome이나 Edge를 쓰세요.
작업하는 동안 터미널을 열어 두고, 끌 때는 터미널에서 **Ctrl+C**를 누릅니다.

- 항상 같은 주소를 여세요. 브라우저 복구는 정확한 주소에 묶여 있어서, `127.0.0.1` 대신
  `localhost`나 다른 포트로 열면 복구할 것이 없는 상태로 시작합니다.
- 다시 켜기 전에 터미널에 프롬프트가 돌아왔는지 확인하세요. Studio가 아직 그 포트에서
  돌고 있으면 두 번째 실행은 끝나 버리고 브라우저는 예전 서버를 보여 줍니다.

## 4. 설계 두 개와 비교

1. **Choose a starting model**에서 **Optical waveguide**를 고릅니다.
2. **Geometry**에서 코어 폭을 600 nm, 높이를 300 nm로 정합니다. 재료는 실리콘, 파장은
   1550 nm입니다(**Optical modes**에서 바꿀 수 있습니다).
3. **Run optical study**를 누릅니다. 결과에 장 분포와 두 후보의 유효굴절률이 나옵니다.
   실행에 이름을 붙이고 **Pin selected run**을 누릅니다.
4. 다시 **Geometry**에서 폭을 700 nm로 바꾸고 실행합니다.
5. **Compare**를 엽니다. A와 B가 자동으로 골라지고, 비교 화면에 유효굴절률 차이가
   나옵니다. 후보 순위는 같은 모드끼리 짝지은 것이 아닙니다.

## 5. 작업 남기기

- 첫 번째 저장 버튼인 **Save session**은 입력, 완료한 실행 전부, 이름과 고정, 비교를 파일
  하나에 씁니다. 끄기 전에 쓰세요. **Save inputs only**는 결과 없이 모델만 저장합니다.
- 새로고침하거나 다시 켜면 시작 화면에 **Continue where you left off**가 나옵니다. 마지막
  세션이나 이전 세션을 복구하거나, 세션 파일을 엽니다.
- 페이지를 열어 둔 채 Studio를 다시 켜면 페이지가 스스로 다시 연결합니다. 다시 실행하라는
  안내가 나오면 Run을 다시 누르세요.

## 검증한 플랫폼

2026-11-08에 Linux(Python 3.12.3, headless Chromium)에서 커밋 `da230150`으로 만든 wheel로
확인했습니다. 새 환경에서 버전을 고정한 설치(다운로드 캐시가 있을 때 14초), 4·5단계,
**Ctrl+C**, 재시작, 시작 화면에서의 복구까지 했고 비교가 그대로 돌아왔습니다. **macOS와
Windows에서는 이 단계를 아직 확인하지 않았습니다.** 이전 Windows 확인 기록은
[수용 점검표](workspace_acceptance.md)에 있습니다.
