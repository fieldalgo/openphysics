# 작업 공간 빠른 시작

[English](../../../../../packages/simcase/workspace_quickstart.md) | **한국어**

Studio 작업 공간을 설치하고, 실리콘 도파관 설계 두 개를 만들어 비교한 뒤, 재시작해도
작업이 남게 합니다. 전체 설명은 [작업 공간 안내](workspace.md)에 있습니다.

OpenPhysics 0.0.2는 아직 PyPI에 없습니다(빈 `0.0.1` 이름 예약만 있음). 그래서 저장소에서
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
`brew install python@3.12`도 됩니다). 버전 확인을 먼저 하는 이유는, 낮은 Python이면
분명한 메시지로 멈추게 하기 위해서입니다. pip도 그 Python에서는 고정한 버전을 거부합니다.

Linux와 macOS:

```sh
python3.12 -c "import sys; assert sys.version_info >= (3, 12), sys.version"
python3.12 -m venv ~/op-studio
~/op-studio/bin/python -m pip install --find-links ~/wheelhouse "openphysics==0.0.2"
~/op-studio/bin/openphysics --help
```

Windows(PowerShell. 환경의 프로그램을 직접 부르므로 활성화 스크립트나 실행 정책 변경이
필요 없습니다):

```powershell
py -3.12 -c "import sys; assert sys.version_info >= (3, 12), sys.version"
py -3.12 -m venv "$HOME\op-studio"
& "$HOME\op-studio\Scripts\python.exe" -m pip install --find-links "$HOME\wheelhouse" "openphysics==0.0.2"
& "$HOME\op-studio\Scripts\openphysics.exe" --help
```

`--help`가 Studio 옵션을 보여 주면 설치가 끝난 것입니다.

## 3. Studio 켜고 끄기

```sh
~/op-studio/bin/openphysics                # Linux, macOS
```

```powershell
& "$HOME\op-studio\Scripts\openphysics.exe"  # Windows
```

브라우저가 `http://127.0.0.1:8765/workspace`를 엽니다. 최신 Chrome이나 Edge를 쓰세요.
작업하는 동안 터미널을 열어 두고, 끌 때는 터미널에서 **Ctrl+C**를 누릅니다.

- 항상 같은 주소를 여세요. 브라우저 복구는 정확한 주소에 묶여 있어서, `127.0.0.1` 대신
  `localhost`나 다른 포트로 열면 복구할 것이 없는 상태로 시작합니다.
- 다시 켜기 전에 터미널에 프롬프트가 돌아왔는지 확인하세요. Studio가 아직 그 포트에서
  돌고 있으면 두 번째 실행은 끝나 버리고 브라우저는 예전 서버를 보여 줍니다.

## 4. 설계 두 개와 비교

1. **Choose a starting model**에서 **Optical waveguide**를 고릅니다. 고르기 전에는 제목에
   *No model chosen*, 상태 표시줄에 *Choose a model to start*가 나오고 Study sequence는
   비어 있습니다. 이 화면의 탭 이름은 **Library**입니다.
2. **Geometry**에서 코어 폭을 600 nm, 높이를 300 nm로 정합니다. Width를 바꾸면 코어가
   가운데를 지키고(Left x가 −300 nm가 됨) Height를 바꾸면 바닥이 y = 0에 남으므로
   **Centre on x = 0**을 누를 필요가 없습니다. 재료는 실리콘, 파장은 1550 nm이며 단계
   표시줄에 *4. Study · Ready to run*과 그 옆의 **λ 1550 nm**가 나옵니다. **λ 1550 nm**는
   **Study → Edit wavelength**처럼 **Physics › Optical modes**의 파장 입력란을 엽니다.
3. **Run study**를 누릅니다. 결과에 장 분포와 모드 표(Mode, n_eff, Polarization, Loss)가 나오고 Study
   단계는 *Run complete*가 됩니다. **Run name**에 이름(예: *design A*)을 입력하고 Enter를
   누릅니다. 이름을 붙인 실행은 고정되어 새 실행이 교체하지 않습니다(**Unpin this run**으로 해제하며
   별도의 Pin 버튼은 없습니다). n_eff는 어디서나 소수 8자리이고, 장 그림과 점 조회는 입력과 같은
   nm를 씁니다.
4. 다시 **Geometry**에서 폭을 700 nm로 바꾸고 실행합니다.
5. **Compare**를 엽니다. A와 B가 자동으로 골라지고, 두 장 그림 아래의 표가 모드를 장 겹침으로
   짝짓습니다. 짝지어진 모드마다 행 하나 *A mode 1 ↔ B mode 1*에 양쪽 편광, 겹침, A와 B의 n_eff,
   Δn_eff (B − A), A 대비 Δ %가 나오며 열 머리글에 각 실행의 이름, 크기, 파장이 붙습니다. 짝이 없는
   모드는 그렇다고 밝히고 Δn_eff를 보이지 않습니다.

## 5. 작업 남기기

- **File › Save**(Ctrl+S, 또는 리본 Project 묶음의 **Save**)는 입력, 완료한 실행 전부, 이름과
  고정, 비교를 세션 파일 하나에 씁니다. 끄기 전에 쓰세요. 파일 이름은 응용과 현지 시각으로 정해집니다(예:
  `optical-waveguide-session-2026-11-21-1305.json`). Chrome과 Edge에서는 브라우저의 저장 대화상자가
  저장 위치를 묻고, Messages에 *Saved to …*가 나오며, 다음 Save는 묻지 않고 같은 파일에 씁니다.
  Firefox와 Safari에서는 Studio가 파일 이름을 묻고 파일을 브라우저 Downloads로 넘깁니다(브라우저가 저장
  위치를 묻거나, 같은 이름이 있으면 “ (1)”을 붙일 수 있습니다). Messages에 *Session file … sent to your
  browser's Downloads*가 나오고, 다음 편집이나 실행 전까지 제목에 *<name> · downloaded 시각*이
  표시됩니다(제목의 title 텍스트는 브라우저가 파일 이름에 “ (1)”을 붙였을 수 있다고 알려 줍니다). Studio는 그 이름을 기억하므로 다음 **Save**는 묻지 않고 같은 이름으로 다시 내려받으며(브라우저가
  “ (1)”을 붙일 수 있음), 편집 뒤 제목은 *<name> · changed since downloaded*입니다. 다른 이름은 **File › Save As…**(Shift+Ctrl+S)로 고르며,
  파일마다 담는 것은 [File 메뉴와 파일 종류](workspace.md#file-메뉴와-파일-종류)에 있습니다. 하단은 제목의 저장 표시를 그대로
  보여 주며, 세션 파일 저장 전에는 *Not saved to a file · kept for recovery in this browser*입니다.
  **File › Export › Model file…**은 결과 없이 모델만 저장하고(`optical-waveguide.json`), Runs 목록의 **Export this run**은
  실행 하나를 자체 파일로 씁니다.
- 새로고침하거나 다시 켜면 시작 화면에 **Continue where you left off**가 나옵니다. 마지막
  세션이나 이전 세션은 **Recover (this browser only)**로 이 브라우저에서 복구하고, 세션 파일은
  Library 맨 위의 **Open session file…**이나 **File › Open…**(Ctrl+O)으로 엽니다. 컴퓨터 사이를 옮길 수 있는 사본은 세션 파일입니다. 새 페이지(기본 입력, 실행 없음)에서는
  바로 열립니다. 그렇지 않으면 **Open saved session?** 창이 돌아올 실행과 비교, 바뀌는 것을
  보여 줍니다. Messages에 무엇을 열었는지 나옵니다. 그다음 변경 전까지 제목에 파일 이름과 함께
  *Opened …*, 또는 *Recovered from this browser*가 나옵니다. 세션 파일을 저장한 적이 있으면 지난
  기록으로 *(last sent to a file: … at 시각)*(저장 뒤 바뀐 작업이면 *; changed since*), 저장한 적이
  없으면 *not saved to a file*이 덧붙습니다.
- 페이지를 열어 둔 채 Studio를 다시 켜면 페이지가 스스로 다시 연결합니다. 다시 실행하라는
  안내가 나오면 Run을 다시 누르세요.
- 입력·세션 파일은 버전 7입니다(Joule 가열 입력 추가). 버전 6 파일도 계속 읽습니다. 단위·이름 일괄 변경 이전 Studio가 저장한 파일(버전 1–5)은
  버전을 밝힌 메시지와 함께 거부되고, 그 Studio의 브라우저 초안은 나타나지 않습니다. 설계를
  다시 넣어 저장하세요.

## 검증한 플랫폼

2026-11-08에 Linux(Python 3.12.3, headless Chromium)에서 저장소로 만든 0.0.2 wheel로
확인했습니다. 새 환경에서 extra 없는 `openphysics==0.0.2` 설치(다운로드 캐시가 있을 때 15초),
`openphysics --help`, `openphysics` 명령의 작업 공간 페이지, 4·5단계, **Ctrl+C**, 재시작,
시작 화면에서의 복구까지 했고 비교가 그대로 돌아왔습니다. **macOS와
Windows에서는 이 단계를 아직 확인하지 않았습니다.** 이전 Windows 확인 기록은
[수용 점검표](workspace_acceptance.md)에 있습니다. 단위·이름 일괄 변경으로 파일 버전과
capability 확인이 버전 6이 된 뒤 2026-11-10에 Linux에서
`tools/studio_browser/studio_workspace_browser.mjs`로 설치한 simcase wheel(headless Chrome)에 대해
4·5단계, 재시작, 복구를 다시 확인했습니다. 위의 `openphysics` 설치로 확인한 것은 아닙니다.
2026-11-16에 파일과 capability 확인이 버전 7이 된 뒤 같은 스크립트가 Linux에서 소스 트리(headless
Chromium, Python 3.13)에 대해 통과했습니다. 설치한 wheel로 확인한 것은 아닙니다.
2026-11-20에 작업대 배치(리본, 모델 빌더 옆 Settings, 하단 해석 영역)로 바뀐 뒤 같은 스크립트가
Linux에서 소스 트리의 편집 가능 설치(headless Chromium, Python 3.12)에 대해 다시 통과했습니다.
