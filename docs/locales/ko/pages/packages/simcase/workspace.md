# 실험적 모델 작업공간

[English](../../../../../packages/simcase/workspace.md) | **한국어**

`openphysics`(배포판 `openphysics`와 함께 설치됨)를 실행하거나, 선택 의존성 `simcase[studio]`를
설치한 뒤 `simcase-studio --workspace`를 실행하면 이 작업공간이 브라우저에 바로 열립니다. 포트는 `simcase-studio --workspace --port 8770`으로
지정하며, `--no-browser`를 추가하면 브라우저를 열지 않고 주소만 출력합니다.
기존 첫 화면의 **Open experimental model workspace**를 누르거나 같은 서버의
`/workspace`를 직접 열어도 됩니다. 기존 광학·열 편집기는 `/`에 있습니다.
별도 프록시, JavaScript 빌드, CDN 또는 새 의존성은 필요하지 않습니다.

처음이면 [빠른 시작](workspace_quickstart.md)부터 따라 하세요. 빌드 검토와 첫 사용자 점검에는 [수용 점검표](workspace_acceptance.md)를 사용하세요.

## 작업 공간 배치와 시각 기반

맨 위 페이지 탭 **Library**, **Model**, **Connections**, **Results**, **Compare**는 탭 목록입니다. 보이는
페이지의 탭이 선택되어 Tab 정지점 하나가 되고, 왼쪽·오른쪽 화살표와 Home, End는 다른 탭으로 옮겨 그 페이지를 엽니다.
그 아래 페이지는 모든 탭이 제어하는 탭 패널(`role=tabpanel`)이며 고른 탭의 이름을 따릅니다.
작업대는 상단 명령 리본, 왼쪽 모델 트리와 인접한 Settings, 오른쪽의 넓은
Graphics, 하단 Study/Messages 영역으로 구성됩니다. 리본은 Project, Edit,
Model setup, Physics, Compute로 묶습니다. **Geometry**, **Materials**, **Mesh**, **Study**는
모델 트리와 같은 설정을 엽니다. **Physics → Installed**는 [설치된 물리](#설치된-물리)를 엽니다.
Compute에는 고른 애플리케이션의 실행 명령이 있으며, 모든 모델(광학, 정상 열, 줄 가열, 다중물리)에서
이름은 **Run study**입니다(모델 이름은 헤더에 나옴). 광학 작업 순서는 모델을 가리지 않는 별도 줄에 표시합니다.
하단 영역은 해석 순서와 Messages를 보여 주며, Joule 가열을 실행한 뒤 Results에서는
**Solver log**가 함께 나옵니다.

리본 왼쪽의 **File** 메뉴로 파일을 열고 저장하며, **Edit**에는 **Reset design**이 있습니다. 리본의
**Open…**과 **Save** 버튼은 **File › Open…**과 **File › Save**의 바로 가기입니다
([File 메뉴와 파일 종류](#file-메뉴와-파일-종류)). Save는 모든 모델(광학, 열, Joule 가열, 다중물리)에서
완료된 광학 실행과 비교를 포함한 세션 전체, 또는 실행을 포함한 다중물리 모델을 저장합니다.
**File › Export › Model file…**은 입력만 저장하고, **File › Browser copy**에 브라우저 초안이 있습니다. 하단 상태줄의
**Workspace tools**에서 연결, 복구, Reset layout에 접근하고, 그 옆에 **Installed physics**가 있습니다.
둘 다 상태줄 위로 열리며 한 번에 하나만 열리고, Escape로 열린 것을 닫습니다. Library를
포함한 모든 페이지에서 쓸 수 있습니다. 1000 px보다 좁으면 Compute 명령이 보이도록 리본에서
Physics 묶음을 뺍니다. Installed physics는 상태줄에 그대로 있습니다. 열 결과와 Joule 가열 결과는 현재 탭에만 남습니다.

넓은 화면에서 Settings와 Graphics는 독립적으로 스크롤됩니다. 모델 트리/Settings의
기본 폭은 240/320 px이며 기존 저장 폭을 유지합니다. 두 구분선 모두 오른쪽으로
끌면 해당 패널이 넓어집니다. 구분선에 포커스하고 좌우 화살표를 사용할 수 있으며
Shift는 큰 간격, Home/End는 최소/최대 폭입니다. 좁은 창에서는 트리·설정이
Graphics 위로 이동하고 휴대전화에서는 세로로 쌓입니다. 위치·크기 입력은 두 열로 묶습니다.

로컬 CSS는 밝은 중립색, 파란 선택 표시, 시스템 글꼴과 작은 사각형 조작부를
사용합니다. 기본 글자·입력 라벨은 13 px, 제목은 18–20 px, 숫자 입력 높이는 32 px입니다.
리본·상태 보조 문구는 별도 크기입니다. 토큰은 `workspace.css` 상단에 있습니다.
포커스 표시, 건너뛰기 링크, 텍스트 상태, 기본 폼 컨트롤을 유지합니다. 화면 틀과
선 아이콘은 직접 작성했으며 새 런타임 의존성, 글꼴 다운로드, CDN은 없습니다.

**Connections**는 이름 있는 포트와 곡선 연결선으로 단방향 설정을 보여 줍니다.
노드·포트·트리의 물리 항목을 선택하면 설정을 엽니다. 열원은 분홍색, 온도는
주황색, 형상 갱신은 보라색 점선입니다. 제외한 물리에 의존하는 선은 사라지고
패널 폭이 바뀌면 포트 위치를 따라갑니다. 작은 화면에서는 그래프를 가로로 스크롤합니다.
포트는 설정 확인용이며 임의 배선, 장 전달, 연성 실행은 미지원입니다.
광학·열 단일 물리 계산의 기존 솔버 계약은 유지합니다. Joule 가열 애플리케이션에서는
하나의 해석이 함께 푸는 두 인터페이스, Electric currents와 Heat transfer를 보여 줍니다(배지에
`joule.steady2d` 또는 `joule.temperature2d` 표시). 분홍색 Joule heat → heat source 선이 있고,
사용하는 재료에 σ(T)가 있으면 노드 아래로 돌아가는 주황색 온도 → 전도율 선이 더해집니다.
인터페이스 체크 상자는 없으며 선을 다시 연결할 수 없습니다.

## File 메뉴와 파일 종류

리본 왼쪽의 **File** 메뉴는 메뉴 버튼입니다. Enter, Space, Down은 첫 항목에서 메뉴를 열고, Up과 Down은
항목을 옮기며, Right는 하위 메뉴(또는 다음 메뉴)를 열고, Left는 하위 메뉴를 닫거나(또는 이전 메뉴를 열고),
Escape는 한 단계를 닫고 초점을 돌려주며, Tab은 메뉴를 모두 닫습니다. 단축키는 항목 옆에 보입니다.

| 항목 | 단축키 | 하는 일 |
|---|---|---|
| **Open…** | Ctrl+O (⌘O) | 프로젝트 파일, 또는 어느 모델의 세션 파일이나 모델 파일을 엽니다. 리본의 **Open…**(round 17부터 접근성 이름이 보이는 글자 그대로 *Open…*입니다. 전에는 *Open*)과 Library의 **Open file…**도 같습니다. |
| **Save** | Ctrl+S (⌘S) | [프로젝트 파일](#프로젝트-파일)을 저장합니다: 탭의 모든 모델과 실행. 브라우저의 저장 대화상자로 Save As를 한 뒤에는 묻지 않고 그 파일에 다시 씁니다. Studio가 대신 내려받는 경우에는 프로젝트 파일 이름(Save As나 Save에서 고른 이름, 또는 연 프로젝트 파일)으로 내려받으며, 이 탭이 이미 내려받은 파일이면 먼저 **Download again**, **Save As…**, **Cancel** 중에서 묻습니다(round 25). 프로젝트 파일이 없으면 Save As처럼 묻습니다. 리본의 **Save**와 같습니다. |
| **Save As…** | Shift+Ctrl+S (⇧⌘S) | 고른 이름으로 프로젝트 파일을 저장합니다. 프로젝트 파일 이름, 없으면 프로젝트 이름을 딴 이름(이름 없는 프로젝트는 `untitled-project.json`)으로 시작합니다. |
| **Export › Model file…** | | 보이는 모델의 모델 파일(입력만)을 모델 이름으로 내려받습니다. 예: `optical-waveguide.json`. |
| **Export › Model with runs (session file)…** | | 보이는 모델과 그 실행을 이전 Studio도 여는 세션 파일로 저장합니다. 늘 이름을 묻습니다. |
| **Browser copy › Save browser draft**, **Restore browser draft** | | 광학 입력을 이 브라우저에만 보관하거나 되돌립니다. |
| **Edit › Reset design** | | 모델을 기본 설계로 되돌립니다. |

파일 종류마다 담는 것:

| 종류 | 담는 것 | 이름 | 만드는 명령 |
|---|---|---|---|
| 프로젝트 파일 | 탭의 모든 모델을 각각 세션 파일로 한 파일에(버전 1, [프로젝트 파일](#프로젝트-파일)). | Save As에서 고른 이름, 이름 없는 프로젝트에는 `untitled-project.json` 제안 | **File › Save**, **Save As…** |
| 세션 파일 | 한 모델의 입력과 완료한 실행, 실행 이름과 고정, 비교(광학, 버전 9, [열린 경계](#광학-작업-공간의-열린-경계)가 있으면 10), 정상 열과 Joule 가열의 입력, 또는 실행과 히터 없는 결과를 포함한 다중물리 모델(버전 8). | `<model>-session-YYYY-MM-DD-HHMM.json`, 또는 고른 이름 | **File › Export › Model with runs (session file)…**, **Results › Export this run** |
| 모델 파일 | 모델 입력만: 실행도 계산 결과도 없음(광학, 정상 열, Joule 가열 입력, 버전 7 또는 8, 열린 경계가 있으면 9, 또는 다중물리 문서). | 모델 이름. 예: `optical-waveguide.json`, `heat-conduction.json`, `joule-heating.json`, `heated-silicon-waveguide.json` | **File › Export › Model file…** |
| 브라우저 초안 | 광학 입력, 이 브라우저에만(파일 아님). | — | **File › Browser copy › Save browser draft** |
| 브라우저 복구 | 완료한 실행이 있는 최근 세션, 이 브라우저에만(파일 아님). | — | 자동([노트북 자동 복구](#노트북-자동-복구)) |

같은 모델과 실행이면 세션 파일과 모델 파일은 프로젝트 파일 이전에 Studio가 쓰던 것과 바이트까지 같습니다.
Messages는 입력만 담은 파일을 *model file*, 한 모델과 그 실행을 *session file*, 탭 전체의 파일을 *project
file*이라고 부르며, 화면의 "project"는 그 파일만 뜻합니다.

**Save As가 저장하는 곳.** 브라우저에 웹 페이지용 저장 대화상자(`showSaveFilePicker`, 보안
컨텍스트에서만: `http://127.0.0.1`과 `http://localhost` 포함)가 있으면 Save As는 사용자의 클릭이나 키
입력에서 바로 그 대화상자를 열고, 제안 이름(현재 파일이 있으면 그 이름)과 JSON 파일 형식 하나를 넘긴 뒤
고른 파일에 씁니다. 대화상자는 브라우저가 Studio에 마지막으로 쓴 폴더(대화상자 `id` `openphysics-project`)에서,
파일을 고른 뒤에는 현재 파일의 폴더에서 열립니다(`startIn`은 그때만 넘김). Studio는 쓴 파일을 기억하므로 파일이 프로젝트를 대신할 때까지 **Save**는 대화상자 없이 그 파일에
다시 씁니다. Chromium은 기억한 파일을
쓰기가 끝나야 바꾸므로 Save의 쓰기가 실패하면 파일은 그대로이고 *Project not saved: … could not be written
(…); the file is unchanged.*가 나옵니다. 대화상자에서 방금 고른 파일은 브라우저가 이미 만들거나 비웠을 수
있으므로 첫 쓰기가 실패하면 *…; the browser may have left it empty.*가 나옵니다. 대화상자를 닫으면 *Save As
cancelled; nothing was written.*(Save가 열었으면 *Save cancelled; …*), 쓰기 뒤에는 *Saved to <name>*이 나옵니다. 그 밖의 경우(Firefox, Safari, 보안 컨텍스트가 아닌
페이지)나 저장 대화상자를 쓸 수 없을 때(예: 이를 막는 관리형 브라우저) Studio는 자체 대화상자에서
**File name**을 묻습니다. 영문(ASCII) 글자, 숫자, 공백과 `.`, `_`, `-`, `(`, `)`만 받고(다른 문자, 예를 들어
한글은 지워짐), `.json`이 없으면 붙입니다.
브라우저가 Downloads 폴더에 저장하거나, 그렇게 설정했다면 위치를 묻는다고 안내하고, (Save As로 열었을 때는)
*This browser cannot write to the file, so later saves download again under this name and may add “ (1)”.*라고
알립니다(이 브라우저는 파일에 쓸 수 없어 이후 저장도 이 이름으로 다시 내려받고 “ (1)”이 붙을 수 있음). 저장
대화상자가 동작하는 Chrome과 Edge는 이 대화상자를 보이지 않고 같은 파일에 씁니다. 저장 대화상자가
없는 브라우저는 파일을 덮어쓸 수 없어 저장할 때마다 새 다운로드로 남깁니다. **Download**는 파일을
브라우저에 넘깁니다. 그러면 Messages에 *Session file <name> sent to your browser's Downloads*가 나옵니다.
**Save**로 연 대화상자는 Downloads 폴더에 같은 이름의 파일이 있으면 브라우저가 “ (1)”을 붙일 수 있다고도 알립니다.
Studio는 다운로드가 보관됐는지 알 수 없습니다. Studio는 그 이름을 **File › Open…**으로 연 프로젝트 파일의
이름처럼 프로젝트의 파일로 기억합니다. 그러면 **Save**(와 Ctrl+S)는 그 이름으로 내려받고, Save As도 그 이름으로
시작합니다. 열거나 복원한 파일은 첫 Save가 묻지 않고 내려받습니다. 이 탭이 그 파일을 한 번 내려받은 뒤에는, 다운로드는 그 파일을
바꿀 수 없으므로 Save가 먼저 묻습니다(round 25, A2): *Download design-a-ng.json again? This browser cannot replace the earlier
file and may name the new one design-a-ng (1).json.*와 **Download again**(*Downloaded <name> again: … A download cannot replace the
earlier file, so your browser may add a number such as “ (1)” to its name.*; round 18: 전에는 (1) 사본이 이미 있어도
*<name> (1).json*이라 했음), **Save As…**(그 이름을 채운 이름 대화상자), **Cancel**(*Save cancelled; nothing was written.*).
**Download again** 뒤에는 다음 Save As나 Open까지 헤더가 그 시각과 브라우저가 붙였을 수 있는 이름을 밝힙니다(round 26, C3):
*design-a-ng · design-a-ng.json · downloaded again 11:45 AM (your browser may have named it design-a-ng (1).json)*, 바꾼
뒤에는 *… · changed since downloaded again 11:45 AM (…) · …*.
파일이 없는 프로젝트의 첫 Save는 이름 대화상자를 그대로 쓰고, 브라우저의 저장 대화상자(Chrome, Edge)는 바뀌지 않습니다. 프로젝트를 저장할 때마다 이름 대화상자는 파일에 담길 모델과 각 모델의 실행 수도 밝힙니다: *The file will hold
Optical waveguide (2 runs) and Heated silicon waveguide (1 run).*(round 18; 열 전도나 Joule 가열 모델은 *(no runs)*). 그 파일을 쓰거나 연 뒤로 프로젝트의 모델이 바뀌었으면(광학
모델을 저장한 뒤 가열 모델을 더한 경우처럼) **Save**는 대신 그 이름을 채운 Save As 이름 대화상자를 열고 까닭을 밝힙니다: *This
project now holds Optical waveguide and Heated silicon waveguide; study.json holds Optical waveguide. Save under
this name or another.*(round 17). 저장 선택 창에서 기억한 파일은 전처럼 씁니다. 파일이 프로젝트를 대신하면 저장 대화상자에서 기억한
파일처럼 이 이름도 버립니다. 모델을 바꾸거나 **Reset design**을 해도 같은 프로젝트이므로 이름은 남습니다.
**Export › Model with runs (session file)…**은 각 모델의 세션 파일 이름(연 세션 파일, 또는 거기서 고른 이름)에
같은 규칙을 쓰고 늘 묻습니다. **Export › Model file…**은 늘 내려받습니다.

저장 대화상자(`window.showSaveFilePicker`)의 브라우저 지원. 2026-11-23에
[MDN browser-compat-data](https://github.com/mdn/browser-compat-data) 8.1.10(2026-11-19 데이터,
[MDN 문서](https://developer.mozilla.org/en-US/docs/Web/API/Window/showSaveFilePicker))과
[Chrome File System Access 문서](https://developer.chrome.com/docs/capabilities/web-apis/file-system-access)에서 확인했습니다.

| 브라우저 | 저장 대화상자(`showSaveFilePicker`) | Studio의 Save As |
|---|---|---|
| Chrome, Edge(데스크톱) | 86부터 지원 | 브라우저의 저장 대화상자, Save는 같은 파일에 다시 씀 |
| Opera(데스크톱) | 72부터 지원 | 브라우저의 저장 대화상자 |
| Android용 Chrome | 132부터 지원 | 브라우저의 저장 대화상자 |
| Firefox(데스크톱, Android) | 미지원 | Studio의 이름 대화상자, 그다음 다운로드 |
| Safari(macOS, iOS) | 미지원 | Studio의 이름 대화상자, 그다음 다운로드 |

자동화되거나 헤드리스인 브라우저(`navigator.webdriver`)는 저장 대화상자를 보여 줄 수 없으므로 Studio가 입력한
이름으로 파일을 내려받습니다. 이 데이터에서 API는 실험적(experimental)으로 표시됩니다. 자동 점검은 데스크톱 Chrome의 실제 대화상자를
조작하지 않고 `showSaveFilePicker`를 그 경계에서 바꿔 넣습니다([개발 안내](../../development.md) 참고).

## 프로젝트 파일

**프로젝트 파일**은 Studio 탭의 모든 모델을 담으므로, 파일 하나로 광 도파로와 가열 실리콘 도파로를 실행과
함께 되돌립니다. **File › Save**와 **Save As…**가 쓰고 **File › Open…**이 읽습니다. 프로젝트에는 작업 공간
모델(광학, 정상 열 또는 Joule 가열 입력과 광학 실행)이 그 카드를 고르거나 작업 공간 파일을 연 때부터, 다중물리
모델이 그것을 연 때부터 들어갑니다.

**탭의 프로젝트.** 제목 표시줄은 저장 표시의 말로 프로젝트와 그 파일을 알립니다.

- 브라우저의 저장 대화상자가 쓴 뒤: *Heater study · heater-study.json · saved 13:15*
- 내려받은 뒤: *Heater study · heater-study.json · downloaded 13:15*, 제목 텍스트는 *Your browser may have
  added “ (1)” to the file name.*
- File › Open 뒤: *Heater study · heater-study.json · opened*
- 모델이 바뀐 뒤: *Heater study · heater-study.json · changed since saved 13:15 · kept for recovery in this
  browser*
- 처음 저장하기 전: *Untitled project · not saved to a file · kept for recovery in this browser*
- File › Open으로 세션·모델 파일(`run-a.json`)을 열어 만든 프로젝트가 바뀐 뒤: *Untitled project · changed since run-a.json,
  not saved · kept for recovery in this browser*(round 24, B2, 코디네이터의 후속 결정: 전에는 상태 표시줄의 *Changed since
  session file run-a.json* 옆에서 *not saved to a file*였음). 막 연 때는 여전히 *not saved to a file*이고, 사본의 이름 없는
  복구 기록도 바뀐 뒤 같은 말을 합니다. 어떤 파일도 없었던 프로젝트만 변경 뒤에도 *not saved to a file*입니다.

"Changed"는 모든 모델의 입력, study 설정, 실행, 이름, 고정, 비교와 프로젝트 이름을 셉니다. 페이지, 보기,
선택한 실행은 바뀜이 아닙니다. 바닥줄은 전처럼 보이는 모델의 저장 표시를 보여 줍니다. Library도 제목 줄에
같은 줄을 보여 주고, **Rename**이 붙은 **Project name** 칸은 **Open file…** 줄 오른쪽에 있습니다(한 줄이라 카드와
복원 제안이 첫 화면에 남음). 이름은 앞뒤 공백을 뺀 1–80자이고 제어 문자는 받지
않습니다. 빈 이름은 이유를 말하며 거부하고 칸은 남은 이름을 보여 줍니다. 바꾼 이름은 다음 File › Save에
쓰입니다. 이름 없는 프로젝트는 처음 저장할 때 고른 파일 이름에서 `.json`을 뺀 이름을 받습니다
(`design-a-ng.json`이면 *design-a-ng*). 파일 이름에서 온 이름은 파일을 따라갑니다: `design-b.json`으로 Save As하면
프로젝트 이름이 *design-b*가 되고, 헤더와 Open 알림도 그 이름을 씁니다. **Rename**으로 정한 이름은 Save As가 다른
파일 이름을 써도 유지됩니다. 연 프로젝트 파일의 이름이 파일 이름에서 `.json`을 뺀 것과 같으면 파일에서 온 이름으로,
그 밖의 이름은 Rename으로 정한 이름으로 봅니다. 파일 형식(`name`)은 바뀌지 않습니다.

**모델 바꾸기.** 다른 카드를 골라도 모든 모델은 탭에 남습니다. 프로젝트에 있지만 보이지 않는 모델의 카드에는
*In this project · N runs*가 나오고, 고르면 그 모델이 실행과 자체 Undo까지 두고 간 그대로 보입니다. 아무것도
묻지 않습니다. 떠나기 질문은 파일이 프로젝트를 대신할 때만 나옵니다: *Replace Heater study? Optical waveguide (2
runs) and Heated silicon waveguide (1 run) have runs in no file. Save project first to keep them.*, 단추는
**Cancel**, **Save project, then open**, **Open without saving**.

**저장.** 각 모델의 세션은 그 모델의 writer가 쓰므로 Studio가 그 모델에 쓰는 세션 파일과 같습니다. 세션
파일의 16 MiB 질문은 모델마다 그 이름과 함께 나옵니다(예: *Heated silicon waveguide: Session is 22 MB; the
limit is 16 MiB. Keep the maps…*). 파일 전체는 64 MiB 이하이며, 넘는 저장은 거부하고 내보낼 모델을 알립니다.
예: *The project is 71 MB, over the 64 MiB limit. Export Heated silicon waveguide (22 MB) to its own file, or
remove runs.* (16 MiB 이하 모델 두 개로는 지금 이 한계에 닿지 않습니다.) 알림은 하나이며 모든 모델을 말합니다:
*Saved Heater study to heater-study.json: Optical waveguide (2 runs, the comparison) and Heated silicon
waveguide (1 run, the without-heater result).* 또는 *Project file heater-study.json sent to your browser's
Downloads: …*, 그 뒤에 field나 map 없이 남은 실행. 다른 모델의 실행이 파일에 없다는 말은 **Export › Model with
runs (session file)…**에만 나옵니다.

**열기.** File › Open은 모든 검사를 통과한 뒤에만 프로젝트 파일을 읽으며, 그 전에는 탭에서 아무것도 바뀌지
않습니다. 하나라도 실패하면 *Project not opened: <이유> The current project is unchanged.*로 파일 전체를 거부하고,
작업 공간, 실행, Undo는 그대로입니다. 검사 순서:

1. 텍스트를 해석하기 전에 크기(64 MiB 이하), 그다음 올바른 JSON(맨 앞 byte order mark는 뺌)
2. 바깥 구조: `format`, `version`(더 새 버전은 이름을 들어 거부: *This project file is version 2, newer than
   this Studio reads (version 1). Open it in a newer Studio.*), 모르는 키 없음, 형식, id가 겹치지 않는 1–8개
   모델, 작업 공간 모델은 많아야 하나, `active`가 그중 하나를 가리킴
3. 모델마다 종류와 세션 버전, 파일에서 다시 만든 세션 텍스트의 크기와 SHA-256(*Heated silicon waveguide changed
   after it was saved (its check value does not match).*), 그리고 세션 파일처럼 읽은 세션. 메시지마다 모델
   제목이 앞에 붙음
4. 다중물리 모델마다 Open session처럼 서버의 검사. 서버가 없으면 아무것도 열지 않음

프로젝트에서 읽은 결과는 파일에서 온 것으로 표시되고(*Loaded from file, not recomputed. Results match the
file's checksum.*), 열기는 실행을 시작하지 않습니다. File › Open으로 연 세션 파일이나 모델 파일은 전처럼 열리고
그 모델 하나를 담은 이름 없는 프로젝트가 됩니다. 그 뒤 Save는 이름을 묻고 세션 파일의 이름 위에 프로젝트 파일을
쓰지 않습니다. 이 브라우저에서 복원(Library 카드의 **Restore from this browser**)하면 프로젝트 안의 그 모델만
바뀝니다. 복원한 기록이 저장했던 프로젝트 파일과 같았으면(카드에 *same as file …json*) 프로젝트가 그 파일과
이름을 다시 가리킵니다: 헤더는 *untitled-project · untitled-project.json · saved 2:24 PM*이 되고 File › Save는 그
파일에 쓰거나 그 이름을 제안합니다. 탭에 다른 모델이 함께 있으면 헤더는 *changed since*로 읽힙니다. round 19부터
저장했던 프로젝트 파일 이후로 바뀐 기록도 이름과 파일을 되살립니다: *y3-saved · y3-saved.json · changed since saved
06:15 AM · kept for recovery in this browser*. [세션 버전 12](#광학-세션-파일버전-12)부터 기록은 프로젝트 이름(`project`)도 담으므로, 저장하지 않고 연 파일의
기록도 프로젝트 파일 없이 이름을 되살립니다: *both-models · recovered from this browser · changed since both-models.json, not
saved · kept for recovery in this browser*(round 23, E5; 기록이 아직 그 파일과 같으면 *· as opened from both-models.json ·*, 파일
없는 기록이면 *· not saved to a file ·*), File › Save는
`both-models.json`을 제안하고 묻습니다. 이전 기록은 파일 이름만 담고 프로젝트 이름은 담지 않으므로 이름을 짐작하지
않습니다: 헤더가 출처를 밝힙니다, *Untitled project · recovered from a copy of both-models.json · not saved to a file ·
kept for recovery in this browser*. 상태 표시줄(*Recovered from this browser (opened from both-models.json; changed
since)*)과 같은 말입니다. 프로젝트를
File › Save하면 저장한 모든 모델의 브라우저 복구 기록이, 보이는 모델이든 아니든, 그 프로젝트 파일을 가리키므로
카드마다 가장 새 프로젝트 파일을 말합니다.

**파일.** 키가 이 순서인 compact JSON 객체 하나입니다.

```json
{"format":"openphysics-studio-project","version":1,"name":"Heater study","savedAt":"2026-11-23T13:15:00.000Z","studio":"0.0.2","active":"m2","models":[
 {"id":"m1","kind":"workspace","title":"Optical waveguide","card":"optical","bytes":7422,"digest":"sha256:…","session":{…}},
 {"id":"m2","kind":"multiphysics","title":"Heated silicon waveguide","card":"heated-waveguide","bytes":396949,"digest":"sha256:…","session":{…}}]}
```

(여기서는 여러 줄로 보였지만 파일에는 줄바꿈이 없습니다.) `name`은 프로젝트 이름(1–80자, 파일 이름 아님)입니다.
`savedAt`과 `studio`는 표시용입니다. `active`는 열 때 보일 모델의 id입니다. 모델마다 `id`(`m`과 숫자 1–3개, 저장해도
유지), `kind`(`workspace`: 세션 reader가 읽는 버전 6, 7, 9, 10(열린 경계)의 광학 세션, `multiphysics`: 버전 8 세션, 이 Studio는
탭에 하나, 버전 1 파일에는 7개까지), 표시용 `title`과 `card`(`optical`, `heat`, `joule`, `heated-waveguide`
또는 `null`), 그리고 바뀌지 않은 `session`이 있습니다. 그 세션을 writer로 따로 쓰면 Studio가 쓰는 세션 파일과
바이트까지 같습니다(버전 7은 `JSON.stringify`, 버전 8과 9는 음의 0을 `-0.0`으로 유지). `bytes`와 `digest`는 그
텍스트의 UTF-8 길이와 `sha256:`입니다. 손상되거나 편집된 파일을 찾을 뿐 인증하지는 않으며, 버전 8과 9 안의 실행별
digest도 마찬가지입니다. 모델 하나는 16 MiB 이하라서 모든 모델을 이전 Studio가 여는 세션 파일로 여전히 내보낼
수 있습니다. 버전 1에 없는 것: 모델 사이의 비교, 정상 열과 Joule 가열 결과(입력은 작업 공간 모델에 있음), undo
기록, provider 목록, 실패하거나 멈춘 실행. 브라우저 복구는 전처럼 모델마다 기록하며 프로젝트 전체를 복원하지
않습니다.

**이전 Studio.** 프로젝트 파일은 이 Studio나 더 새 Studio가 필요합니다. 이전 Studio는 자체 메시지(*Session open
failed: Unsupported session format or run count. …*)로 거부하고 작업 공간을 그대로 둡니다. **File › Export › Model
with runs (session file)…**은 이전 Studio도 여는 파일을 씁니다.

**검사.** `tests/simcase/studio_project_file.cjs`는 형식을 검사합니다: −0.0, subnormal, 1e308, 2^31보다 큰
정수가 든 파일의 저장, 열기, 다시 저장이 바이트까지 같음(V-P1), 각 항목의 크기와 SHA-256이 node:crypto와
`tests/simcase/test_studio_project_file.py`의 Python hashlib와 같음(V-P2), 읽기 검사마다 그 메시지로 거부(V-P3),
16 MiB와 64 MiB 한계의 ±1 바이트, 64 MiB는 해석 전(V-P6). `tools/studio_browser/studio_project_browser.mjs`는
1440 × 900과 390 × 844에서 역할과 접근 가능한 이름으로 브라우저 단계를 밟습니다: 두 모델 실행, 프로젝트 이름
*Heater study*와 제안 이름 `heater-study.json`으로 Save As, 서버 재시작과 새 브라우저 프로필, File › Open, 두 모델이 실행 없이 같은 값을 다시 읽음(V-P7,
V-P13), 기억한 이름으로 다시 Save(V-P11), `window.showSaveFilePicker`에서 바꾼 저장 대화상자(V-P10), 손상된 파일
세 개를 탭 그대로 거부(V-P3). `--old-python`을 주면 이전 Studio에서 파일을 여는 것(V-P9)도 봅니다.

## 첫 광학 해석

1. **Library → Optical waveguide**를 선택합니다(시작 화면이며 탭 이름은 **Library**). (Heated silicon waveguide 카드는
   대신 열과 광을 결합한 모델을 엽니다. [다중물리 모델](#다중물리-모델-열--광-모드)을 보십시오.)
2. **Geometry**에서 코어를 숫자로 편집하거나 코어·가장자리를 드래그합니다.
   슬랩·슬롯·클래딩·구멍은 사각형·원·다각형을 추가해 만들고 형상마다 재료를 고릅니다.
   실리카 배경은 유지됩니다. 사각형의 **Width**를 바꾸면 가로 중심이 유지되고(Left x가
   변화량의 절반만큼 움직임) **Height**를 바꾸면 아래 변이 유지되므로, y = 0에 놓인 코어는
   그 자리에서 가운데를 지킵니다. 가운데를 지키면 계산창을 벗어나지만 왼쪽 변을 지키면 들어가는 경우에는
   Width가 왼쪽 변을 지키고 Messages가 그렇게 말합니다: *Width set to 3000 nm. Left x kept at −1500 nm:
   centred, the shape would leave the window.* (Left x −1500, Bottom y −1200, Width 3000, Height 700 순서로 입력한
   3000 nm 기판은 (−1500, −1200)에 놓인 3000 × 700 nm 사각형). Width는 입력란에 포커스가 들어왔을 때의 형상에서
   계산하므로 입력 도중의 숫자가 형상을 옮기지 않습니다. 어느 쪽으로도 들어가지 않는 크기는 기존 규칙대로
   거부되며, 거부된 값은 입력란에 남아 같은 형상의 다른 값이 바뀔 때 다시 적용을 시도합니다. 이전에
   저장한 프로젝트는 저장된 좌표를 그대로 씁니다. 단계 표시줄의 **4. Study**에는 *Ready to run*이,
   현재 입력의 결과가 생기면 *Run complete*가 나오고, 옆의 파장(예: **λ 1550 nm**)은 파장 입력란을
   여는 버튼이며 이름은 *Wavelength 1550 nm, edit*입니다. 필요하면 **Physics › Optical modes**(설정 제목도 *Optical modes*) 또는 Study 실행
   설정에서 파장을 바꿉니다. **Modes to find**처럼 두 곳은 같은 입력란이며, **Study → Edit wavelength**와
   단계 표시줄의 파장은 Optical modes의 그 입력란에 포커스를 둔 채 엽니다. Study 설정은 Results가 어느
   실행을 보여 주든 다음 실행이 쓸 입력도 밝힙니다: *Next run uses 700 × 300 nm · Silicon · λ 1550 nm ·
   core mesh 30 nm · Modes to find 2*. **Also compute group index**를 켜면 *· group index on*이 붙습니다.
   리본은 **Run study** 옆에 다음 실행이 무엇을 하는지, 그리고 이 탭에 있으면 마지막 비교 가능한 실행이 얼마나 걸렸는지
   밝힙니다(round 18; round 17은 느리게 하는 선택만 밝힘): *Open boundary · 2 modes · 2 searches · group index on (3 solves) ·
   last such run 3:40*. 경계(*Closed window* 또는 *Open boundary*), **Modes to find**(*4 modes*, *1 mode*; round 28 G2부터, 작업 줄이
   밝히는 것처럼 밝혀서 슬래브 바로 가기가 4로 정한 개수가 다음 실행 전에 보임), 열린 경계의 검색 수(*1 search* 또는 *2 searches*), 풀이를
   늘리는 선택과 그 마지막 뒤의 풀이 수(*group index on*, 열린 경계의 *PML check on*: 모드마다 많아야 한 번 더 풂; 둘 다면
   *group index on · PML check on (5 solves)*), 탭에 시간이 있는 비교 가능한 실행이 있으면 그다음 *last such run m:ss*입니다. round 20부터 그런 실행이 없으면 시간 부분이 없습니다(*Closed window · 2 modes*): round 19의 *no timed run in this tab yet*(그 전에는 *no earlier run*)은 시간을 잰 실행이 무엇이냐는 물음을 낳았고, 탭에서 다른 경계나 군굴절률 상태로 계산한 실행 옆에서 맞지 않았습니다. 비교 가능한
   실행은 경계 종류와 군굴절률 상태가 같은 실행이며, 그 시간은 이 탭에서 작업 시작부터 결과까지의 실제 시간으로 이 탭의
   실행에만 보존됩니다: 연 실행과 복원한 실행에는 없고 어떤 파일에도 담기지 않습니다. round 23(E3)부터 군굴절률이 켜져 있으면
   시간 부분은 이 탭에서 경계 종류가 같은 가장 새 실행(군굴절률 상태와 무관)으로 낸 어림값입니다: 그 실행도 군굴절률을 계산했으면
   그 시간, 아니면 그 시간의 세 배(군굴절률은 풀이 두 번을 더함), *Open boundary · 2 modes · 2 searches · group index on (3 solves) ·
   about 3 min*(1분 30초 미만이면 *about 20 s*). 그런 실행이 없으면 어림값도 없습니다(round 20 규칙). round 24(B5)는 비교할 열린
   실행이 파일에서 연 것뿐이던 P04의 경우를 확인했습니다: 세션 파일과 브라우저 복구 기록은 실행마다 완료 시각을 담지만 실제
   시간은 담지 않으므로(세션 형식은 그대로) 그런 실행에는 시간이 없습니다. 어림값은 그 실행을 건너뛰고 이 탭에서 시간이 있는
   더 오래된 실행을 쓰며, 없으면 어림값을 보이지 않습니다. 선택이 켜져 있는 동안 줄
   옆에 **Turn off group index** 버튼이 있습니다. 선택 자신의 편집이라(Undo로 되돌리고, Messages는 확인란과 같은 말을 함) 그
   뒤 줄은 선택이 꺼진 때처럼 읽힙니다. 군굴절률은 계속 입력입니다: 어떤 실행도 그것을 끄지 않습니다. round 23 테스터들은
   실행마다 그것을 켜 둔 채 열린 실행을 3:20–4:00 동안 *Computing job … 2:00*만 보며 기다렸습니다. 2026-11-24에 T18 열린 실행은
   군굴절률 없이 68 s, 함께 199 s 걸렸습니다. 가열 모델에는 군굴절률이 없어 그 줄은 그대로입니다. 이 줄은 크기가 고정된 상자에 있어
   바뀌어도 리본이 움직이지 않습니다(round 23: 아래 슬래브 경고에 자리가 더 필요할 때는 예외). 군굴절률이 켜진 채 **Open boundary**를 고르면 Messages에 경고가 붙습니다: *Group index
   is on: open-boundary runs with it take about three times as long.* 선택은 작업 사이에도 그 상태를 유지합니다.
   코어 메시 크기는 **Mesh**에서 바꿉니다.
3. 필요하면 **Mesh**를 생성하고 **Study → Check inputs**로 문서를 점검합니다.
   두 동작은 광학 장을 계산하지 않습니다. 필요 시 솔버 JSON도 확인·내보내기 합니다.
4. **Run study**를 누릅니다. 기다리는 동안 모델을 바꿔도 결과는 실행 당시
   입력을 유지합니다. Stop waiting은 상태 조회만 중단합니다. 입력을 바꾸면 완료 메시지가
   바뀌므로, 완료 메시지가 바뀐 입력을 설명하는 일은 없습니다. 실행 배너(*Optical run complete…*, 실행
   중에는 **Stop waiting**)는 보기 제목 줄의 일부로 보기 제목(*Results*, *Comparison*) 뒤에 놓여 어떤 제목이나
   컨트롤도 가리지 않고, 그 줄의 높이가 그대로이므로 나타나거나 사라질 때 패널을 움직이지 않습니다.
   *Optical run complete…* 배너는 보인 뒤(결과 페이지를 그린 뒤) 6초 뒤에, 또는 그보다 먼저 클릭, 탭이나 키 입력이 있으면 그때 사라지며,
   Messages에는 같은 말이 남습니다. 도크 제목, 상태 표시줄, 제목 표시줄과
   단계 막대는 보고 있는 실행(고른 실행)을 번호와 이름으로 가리킵니다: 실행 뒤에는 *Run 1 · solved
   from the current inputs*(상태 표시줄은 *press Run to solve again*을 덧붙임), 보고 있는 실행의 입력이
   다르면(편집 뒤나 이전 실행을 골랐을 때) 두 기하를 모두 밝혀 *Run 1 · design A 600 × 300 nm · current
   inputs 700 × 300 nm*. 형상이 여럿이면 실행 목록처럼 이름과 크기로 밝힙니다: *Run 6 · Core 500 × 220 + Substrate 3000 × 700 nm*(round 17; 전에는 *2 shapes*)(기하가 같으면 다른 설정을 두 개까지: *· current inputs differ: Wavelength 1550 →
   1310 nm*)(상태
   표시줄은 다른 실행이 현재 입력을 가지면 현재 입력의 출처를 *current inputs from Run 2 · Design B*로 밝히고(round 18;
   전에는 *Run 2 has them*), 아니면 *press Run to compute them*을 덧붙임)이며, 입력을 편집하지 않았으면 Results와 Compare에서 제목 표시줄이 *viewing Run 1 · design A
   (other inputs)*를 덧붙여 그 차이가 저장하지 않은 편집으로 읽히지 않게 합니다(Model 탭의 제목은 현재
   입력만 설명함). 편집, Undo나 Redo 뒤에 현재 입력과 스터디 설정(기하, 재료, 파장, 메시, Modes to find, 군굴절률,
   경계와 검색 목표)이 어떤 실행과 같으면 Messages가 편집 메시지 뒤에 가열 모델의 문장 *No need to run: Run 5 already
   has these results. Run study adds a copy with the same values.*와 **Show Run 5**를 붙입니다. 그 버튼은 입력을
   바꾸지 않고 그 실행을 Results에 보입니다(round 18). round 20부터 그때 편집 메시지는 자기 문장만 남기고 실행하라는
   요청을 뺍니다(*Modes to find set to 3. No need to run: Run 6 already has these results. …*). 어떤 실행과도 같지 않은
   편집은 *… Run explicitly to compute new results.*를 그대로 둡니다. Run study는 눌리면 그래도 실행합니다. 고른 실행의 Inputs 행 아래 **Use this run's inputs**는 그 실행의 입력(Modes to find와
   군굴절률 선택 포함)을 묻지 않고 바로 현재 입력으로 불러옵니다. 실행은 그대로 남기 때문입니다. Messages는 바뀌는
   설정만 이전 → 이후로 밝힙니다(*Current inputs set from Run 1 · design A: Width 700 → 600 nm · Modes to find
   4 → 2. The next run uses them; Undo takes them back.*). 같은 문구는 다음 입력 편집까지 실행 패널의 버튼이
   있던 자리에도 남습니다. 입력
   편집 하나이므로 **Undo**가 Modes to find와 군굴절률 선택까지 모두 되돌리고 **Redo**가 다시 적용합니다. 실행 전에는 *Nothing is
   computed until you press Run*과 *Optical adapter ready · explicit Run required*입니다. 실행 번호는 탭이 열려 있는 동안 바뀌지 않습니다(round 17). 새 실행은 지금까지 쓴 가장 큰 번호 + 1을 받으므로,
   실행 20개 한도가 가장 오래된 고정되지 않은 실행을 내보내도 나머지는 번호를 유지하고, Messages가 내보낸 실행을
   밝힙니다(*Run 3 (closed · 4 modes · 700 × 300 nm) was dropped: up to 20 runs are kept; pin a run to keep it.*;
   Add runs from file도 내보낸 실행을 같은 방식으로 밝힙니다). round 23(E4)부터 내보내기 문구는 모두 실행 목록 라벨과 같은
   부분으로 실행을 부릅니다: 경계(*closed*, *closed near 2.46*, *open (PML 1 µm)*), 2가 아닐 때의 Modes to find, *n_g*, 그리고
   형상. 그래서 *Run 4 (closed · n_g · 600 × 300 nm)*는 목록의 *Run 4 · closed · n_g · 600 × 300 nm · Silicon*입니다(그 전에는
   *Run 4 (600 × 300 nm · 2 modes)*). Run study 옆 줄, 내보낸 문구, 바꾸기 버튼, Pin 알림 모두 그렇고, 가열 모델은 자기 이름을
   그대로 씁니다. round 18부터 실행 20개가 있고 하나라도 고정되지 않았으면
   **Run study** 옆 상자가 실행 전에 알립니다: *If you run: drops Run 3 (closed · 4 modes · 700 × 300 nm) · pin it to keep it*(round 20;
   전에는 실행이 진행 중인 듯 *Running drops …*였음)와
   **Pin Run 3**. 그 버튼은 그 실행을 고정하고 줄을 다음 고정되지 않은 실행으로 옮기거나 없앱니다. round 22(V4)부터
   Messages는 그 대신 다음 결과가 내보낼 실행을 밝힙니다: *Run 3 pinned. If you run: drops Run 4 (closed · 4 modes · 700 × 300 nm) ·
   pin it to keep it*(실행이 계산 중이면 *Run 3 pinned. When this run finishes, Run 4 (…) is dropped*). 내보낼 실행이 없을
   때만 평소의 고정 메시지입니다.
   round 21부터 현재 입력이 어떤 실행의 입력과 같아 Messages가 *No need to run: Run 6 already has these results*라고 적는
   동안 이 줄은 숨고, 입력이 모든 실행과 달라지면 돌아옵니다(아래 가열 모델의 줄도 그 모델에 같은 규칙을 따름).
   round 21부터 **Run study**는 바로 시작합니다: round 19와 20이 그런 실행 전에 보이던 대화 상자(*Running drops Run 3 …*와
   Pin Run 3 and run, Run, Cancel, 그리고 *Waiting for your answer* 문구)는 없어졌습니다. 답을 기다리던 실행은 사용자가
   다른 곳을 보는 동안 아무것도 계산하지 않았기 때문입니다. 실행이 계산하는 동안 줄은 *When this run finishes, Run 3
   (closed · 4 modes · 700 × 300 nm) is dropped*로 읽히고, 그때도 **Pin Run 3**가 동작합니다: Run 3를 남기고, 줄은 다음 고정되지 않은
   실행이 있으면 그것을 밝힙니다. 고정하면 결과가 내보내야 할 수보다 고정되지 않은 실행이 적어질 때(마지막 고정되지 않은 실행:
   결과에 그 자리가 필요함)는 Pin이 없습니다. 내보내기는 결과가 도착할 때만, 그때의 가장 오래된 고정되지 않은 실행에 일어납니다.
   Messages는 실행 자신의 메시지 뒤에 *Run 3 (closed · 4 modes · 700 × 300 nm) was dropped*를 덧붙이고, 새 결과 말고도 고정되지 않은
   실행이 있으면 **Keep Run 3, drop Run 4 (closed · 4 modes · 700 × 300 nm) instead** 버튼을 둡니다(Run 4는 그런 실행 중 가장 오래된
   것). 버튼은 Run 3를 제자리로 되돌리고 Run 4를 내보냅니다: *Run 3 (…) is back; Run 4 (…) was dropped instead.*, 그 뒤 버튼은
   더 없습니다. 앞선 다른 실행이 모두 고정되어 있으면 바꿀 실행이 없고, round 22(V4)부터 문구가 그 까닭을 말합니다: *Run 3 (…)
   was dropped; every other earlier run is pinned, so no other run can be dropped instead*. 탭은 실행을 20개보다 많이 두지 않습니다([실행 보관](#실행-보관-값과-필드) 전에는 여섯 개). 버튼은 다음 Run study가 시작되거나 실행 목록이 바뀔 때(파일 열기,
   세션 복원, 파일에서 실행 추가, Start new)까지 동작하고, 지난 버튼은 아무것도 하지 않고 사라집니다. 메모리에만 있습니다.
   Add runs from file은 내보낸 실행을 여전히 위 문장으로 밝힙니다. 실행 보관부터 한도는 실행 20개이며, 그 필드는 하나의 예산 안에서 보관합니다([실행 보관](#실행-보관-값과-필드)). [세션 버전 12](#광학-세션-파일버전-12)부터
   파일과 브라우저 복구는 번호가 목록 안 자리와 다를 때 번호를 담고, File › Open, Open project, Restore는 그 번호를
   유지합니다: 가장 큰 번호가 8인 파일 뒤의 다음 실행은 Run 9입니다. 이전 버전 파일은 파일 순서대로 1부터 번호를 매기고,
   파일에서 추가한 실행은 가장 큰 번호 다음부터 이어집니다(*Added Run 2 and Run 4 of design-b.json as Run 9 and Run 10.*).
   열기나 복원의 어떤 메시지도 번호에 대해 말하지 않습니다(round 19는 열 때마다 *Runs are numbered from 1 in this tab;
   …*라고 했음): 버전 12 이전에 쓴 세션은 실행 번호를 담지 않으며, 그 실행은 파일 안 자리로 번호가 매겨집니다. Studio는
   그 번호가 정확할 때만 이전 버전을 씁니다.
   이 탭이 계산하지 않은 현재 실행은 그 출처를 밝힙니다: Open session 뒤에는 *Run 2 · read from
   file, not recomputed*, 복구 뒤에는 *Run 2 · recovered from this browser, not recomputed*이며
   상태 표시줄은 *has the results of the current inputs*를 덧붙입니다(round 20; 전에는 이미 결과가 있는 실행 옆에서
   *press Run to compute it here*라고 요청했음). 실행 목록 항목은 실행을 번호와 이름으로
   가리키고(*Pinned · Run 1 · design A · closed · 600 × 300 nm · λ 1550 nm · 3:50:12 PM*) 시각은 초까지 나옵니다.
   Compare의 선택 목록과 제목도 실행을 같은 방식으로 가리킵니다. 형상이 여럿인 실행은 처음 세 형상의 이름과
   크기를, 그 뒤는 *+N more*로 적습니다. 모든 실행 이름은 실행 번호와 이름 바로 뒤에 경계 태그 *closed* 또는
   *open (PML 1 µm)*을 둡니다(실행 목록, Compare 선택 목록, Compare 제목, n_eff 표의 실행 줄). 선택 목록에서
   이름이 잘려도 경계가 보입니다: *Run 7 · open (PML 1 µm) · Core 500 × 220 + Substrate 3000 × 700 nm · Silicon ·
   λ 1550 nm*. round 21부터 경계 태그 뒤에 연구가 기본값과 다르게 계산한 것을 적어 같은 설계의 두 실행을 구별합니다:
   Modes to find가 2가 아니면 *· 4 modes*(*· 1 mode*), 군굴절률을 계산했으면 *· n_g*: *Run 7 · open (PML 1 µm) · 4 modes ·
   n_g · Core 500 × 220 + …*. 둘 다 형상 앞에 오므로, 이름보다 좁은 선택 목록이 끝에서 자르더라도(전체 이름은 제목 텍스트)
   보입니다. Compare는 가장 새 실행 두 개로 열리며,
   오래된 쪽이 A, 새 쪽이 B입니다(방금 계산한 실행이 B). Compare에서 고른 쌍이나 두 실행 모두 이름이 있는 쌍은 새
   실행이 생겨도 유지됩니다. 직접 고른 쌍이면 Compare에 *Run 5 is newer than this pair · Compare Run 5 with B*가 나오고
   그 버튼은 가장 새 실행(B)을 그 쌍의 B(A로)와 비교하며, 그 쌍이 저절로 바뀌는 일은 없습니다. 두 실행에 이름이 있어서만
   유지된 쌍이면 대신 동작 하나를 제안합니다(round 24, B4): *Run 7 is newer than this pair · Compare the two newest: Run 6
   and Run 7*. 이 버튼은 새 실행이 생겼을 때처럼 가장 새 두 실행을 보여 줍니다(동작 하나로 가장 새 쌍에 닿으므로 그 옆에
   *Compare Run 7 with B*는 두지 않습니다). 프로젝트 파일은 그 쌍을 저장하고 열면 그 쌍을 다시 보여 줍니다. 파일에서
   읽은 쌍이 가장 새 두 실행이 아니면 고른 쌍으로 봅니다. 다만 두 실행 모두 이름이 있으면 이름 때문에 유지되는 쌍으로 보므로
   (round 25, A3), 새 실행 뒤 Compare는 위와 같이 *Compare the two newest: …*를 제안합니다. 실행 목록은 새 실행이 위에 오므로 Compare에서는
   두 카드 끝에 *Compare A*, *Compare B* 배지가 붙습니다(*· Compare A*, *· Compare B*로 읽힘). 고른 실행이 사라지면 둘 다 그 쌍으로 돌아갑니다.
   고른 것으로 보이는 실행 카드는 정확히
   하나입니다(포인터가 올라간 다른 카드는 테두리만 바뀜). Compare에서 실행 목록의 실행을 누르면 그 실행을
   고르고(Run name과 실행 명령이 그 실행에 적용됨) Compare는 그대로 남습니다. A와 B는 그림 위의 선택
   목록으로 고르고(보조 기술에는 *Run A*, *Run B*라는 이름이며 전체 실행 이름이 제목으로 붙습니다, round 17), 목록 아래 **Open Run 1 · design A in Results**가 고른 실행을 Results에서 보여 줍니다.
   입력 오류, 진행 중인 계산이나 작업, 지원하지 않는 입력처럼 Run을 막는 것이 있으면 도크 제목은
   상태 표시줄의 문구를 그대로 씁니다.
5. **Run name**을 입력하고 Enter를 누릅니다. 이름을 붙인 실행은 고정되어 새 실행이 교체하지
   않습니다. 별도의 Pin 버튼은 없으며, **Unpin this run**으로 해제하고 Run name에서 Enter를 누르면 이름 붙은
   실행을 다시 고정합니다. 모델을 변경해
   다시 실행한 뒤 **Compare**에서 A/B, 짝지어진 모드, 성분, probe와 단면을 선택합니다.
   두 장(field) 그림이 먼저 나오고, 제목은 쪽과 실행으로 이루어집니다(A 쪽의 *A*라는 이름의 실행은
   이름을 두 번 쓰지 않음). 그림은 같은 실행에 Results가 그리는 창(코어를 가운데 둔 창)을 Results 그림과 같은
   높이로 그리며, Compare를 열면 창(pane)이 스크롤되어 그림의 가운데가 보이고 짝지어진 모드 선택은 그 위에
   남습니다. probe 줄(*No point selected.*)은 각 그림 아래에 있고, A와 B의 형상, 파장, 코어 메시를 밝히는
   문장은 그림 뒤에 옵니다. 그 아래 표는 A와 B의 모드를 장 겹침으로 짝짓습니다([모드 짝짓기](#compare의-모드-짝짓기)).
   짝지어진 모드마다 행 하나 *1 ↔ 1*(A mode 1 ↔ B mode 1)에 양쪽 편광, 겹침, A와 B의 n_eff, Δn_eff (B − A),
   A 대비 Δ %, A와 B의 A_eff, 흡수 손실, n_g가 나오고, 표 위 줄에 각 실행(이름, 크기, λ)이 표시됩니다. n_eff는 어디서나(결과, 모드 목록,
   Compare) 소수 8자리입니다.
6. 첫 번째 저장 버튼인 **Save**(**File › Save**, Ctrl+S)는 탭의 모든 모델과 보관 결과·보기 설정을
   [프로젝트 파일](#프로젝트-파일)로 저장합니다. 이 모델만은 **File › Export › Model with runs (session
   file)…**이 세션 파일로 씁니다. 파일 이름은 응용과 현지 날짜·시각으로 정해지며(예:
   `optical-waveguide-session-2026-11-21-1305.json`) 브라우저 다운로드로 넘어가거나(Studio의 이름
   대화상자에서 이름을 바꿀 수 있음), 브라우저에 저장 대화상자가 있으면 거기서 고른 파일에 씁니다
   ([Save As가 저장하는 곳](#file-메뉴와-파일-종류)). Studio는 다운로드를 브라우저에 넘길 뿐 실제로
   보관됐는지 알 수 없으므로(다운로드는 취소될 수 있음) Messages에 *Session file … sent to your
   browser's Downloads*가 나오고, 저장 대화상자로 쓰기를 마치면 *Saved to …*가 나옵니다. 현재 입력의 실행이
   없으면 알림이 그렇다고 말합니다: *Current inputs (650 × 300 nm) have no run yet.* 저장 표시는
   헤더에 하나만 있고 하단(footer)은 같은 문구를 그대로 보여 줍니다. 현재 파일 이름과 상태가 나오며,
   다음 편집이나 실행 전까지 *design-a.json · downloaded 03:42*(저장 대화상자로 쓴 뒤에는
   *design-a.json · saved 03:42*), 그 뒤에는 *design-a.json · changed since downloaded*(저장 대화상자로 쓴
   뒤에는 *· changed since saved*, **File › Open…** 뒤에는 *· changed since opened*, 복원 뒤에는 *· changed
   since restored*)입니다. 내려받은 뒤에는 헤더와 하단에 *Your browser may have added “ (1)” to the file
   name.*이라는 title 텍스트가 붙고, Save As 이름 대화상자는 *Later saves download again under this name;
   your browser may add “ (1)”.*이라고 알려 줍니다. 다음 **Save**는 묻지 않고 같은 이름으로 내려받습니다. **File › Export › Model file…**은 결과 없이
   모델만 저장합니다. 완료한 실행이 세션 파일에 없으면 *Not saved to a file · kept for recovery in
   this browser*(기록 중에는 *· updating browser recovery*, 쓸 수 없으면 *· browser recovery
   unavailable*), 세션 파일 저장 뒤 바뀌었으면 *design-a.json · changed since downloaded · kept for
   recovery in this browser*가 표시됩니다. **File › Open…** 뒤에는 헤더에 파일 이름과 함께 *Opened …*가, 복구
   뒤에는 *Recovered from this browser*가 나옵니다. 브라우저 복구는 노트북을 마지막으로 보낸 세션 파일이나
   연 세션 파일과, 노트북이 그 파일과 아직 같았는지를 함께 보관하므로 복구한 세션은 그 파일을 밝힙니다:
   같았으면 *Recovered from this browser · same as file …json*, 바뀌었으면 *Recovered from this browser
   (last sent to a file: … at 13:05; changed since)* 또는 *(opened from …json; changed since)*, 저장하거나 연
   파일이 없으면 *· not saved to a file*. 그 파일과 아직 같았던 복원은 그 파일을 현재 파일로 삼으므로
   **Save**는 바로 그 이름으로 내려받고 **Save As**는 그 이름을 제안합니다. 이 제목과 저장 뒤의 *… · downloaded …*(또는 *· saved …*)는 모델이나 실행이 바뀌거나(입력 편집, 실행 추가, 이름 바꾸기, 고정이나 해제) 다른 파일을 열
   때까지 유지됩니다. 탭 클릭(**Library**, **Model**, **Connections**, **Results**, **Compare**), 고른 실행,
   Compare 선택, 장 보기는 변경이 아닙니다. 변경 뒤에는 제목이 무엇이 바뀌었는지 말합니다: 입력 편집이면
   *design-a.json · changed since downloaded*(모델에 현재 파일이 없으면 *Unsaved inputs*), 실행이면
   *design-a.json · changed since downloaded · kept for recovery in this browser*. 헤더에는 revision 번호가 없습니다. Width를 홀수 nm만큼 바꾸면 Left x가
   0.5 nm 단위가 됩니다. 중심은 정확히 유지되고 Messages가 Left x가 옮겨진 곳을 알려 주며(*Width set
   to 600 nm. Left x moved to −300 nm to keep the centre.*), 입력한 값은 드래그 간격에 맞춰지지 않습니다(크기
   입력란 아래 **More about width and height**). 로컬 복구를 사용하려면 *kept for recovery in this
   browser*를 확인합니다(마지막 갱신 시각은 **Workspace tools**에 나옴). 새로고침하거나 Studio를 다시
   켜면 시작 화면의 **Continue where you left off** 카드에 탭이 가지지 않은 저장된 세션이 모두 최신순으로, 그리고 상자만 닫는
   **Not now (choose a model below)**가 나옵니다. round 19부터 첫째이자 가장 눈에 띄는 제안은 모델과 상관없이 실행이 있는
   가장 새 세션입니다: *Restore newest from this browser: Optical waveguide · 6 runs · … · saved 5:46 AM*. 나머지는 더
   오래되었다고 밝힙니다: *Restore from this browser: Optical waveguide · 5 runs · … · older · saved 5:38 AM*(전에는 *Last
   session in this browser*와 *Restore earlier from this browser: Earlier session*이었고, 더 오래된 세션이 먼저 나올 수
   있었습니다). 탭이 광 실행을 가지는 동안 상자는 숨겨집니다. 복원 뒤에는 복원한 기록이 목록에서 빠지고 나머지는 새로고침
   없이 Workspace tools(*Restore earlier session from this browser · …*)에 남습니다. **Open file…**은 제안 상자와 카드가 무엇을 제안하든 Library 맨 위 한 곳(그 줄 오른쪽에 프로젝트 이름)에 고정되어
   있고, 프로젝트 파일은 컴퓨터 사이를 옮길 수 있는 사본이며 브라우저 복구는 이 브라우저에만 남는다는 안내가
   함께 있습니다. 이 버튼은 **File › Open…**과 같습니다. Library 페이지는 브라우저 복구를 한 문구 *Restore
   from this browser*로 부릅니다. 복구는 기록을 쓸 때 보이던 페이지(Model, Results, Compare)를
   그때 고른 실행과 함께 엽니다. Studio가 페이지를 보관하기 전에 쓴 기록과, 페이지를 담지 않는 세션 파일을 열
   때는 실행이 둘 이상이면 Compare, 아니면 Results를 엽니다.
   기본 입력이고 결과가 없는 작업 공간에서는 열기와 복구가 확인 없이 진행됩니다. 그 밖에는
   **Open saved session?**(또는 **Recover saved session?**) 창이 돌아올 실행(이름과 고정
   포함)과 비교, 바뀌는 것, 실제로 있는 물리만 보여 줍니다. 모델을 고르기 전에는 헤더에
   *No model chosen*, 상태 표시줄에 *Choose a model to start*가 나오고 Study sequence에는
   단계가 없습니다. 방금 고른 모델은 첫 편집 전까지 *New model · not saved*, 그 뒤에는
   *Unsaved inputs*로 표시됩니다. 시작 화면은 모델을 고르면 무엇이 일어나는지 밝힙니다: 모델이
   풀 물리를 정하고, 입력한 치수와 완료한 실행은 그대로 두며, 광학·정상 열·줄 가열 모델 사이에서는
   Undo로 되돌릴 수 있습니다. 가열 실리콘 도파로는 자기 편집용 Undo를 따로 가지며, 다른 모델을
   고르면 빠져나옵니다. 모델마다 Save session이 무엇을 남기는지 적혀 있습니다: 광학 모델은 입력과
   실행, 정상 열과 줄 가열은 입력(결과는 탭에만 남음), 가열 실리콘 도파로는 모델과 그 실행입니다.
   광학 실행이 있는 채로 가열 모델을 열면 Messages가 한 줄로 *Optical waveguide runs stay in this tab ·
   Library › Optical waveguide returns to them*이라고 알립니다. 그 뒤의 **More**는 이 탭이 닫거나
   새로고침할 때까지 그 실행을 가진다는 것과, 그 뒤에 무엇이 그 실행을 가지는지를 밝힙니다:
   **Library › Optical waveguide › Restore from this browser**(최신 세션 네 개를 보관하는 브라우저 복구), 그 실행을 가진
   세션 파일로 **Open session**, 또는 아무것도 없음. 탭에 광학 실행이 없고 브라우저 복구에 광학 세션이 있으면(예:
   다시 켠 뒤) Optical waveguide 카드가 그것을 먼저 제안합니다: *Restore from this browser · Optical
   waveguide · Run 1 · design A, Run 2 · 2:25 PM*, 그 옆에 그 실행 없이 모델을 여는(카드 자체와 같음) **Start new (no
   runs)**. 카드마다 끝에 **Open model**이 있습니다. 이미 프로젝트에 있는 모델의 카드는 보이든 아니든 대신
   **Return to Optical waveguide (2 runs)**로 끝나며(round 18; *Open model*이 모델을 초기화할 것처럼 읽혔음), 실행이 없는 모델은
   **Return to Optical waveguide**입니다. round 20부터 문구가 모델 이름을 담으므로(*Return to Heated silicon waveguide (1 run)*)
   두 카드가 같게 읽히지 않습니다. 설명 끝에 *Runs stay in this tab when you switch models; this browser can bring completed runs back after you close it.*이 있습니다(round 28, G4; 그 전에는 브라우저 복구와 어긋나는 *Runs stay in this tab until you close it.*):
   모델을 골라도 이 탭의 실행은 남고, 복원 제안은 브라우저의 실행을 되살립니다. 실행이 있는 탭의 모델을 열면 떠날
   때의 페이지와 상관없이 그 Results로 갑니다(round 17; round 16은 Compare로도 돌아갔습니다): 광학 모델은 마지막으로 본 실행과
   함께, 가열 모델은 마지막 결과 페이지와 함께. 실행이 없는 모델은 Model로 엽니다. 페이지는 맨 위에서 시작합니다. 탭에 다중물리 실행이 없으면 Heated
   silicon waveguide 카드도 가장 새 다중물리 세션을 같은 방식으로 제안합니다: *Restore from this browser ·
   Heated silicon waveguide · Run 1, Run 2 · Heater 2e14 · 2:25 PM*. 기록이 저장했던 세션 파일과 같으면
   기록 시각 대신 파일을 저장한 시각을 씁니다(*· same as file …json, saved 2:24 PM*). 연 파일과 같은 기록은
   어느 시각인지 밝힙니다(*· browser copy 2:25 PM · same as file …json*). round 19부터 카드 위 상자는 카드가 제안하는
   세션까지 모든 세션을 나열합니다(전에는 어느 카드도 제안하지 않는 세션만). 실행이 있는 가장 새 세션이 아닌 세션을 제안하는
   카드는 *· older · saved 5:30 AM*이라고 밝힙니다(*· older · same as file …json, saved …*, *· older · browser copy … · same
   as file …json*). round 20부터 상자는 한 기록에 대해 카드와 같은 시각을 밝힙니다: 저장했던 파일과 아직 같은 기록은 둘 다
   그 파일의 저장 시각을 씁니다(프로젝트를 저장하면 보이지 않는 모델의 기록이 파일과 그 저장 시각에 이어지지만 기록 자체는
   더 일찍 쓰였으므로, 카드는 8:31 AM, 상자는 8:30 AM이었음). 새것부터의 순서는 그대로 기록 자신의 시각을 따릅니다.
   프로젝트의 다른 모델이 이 탭에 있으면 *(already in this tab)*는 탭이 가진 실행을 밝힙니다. 복구 항목은 모두 모델, 실행 수,
   실행(*Run N*, 이름이 있으면 이름과 함께)을 보여 줍니다. 예: *Optical waveguide · 2 runs · Run 1 ·
   design A, Run 2*. 기록이 연 세션 파일이나 마지막으로 보낸 세션 파일이 있으면 그 이름도 붙습니다: 기록이
   그 파일과 아직 같았으면 *· same as file …json*, 아니면 *· file …json, changed since*, Studio가 그것을
   보관하기 전에 쓴 기록이면 *· file …json*. 기록은 모델 하나를 담지만 프로젝트 파일은 둘 다 담을 수 있습니다: round
   18부터 브라우저 복구가 같은 파일에 다른 모델의 기록도 가지고 있으면 항목이 그 모델과 실행을 밝히고 이 버튼이 그것을
   복원하지 않는다고 적습니다(*· also in this project: Heated silicon waveguide · Run 1 (restored separately)*, 탭이 그
   모델의 실행을 가지고 있으면 *(already in this tab)*). 버튼은 자기 모델만 복원합니다. round 20부터 탭이 두 모델 어느
   쪽의 실행도 가지고 있지 않으면 카드 위 상자의 가장 새 제안이 둘 다 복원합니다: *Restore newest from this browser: Optical
   waveguide (6 runs) and Heated silicon waveguide (2 runs) · file both-models.json, changed since · saved 8:44 AM*.
   가장 새 기록을 그 버튼처럼 복원하고, 그 복원이 끝나면(불러오기 질문에 Replace로 답한 뒤; Cancel은 둘 다 멈춤) 모델,
   시각, 파일로 다시 찾은 다른 모델의 기록을 복원한 다음 가장 새 기록의 모델을 Results에 보입니다. Messages는 *Restored
   Optical waveguide (6 runs) and Heated silicon waveguide (2 runs) from this browser, not recomputed.*입니다(round 19~21이
   붙이던 번호 문장은 [버전 12](#광학-세션-파일버전-12)부터 없음). 프로젝트 이름과 파일은 각 기록이
   가진 대로 돌아오며(두 기록의 프로젝트 이름이 다르면 더 새 기록의 이름), 두 기록이 모두 같은 프로젝트 파일과 아직 같았으면 헤더가 *… · saved …*로 읽힙니다. 두 번째 복원이 실패하면
   첫 번째는 남고, Messages가 복원하지 못한 모델을 밝히며(*Heated silicon waveguide was not restored: …*) 그 모델의 카드
   제안은 그대로 남습니다. 탭이 한 모델의 실행을 가지고 있으면 제안은 전처럼 자기 모델만 복원하고 다른 모델을 *(already in
   this tab)*로 밝힙니다. 두 카드의 제안은 그대로입니다. round 21부터 가장 새 제안이 둘 다 복원하는 동안 상자는 다른 모델
   자신의 기록을 다시 나열하지 않고(그 모델의 카드는 여전히 제안함), 오래된 항목은 *also in this project*를 뺍니다: 그것은
   다른 모델의 가장 새 기록을 가리켜, 오래된 항목이 저장된 뒤에 만든 실행을 밝힐 수 있었습니다. 이 브라우저에서의 모든 복원은 먼저 이 탭의
   대기 중인 복구 저장을 씁니다(0.7초 타이머를 기다리지 않고 바로). 그래서 이어 가는 기록이 저장된 기록입니다: 전에는 한 쌍의
   두 번째 복원이 서버가 모델을 확인하는 동안 이 탭이 바꾼 기록을 이어 갈 수 있었고, 그러면 이후의 모든 저장이 다른 탭의 변경으로
   읽혀(*browser recovery changed in another tab*) 자동 복구가 멈췄습니다. 다른 탭이 한 변경은 전처럼 감지합니다.
   저장된 세션은 최신순으로 한 번씩만 나옵니다. 입력(또는 모델)과 실행이 같은 기록은
   보기(페이지, 장 보기), 고른 실행, Compare 선택, 실행의 출처(여기서 계산, 파일에서 엶, 복구), 파일
   연결이나 저장 시각이 달라도 한 세션입니다. 가장 새 기록을 보여 주고, 합친 기록 중 하나라도 파일을
   가리키면 그 파일 이름을 붙이며, 이 탭에 열려 있는 세션은 제안하지 않습니다. 시작 화면은 한 단어, model을 씁니다: **Library** 탭, *Choose a starting model*,
   *Model library · Choose a model*. 카드의 표시는 돌리는 솔버를 적습니다: *Optical mode solver*, *Heat conduction
   solver*, *Electric current and heat solver*, 가열 실리콘 도파로는 *Heat → optical modes · coupled*. **Run
   study**를 누르기 전에는 아무것도 계산하지 않습니다.

현재 모델을 유지하고 결과만 추가하려면 **Add runs from file (inputs unchanged)**을, 모델과 노트북을
모두 교체하려면 **File › Open…**을 사용합니다. *Result for the current inputs*와 *Current inputs
differ from this run: this run 600 × 300 nm · Silicon, current 700 × 300 nm · Silicon*(다른
부분만: 형상, 파장, 코어 메시)은 Results와 고른 실행의 설정에서 결과의 설계 출처를 나타냅니다. 단계
막대의 Results 단계는 보고 있는 실행을 설명하고(*Result for these inputs* 또는 *Current inputs differ
from this run*), 누르면 그 실행을 보여 줍니다. Results 제목 아래 줄은 각 부분을 한 번만 씁니다: 다른
부분은 두 값을, 나머지는 그 뒤에 씁니다(*…, current 700 × 300 nm · Silicon; unchanged: λ 1550 nm ·
core mesh 30 nm*). round 23(E6)부터 광학 줄은 어느 한쪽이 기본값이 아니면 실행을 비교하는 모든 입력(스터디 서명)을
씁니다: 위치만 다를 때 형상 위치(*at Core (-300, 0) nm*), PML 두께와 열린 가장자리를 포함한 경계(*closed window*, *open
boundary (PML 1 µm) on left, right and bottom*), 탐색(*highest n_eff*, *nearest to n_eff 2.46*, 열린 경계의 *search near
2.46*), *Modes to find 4*, *group index on* 또는 *off*: *this run 600 × 300 nm · Silicon · closed window · highest n_eff ·
Modes to find 2 · group index on, current Core 500 × 220 + Substrate 3000 × 700 nm · Silicon · open boundary (PML 1 µm) on
left, right and bottom · search near 2.46 · Modes to find 4 · group index off; unchanged: λ 1550 nm · core mesh 30 nm*(전에는
경계, 탐색, 바뀌지 않은 n_g가 빠졌음). 기본 스터디의 실행과 입력은 전과 같이 읽힙니다. 정상 열과 줄 가열 결과도 같은 말을 씁니다. 광 Results는
모드 표를 먼저, 그 아래에 표본과 선 프로파일이 있는 장 그림을 보여 줍니다. 설계 사이의 모드는
Compare가 순위가 아니라 장 겹침으로 짝짓고, Results와 Compare의 도크 안내는 *Each result keeps the
inputs it was run with · Compare matches modes by field overlap · convergence not certified*입니다.

## 모델 편집

애플리케이션을 고르고 모델 트리나 그림에서 물체·경계를 선택한 뒤 속성을
편집합니다. 고른 형상의 **Name**과 **Material** 칸은 각자 레이블을 가지므로(`for`) 화면 낭독기와
테스트가 그 낱말만으로 이름을 붙입니다(round 19; 전에는 Material 레이블이 목록을 감싸 고른 값까지 읽었습니다).
광학 애플리케이션은 실제 2D 모드 계산을 실행합니다.
Heated silicon waveguide 애플리케이션은 정상 열전도와 광 모드를 결합한 모델 하나로
실행합니다([다중물리 모델](#다중물리-모델-열--광-모드)). 네 인터페이스를 모두 켠 예전 입력 파일은 이전의
개념 미리보기를 열며, 그 결합 그림, 전압, 기계 조건은 아무것도 실행하지 않습니다.

광학 어댑터는 계산창 x = ±1500 nm, y = ±1200 nm 안에 형상 최대 여덟 개를
지원합니다. 사각형, 원, 꼭짓점 3–12개의 다각형이며 배경은 실리카입니다. 형상 재료는
실리콘, 실리콘 질화물, 실리카, 공기, 사파이어, 니오브산리튬, 인화인듐, 비소화갈륨,
플루오린화칼슘, 플루오린화마그네슘 중에서 고르며 모두 1400–1700 nm에서 무손실 physmat
데이터를 사용합니다. 사파이어·니오브산리튬·플루오린화마그네슘은 단축 결정이지만 상광선
굴절률을 등방성 재료로 사용하므로 복굴절과 결정 방향은 다루지 않습니다. 빛을 가두려면
실리카보다 굴절률이 높은 재료(실리콘, 실리콘 질화물, 사파이어, 니오브산리튬, InP, GaAs)의
형상이 하나 이상 있어야 합니다. 형상은 목록 순서대로 그리며 simcase 형상
계약과 같이 **겹치는 곳에서는 나중 형상이 우선**합니다. 립 도파관은 슬랩을 먼저,
리지를 나중에 둡니다. 사각형과 다각형은 꼭짓점 좌표로 제출하므로 nm 단위로 맞닿은
형상은 솔버 문서에서도 정확히 같은 경계를 공유합니다. 파장(1400–1700 nm)은
**Optical modes**, 코어 메시 크기(20–60 nm)는 **Mesh**에서 정하며 새 모델은 500 × 220 nm
실리콘 코어 하나와 1550 nm, 30 nm로 시작합니다. 코어 메시는 이 고굴절 재료
형상에 적용하고 실리카·공기·CaF2·MgF2 형상은 점진적 배경 메시를 사용합니다. 계산창
[-1.5, 1.5, -1.2, 1.2] µm와 PEC 경계는 고정됩니다. **Modes to find**(**Optical modes**와
**Study**에 있음, 1–8의 정수, 기본값 2)는 실행이 요청하는 모드 수를 정합니다. 엔진은 n = 1.45보다
위(Re n_eff)인 모드를 Re n_eff 순서로 남깁니다. 도파 모드가 그보다 적으면 Results가 모드 표 위에
*Found 3 of 8 modes above n = 1.45*라고 알리고, 표에는 그만큼의 행만 있습니다. 결과마다 사용한
형상·파장·코어 메시를 표시하고 요청한 모드 수를 함께 보존합니다.

Modes to find는 모델과 함께 저장됩니다. 모델 파일, 브라우저 초안, 브라우저 복구, 세션의 입력이
이 값을 보존하고([버전 8](#입력-파일의-study-설정버전-8)), 세션의 실행마다 요청한 모드 수도 보존합니다.
이 값의 변경은 입력 편집이므로 **Undo**와 **Redo**가 다루며, 저장할 때까지 제목은 *Unsaved inputs*입니다.
입력 파일을 열면 파일의 값으로 설정되며 버전 6·7 파일이면 2입니다(이전 Studio는 값을 바꾸지 않았음). 세션을
열면 세션의 입력이 버전 8일 때는 그 입력의 값으로, 아니면 이전처럼 선택한 실행의 값으로 설정됩니다. 그래서
모드 4개 실행을 고른 채 모드 2로 저장한 세션(입력은 버전 7)은 이전 파일처럼 4로 열립니다. 새 모델은 2로 시작합니다. 모드 2개일 때 솔버 문서는 이전 Studio가
보낸 문서와 바이트 단위로 같으므로 n_eff, TE 비율, 유효 면적이 바뀌지 않습니다.

**Study**와 **Physics › Optical modes**의 **Also compute group index (3 solves)**(두 곳에 같은 상자 하나,
기본값 꺼짐. 설명은 “Also solves at λ ± 1 nm and takes n_g from the change (about 3× slower). Off: one
solve, no n_g. n_g includes the dispersion of the materials (evaluated at λ ± 1 nm).”이고, 켜거나 끄면 Messages가 다음 실행이 하는 일을 *Group index on: the next run also
solves at λ ± 1 nm and gives n_g (about 3× slower).* 또는 *Group index off: the next run is one solve,
without n_g.*로 알립니다)는 실행 문서에
`results.group_index = {"wavelength_step": "1 nm"}`를 더합니다. 그러면 엔진은 같은 메시를
λ0 − 1 nm와 λ0 + 1 nm에서도 풀고(광학 모델의 재료는 모두 physmat 기록이며 엔진이 푸는 파장마다 값을 구하므로
n_g에 재료 분산이 들어감. **Physics › Optical modes**의 **Material data**가 *physmat materials, evaluated at
each wavelength solved*로 알림), 중앙 차분으로
n_g = n_eff − λ0 dn_eff/dλ0를 돌려줍니다. 실행 시간은 약 세 배입니다([단일 study의 군굴절률](group_index.md)).
꺼져 있으면 문서는 이전과 같은 `optical-shapes-v8` 문서이며 바이트 단위로 같습니다. 켜면 달라지는 것은
`results.group_index`뿐이고, λ0의 n_eff와 장은 같은 값입니다. 이 상자는 Modes to find처럼 모델과 함께
저장되며 **Undo**와 **Redo**가 다룹니다. 새 모델은 꺼진 상태로 시작합니다. 입력 파일을 열면 파일의 값으로
설정됩니다(버전 6·7이면 꺼짐). 세션을 열면 세션의 입력이 버전 8일 때는 그 입력의 값으로, 아니면 선택한
실행의 값으로 설정됩니다. **Use this run's inputs**를 누르면 실행에 맞춰 설정됩니다(n_g가 있는 실행이면 켜짐). 이 상자는 실행과
비교하는 study의 일부입니다. 상자를 켜면 n_g가 없는 실행은 현재 입력의 실행이 아니고, 상자를 끈 채 한
문서 검사는 이전 입력의 검사입니다. 어댑터는 `optical-shapes-v8` 그대로이고 실행의 `settings`도 바뀌지
않습니다. 실행 표 CSV는 n_g를 `group_index [1]` 열에 씁니다.

n_g가 있는 실행은 그 값을 버전 9 칸 `group_index`와 `group_index_method`에 보관합니다. 그 문서는 다른
실행처럼 settings에서 다시 만들고, `results.group_index`를 더합니다. 그 `wavelength_step`은
`group_index_method`에 적힌 간격입니다.

재료 굴절률은 선택한 파장에서 계산하며, 하한은 실리콘 데이터 범위 안에 있습니다.
코어 메시를 거칠게 하면 계산이 빠르고 세션 파일이 작아지지만 n_eff가 달라집니다.
1400 nm에서 500 × 220 nm 실리콘 코어는 20 nm와 60 nm 메시 사이에 약 0.01 차이가 납니다.
설계는 같은 메시 크기에서 비교하고, 차이가 수치적으로 분해되는지는 메시를 줄여 확인하세요.
고정 계산창과 PEC 경계의 영향은 긴 파장과 작은 코어에서 커집니다. 이 설정은 메시나
계산창 수렴을 인증하지 않습니다. 넓은 실리콘·실리콘 질화물 영역을 촘촘한 코어 메시로
계산하면 오래 걸리고 결과도 커집니다. Linux 점검에서 계산창을 채운 실리콘 블록은 20 nm에서
약 22초, 결과 14 MB였으므로 이런 실행이 여러 개면 세션이 16 MiB를 넘을 수 있습니다.
이때는 실행을 하나씩 내보내세요(**Export this run**). 다른 지원 광학 해석은 기존 편집기를
사용하세요. 작업공간이 엔진의 모든 API를 노출하지는 않습니다.

잘못된 숫자 입력은 화면을 옮겨도 유지됩니다. 저장·열기·실행 전에 수정하거나
버려야 합니다. 실행 취소·다시 실행은 최대 60회 편집을 유지하며, 결과의 입력
복원도 새 편집으로 기록합니다. 넓은 화면에서는 패널 폭을 조절할 수 있으며
브라우저에 저장됩니다. 입력 revision은 이 탭의 편집 횟수일 뿐이며 헤더에 표시하지 않고 Git
커밋도 아닙니다.

모델 그림에서 확대·축소, 이동, 전체 맞춤을 사용할 수 있습니다. 그림에 포커스를
두고 +/−, 방향키, Home으로도 조작합니다. 확대는 100–400%이며 각 뷰의 카메라는
탭에서 화면을 이동해도 유지됩니다. 개념 미리보기는 개념도입니다. 광학전용 뷰는 x/y 동일 축척과 nm 치수를 갖는
2D 단면이며 실행 문서와 같은 형상으로 그립니다. 실리카 계산창 x = ±1500 nm,
y = ±1200 nm 위에 모든 형상을 그리는 순서대로 표시합니다. 처음에는 계산창에 맞춰 열리며
**Fit view**로 돌아가고 **Fit shapes**로 현재 설계를 확대합니다. 옅은 격자는 100 nm마다,
진한 선은 500 nm마다 표시하며 위치를 읽기 위한 표시일 뿐입니다. Boundaries에서 고정된 네
PEC 경계를 확인할 수 있으며 열·기계 경계조건으로 지정하지 않습니다. CAD 편집기는
아닙니다. 카메라 변경은 입력·편집 이력·저장 파일·계산 결과를 바꾸지 않습니다.

광학 Geometry 속성 패널은 형상을 그리는 순서대로 나열합니다. 형상을 추가·복제·삭제하고
앞/뒤 순서를 바꾸며 이름과 재료를 정합니다. 사각형은 왼쪽 x·아래 y·폭·높이, 원은
중심·반지름, 다각형은 한 줄에 꼭짓점 하나씩 `x, y`로 편집합니다(필드를 벗어날 때
적용하며 변이 교차하거나 닿으면 안 됩니다). 계산창 밖이나 10 nm 미만 값은 잘못된
초안으로 남아 저장·실행을 막고, 고치거나 되돌리기 전에는 다른 형상을 선택할 수 없습니다.

**Align**은 선택한 형상의 외곽이 정확히 맞닿도록 옮깁니다. x = 0 가운데 맞춤, y = 0 위에
놓기, 기준 형상의 왼쪽·오른쪽·위·아래에 붙이기, 기준 형상 가운데 맞춤을 지원하며 맞닿은
변은 실행 문서에서도 같은 좌표가 됩니다. 계산창을 벗어나는 정렬은 거부하고 형상을
유지합니다. **Drag step**(1, 5, 10, 50 nm)은 드래그 이동 간격과 변·꼭짓점이 맞춰지는 격자를
정하며 모델이 아닌 화면 설정입니다.

Bodies를 선택한 상태에서 그림의 형상을 누르면 선택합니다. 선택한 형상을 드래그하면
이동하고, 노란 핸들을 드래그하면 사각형 한 변·원 반지름·다각형 꼭짓점을 옮기며
놓을 때 적용합니다. 드래그는 Drag step(기본 5 nm)을 따르고, 형상이나 핸들에 포커스를 두면
방향키로 10 nm(Shift: 1 nm)씩 옮깁니다. 미리보기는 놓기 전까지 모델을 바꾸지 않으며
Escape·포인터 취소·창 크기 변경·포커스 상실·페이지 숨김은 미리보기를 버립니다.
이동은 계산창 안으로 제한하고 완료한 조작 하나가 되돌리기 하나입니다. 조작 시작 시의
화면 좌표 변환을 사용하므로 확대·이동 상태에서도 단위 변환이 같습니다.

## 정상 열전도 판

**Library → Steady heat conduction**을 고르면 JSON 없이 정상 열전도 문제를 편집합니다.
판은 왼쪽 아래 모서리가 (0, 0)인 균질 직사각형 하나이며 크기는 mm, 열전도도 k [W/(m·K)]와
균일 열원 Q [W/m³]는 상수입니다. 그림에서 변을 선택하거나 **Heat transfer**를 열어 변마다
조건 하나를 줍니다. 단열(열유속 0), 고정 온도 [K], 안쪽 방향 열유속 [W/m²](양수는 판 안으로
들어옴, 문서의 `inward_heat_flux`), h [W/(m²·K)]와 주위 온도 [K]의 대류 중에서 고릅니다. **Mesh**는 x·y 방향 구조 분할 수를
정하고 노드·삼각형 수를 이 서버의 한도와 함께 보여 줍니다.

온도 수준이 정해지고(어느 변에 고정 온도나 h > 0인 대류), 이웃한 고정 온도 변이 모서리에서
같고, 메시가 서버 한도 안이면 실행할 수 있으며 그렇지 않으면 이유를 표시합니다. 잘못된 값은
강조된 초안으로 남아 고치거나 되돌리기 전까지 실행·저장을 막습니다. **Run study**는
`thermal.steady2d` 문서(정확한 JSON은 **Study**에서 확인)를 만들고 고전 Studio 페이지와 같은
공개 열 경로로 검증한 뒤 계산합니다. 결과는 실제 결과 메시 위에 온도(P1, 삼각형 안에서 보간)
또는 열유속 |q|·qx·qy(삼각형마다 상수)를 열유속 화살표와 함께 보여 주며, 최저·최고 온도와
클릭한 지점의 값을 표시합니다. 결과는 계산할 때의 입력을 유지하고, 편집 후에는 이전 입력으로
표시되며 **Restore run inputs**로 그 입력을 되돌릴 수 있습니다.

열 입력은 입력 파일·초안·브라우저 입력 복구·실행 취소 기록에 저장됩니다(프로젝트 버전 7,
판 길이 mm, 열유속 변은 안쪽 방향 열유속). 열 결과는 탭 안에만 남고 세션·실행 기록·비교·브라우저 노트북 복구는 광학 전용입니다.
과도 열전도, 영역별·온도 의존 재료, 임의 형상은 이 애플리케이션에 없으며(Joule 가열의 영역별 재료는
[Joule 가열 애플리케이션](#이름-붙은-영역의-joule-가열)), 고전 페이지의 JSON
인터페이스가 계속 제공합니다.

## 이름 붙은 영역의 Joule 가열

**Library → Joule heating**을 고르면 JSON 없이 이름 붙은 재료 영역의 정상 Joule 가열을
설정합니다. 계산 영역은 왼쪽 아래 모서리가 (0, 0)인 mm 단위 직사각형과 바탕 재료입니다.
**Geometry**에서 사각형·원·다각형을 최대 여덟 개 더하며(겹치는 곳은 나중 형상이 이김), 각
형상은 재료 하나의 이름 붙은 영역입니다. **Materials**에는 이름 붙은 재료를 최대 여섯 개 두고,
재료마다 열전도율 k [W/(m·K)]와 전기전도율을 줍니다. 전기전도율은 상수 σ [S/m]이거나 기준
전도율·기준 온도·계수 α [1/K]·유효 온도 범위를 가진 선형 저항률 모델
σ(T) = σ₀ / (1 + α (T − T₀))입니다. **Electric currents**에서 변마다 절연, 고정 전위 [V], 안쪽
방향 전류 밀도 [A/m²] 중 하나를, **Heat transfer**에서 단열, 고정 온도 [K], 안쪽 방향 열유속
[W/m²], 대류 중 하나를 고릅니다. **Mesh**는 mm 단위 요소 크기입니다. 사용하는 재료에 모델이
있으면 해석은 `joule.temperature2d`이고 **Study**에서 반복을 정합니다: 방법(Picard 기본, 또는 Newton),
초기 온도와 문서의 기본값(완화 0.5, 상대 허용오차 1e-10, 반복 100회, Studio 상한 500회), 그리고 양식이
1e-9 K로 시작하는 온도 허용오차입니다. Newton은 완화를 쓰지 않고(칸을 숨기고 값은 보관) Studio 상한인
최대 17걸음입니다. Newton을 고르면 한도를 17 이하로 낮추고, 다시 Picard를 고르면 한도를 100으로
되돌립니다. 상수 재료만 쓰면 `joule.steady2d`입니다. 기본 모델은
[영역 Joule 검사](electric_joule.md#재료-영역-온도-의존-joule-가열)의 두 재료 띠입니다.

어떤 변이 전위를 고정하고, 어떤 변이 온도를 고정하거나 h > 0인 대류를 가지며, 주어진 모든 온도가
모든 모델 재료의 유효 범위 안에 있고, 이웃한 고정 변이 모서리에서 같은 값(전위와 온도)을 가지며, Studio의
작업 자리 하나를 열 작업이 쓰고 있지 않으면(열 작업도 Joule 작업을 같은 방식으로 기다림) Run이 켜지고,
아니면 이유를 보여 줍니다.
**Run study**는 문서(**Study**에 표시)를 만들어 Studio의
[Joule route](electric_joule.md#studio-영역-문서)에서 그 영역·메시 한도로 검증하고 실행합니다. 거부(예:
한 모서리의 두 전위, 절점 상한을 넘는 메시, 수렴하지 않는 반복)는 그 문장으로 보여 줍니다.
결과는 Graphics의 실제 메시와 영역 경계 위에 온도와 전위(P1) 또는 전류 밀도 |J|, Joule 전력 밀도,
열유속 |q|(삼각형마다, 화살표 선택)를 그리고, Settings에 수지(공급 전력, Joule 전력, 바깥으로
나가는 열, 온도 범위, 고정 변마다 흐르는 전류, 깊이 1 m당)를, 클릭한 지점의 값을 보여 줍니다.
하단 영역의 **Solver log** 줄은 방법과 횟수("Picard 31 iterations", "Newton 3 steps"), 마지막 온도·전도율
변화, 세 전력 수지를 보여 주고, 펼치면 Picard 반복 또는 받아들인 Newton 걸음마다 |ΔT|, Δσ/σ, 최고 온도를
나열합니다. 재료가 모두 상수이면 한 번에 풀었다고
표시합니다. 결과는 입력을
유지하며 **Restore run inputs**로 되돌립니다. Joule 입력은 입력 파일·세션·초안·복구·실행 취소
기록에 저장되고(버전 7. 반복 방법은 선택 키로, 없으면 Picard이므로 이전의 버전 7 파일은 그대로 읽힙니다.
방법이 추가되기 전의 Studio는 Newton 파일을 경고 없이 Picard로 엽니다), Joule 결과는 열 결과처럼 탭 안에만 남습니다. 다른 애플리케이션으로 옮긴 뒤 끝난 실행의 결과는
Joule 애플리케이션에서 기다립니다. 실행 취소는 진행 중인 작업을 계속 따라가고, 파일을 열면 그 결과를
버립니다. 다중 물리 미리보기의 인터페이스 상자로는 전류와 열만 남길 수 없습니다. 그 조합은 Joule 가열
애플리케이션입니다. CI는 Linux, macOS, Windows에서 설치한 wheel로 이 애플리케이션을 실제
브라우저로 실행합니다([개발 안내](../../development.md)): 기본 모델의 Picard·Newton 실행, 거부된 Newton
실행의 문장 표시, 상수 재료.

## 다중물리 모델: 열 → 광 모드

**Library → Heated silicon waveguide**(“Heat → optical modes · coupled”)를 고르면
[다중물리 문서](multiphysics_document.md)가 열립니다. 한 형상, 한 메시 위의 두 물리를 결합 하나로
잇고 **Run** 한 번으로 풉니다. 템플릿은 6 × 4.5 µm 창 안의 `physmat:SiO2` 위에 놓인
500 × 220 nm `physmat:Si` 코어와, 코어 1.1 µm 위의 2 µm × 100 nm 히터입니다. **Heat 1**은 아래
변을 300 K로 두고 히터 영역을 가열하며, **Modes 1**은 1550 nm 광 모드를 찾습니다. 결합
**Heat 1 temperature → Modes 1 temperature**는 삼각형마다 세 절점 온도의 평균을 넘기고, 광 계산은
그곳에서 n = n₀ + (dn/dT)(T − T_ref)를 씁니다. 히터는 손실 없는 임시 굴절률을 가진 로컬
기록이며, 금속 손실은 이후 작업입니다.

작업 공간은 문서 자체를 편집하므로 양식이 없는 키도 그대로 둡니다. **File › Open…**으로 배포된 [가열 슬랩 예제](../../../../../../examples/simcase/multiphysics_heated_slab.json) 같은
다중물리 문서를 열 수 있습니다.

- **모델 트리.** 컴포넌트 하나(Geometry 1, 쓰인 재료마다 항목 하나인 Materials, 모든 물리가
  공유하는 Mesh 1), 풀이 순서의 자리를 표시한 배지를 단 물리(순환은 주황 번호 하나를 공유),
  결합마다 말로 이름 붙은 항목이 있는 **Couplings**, **Study 1** 노드와 도출된 풀이 순서, 반복 단계가
  있는 **Study**(그룹 이름이 *Study*이므로 트리의 두 항목이 같은 이름을 갖지 않음). Settings는 쉬운 이름을 보여 주고, 파일이 쓰는 이름(물리 type, “Name in file”, 형식 줄,
  결합이면 입력이 소스를 하나 받는지)은 닫힌 **File details** 안에 둡니다. 노드의 빨간 숫자는 그곳에서
  고칠 문제의 수입니다.
- **Add physics**는 설치된 제공자와 그 종류를 매니페스트에서 읽어 포트(단위, 값이 놓이는 곳,
  입력이면 소스를 하나 받는지 더하는지)와 함께 보여 줍니다. 여기서 Studio가 추가하는 것은
  열전달과 광 모드이며, 나머지 종류는 이유와 함께 회색으로 표시됩니다(Joule 가열과 열탄성
  종류는 자기 결합을 스스로 풀므로 시작 화면 애플리케이션으로 남습니다). 두 번째 물리를 더하면
  물리 하나인 모델이 다중물리 모델이 됩니다. **Remove physics**는 그 물리를 가리키던 결합을
  조용히 지우지 않고 고칠 문제로 화면에 남깁니다.
- **Add coupling**은 출력을 고른 뒤 그것을 받을 수 있는 입력 하나를 고릅니다. 나머지는 이유와
  함께 회색입니다(같은 물리, 다른 양, 다른 단위, 이미 소스 하나를 받은 입력). 단일 숫자인 출력은
  예를 들어 *Modes 1 effective index (single numbers, not a map)*처럼 회색으로 나옵니다. 입력 하나를 위해
  열면(Messages의 제안에서 **Add coupling**) From에는 그 입력이 받을 수 있는 출력만 나옵니다: 온도 입력에는
  온도 장만 제안합니다. 전달은 이번 릴리스의
  유일한 방식인 Same mesh입니다. 분명히 이을 수 있는 입력(Heat 1에서 받는 Modes 1 온도)이 있으면
  Messages가 결합을 제안하지만, 직접 추가하기 전에는 아무것도 결합되지 않습니다. 그동안 Modes 1은
  트리, Connections 노드, Settings, Messages에 경고를 답니다: “Temperature input has no source:
  uses n₀ at T_ref (300 K)”. 트리의 **!** 배지는 물리와 문제를 이름으로 가집니다(도움말과 접근성 이름):
  *Modes 1: Temperature input has no source: uses n₀ at T_ref (300 K)*. 결합된 온도가 없으면 광 풀이는 굴절률을 바꾸지 않으므로 모든 재료가
  n₀, 곧 자기 기준 온도에서의 굴절률을 그대로 씁니다(모든 재료의 T_ref가 같을 때만 그 값을
  적습니다). 결합을 지우면 다음 편집까지 **Undo**가 있는 메시지가 남습니다.
- **포트는 끌지 않습니다.** 포트 점은 각 물리가 보내고 받는 것을 보여 주며, 도움말은 짝을 검사하는
  **Add coupling**을 가리킵니다. 트리에서 열전달은 ∿, 광 모드는 λ로 표시해 단일 물리
  애플리케이션과 같습니다.
- **Connections**는 결합으로 그립니다. 풀이 순서 열에 노드를 놓고, 왼쪽에 입력 핀, 오른쪽에 출력
  핀을 단위와 함께 그리며, 결합마다 선 하나를 긋습니다. 포트마다 자기 줄이 있고 점은 노드
  가장자리에 있으며, 선은 결합이 잇는 포트의 점에서 시작하고 끝납니다(Heat 1의 선은 그 아래
  “heat flux”가 아니라 “temperature”에서 나갑니다). 검사에 실패한 결합은 빨간 점선과 짧은
  원인으로 그리고, 물리가 없으면 그림 아래에 나열합니다. 순환은 상자로 묶습니다. 반복 단계가
  없으면 주황, 있으면 파랑입니다. 메시지는 엔진의 기본값을 제안하고, **Accept iteration step**은
  그 값을 `study.loops`에 씁니다(Undo로 되돌림). 값은 Study 1 › Iteration step에서 고칩니다.
- **검사는 편집마다 돌며** `simcase validate`와 같은 규칙을 씁니다. 문제마다 Messages(Show와,
  있으면 한 번에 고치는 버튼: Remove coupling, Use same mesh, 한 물리가 읽지 않는 메시 키 제거,
  Accept iteration step, Fill from physmat), 트리 노드, Settings, 결합이면 그림에 함께 나타납니다.
  엔진의 코드와 문장은 Details 아래에 있습니다. 문제가 남아 있으면 Run이 꺼지고 이유를
  보여 줍니다(“Fix 1 problem in Messages to run”). 결합된 온도를 받으면 모든 광학 재료에
  열광학 계수와 기준 온도가 필요합니다. `physmat:Si`와 `physmat:SiO2`는 이를 갖고 있고, 로컬
  기록에서는 **Fill from physmat**이 physmat 값을 복사해 넣거나(출처를 적음) **Use physmat:…
  instead**가 그 영역을 라이브러리 재료로 바꿉니다.
- **Run study**는 단일 물리 모델과 같은 ▶와 이름으로 모든 물리를 풀이 순서대로 풉니다. ▶는 빈 대체
  텍스트를 가진 장식이라 화면 낭독기는 이름(“Run study”)만 읽습니다. Study 도크는 물리나 반복 단계마다 상태(Waiting,
  Solving…, Done in 0.3 s, 마지막 변화와 함께 Iteration 7 of up to 30, Did not settle, Not run)를
  보여 주고, Connections도 열려 있는 동안 같은 상태를 보여 줍니다. **Stop run**은 엔진의 다음
  단계에서 실행을 멈춥니다. 풀고 있는 물리가 끝난 뒤, 반복 단계 안에서는 지금 반복이 끝난
  뒤입니다. 실패하거나 멈춘 실행은 부분 결과를 남기지 않습니다. Messages가 실패한 물리를
  밝히고, 앞선 완전한 실행은 그대로 남습니다. 스윕은 검사만 하고 실행하지 않습니다(실행 이유에
  적힙니다). 실행 뒤 편집하면 도크와 Connections에서 입력이 바뀐 단계의 행만 **Out of date (last run: Done
  in 0.3 s)**가 됩니다. 단계의 입력은 그 물리, 그 물리로 들어오는 결합, 공유하는 형상·재료·메시·
  스터디, 그리고 그 앞의 모든 단계입니다. 광 모드로 들어오는 결합만 지우면 *Heat 1 · Done in 0.3 s*는
  그대로이고 *Modes 1 · Out of date (last run: Done in 1.2 s)*가 됩니다. 이때 도크 제목은 “Run 1 · the model changed since; press Run to update”, 하단은 “Model edited
  since run 1 · press Run to update”입니다. 실행이 현재 모델의 것인지는 내용으로 정하므로, 손으로
  되돌린 편집(결합을 지웠다가 다시 추가, 또는 Undo)은 다시 현재가 됩니다. 그때 Messages, 도크
  제목, 하단은 같은 문장 “No need to run: Run 1 already has these results. Run study adds a copy with the same values”를
  보여 주어 실행할 필요가 없다는 것을 먼저 밝힙니다(Undo가 선택을 되살렸으면 Messages가 “Also solve
  without heater” is ticked again을 덧붙임). Messages는 **Show Run 1**도 내놓으며, 이 버튼은 모델을 바꾸지
  않고 그 실행을 Results에 보여 줍니다. 세션 파일에서 읽었거나 이 브라우저에서
  복구한 실행에는 풀이 시간이 없습니다: 행은 **From file** 또는 **From this browser**(반복 단계는 *Settled in 7 iterations · from file*처럼
  반복 횟수를 유지), 도크 제목은
  “Run 1 · read from file, not recomputed”(또는 “recovered from this browser, not recomputed”)이고
  하단은 “has the results of the current model”을 덧붙입니다(round 20; 전에는 “press Run to compute it here”). 탭에서 만든 실행은 위 문구를 그대로 씁니다. 이름
  붙은 실행은 광학 애플리케이션처럼 도크 제목과 하단에서 “Run N · 이름”으로 불립니다: “Run 1 · Heater 2e14 ·
  solved from the current model”, “Run 1 · Heater 2e14 matches the model · press Run to solve again”,
  “Model edited since Run 1 · Heater 2e14 · press Run to update”.
- **Also solve without heater**(Run 옆, *(about 1 s more)*)는 광 모드가 결합된 온도를 받는 모델을 열 때 켜져
  있습니다. 결합 실행 뒤 Studio가 같은 실행 경로로 광 모델을 온도 입력 없이 따로 풀어 히터 없는
  열을 채웁니다. 내용이 같은 열이 이미 있으면 건너뜁니다. 광 온도를 정하는 결합이 없는 동안에도
  이 옵션은 그 자리에 남아 꺼진 채 “needs a temperature coupling”이라고 이유를 밝힙니다.
  결합이 돌아오면(다시 추가, Undo 또는 Redo) 옵션은 고른 대로 돌아오고, Messages에
  “Also solve without heater” is ticked again이 덧붙습니다. 레이블은 상자와 연결되어 있어(`for`)
  시간 메모를 포함해 레이블 어디를 눌러도 상자가 켜지거나 꺼집니다. 모델을 열면 상자가 켜져 있으므로 첫
  클릭은 상자를 끕니다(round 19).
- **Results**는 물리마다 한 쪽과 **Coupling check**를 둡니다. 쓰인 풀이 순서와, 결합마다 보낸
  것(“1,726 node temperatures, 300.0–319.0 K”), 받은 것(“3,334 triangle means (mean of 3
  nodes)”), 검사 결과(“Passed · max |received − sent| = 0 K”)를 보여 줍니다. Heat 1은 온도 지도를,
  Modes 1은 답인 n_eff 표를 먼저 보여 주고, 그 아래에 결합 입력의 지도인 코어의 온도와 굴절률(또는
  서버가 문서 값으로 계산한 변화 n − n₀ = (dn/dT)(T − T_ref))을 보여 줍니다. 모드 표는 광 애플리케이션과
  같은 열 | Mode | n_eff | Polarization | Loss (dB/cm) | A_eff (µm²) |([모드 표](#모드-표); 손실 머리글 둘째 줄이 *absorption only (closed window)*, 열린 경계 결과는 *absorption + leakage into the PML*)를 쓰고 행은 *Mode 1*, …이며, 표 아래
  문장은 순위 문장 “Modes are ranked by effective index.”와 모델이 요청한 모드 수 “This model asks
  for 2 modes: Modes 1 › Modes to find”(템플릿은 두 모드를 요청하므로 표에 TE-like와 TM-like 모드가 나옴)(그 설정으로 가는 링크, 편집 뒤에는 “This run asked for …”)를 보여 줍니다.
  n_eff 표에는 “n_eff without heater”와 “Δn_eff (coupled − without heater)”가 부호와 n_eff와 같은
  소수 8자리로 나옵니다(템플릿은 +0.00215086). 표 아래 문장이 기준을 밝힙니다: “without heater =
  Modes 1 alone with no temperature input: every material keeps n₀, its index at T_ref = 300 K”.
  이 열은 따로 푼 광 모델(실행 문서에서 결합, 반복, 열광학 키를 뺀 것을 키 정렬로 비교)이 보이는
  실행의 것과 같을 때 유효합니다. 아니면 “(other model)”로 표시하고 Δn_eff를 비우며,
  **Run Modes 1 alone**으로 새로 풉니다. 결과는 자기 실행을 밝히며 모델을 고쳐도 바뀌지 않습니다.
- **실행.** 실행은 광학과 같은 규칙과 문구로 최대 20개의 값을 보관하고, 그 맵은 16.8 MB 예산 안에서
  보관합니다([가열 실행 보관](#가열-실행-보관-값과-맵); H1 전에는 여섯 개). Results › Runs에
  “Run N · 이름 · 시각” 목록, **Run name**(Enter로 고정), **Unpin this run**이 있습니다. 고정한
  실행은 남고, 21번째 실행이 오면 고정하지 않은 가장 오래된 실행을 바꿉니다. 실행을 고르면 그 결과와
  최신 여부 줄이 보이며 모델은 바뀌지 않습니다. 20개가 모두 고정되면 Run이 먼저 하나를 풀라고 합니다.
  round 21부터 Run study는 광학 모델처럼 바로 시작합니다(round 19의 질문은 없어짐). 그 옆 줄이 한도가 내보낼 실행을
  밝힙니다: 실행 전 *If you run: drops Run 3 (run at 05:31 AM) · pin it to keep it*, 계산 중 *When this run finishes, Run 3
  (run at 05:31 AM) is dropped*, 그리고 **Pin Run 3**. 그 뒤 Messages는 *Run 7 complete. …*에 *Run 3 (run at 05:31 AM)
  was dropped*를 덧붙이고, 광학 규칙대로 **Keep Run 3, drop Run 4 (run at 05:40 AM) instead**를 둡니다(가열기 없는 풀이가
  끝나면 다시 밝힘). round 22(V4)부터 광학 모델처럼 Pin Run 3는 *Run 3 pinned. If you run: drops Run 4 (run at 05:40 AM) ·
  pin it to keep it*라고 말하고, 앞선 다른 실행이 모두 고정된 채 내보내면 *… was dropped; every other earlier run is pinned,
  so no other run can be dropped instead*로 읽힙니다. 가열기 없는 풀이는 실행이 아니므로 아무것도 내보내지 않습니다.
- **파일.** **File › Save**는 탭의 모든 모델을 [프로젝트 파일](#프로젝트-파일)에 씁니다.
  **File › Export › Model with runs (session file)…**은 이 모델과 실행, 실행 이름과 고정, 히터 없는 결과를 한 파일
  `<model-name>-session-YYYY-MM-DD-HHMM.json`에 씁니다(모델 이름을 소문자로, 다른 문자는 하이픈으로,
  최대 40자, 아니면 `multiphysics`). 형식은
  [다중물리 모델의 세션 파일](#다중물리-모델의-세션-파일버전-8)에 있습니다. 탭에 Optical waveguide 실행도
  있으면 그 메시지가 그 실행은 이 파일에 없다고 밝힙니다: “The 2 Optical waveguide runs of this tab are
  not in this file; File › Save keeps them with this model in one project file.” **File › Open…**은 이런
  파일, 광학 세션, 또는 모델 파일 하나만도 엽니다(“Opened model file …: it holds the model but no
  runs.”). **File › Export › Model file…**은 문서만 모델 이름을 딴 모델 파일로 씁니다. 바닥줄은 광학과 같은 문구를 씁니다: “Not saved to a file · kept for recovery in this
  browser”, “heated-silicon-waveguide-session-….json · downloaded 10:15”, “Opened …”, “Recovered from
  this browser”. 제목 표시줄은 [프로젝트](#프로젝트-파일)를 알립니다. 다른 모델 카드를 골라도 이 모델은
  프로젝트에 남습니다. 그러면 이 카드에 “In this project · N runs”가 나오고, 고르면 실행과 Undo까지 그대로
  다시 보이며 아무것도 묻지 않습니다. 파일이 프로젝트를 대신할 때 파일에 없는 실행이 있으면 먼저 묻습니다
  (“Replace … ? Heated silicon waveguide (3 runs) has runs in no file. Save project first to keep them.”).
  파일에 없는 실행 위로 이 모델을 브라우저에서 복원하면 “Leave this model? 3 runs are only in this tab and in
  browser recovery. Save session first to keep them in a file.”라고 묻고, 버튼은 **Cancel**, **Save session**,
  **Leave**입니다.
  그래픽 하단은 형상의 길이 단위를 밝힙니다(“Lengths in µm; …”). 연 파일은
  서버가 먼저 읽으므로 중복 키나 JSON이 아닌 글은 이름을 밝혀 거부합니다. 저장한 파일은
  숫자를 가장 짧은 꼴로 씁니다. 스윕은 검사하되 이 화면은 한 점만 실행합니다.

Studio는 이 문서를 `/api/multiphysics/*`(validate, run, 진행 이벤트, stop, result)로 실행하며
`simcase.multiphysics`의 평범한 사용자로 동작합니다. 화면의 n_eff는 같은 문서를 엔진으로 푼 값과
정확히 같습니다. CI는 이 모델을 실제 브라우저에서 조작하고
(`tools/studio_browser/studio_multiphysics_browser.mjs`, 세션 파일은
`studio_multiphysics_session_browser.mjs`),
`tests/simcase/test_studio_multiphysics.py`와 `studio_workspace_multiphysics.cjs`가 경로와 문구를
검사합니다. 한계: 여기서 편집하는 물리는 열전달(`thermal.steady2d`)과 광 모드(`em.modes2d`)뿐이고,
전달은 Same mesh뿐이며, 다중물리 스윕은 실행하지 않습니다. 형상 양식은 직사각형과 창만 고치고,
다른 도형은 파일에 쓴 대로 둡니다.

### 다중물리 모델의 세션 파일(버전 8)

다중물리 모델은 **버전 8** 세션 파일로 저장합니다. 광학 세션은 여전히 버전 7로, 이전과 바이트 단위까지
같게 쓰므로 이전 Studio와 나눈 파일도 그곳에서 계속 열립니다. 이 절이 형식의 공개 명세입니다.

```json
{"format": "openphysics-studio-session", "version": 8, "application": "multiphysics",
 "document": {"openphysics": "0.3/multiphysics.1", "name": "Heated silicon waveguide", "...": "..."},
 "runs": [{"job": "mp-3f2a9c1d7e4b", "number": 1, "label": "Heater 10 mW", "pinned": true,
           "completedAt": "2026-11-22T10:15:03.120Z", "serverVersion": "0.0.2",
           "document": {"...": "이 실행이 푼 문서"}, "events": [{"event": "physics_started", "physics": "heat1"}],
           "maps": "kept", "result": {"result": "multiphysics-run-v1", "...": "..."}, "digest": "sha256:9c1e…"}],
 "baselines": {"modes1": {"job": "mp-77a01b2c3d4e", "completedAt": "…", "document": {"...": "Modes 1 단독"},
                          "result": {"type": "em.modes2d", "effective_index": {"unit": "1", "values": [[2.443499265702046]]}, "...": "..."},
                          "digest": "sha256:41d0…"}},
 "selected": "mp-3f2a9c1d7e4b",
 "view": {"page": "Results", "selection": "results:modes1", "index_map": "change", "baseline_option": true}}
```

- `application`은 필수이며 버전 8에서 값은 `"multiphysics"` 하나뿐입니다. `document`는 지금의
  모델이며(어느 실행과도 다를 수 있음) File › Export › Model file이 쓰는 그대로 씁니다.
- `runs`는 완료 순서대로 최대 여섯 실행입니다([버전 15](#다중물리-모델의-세션-파일버전-15)는 최대 20). `job`은 서버의 작업 식별자(`mp-`와 16진수 12자리),
  `number`는 화면의 “Run N”이며(다음 실행은 저장된 가장 큰 번호 다음), `label`과 `pinned`는 광학
  규칙(최대 80자, 제어 문자 없음)을 따릅니다. `document`는 그 실행이 푼 문서이고, 그 뒤 모델이
  바뀌었는지는 화면과 같이 키를 정렬해 지금 모델과 비교해 정합니다. `events`는 실행의 진행 이벤트
  (Study 하단 줄)입니다. `result`는 `/api/multiphysics/jobs/{job}/result`의 응답 그대로입니다
  (`multiphysics-run-v1`; 이 화면에서 실행한 물리 하나의 `"0.3"` 모델은 그 종류의 응답, 예를 들어
  `em-modes2d-p1-node-centroid-v2`). 풀이 순서, 물리별 결과, 결합 기록, 잔차를 포함한 반복 단계,
  공유 메시(m 단위 `node_coordinates`, `triangles`, `regions`, `region_names`), 절점별 열 온도(K),
  광 모드의 `effective_index`와 삼각형별 결합 `temperature`(K), `refractive_index.n`,
  `refractive_index.k`(손실이 없으면 null), `index_change`(열광학 모델이 없는 재료가 있으면 null)를
  담습니다. 모드 장은 응답에도 파일에도 없습니다.
- `maps`는 `"kept"` 또는 `"not kept"`입니다. 맵을 보관하지 않은 실행은 `counts`
  (`{"nodes": N, "triangles": M}`)를 가지며 `result`에 `mesh`와 절점·삼각형별 값이 없습니다. 풀이
  순서, 결합 기록, 잔차를 포함한 반복 단계, `effective_index`, 열 범위와 요약은 남습니다. 화면에는
  “Maps not kept in this file: n_eff, the coupling check and the iteration history are.”로 나오고
  실행 목록에는 “values only”가 붙습니다.
- `baselines`는 광 물리마다 히터 없는 결과를 최대 하나 담습니다: 푼 비결합 문서와 그 응답의 모드
  부분입니다. 실행과의 연결은 저장된 키가 아니라 열 때 내용으로 정합니다(실행 문서에서 결합, 반복,
  열광학 키를 뺀 것을 키를 정렬해 비교). 파일의 어느 실행에도, 모델에도 속하지 않는 기준 결과가
  있으면 파일을 거부합니다.
- `selected`는 Results에 보이는 실행(또는 null)이고, `view`는 페이지(`Model`, `Connections`,
  `Results`), 고른 트리 항목, 굴절률 맵(`index` 또는 `change`), “Also solve without heater” 선택입니다.
  실행 취소 기록, 비교, 실패하거나 멈춘 실행, 제공자 목록은 저장하지 않습니다.
- **숫자.** 모든 숫자는 JavaScript `JSON.stringify`가 쓰는 가장 짧은 왕복 꼴(ECMAScript
  Number::toString)의 JSON입니다. 단 음의 0은 음의 0으로 다시 읽히도록 `-0.0`으로 씁니다. NaN과
  무한대는 쓰지 않으며 읽을 때 거부합니다. 정수는 정수로 남습니다. 저장한 모든 값은 비트 단위로
  그대로 돌아옵니다.
- **다이제스트.** 실행과 기준 결과마다 `"digest": "sha256:<hex>"`가 있습니다. `digest`를 뺀 기록을
  모든 객체의 키를 정렬하고 같은 숫자 규칙으로 쓴 JSON의 SHA-256입니다. 잘리거나 손상되거나 손으로
  고친 파일을 알아냅니다. 인증은 아닙니다: 파일을 고치는 사람은 다시 계산할 수 있으므로, 연 결과는
  “Loaded from file, not recomputed. Results match the file's checksum.”으로 표시하고, 그 문장의 title
  텍스트가 *The checksum detects a damaged or hand-edited file; it does not show who made the file:
  whoever edits a file can recompute it.*이라고 알려 줍니다. 복구한 결과는 “Recovered from this browser, not recomputed.”입니다. 광학 세션 파일에는
  다이제스트가 없으므로 연 결과는 “Loaded from file, not recomputed. Studio checks that the file is
  well formed, not who made it.”으로 표시합니다.
- **크기.** 파일은 최대 16 MiB이며 읽기 전에 검사하고, 그 안의 문서는 각각 최대 1 MiB입니다. Save
  session은 파일이 맞으면 모든 실행을 맵과 함께 씁니다(템플릿 메시 실행 여섯 개는 약 2.5 MB). 실행
  보관부터 탭은 맵을 16.8 MB 예산 안에서 보관하므로([가열 실행 보관](#가열-실행-보관-값과-맵)) Save는 탭을 그대로
  씁니다. 파일보다 많이 담은 탭(고른 실행 하나가 예산을 넘거나, 마지막 도착 뒤 입력이 16 KiB 넘게 커진 경우)만
  아직 질문에 닿습니다. 맞지 않으면 아무것도 쓰지 않고 크기를 밝혀 묻습니다: “Session is 22 MB; the limit is 16 MiB. Keep the
  maps of the selected and pinned runs only? …”. **Keep maps for selected and pinned runs**는 나머지를
  `"maps": "not kept"`로 쓰고, **Cancel**은 아무것도 쓰지 않습니다. 고른 실행과 고정한 실행만으로도
  한도를 넘으면 Save session은 거부하고 그 실행을 밝힙니다(“Run 3 alone is 18 MB, over the 16 MiB
  session limit. Unpin it or keep it in a smaller-mesh model.”). 맵을 말없이 버리지 않습니다.

**열기.** 결과는 다시 계산하지 않고 파일에서 읽습니다. 알림은 “Opened … Its results were read from the
file, not recomputed; input undo starts here.”이고, 실행에는 “from file”(또는 “recovered”)이 붙으며,
열기는 어떤 실행도 시작하지 않습니다. 모든 검사는 탭의 무엇이든 바꾸기 전에 돌고, 하나라도 실패하면
검사를 밝힌 메시지로 파일 전체를 거부하며 모델, 실행, 실행 취소는 그대로입니다:

- 크기와 JSON(맨 앞의 바이트 순서 표시는 지움), 실행 최대 여섯(버전 15는 20), 고유한 작업 식별자와 실행 번호, 올바른
  이름·고정·시각·서버 버전, 저장된 실행인 `selected`, 작업공간이 제공하는 화면 상태;
- 실행마다 결과와 문서: 물리 이름과 종류, 서버가 문서에서 끌어내는 풀이 순서, 같은 `from`, `to`,
  `transfer`의 결합(Same mesh는 일치하는 메시와 차이 0), `study.loops`의 반복 단계(각각 수렴, 반복
  횟수보다 하나 적은 잔차, 마지막 잔차는 허용오차 이하);
- 맵을 보관한 실행: 유한한 N × 2 `node_coordinates`, [0, N)의 정수로 된 M × 3 `triangles`, 영역을
  가리키는 정수 M개의 `regions`, 유한한 값 N개의 절점 온도, 유한한 값 M개의 삼각형별 맵, 유한한
  `effective_index`, 저장된 온도의 최솟값·최댓값과 정확히 같은 열 범위, 각 삼각형 세 절점 온도의
  평균과 상대 1e-12 안에서 같은 결합 온도;
- 모든 실행과 기준 결과의 다이제스트(“Run 2 changed after it was saved (its check value does not
  match).”);
- 모든 실행과 기준 문서를 `simcase validate` 규칙으로 서버가 검사(“Run 2's model does not pass
  today's check: …”), Studio가 실행하는 문서인지, 그리고 지금 모델은 File › Open이 모델 파일을 읽듯이 읽음(그
  문제는 Messages에 나옴). 서버가 없으면 파일을 열지 않습니다.

15보다 큰 버전은 이름을 밝혀 거부합니다(“This session file is version 16, newer than this Studio reads
(versions 6–15). Open it in a newer Studio.”. 버전 9~14는 [광학 세션](#광학-세션-파일버전-9), 버전 15는 실행이
여섯 개보다 많은 다중물리 세션이며, 버전 9 아래의 버전 8 구성은 처음 만난 모르는 키로 거부합니다). 다른 `application`(“This session file holds a “…” model,
which this Studio does not read.”), 다른 결과(“Run 2 was saved as result “multiphysics-run-v2”, which
this Studio does not read.”), 다른 문서 봉투(서버 읽기기의 거부를 실행 이름과 함께)도 마찬가지입니다.
버전 6과 7 세션 파일은 이전처럼 열리고, 버전 1–5는 이전의 거부를 유지합니다. 버전 8 이전의 Studio는
버전 8 파일이나 복구 기록을 “Unsupported session format or run count.”로 거부하고 작업공간을
유지하므로, 다중물리 세션에는 이 Studio 이상이 필요합니다.

**브라우저 복구**는 다중물리 모델을 광학 세션과 같은 저장소에 같은 한도로 보관합니다(최신 하나와 이전
세 개, 각각 최대 16 MiB, 변경 0.7초 뒤 기록, 탭 사이 충돌 규칙). 모델에 실행이 있거나 연 뒤 편집했을
때부터 Save session이 쓸 글(버전 8, 실행이 여섯 개보다 많으면 15)로 기록합니다. 실행 보관부터 복구는 탭을
그대로 담습니다. 16 MiB를 넘으면(파일보다 많이 담은 탭) 대화 상자 없이 실행 보관의 순서대로, 곧 고른 실행의 맵,
그다음 고정한 실행과 나머지 실행의 맵을 최신부터 맞는 만큼 두고(H1 전에는 고른 실행과 고정한 실행의 맵만), 표시는 “kept for recovery in this browser without the maps of 2 runs · File › Save
keeps them”입니다. 그래도 한도를 넘으면 새로 쓰지 않고(“browser recovery unavailable: session over 16
MiB · File › Save keeps your work”) 이전 기록이 남습니다. **Restore last session from this browser**, **Restore earlier session from this
browser · Heated silicon waveguide · 3 runs · Run 1, Run 2, Run 3 · 시각**(Workspace tools)과 Heated silicon
waveguide 카드의 **Restore from this browser**는 Open session과 같은 검사를 합니다. 저장했던 세션 파일이나
연 세션 파일과 같았던 기록을 복구하면 광학 기록처럼 *Recovered from this browser · same as file …json*으로
읽힙니다. 방금 연 템플릿은 첫 편집, 실행, 저장 전까지 *New model · not saved*로 읽힙니다. 프로젝트에 프로젝트 파일이
있고 다른 모델도 있으면 가열 모델의 상태 표시줄은 제목 표시줄의 말로 프로젝트 안의 모델에 대해 말하므로 둘이 서로 어긋나지
않습니다(round 18; 제목은 *waveguide-AB · waveguide-AB.json · changed since opened*인데 상태 표시줄은 *New model · not
saved*였음): 파일의 모델 목록에 없으면 *Heated silicon waveguide · in project waveguide-AB.json · not saved since it
joined*, 아니면 *… · in project heater-study.json · saved 13:15* 또는 *… · changed since saved 13:15*이며 제목 표시줄의
브라우저 복구 말이 붙습니다.

모듈 검사는 `tests/simcase/studio_workspace_multiphysics_session.cjs`에 있습니다(버전 8 이전 Studio가
쓴 버전 6, 7 광학 파일이 `tests/simcase/studio_session_fixtures/`에 있고, 이전처럼 열리며 바이트
단위로 같게 쓰임). `tests/simcase/test_studio_multiphysics_session.py`는 Python hashlib과 자체 쓰기기로
다이제스트를 다시 계산합니다. 브라우저 검사는 템플릿, 0.12 µm 메시, 실행 두 개 세션을 저장·열기·다시
저장하고(두 번째 파일은 바이트 단위로 같고, 모든 배열은 서버 응답과 Float64로 같음), 0.08 µm 메시 실행
여섯 개로 16.8 MB 예산과 Recompute Run 1's maps를, 실행 20개와 21번째 실행의 내보내기를, 거부와 브라우저
복구를 검사합니다. 버전 8에 없는 것: 광학과 다중물리 실행을 섞은
세션, 실행 사이의 메시 공유, 파일에서 실행 추가, 결합 실행의 모드 장.

### 가열 실행 보관: 값과 맵

실행 보관의 H1 조각(설계 *Keeping more runs* 7절)부터 가열 모델은 실행 최대 20개의 **값**을 보관하고, 그
**맵**은 광학 모델의 필드와 같은 예산([실행 보관](#실행-보관-값과-필드)) 안에서 보관합니다. 예산은 16 MiB 세션에서
입력 몫 16 KiB를 뺀 16,760,832바이트이며 16.8 MB라고 말합니다. 탭, File › Save, Export › Model with runs,
프로젝트 파일의 항목, 브라우저 복구가 같은 맵을 담습니다.

- **값.** n_eff, 결합 검사, 반복 이력, 절점·삼각형 개수입니다. 모든 실행이 보관합니다. 맵 없는 실행은 파일에서
  약 20 kB(템플릿과 그 고운 메시), 가열 슬래브 예제는 14 kB이며, 그런 실행 20개는 약 0.4 MB입니다.
- **맵.** 메시, 절점마다의 열 온도, 삼각형마다의 결합 입력(온도, n, k, n − n₀)으로, 열 페이지와 모드 페이지의
  맵이 그리는 것입니다. 맵 없는 실행은 [버전 8](#다중물리-모델의-세션-파일버전-8)의 기록대로 `"maps": "not kept"`와
  개수로 씁니다.
- **언제 맵을 놓는가.** 맵이 도착할 때만: 새 결과, 재계산, File › Open, Open project, Restore, 그리고
  **Keep Run N, drop … instead**로 돌아오는 실행입니다. 실행 고르기, 고정, 고정 풀기, 이름 짓기, 히터 없는 풀이,
  Show Run N은 맵을 놓지 않습니다.
- **순서.** 보관하는 맵은 고른 실행의 것, 방금 맵이 도착한 실행의 것(고른 실행이 아닌 재계산이나 되돌린 실행),
  고정한 실행의 것(최신부터), 나머지 실행의 것(최신부터) 순으로, 세션이 예산 안에 있는 동안 더합니다. 맞지 않는
  맵은 건너뛰고 다음으로 오래된 실행을 봅니다. 고른 실행은 혼자 예산을 넘어도 맵을 둡니다. 그러면 Save는 전처럼
  거부합니다(*Run 3 alone is 18 MB, over the 16 MiB session limit. …*).
- **문구**는 광학 문구에서 *fields*를 *maps*로, 실행 이름을 가열 모델의 것으로 바꾼 것입니다. **Run study** 옆에서는
  같은 형상·메시·재료·물리·결합인 최신 실행의 맵 크기로 *If you run: Run 3 (run at 14:02) keeps its values, not its
  maps*와 **Pin Run 3**을, 그런 실행이 없으면 남은 자리가 보관 중인 가장 작은 맵보다 작을 때 *If you run: older
  runs' maps may not be kept (16.8 MB limit) · pin a run to keep its maps first*를 보입니다. 계산 중에는 *When this
  run finishes, Run 3 (run at 14:02) keeps its values, not its maps*, 결과 뒤에는 *Run 3 (run at 14:02) keeps its
  values; its maps were not kept (16.8 MB limit).*와 **Recompute Run 3's maps**, 그리고 고정하지 않고 고르지 않은 다른
  실행의 맵이 그만큼 크면 **Keep Run 3's maps, not Run 4's (run at 14:05)**(*Run 3's maps are back; Run 4 (run at
  14:05) keeps its values, not its maps.*)입니다. 고정한 실행의 맵이 빠지면 *Run 2 (pinned) keeps its values; its maps
  were not kept: the selected and pinned runs' maps are 17.4 MB, over the 16.8 MB limit. Unpin a run to keep the newer
  maps first.*입니다. 트리는 *Runs · 9 of 20*, 실행 목록은 *· values only*, 실행 목록 아래 안내는 *Up to 20 runs are
  kept with their values. Maps are kept up to 16.8 MB. When a result or a recompute arrives, Studio keeps the selected
  run's maps first, then pinned runs', then the newest. Selecting a run does not bring its maps back; Recompute does.
  Pinned runs stay; when a 21st run arrives, the oldest unpinned run is replaced. File › Save keeps every run in one
  file.*입니다.
- **맵 없는 실행.** Results는 n_eff 표와, 저장된 개수와 범위로 된 결합 검사를 보이고, 맵 자리에 *Run 4's maps are
  not kept; its n_eff, coupling check and iteration history are kept. Maps are kept up to 16.8 MB. …*(맵 없이 파일에서
  읽은 실행은 *Maps not kept in this file: n_eff, the coupling check and the iteration history are.*)와 **Recompute
  Run 4's maps**를, 이 탭에서 계산한 실행이면 *· about 10 s*도 보입니다. 그런 실행의 *No need to run*은 *No need to
  run: Run 4 already has these values; its maps are not kept. Run study adds a copy with the same values*이며
  **Show Run 4**와 **Recompute Run 4's maps**가 붙습니다.
- **Recompute Run N's maps**는 실행이 푼 문서를 같은 실행 요청으로 보냅니다. 새 실행이 아닙니다: 번호를 받지 않고
  목록에 들어가지 않으며 모델, Undo, 고른 실행, 히터 없는 결과를 그대로 둡니다. 도크와 상태 표시는 *Recomputing Run
  4's maps · about 10 s*이고 **Stop run**이 동작합니다(*Recompute of Run 4's maps stopped; Run 4 is unchanged.*).
  절점·삼각형 개수가 같아야 하고, 모든 모드의 n_eff(실수부와 허수부), 열 물리마다의 온도 범위, 결합마다의 max
  |received − sent|와 보존 잔차, 반복 단계마다의 잔차가 상대 1e-12(1e-3 미만은 절대 1e-15) 안에서 같아야 하며, 메시
  검사와 반복 횟수는 정확히 같아야 합니다. 맞으면 맵을 같은 실행에 붙이고, 실행은 작업·번호·이름·고정·시각·저장된
  값을 그대로 둡니다: *Run 4's maps recomputed from its stored model; its values match.* 그리고 맵이 도착했으므로 위
  순서를 적용합니다. 아니면 아무것도 바꾸지 않습니다: *Run 4's maps were not recomputed: Modes 1 mode 1 n_eff came out
  2.44565014, stored 2.44565013. Run 4 is unchanged; Run study makes a new run from the current model.*(버전이 다르면
  *(stored by Studio 0.9.3; this is 0.9.4)*가 붙음). 서버가 이제 거부하는 문서는 *Run 4's maps cannot be recomputed:*
  와 서버의 말입니다. 가열 풀이는 단일 스레드에서 비트 단위로 재현됩니다(측정: 템플릿, 그 4모드·0.12 µm 변형, 슬래브
  예제를 각각 두 번 풀어 맵이 비트까지 같았음).
- **측정**(2026-11-25, `tools/studio_heated_retention.mjs`, 단일 스레드): 실행당 텍스트 맵은 템플릿(절점 1,726개,
  삼각형 3,334개, 모드 2개나 4개) 0.37 MB, 0.12 µm 메시 1.49 MB, 0.08 µm 2.79 MB, 가열 슬래브 예제 2.53 MB입니다.
  결과 20개에서 예산은 템플릿 실행 20개 모두(7.7 MB), 0.12 µm 10개, 슬래브 6개, 0.08 µm 5개의 맵을 최신부터
  보관합니다. 압축(단정밀도) 맵은 H1에 들어 있지 않습니다.

검사는 `tests/simcase/studio_heated_retention.cjs`(HK2~HK4, HK6~HK9, HK12~HK14: 형식, 시드 고정 2000단계 순서열,
순서, 문구, 재계산 거부, 복구), 엔진 결과가 있을 때의 `tests/simcase/studio_heated_retention_engine.cjs`(HK1, HK5),
`tools/studio_browser/studio_multiphysics_session_browser.mjs`의 S5와 R21 단계(HK10)입니다.

### 다중물리 모델의 세션 파일(버전 15)

버전 15는 실행을 최대 20개 담는 [버전 8](#다중물리-모델의-세션-파일버전-8)입니다. 최상위 키, 실행 기록(맵 보관, 또는
`"maps": "not kept"`와 `counts`), 다이제스트, 숫자 규칙, 검사가 같습니다. 버전 8은 실행을 최대 여섯 개 담습니다.

- **언제 쓰는가.** 세션의 실행이 여섯 개보다 많을 때만 씁니다. 실행이 여섯 개 이하인 세션은 전처럼 버전 8로 바이트
  그대로 쓰므로 이전 Studio도 그대로 읽습니다. 실행이 여섯 개 이하인 버전 15 파일(손으로 고친 것)은 읽고, 다시 쓸
  때는 버전 8로 씁니다.
- **읽기.** File › Open, Open project, Restore는 실행을 최대 20개 읽습니다. 실행 21개인 파일이나 실행 일곱 개인
  버전 8 파일은 *Unsupported session format or run count.*로 거부합니다. `application`이 `"multiphysics"`가 아닌
  버전 15 파일은 버전 8처럼 거부합니다(*This session file holds a “optical” model, which this Studio does not read.*).
- **이전 Studio.** 버전 14까지 읽는 Studio(main ddb09a1)는 실행을 세기 전에 버전 15 파일을 이름을 밝혀 거부합니다:
  *This session file is version 15, newer than this Studio reads (versions 6–14). Open it in a newer Studio.*(프로젝트
  파일의 항목이면 앞에 *Heated silicon waveguide: *). 그런 파일을 담은 브라우저 복구 기록은 넘겨받지 않습니다. 그런
  Studio와 실행을 나누려면 최대 여섯 개를 저장하십시오. 프로젝트 파일은 버전 1 그대로이며(다중물리 항목은 버전 8이나
  15), 광학 세션, 문서, 서버 응답, 결과는 바뀌지 않습니다.

검사는 `tests/simcase/studio_heated_retention.cjs`에 있습니다(HK2: main ddb09a1의 버전 8 세션
`multiphysics-v8-ddb09a1.json`을 바이트 그대로 다시 씀, HK3: 실행 2와 4~15의 고정 파일
`multiphysics-v15-thirteen-runs.json`, HK4: main ddb09a1이 읽는 것 `refusals-v15-ddb09a1.json`).

## 결과와 파일

고정한 기준 실행을 유지하면서 성공한 실행 최대 여섯 개를 보관합니다. 모드의 장 분포를 보거나 두 실행을
비교할 수 있습니다. 모드 번호는 유효 굴절률 순위이며, Compare가 두 실행 사이의 모드를 장 겹침으로 짝짓습니다. 장 색상은 모드마다
벡터 크기를 따로 정규화한 값이며, 광학 전력이나 공통 물리 색상 척도가 아닙니다.

### 모드 표

결과에는 실행마다 표 하나, | Mode | n_eff | Polarization | Loss (dB/cm) | A_eff (µm²) | n_g |가 광 애플리케이션에 나오고,
다중물리 모델의 Modes 1 페이지에는 n_g가 없는 같은 표가 나옵니다. “Modes are ranked by effective index.”(광 애플리케이션은 “Compare matches them between runs by field overlap.”을 덧붙임) 모든 값은 저장된 중심 장
`unnormalized_electric_field`에서 정의되므로 Studio, 엔진, 이전 세션 파일이 같은 샘플에서 같은 값을 얻습니다.

- **Polarization**은 창의 모든 삼각형에 대한 TE 비율 `f_TE = Σ A_T |E_x|² / Σ A_T (|E_x|² + |E_y|²)`입니다(열
  도움말: “TE = share of |E_x|² in |E_x|² + |E_y|², x horizontal”). 낱말과 TE 백분율로 보여 줍니다(예:
  *TE-like · 98.2 % TE*). TM-like 칸은 TM 비율을 먼저 씁니다: *TM-like · 96.9 % TM (3.1 % TE)*. hybrid 칸은 둘 다
  씁니다: *hybrid · 21.7 % TE / 78.3 % TM*. 두 비율은 한 값에서 나옵니다: TE는 f_TE × 100을 소수 한 자리로
  반올림한 값, TM은 100에서 그 반올림한 TE를 뺀 값이므로 보이는 두 값의 합은 정확히 100.0입니다. Studio의 낱말은 f_TE ≥ 0.9이면 **TE-like**, f_TE ≤ 0.1이면 **TM-like**, 그 밖에는
  **hybrid**이며, 엔진은 수만 저장합니다(`te_polarization_fraction`, [결과 형식](overview.md)).
- **축퇴 쌍**: 한 실행에서 Re n_eff 차이가 1e-3 이하인 이웃한 두 모드는(둘 다 비율이 있을 때) 합친 칸 하나 *pair (n_eff within 1e-3) ·
  50 % TE together*(두 비율의 평균)를 씁니다. 도움말은 각 모드의 편광이 정의되지 않는다고 밝힙니다(쌍 안의
  어떤 회전도 해입니다). 장 보기의 모드 선택은 그 모드를 *pair*로 부릅니다. 임계값이 1e-3인 까닭은 메시가 대칭 쌍(정사각형
  코어)을 40~10 nm에서 1e-4~6e-4만큼 갈라 놓는데, 이는 같은 메시에서 솔버의 n_eff 오차보다 작기 때문입니다. 아주 성긴
  메시에서 생길 수 있는 1e-3 초과의 분리는 표시되지 않으며, 그때 각 모드의 편광은 메시가 고른 회전입니다.
- **창 가장자리의 모드(round 17).** 닫힌 창에서 창 가장자리에 닿는 형상은 그곳에서 PEC 벽을 만나므로, 대부분 그
  형상 안에 있는 모드(기판 슬랩 모드)의 n_eff는 코어뿐 아니라 창에도 달려 있습니다. Studio는 실행에 저장된 표본과 형상으로(엔진과
  파일은 그대로) 창 가장자리에 닿는 형상마다, 무게중심이 그 형상 안에 있는 삼각형(형상이 겹치면 기하 계약처럼 나중 형상이
  이김)에서 모드 |E|²(Σ A_T |E_T|², 세 성분 모두)의 몫 *f*와, 무게중심이 그 형상이 닿는 창 가장자리에서 300 nm 안에 있는
  삼각형의 몫 *g*를 구합니다. *f*가 가장 큰 형상에서 *f* > 0.5이고 *g* ≥ 0.01이면 그 모드 행 아래에 안내 행이 *Mode 1 is
  mostly in Substrate (99 % of |E|²), which touches the window edge; its n_eff depends on the closed window. Use
  Open boundary to leave that edge open.*로 나오고, Compare도 그 실행에 대해 같은 말을
  되풀이합니다(*A · Run 3: Mode 1 is …*). 그런 실행이 열린 실행의 어떤 모드와도 짝지어지지 않는 까닭도 이것입니다. round 22(V3)부터 Compare가 짝지은 모드가
  없고 한 실행의 모드 1에 그 안내가 있으면, 빈 짝 줄(*No mode of A matches a mode of B; the plots show mode 1 of each run, not
  matched.*)에 그 실행에 대해 *A · Run 6: its modes are mostly in Substrate, which touches the window edge; the core mode was not
  found.*와 링크 **Open Run 6 in Results**가 붙습니다. 링크는 입력을 바꾸지 않고 그 실행을 Results에 보여 줍니다. 짝지은 모드가
  있으면 이 줄은 없습니다. round 18부터 Results에서
  마지막 그런 안내 아래 행에 **Use Open boundary**와 **Set Modes to find to 4**(실행의 Modes to find + 2, 많아야 8; C0 전에는 *Find 4 modes*)가
  있습니다: 각각 평소의 메시지와 함께 그 입력을 정하고 아무것도 실행하지 않으며, 현재 입력이 이미 그렇다면 나오지 않습니다.
  C0부터 모드를 더 찾으면 코어 모드에 닿는다고 말하는 문구는 없습니다: 기판 위 닫힌 창에는 코어 모드보다 위에 기판 모드가
  많습니다(기판 위 스트립의 코어 TE 모드는 기본 닫힌 실행의 32번째 모드입니다). *g*의
  0.01 경계는 측정 뒤에 고른 경험적 기준입니다(엔진 장, Linux): 기판 위 스트립(Core 500 × 220 + Substrate 3000 × 700 nm)에서
  두 모드 모두 *f* 0.994, *g* 0.72입니다. 창 전체에 걸친 슬랩 위에 그린 리브에서 리브 모드는 *f* 0.60~0.71이지만 *g*가
  1.4e-4~2.5e-3이라 밝히지 않고, 슬랩 같은 모드는 *g*가 0.087 이상입니다. 20 nm만 식각한 리브(*g* 0.024와 0.046, 창을 넓히면
  n_eff가 약 1e-3 움직임)는 밝힙니다. 창 가장자리에 형상이 없는 템플릿에서는 나오지 않습니다. 열린 실행과 장이 없는 실행은
  검사하지 않습니다.
- **Loss (dB/cm)**는 Im n_eff에서 구합니다: dB/cm = 20 · log10(e) · k0 · Im(n_eff) / 100, k0 = 2π / λ0(1/m 단위,
  exp(−iωt), Im n_eff > 0이 손실). 이는 엔진의 `propagation_loss = (40π / ln 10) · Im n_eff / λ0`(dB/m)를
  100으로 나눈 값이며 유효숫자 4자리까지 보입니다(*37.49 dB/cm*). 닫힌 창에서 이 열은 재료 흡수(k)만 세며,
  열 머리글 둘째 줄(*absorption only (closed window)*), 모든 칸의 도움말, 표 아래 안내가 그렇게 밝힙니다: 도움말은 “Absorption (material k) only; leakage
  and radiation are not computed in a closed window”, 안내는 “Absorption loss counts material absorption (k)
  only. Leakage and radiation are not computed in a closed window.”입니다. 모든 Im n_eff가 정확히 0이면 행마다
  *0 dB/cm*(계산된 누설 0이 아니라 무손실 실행)를 쓰고, 안내는 “Absorption loss counts material absorption (k)
  only: all materials have k = 0 at this wavelength, so it is 0 dB/cm. Leakage and radiation are not computed
  in a closed window.”입니다. 광 애플리케이션은 닫힌 실행의 안내에 “For leakage, choose Open boundary in
  Physics › Optical modes.”를 덧붙입니다. [열린 경계](#광학-작업-공간의-열린-경계)가 있는 실행은 자기 칸을
  씁니다. 열린 경계(PML)가 있는 다중물리 결과는 Im n_eff가 PML로의 누설을 포함하므로 머리글
  둘째 줄이 *absorption + leakage into the PML*이고, 도움말은 “Material absorption (k) and leakage into the PML of the open boundary”, 안내는
  “Loss includes material absorption (k) and leakage into the PML of the open boundary. Leakage depends
  on what lies outside the window: shapes touching an open edge continue through the PML.”입니다. round 24(B6, 코디네이터
  결정)부터 모든 표가 결과, Compare, 가열 모델에서 열 이름을 **Loss (dB/cm)**로 씁니다(전에는 닫힌 창의 열이 **Absorption loss
  (dB/cm)**). Compare는 같은 값을 같은 둘째 줄이 붙은 *Loss (dB/cm)* 아래 *Loss A (dB/cm)*, *Loss B (dB/cm)*로 보이며, 한쪽은
  닫힌 창이고 다른 쪽은 열린 경계이면 묶음에 둘째 줄이 없고 표 아래 안내가 각 쪽이 무엇을 세는지 밝힙니다. 문턱값은 없습니다:
  0이 아닌 Im n_eff는 아무리 작아도 그대로 보입니다. 엔진은 k > 0인 재료나 PML이 있을 때만 복소 n_eff를
  돌려주며, 무손실 문제는 실수 n_eff를 주므로 그 Im은 정확히 0입니다. 광 애플리케이션의 재료와 가열 템플릿은
  무손실이라 0 dB/cm로 읽히고, 다중물리 세션이나 모델 파일은 복소 n_eff(손실 재료나 PML)를 가질 수 있으며 그
  손실은 숫자로 보입니다. 손실은 표시만 바꾸며 결과와 세션 형식은 그대로입니다.
- **A_eff (µm²)**는 창의 모든 삼각형에 대해 세 성분을 모두 쓴 유효 면적 `(Σ A_T |E|²)² / Σ A_T |E|⁴`,
  `|E|² = |E_x|² + |E_y|² + |E_z|²`를 유효숫자 4자리로 보인 값입니다(열 도움말: “Effective area
  (∫|E|²)²/∫|E|⁴ over the window, all three field components”, `effective_area`, [결과 형식](overview.md)).
  흔한 모드 솔버 형식이며 벡터 비선형 면적이 아닙니다. 축퇴 쌍의 각 모드는 자기 값을 보이고, 도움말은 그 값이
  쌍 안의 회전에 따라 달라진다고 밝힙니다. 스칼라 다중물리 결과는 엔진의 |φ|² 면적을 보입니다.
- **n_g**(광 애플리케이션만)는 **Also compute group index**를 켠 실행의 엔진 군굴절률이며 소수 4자리로
  보입니다. 열 도움말은 “n_g = n_eff − λ0 dn_eff/dλ0: central difference over λ0 ± 1 nm (3 solves),
  materials evaluated at each wavelength”입니다. 칸은 두 경우에 **—**입니다.
  - 실행이 n_g를 계산하지 않았을 때. 도움말은 “Turn on Also compute group index in Study or Optical modes”이고, 모드
    표 위 줄에 *n_g: Off · turn on in Study or Optical modes*가 나오고 머리글은 *n_g*뿐입니다(Compare도 두 실행 모두
    n_g가 없을 때 n_g 열이 좁게 유지되도록 표 위 줄에 같은 말을 보여 줍니다).
  - 엔진이 옆 파장에서 그 모드를 대응시키지 못했을 때(`null`, 예: 축퇴 쌍의 한 모드). 그 실행을
    한 탭에서는 도움말이 엔진의 이유 *Not matched: vacuum_wavelength 1.549 um: …*를 보입니다. 세션
    파일은 이유를 보관하지 않으므로, 파일을 연 뒤에는 “Not matched at λ0 ± 1 nm; the reason is not
    kept in session files”입니다.
- 장 보기의 모드 선택은 *Mode 1 · TE-like · n_eff 2.44406001*처럼 읽힙니다.

Run details는 비율과 유효 면적의 출처를 밝힙니다. 이 탭에서 계산한 실행은 *computed by the engine from the saved
field*, 세션 파일에서 연 실행은 *computed by Studio from the saved field*입니다(광 버전 6과 7은 비율이 아니라
샘플을 저장하며, 파일은 이전과 똑같이 써집니다). 다중물리 실행은 엔진 값을 씁니다. Studio가 그 값을 보관하기
전에 저장한 버전 8 실행이나 스칼라 정식화 실행은 “—”를 보여 줍니다(도움말: *Run again to compute*, 또는 스칼라
정식화에는 편광이 없음). 유효 면적도 같은 규칙을 따릅니다. 버전 6과 7 파일의 광 실행은 Studio가 저장 샘플에서
계산한 값을 보이고(Run details: *Effective area · computed by Studio from the saved field*), Studio가 그 값을
보관하기 전에 저장한 버전 8 실행은 *Run again to compute*와 함께 “—”를 보입니다. 세션 버전은 바뀌지 않으며 광
버전 7 파일은 이전과 바이트 단위로 같게 써집니다. 버전 8 파일은 이제 복소 유효 굴절률 `{re, im}`도 읽습니다. 실행 표 CSV의 `candidate`
열 이름은 그대로입니다. [버전 9](#광학-세션-파일버전-9) 광학 세션은 실행마다 엔진의
`te_polarization_fraction`과 `effective_area`를 보존하므로, 그 파일에서 연 실행은 *computed by the engine from
the saved field*를 보이고, 그 파일이 장을 보존하지 않은 실행은 *saved in the session file; its fields were not
kept*를 보입니다.

입력 JSON은 설계를, 세션 JSON은 검증된 결과까지 저장합니다. 열기로 복원하며
입력 파일은 64 KiB, 세션은 16 MiB로 제한합니다. CSV·PNG 내보내기도 제공합니다.
작업공간 형식은 headless simcase JSON 문서와 다릅니다. 새로고침 후에는
Restore last session from this browser로 완료된 브라우저 스냅샷을, Open session으로 파일을 명시적으로
복원합니다. 저장 대기 중인 변경은 백업이 아닙니다.

입력 파일은 버전 7이며, study 설정을 담으면 [버전 8](#입력-파일의-study-설정버전-8)입니다. 버전 7은 버전 6(단위·이름 일괄 변경)에 Joule 가열 입력(`model.joule`, 길이 mm,
`units.joule_length`)을 더했습니다. 버전 6 파일도 기본 Joule 입력으로 계속 읽으며, 인터페이스가
전류와 열뿐인 프로젝트는 Joule 가열 애플리케이션으로 열립니다. 코어 높이·파장·코어 메시 크기·형상 목록은
nm, 열 판은 mm로 각각 단위와 함께 기록하고, 열 판의 열유속 변은 안쪽 방향 열유속으로 기록합니다
(버전 5는 바깥 방향 열유속을 저장했습니다). 버전 1–5 입력 파일은 다른 뜻으로 읽지 않도록 버전을
밝혀 메시지와 함께 거부하므로 입력을 다시 넣고 새 파일로 저장하세요. 브라우저 초안과 입력 복구는
새 저장 키(`openphysics.studio.workspace.v2`, `openphysics.studio.recovery.v2`)를 쓰므로 이전
Studio가 저장한 초안은 나타나지 않습니다. 결과마다 실행 당시 입력을 보존하고 장 윤곽선·비교·
CSV/PNG 내보내기에도 반영합니다.

실행 표 CSV(`studio-runs.csv`)는 모든 양의 열을 `name [unit]` 머리글과 SI 값으로 씁니다.
`core_width [m]`·`core_height [m]`(사각형 하나인 설계), `vacuum_wavelength [m]`,
`core_element_size [m]`, `effective_index [1]`이며, 작업·이름·고정·완료 시각·`core_material`·
모든 형상을 설명하는 `shapes` 열(페이지처럼 nm)·후보 번호에는 단위가 없습니다. `effective_index [1]`은
Re n_eff입니다. 이전 열이 모두 제자리에 있도록 `origin` 뒤에 두 열이 붙습니다: `effective_index_imag [1]`은
exp(−iωt) 아래의 Im n_eff(n_eff가 실수인 무손실 실행은 0), `group_index [1]`은 군굴절률을 계산한 실행의
n_g(실행에 없거나 그 모드에 값이 없으면 빈칸)입니다.

광학 세션 파일은 버전 7이며 입력은 버전 7 입력 파일입니다(버전 6 세션도 계속 읽고, 그 입력은 버전 6 입력
파일로 읽습니다. 다중물리 모델은 [버전 8](#다중물리-모델의-세션-파일버전-8)로, 버전 7이 담을 수 없는 실행이 있는
세션은 [버전 9](#광학-세션-파일버전-9)로 저장합니다). 버전 6은 단위·이름 일괄 변경 이후의 형식입니다. 작업공간은 형식 0.3 문서(`"1550 nm"` 같은
양 문자열의 길이, 정확한 `physmat:` 이름의 재료)를 만들고, 실행 기록마다 결과의
`effective_index`(exp(−iωt)의 Re와 Im)와 미터 단위 `node_coordinates`를 가진 장 표본을 보존합니다.
버전 1–5 세션은 이전 이름과 문서 길이 단위의 결과를 담고 있어, 다른 뜻으로 읽지 않도록 버전을
밝혀 메시지와 함께 거부합니다. 버전 6 세션의 입력은 버전 6 입력 파일과 같습니다. 설계를 다시 넣어
실행하고 새 세션을 저장하세요.

실행 전에 `/api/workspace/capabilities/v8`을 확인합니다. 계약 버전 8(모드 1–8개 실행을 위해 버전 7에서
고정 `mode_count: 2`를 settings에서 빼고 `mode_count_range: [1, 8]`, `mode_count_default: 2`를 그 옆에 둠.
버전 7은 버전 6과 내용이 같으며 버전 7 입력·세션 파일을 저장하는 작업공간용. 버전 6은 버전 5와 내용이 같으며
버전 6 파일과 문서 검사의 코드 있는 `diagnostics`용)과
`optical-shapes-v8` 어댑터(요청한 모드 수를 넣은 `optical-shapes-v7` 문서)는 nm 단위 계산창, 최대 형상 여덟 개·다각형 꼭짓점 열두 개,
형상 종류와 `physmat:` 이름을 가진 재료 열 가지, 파장 1400–1700 nm와 코어 메시 20–60 nm
범위(양 문자열), 고정된 계산창·경계 조건, 모드 수 범위, `optical: true`, `coupled: false`,
`simcase_version`을 알립니다. 작업공간 요청(`workspace_instance`를 밝힌 요청)이 `/api/validate`나
`/api/run`에 보낸 `em.modes2d` 물리의 `mode_count`가 범위 밖이면 *Modes to find must be a whole number
from 1 to 8 (got 9).*로 거부합니다. 0, 9, 2.5, 2.0, `"2"`, `true`는 거부되며, 단일 페이지 Studio의 요청은
문서 자체의 규칙으로 읽습니다. 계약이 없거나 다르면 실행을 차단하며
**Check connection**으로 재시도합니다. 실행 시 보고된 simcase 패키지 버전을
실행 당시 형상·파장·코어 메시와 함께 기록하고 세션 JSON에도 보존합니다. 이전 capability
엔드포인트(`/api/workspace/capabilities`와 `/v2`–`/v7`)는 같은 경로와 schema 버전으로 유지하며, `/v7`은 고정된 모드 두 개를 그대로 알립니다. 모든 어댑터가 이제 형식 0.3 문서를 쓰고
새 결과 이름을 읽으므로 각각 계열의 다음 어댑터 버전(`optical-fixed-v2`, `optical-rectangle-v4`와
`-v5`, `optical-shapes-v6`와 `-v7`)을 알리고 값은 양 문자열입니다. 전체 엔진 의존성이나 Git
이력을 나타내는 정보는 아닙니다.

### 입력 파일의 study 설정(버전 8)

버전 8은 버전 7의 `model`에 광학 study 설정을 `model.joule` 뒤에 더한 것입니다. `modeCount`(Modes to find,
1–8의 정수)는 2가 아닐 때만, `groupIndex`(`true`)는 **Also compute group index**를 켰을 때만 씁니다.
모드 2개에 상자가 꺼진 입력은 이전과 바이트 단위로 같은 버전 7로 쓰므로 이전 Studio에서도 열리며, 버전 6·7
파일을 열어도 다시 쓰지 않습니다. 버전 8 파일은 두 키를 검사해 읽습니다(1–8 밖의 `modeCount`나 boolean이
아닌 `groupIndex`는 거부). 값이 기본값이면 버전 7 입력으로 읽습니다. 입력 파일을 버전 7까지 읽는 Studio는
버전 8 파일을 *Unsupported project format or version.*으로 거부합니다. 실행은 입력을 버전 7로 보존하며, 실행의
study는 `settings.mode_count`와 군굴절률이 담습니다. 실행이 없는 세션은 입력만으로 설정을 정합니다(버전 7
입력이면 2와 꺼짐).

### 열린 경계 문서(optical-shapes-v9)

`/api/workspace/capabilities/v9`는 버전 8에 어댑터 `optical-shapes-v9`와 `open_boundary` 블록을
더한 것입니다. 페이지는 버전 8을 확인하며, 슬라이스 P2부터 이 선택을 제공합니다
([광학 작업 공간의 열린 경계](#광학-작업-공간의-열린-경계)). 어댑터의 문서 작성기
(`openBoundary: {edges, thickness, target}`를 받은 `opticalDocument`)는 계산창의 어느 변이든 열 수 있습니다.

- 열린 변마다 두께 *t* = 1 µm(1000 nm, 제공하는 유일한 값)의 완전 정합층(PML)이 3 × 2.4 µm
  계산창 **바깥**에 놓입니다. 그 변에서 영역이 *t*만큼 커지고 바깥 벽은 PEC입니다. 닫힌 변은 PEC 벽입니다.
- 열린 변에 놓인 다각형 변은 층을 지나 곧게 이어지고, 형상의 모서리에서 열린 두 변이 만나면 모서리
  정사각형도 채웁니다(계산창 바닥을 채운 기판은 바깥 벽까지 닿음). 원은 변과 한 점에서만 만나므로
  이전처럼 씁니다.
- PML 설정은 고정입니다: `pml_strength` 3, `pml_order` 2, `pml_minimum_physical_fraction` 0.5,
  `pml_search_mode_count` 32.
- **Search near n_eff**(`target_effective_index`)는 1.45보다 크고 설계의 최대 굴절률보다 작습니다.
  기본값은 재료의 1550 nm 굴절률로 구한 (n_max + n_SiO2) / 2를 소수 둘째 자리로 반올림한 값입니다
  (실리콘 코어는 2.46).
- slice T2부터 고정 설정 뒤에 t_low = (t + n_SiO2) / 2(소수 둘째 자리) 근처 후보 16개의 두 번째 검색을
  더합니다. t = 2.46이면 `"pml_additional_searches": [{"target_effective_index": 1.95,
  "pml_search_mode_count": 16}]`입니다([추가 검색](pml_modes.md#추가-검색)). t_low는 천분의 일 단위로
  계산하고 반은 올립니다(2.20 → 1.82, 사파이어 1.60 → 1.52, 질화규소 1.72 → 1.58). t가 1.466 미만이면 두
  번째 검색이 없습니다. t_low가 하한 1.45로 반올림되기 때문이며(1.465 → 1.45), 이런 실행은 t 근처만
  검색합니다.
- 열린 경계에서는 군굴절률을 계산하지 않습니다.

모든 변이 닫혔거나 `openBoundary`가 없으면 문서는 `optical-shapes-v8` 문서와 바이트 단위로 같고 결과도
그 문서의 결과입니다. 작업공간 요청의 `em.modes2d` 물리에 다른 `pml`(다른 두께, 서로 다른 두께, 다른 고정값)이 있거나, 목표가 1.45 이하이거나, 영역이 열린 변에서만 그 두께만큼 커진 계산창(nm)이 아니면 *The open boundary of a workspace run has a PML of 1 µm on each open edge with strength 3,
order 2, physical fraction 0.5, a search of 32 candidates near the target and one of 16 near (target +
1.444) / 2 to two decimals; a PML check has strength 6 and one search of 16.*로 거부합니다. 실행(강도
3)은 t = 1.466부터 그 목표의 두 번째 검색을 정확히 하나(정확한 십진수 목표, 정수 개수 16) 가져야 하고,
1.466 미만과 PML 점검에서는 가지지 않습니다. t = 1.466 이상인데 두 번째 검색이 없는 실행은 Studio가 slice
T2로 갱신되기 전에 열린 페이지의 문서이며 *This page was loaded before Studio was updated; reload the
page to run again.*으로 거부합니다. 페이지에는 저장된 문서를 보내는 경로가 없습니다: 실행, PML 점검,
사전 점검, 메시 미리보기, 실행의 입력으로 다시 한 실행 모두 입력에서 문서를 만들고, 세션·프로젝트·대기
작업 파일은 문서를 보존하지 않습니다. `/api/workspace/capabilities/v9`는 `additional_search_count` 16과
`additional_search_target` "(target + n_SiO2) / 2, two decimals"를 나열합니다. PML 결과는
[PML 모드 규칙](pml_modes.md)을 따르는 후보입니다.

검증에서 드러난 열린 경계의 한계:

- **검색 목표는 둘.** 후보는 **Search near n_eff**에 가장 가까운 고유값과, slice T2부터 t_low = (t +
  n_SiO2) / 2에 가장 가까운 고유값이며 각 목표 주변은 PML 자체의 모드로 붐빕니다. 2.46 근처 검색만으로는
  실리콘 기판 위 스트립의 클래딩 굴절률 근처 세 번째 모드(n ≈ 1.486 + 0.008i, 약 2800 dB/cm)를 놓치지만
  1.95 근처 검색이 찾습니다(W1). 두 검색에서는 Re n_eff가 가장 큰 적격 후보가 모드이며 닫힌 실행처럼 Re
  내림차순으로 나열합니다. 두 검색이 모두 찾은 후보는 한 번만 남깁니다. 두 목표 모두에서 먼 모드는 여전히
  놓칠 수 있으니 Search near n_eff를 옮겨 찾습니다. t가 1.466 미만이면 검색은 하나입니다(위 참조). 순위는
  PML이 지배하는 후보를 빼는 데 최소 물리 비율 0.5에 기대며, 원하는 낮은 Re 모드 위에 있는 모드 수보다
  적게 요청하면 그 모드는 돌아오지 않습니다([추가 검색](pml_modes.md#추가-검색)).
- 열린 경계의 엔진 검증(P1의 V1–V8, P3의 모드 식별과 군굴절률)은 P1의 단일 검색 문서를 풉니다
  (`tests/simcase/open_boundary_fixtures.py`의 `build(..., single=True)`). 이 검증은 선택 규칙이 아니라
  PML과 후처리를 검증합니다. 두 검색을 쓰는 Studio 기본값은 W1, W4, W6과 Studio 점검이 다룹니다.
- **1 µm와 32인 이유.** 메시를 고정하면 1.5나 2 µm 층은 손실을 최대 0.02 %, n_eff를 약 1e-8만
  바꾸므로 정확도를 높이지 않습니다. 대신 목표 근처에 PML 모드를 늘려 기판 위 스트립의 TM 유사 모드를
  후보 16개 밖으로 밀어냈습니다. 32이면 시험한 모든 두께에서 그 모드를 찾습니다.
- **기본 메시의 오차.** 기본 메시는 기판 위 스트립의 손실을 약 3 % 크게 냅니다(요소 길이 0.7, 0.5,
  0.35배에서 외삽한 28.35, 988.7 dB/cm에 대해 TE 유사 +2.8 %, TM 유사 +1.8 %). 해석적 극에 대한 누설
  슬래브도 같은 크기의 독립적 검사입니다(기본 메시에서 TE +2.96 %, TM −1.41 %). 처음 등록한 수렴
  검사(× 1, 0.7, 0.5)는 실패했습니다(TE 유사 손실 변화 0.096, 0.301 dB/cm). 그래서 그 결과 뒤에 0.7, 0.5,
  0.35배로 다시 등록했습니다. 계획의 근거였던 값(0.7, 0.5배에서 28.72, 28.55 dB/cm)은 정제 거리를 고정해도,
  함께 줄여도 재현되지 않았습니다.
- **PML 설정도 검색의 일부입니다.** PML 두께·세기·차수를 바꾸면 PML 자체 모드의 스펙트럼이 바뀌어
  고정된 검색이 모드를 놓칠 수 있습니다. 2.46 근처 후보 32개 검색에서 기판 위 스트립의 TM 유사 모드는
  세기 1.5에서 빠집니다. 페이지는 이 설정을 바꾸지 못하게 합니다.
- 처음 등록한 두께 검사(V4: 두께마다 창을 다시 메시, 후보 16개)는 네 번 실패했습니다. 1.5 µm에서
  TE 유사 손실이 +1.28 %, n_eff가 8.7e-4 바뀌었고(다시 메시한 차이: 요소 길이 0.7배에서 −0.31 %,
  4.3e-4), TM 유사 모드는 2 µm와 세기 1.5, 6에서 빠졌습니다. 한 메시와 후보 32개로 다시 등록한 검사는
  다섯 번째로 실패했습니다(세기 1.5에서 TM 유사 모드 누락). 이제 PML 독립성은 모든 기준 모드에 닿는
  검색으로, 제공하는 검색의 완전성은 따로 검사합니다.
- 필터 검사(V8)는 처음에 해석적 슬래브 모드가 극에서 1e-3 이내로 돌아오기를 요구했는데, 이 허용치는
  등록한 값이 아니라 테스트를 쓸 때 정한 값입니다. 모드 1–4개에서 실패했습니다. 기본 메시에서 돌아온 TE
  모드는 극에서 4.76e-3 떨어져 있으며, 이는 슬래브 수렴 검사가 재는 이산화 오차입니다(그 검사는 요소 길이
  1/4배에서만 n_eff를 1e-3 이내로 요구). 그 결과 뒤에 극에 가장 가까운 모드를 해석적 모드로 보고, 슬래브
  검사의 기본 메시 기준(손실 3.5 % 이내, 측정값 +2.96 %)을 만족하도록 했습니다. 처음의 놓친 모드 규칙도
  슬래브에서 실패했습니다. 1.95 근처 검색이 찾는 슬래브의 가로 고차 모드(Re 2.38–1.90, 5번째 이후)까지,
  즉 요청한 수 밖의 모드를 셌기 때문입니다. 그 결과 뒤에 놓친 모드는 두 검색의 물리 모드 중 요청한 수 안에
  들면서 돌아오지 않은 모드로 정했습니다. 그런 모드는 모드 8개를 요청한 기판 위 스트립의 1.486 근처 모드
  하나뿐입니다.

### 닫힌 창 탐색 문서(optical-shapes-v10)

`/api/workspace/capabilities/v10`은 버전 9에 adapter `optical-shapes-v10`과 `closed_target` 블록(`default`
*(n_max + n_SiO2) / 2 at 1550 nm, two decimals*, `bounds` *above 1.45 and below n_max*)을 더한 것입니다. adapter의 빌더
(`opticalDocument`에 `searchTarget`)는 닫힌 창에 **Search near n_eff**를 더합니다: 모든 가장자리가 닫혀 있으면
`physics.em1`의 다른 키 뒤에 `"target_effective_index": t`가 붙고, 엔진은 *t*에 가장 가까운 고윳값 `mode_count`개를
(Re > 0, 1.45 문턱 없이) Re n_eff가 큰 순서로 돌려줍니다. 엔진은 바뀌지 않습니다: `simcase.modes_document`가 이미 그 키를
커널의 목표로 옮깁니다. `searchTarget`이 없으면 문서는 `optical-shapes-v8`(열린 가장자리가 있으면 `-v9`) 문서와 바이트까지
같습니다. `tests/simcase/studio_closed_target.cjs`가 닫힌 문서 24개(템플릿과 기판 위 스트립, 모드 1·2·8개, 군굴절률
있음/없음, 모든 가장자리를 닫은 경우)를 main 13f07f4가 쓴 것과 비교합니다. 열린 가장자리가 있으면 열린 경계가 자기 목표를
쓰고 `searchTarget`은 읽지 않습니다.

닫힌 목표가 있는 작업 공간 요청은 쿼리에 capabilities v10을 적습니다(`workspace_instance` 옆에
`workspace_capabilities=10`). 다른 닫힌 목표는 각각 이유와 함께 거절됩니다: 숫자가 아닌 목표(*Search near n_eff must be
a number (got "2.46").*), 1.45 이하이거나 설계의 1550 nm 최대 굴절률 이상인 목표(정확한 십진수로 비교; *Search near n_eff in
a closed window must lie above 1.45 and below 3.4777 (the design's largest index) (got 1.45).*), `pml_additional_searches`가
있는 목표(*A closed-window search has one target; pml_additional_searches belongs to an open boundary.*), capabilities v10이
없는 요청의 목표(*Search near n_eff in a closed window needs workspace capabilities v10; reload the page.*). 목표가 없는 같은
문서는 전처럼 받습니다.

검증(`tests/simcase/test_studio_closed_target.py`, 사전 등록; 기준값은 main 13f07f4, Linux에서 측정):

| 검사 | 경우 | 결과 |
|---|---|---|
| K2 | 기판 위 스트립(Core 500 × 220 nm, Substrate 3000 × 700 nm), 닫힌 창 @2.46 | 모드 1개: 2.43931663(코어 가둠 0.912, TE 0.981); 모드 2개: 2.48623178(기판)과 2.43931663. 기본 닫힌 실행의 두 모드는 기판 모드(3.42534929, 3.39599656)이고 코어 TE 모드는 그 실행의 32번째 모드. CI 결과 뒤 다시 등록(2026-11-24, 사전 아님): 목표 모드는 같은 메시에서 목표 없는 모드 40개 닫힌 실행의 해당 모드와 1e-8 안에서 같고, 2.43931663과 2.48623178은 2e-4 안의 기준값입니다. 메시가 CPU마다 다를 수 있기 때문입니다(아래). 처음 등록한 대로(절대값 ±1e-8)는 AVX2 디스패치에서 −1.93e-5로 실패했습니다 |
| K3 | 닫힌 창 @2.46과 열린 기본값(Compare의 짝짓기) | 코어 모드끼리 짝, 겹침 0.988, Δn_eff −1.95e-3 |
| K4 | 창 전체 폭의 220 nm Si 막, @2.85, 요소 길이 × 1, 2/3, 1/2, 1/3, ±1.2 µm PEC 사이 1D TE 전달 행렬 2.84948947과 비교 | 오차 −4.80e-3, −2.46e-3, −1.99e-3, −1.02e-3(음수, 줄어듦; × 1에서 \|오차\| ≤ 5e-3) |
| K5 | 기판 위 막, 2.84916936과 비교 | 막 같은 모드(가둠 0.94)는 모드 2개 중 2번째; 오차가 각 수준에서 K4의 오차와 4.4e-4 안(기준 5e-4) |
| K6 | 템플릿 @2.46, 모드 2개 | 기본 닫힌 실행의 n_eff와 5e-15 안 |
| K7 | 기판 위 스트립 @2.46, 모드 4개, 폭 3, 4, 5, 6 µm 창, 500·1000 nm 두꺼운 기판, BOX 800·300 nm | 8개 중 8개에서 코어 모드가 3, 3, 3, 4, 4, 3, 3, 4번째로 나옴 |
| K8 | n_g, 닫힌 창 @2.46, 모드 1개 | 4.19234, 열린 실행의 Re n_g 4.19152와 비교(기준 2e-3) |
| K13 | 템플릿 @2.46, 모드 4개 | 4번째 모드는 클래딩보다 낮은 1.39191472(2e-4 안의 기준값; 같은 메시의 목표 없는 값과 1e-8 안에서 같음. AVX2 디스패치에서 +3e-8이 나와 K2와 함께 다시 등록): Studio는 이를 목록에서 뺍니다([닫힌 창의 탐색](#닫힌-창의-search-near-n_eff)) |

닫힌 탐색의 한계:

- **고정된 목표는 코어 모드의 n_eff가 목표에 가장 가까운 기판 모드들 사이에 있을 때만 코어 모드에 닿습니다.** 실리콘 기판
  위 닫힌 창에는 코어 모드 주위에 기판 모드(PEC 벽 사이 슬랩의 가로 고조파)가 많습니다. 2.46 근처 모드 4개로 500 × 220 nm
  스트립의 코어 모드는 나오지만, 다른 코어에서는(등록 뒤 측정, 기준 아님) 8개 중 3개에서만 나왔습니다: 폭 400, 450, 600,
  700 nm와 높이 250 nm에서는 나오지 않았습니다(550 nm 코어 모드 2.511은 닫힌 실행의 31번째, 450 nm의 2.348은 34번째). 작은
  변화(폭 480·520 nm, 높이 230 nm, 1500·1600 nm, 코어 메시 25·40 nm)에서는 8개 중 7개에서 나왔고, 높이 210 nm에서는 기판 모드와
  섞여(가둠 0.37과 0.46) 어느 쪽도 코어 모드가 아닙니다. 다른 코어에서는 Search near n_eff를 코어 n_eff의 어림값으로 정하십시오.
- **닫힌 값과 열린 값은 다릅니다.** 닫힌 창의 PEC 벽은 n_eff를 옮기고(기판 위 스트립에서 열린 기본값 대비 −1.95e-3), 기본
  메시의 이산화 오차도 같은 크기입니다(K4: −4.8e-3). 가까운 비교 전에는 메시를 세분하십시오.
- **기본 메시는 컴퓨터마다 조금 다를 수 있습니다.** meshine은 세분 점을 외접원 반지름이 큰 것부터 받아들이고, 반지름이 같은
  점은 NumPy의 quicksort로 정렬하는데, 같은 값의 순서는 NumPy가 쓰는 CPU 명령(AVX-512 또는 AVX2)에 따라 달라집니다. 그러면 같은
  입력에서도 노드 몇 개가 옮겨진 메시가 나오고 n_eff가 1e-5~1e-4 자리에서 달라질 수 있습니다: K2의 코어 모드는 AVX-512에서
  2.43931663, AVX2 디스패치에서 2.43929738(−1.93e-5)이고, 다른 동점 순서에서는 최대 1.5e-4 움직였습니다. 한 컴퓨터에서의 결과는
  재현됩니다. 다른 컴퓨터의 값을 이 수준에서 비교하려면 먼저 메시를 세분하십시오.

### 닫힌 창의 Search near n_eff

C2부터 페이지가 [닫힌 창 탐색](#닫힌-창-탐색-문서optical-shapes-v10)을 제공합니다.

- **Modes to return.** *Closed window (PEC)*를 고르면 **Physics › Optical modes**에 선택 하나, **Modes to return**이
  있습니다: 라디오 **Highest n_eff above 1.45**(기본값)와, 필드 **n_eff to search near**(소수 3자리, 기본값은 (n_max +
  1.444)/2를 0.01로 반올림한 값: 실리콘이면 2.460)가 뒤따르는 라디오 **Nearest to n_eff**입니다. round 22(V1)부터 필드는 늘
  쓸 수 있고, 필드에 굴절률을 입력하면 Nearest to n_eff가 선택됩니다. 그 전에는 체크 상자 *Search near n_eff*가 따로 있는 필드
  *Search near n_eff (closed window)*를 켰는데, 시험자 다섯 중 넷이 필드부터 건드렸습니다. 뜻은 상자의 뜻 그대로입니다:
  Highest는 상자를 끈 것, Nearest는 켠 것이며 문서, capabilities, 세션은 바뀌지 않습니다. 도움말은 “Highest n_eff above
  1.45: the modes of highest n_eff. Nearest to n_eff: the modes nearest the index in the field, listed by n_eff, highest
  first; modes at or below 1.45 are left out. Typing an index selects Nearest to n_eff. Closed and open values differ:
  refine the mesh before a close comparison.”입니다. Messages에는 *Modes to return: nearest to n_eff 2.460 in the closed
  window. The next run returns the modes nearest it.* 또는 *Modes to return: highest n_eff above 1.45. The next run returns
  the modes of highest n_eff.*가 나오고, 보관된 실행이 새 입력을 가지면 *No need to run: Run N already has these results.*가
  이어집니다. 설계 범위 밖 굴절률은 그 메시지와 함께 거절되고 선택은 그대로입니다. Highest가 선택된 동안 입력한 굴절률은
  메모리에만 남습니다. 형상이 창 가장자리에 닿아도 기본값은 Highest입니다.
- **바로 가기.** 닫힌 실행의 가장자리 안내 아래 round 18 행에는 **Use Open boundary**와, C2부터 C0의 *Set Modes to find to 4*
  대신 **Set search near 2.46 · 4 modes**(round 22 V5 전에는 *Search near 2.46 · 4 modes*)가 있습니다: 설계의 기본 목표로
  Nearest to n_eff를 고르고 Modes to find를 4로 정하며 *… Modes to find set to 4. Press Run study to compute.*라고 알리고
  아무것도 실행하지 않습니다. 입력이 이미 둘 다 그렇다면 나오지 않습니다. 보관된 실행이 이 입력을 가지면 마지막 문장 자리에 *No
  need to run: Run N already has these results.*가 옵니다. 등록된 모든 변형에서 모드 4개로 기판
  위 스트립의 코어 모드에 닿습니다([K7](#닫힌-창-탐색-문서optical-shapes-v10)).
- **실행 전**(round 22, V2). Highest n_eff above 1.45를 고른 닫힌 창에서, 창 가장자리에 닿는 형상의 굴절률이 닿지 않는
  형상들의 가장 높은 굴절률 이상이면, Physics › Optical modes(Modes to return 위)가 형상 이름으로 *Substrate touches the window
  edge and its index is as high as Core's: in a closed window its slab modes come first.*라고 말하고, Run study 옆 계획 줄은
  계획 아래 한 행에 짧은 형태 *Substrate touches the window edge: in a closed window its slab modes come first.*를 보입니다(round
  23, E1; 전체 문장은 title). 이 행은 잘리지 않습니다: 문구는 줄바꿈되고, 버튼이 옆에 들어가지 않으면 버튼만 다음 줄로 가며,
  Run study 옆 상자가 그만큼 커집니다(round 23 전에는 상자에 맞게 잘려서 테스터 다섯 중 넷이 title이나 패널을 봐야 읽었습니다.
  1440 × 900과 390 × 844에서 확인). 두 곳 모두 **Set search near 2.46 · 4 modes**(바로 가기와 같은 목표 어림값,
  (n_max + 1.444)/2)와 **Use Open boundary**를 둡니다. 둘 다 입력만 정하고 아무것도 실행하지 않습니다. 바로 가기의 모드 4개는 닫힌 창의 검색을 위한 것입니다(round 29, L1): Modes to find의 마지막 변경이 바로 가기였고 그다음 바깥 경계를 Open boundary로 바꾸면, Modes to find는 바로 가기 전의 개수로 돌아가고 Messages가 경계 문장 뒤에 *Modes to find back to 2: 4 was for the closed window's search near 2.46.*이라고 알립니다. 이것은 따로 하나의 편집이므로 Undo는 Open boundary를 그대로 둔 채 4를 돌려줍니다. 바로 가기 뒤에 Modes to find를 손으로 바꿨거나, 이미 4였거나, Undo, Redo, 새 입력 뒤에는 아무것도 바뀌지 않으며, 닫힌 창으로 되돌려도 바뀌지 않습니다. Nearest to n_eff나 Open
  boundary를 고르면 경고가 사라집니다. 경고가 보이는 동안 **Run study**는 실행 전에 한 번 묻습니다(round 27, D2). 대화상자
  *Slab modes first*: *Substrate touches the window edge, so a closed-window run returns its slab modes first. Search near the
  core instead?*와 **Set search near 2.46 · 4 modes and run**(경고의 바로 가기를 정한 뒤 실행), **Run as set**(묻지 않았을 때와
  같은 실행: 같은 문서, 값, 기록), **Cancel**(Escape도 같음, 아무것도 실행하지 않음). round 28(G3)부터, 바로 가기의 결과를 이미 가진 실행이 있으면(Nearest to n_eff 2.46, Modes to find 4와 나머지 현재 입력: 패널 버튼의 *No need to run*과 같은 규칙) 첫 버튼은 **Set search near 2.46 · 4 modes · show Run 6**입니다: 바로 가기의 입력을 패널 버튼의 메시지와 함께 정하고, 사본을 실행하지 않고 Results에 Run 6을 보여 줍니다. Run as set과 Cancel은 그대로입니다. 초점은 첫 버튼에서 시작합니다. 형상, 경계,
  Modes to return이 바뀐 뒤에만 다시 묻고(바꿨다 되돌린 것도 바뀐 것), 그 밖에는 Run study가 곧바로 그대로 실행합니다. 풀이 없는 형상과 재료 점검입니다: 형상의 경계가 창에 닿으면 가장자리에 닿는 것이고, 이름은
  가장자리에 닿는 형상 중 굴절률이 가장 높은 것과 닿지 않는 형상 중 가장 높은 것(같으면 앞의 것)이며, 가장자리에 닿는 형상이 없거나
  모든 형상이 닿으면 경고하지 않습니다. 결과 쪽 가장자리 안내는 그대로이고, 닫힌 탐색의 기본값은 계속 Highest입니다. 한계:
  Studio는 1550 nm 표(physmat)로 비교합니다. 열 가지 재료는 1400–1700 nm의 모든 파장에서 같은 순서이고 같은 값이 없으므로
  (`tests/simcase/test_studio_round22.py`) 실행 파장에서도 판단이 같습니다. 겹친 형상은 뒤 형상이 가리는 부분을 따지지 않고
  그려진 대로 비교합니다.
- **실행.** Nearest to n_eff를 고른 실행은 `target_effective_index`를 쓰고 capabilities v10을 적습니다. Studio는 Re n_eff가 1.45보다 큰
  모드만 보관합니다(결정 A1): 표 위 줄은 늘 *Found k of M modes near n_eff 2.46, above n = 1.45.*(M: Modes to find)이고, 엔진이
  그 아래 모드를 돌려주었으면 표 아래 안내가 *1 mode at or below n = 1.45 was left out.*라고 말합니다(템플릿 @2.46, 모드 4개:
  2.44257822, 1.76989777, 1.49297336을 싣고 1.39191472를 뺌). 모드는 엔진의 순서(Re n_eff 내림차순)를 지킵니다.
- **코어 모드.** 형상이 창 가장자리에 닿는, Search near n_eff를 쓴 닫힌 실행에서 가장자리에 닿지 않는 한 형상 안 |E|² 몫(가장자리
  안내의 몫)이 0.5보다 큰 모드에는 안내 행 *Mode 2 is the core mode: 64 % of |E|² is in Core, which does not touch the window
  edge.*가 붙습니다(기판 위 스트립 @2.46, 모드 2개; 모드 4개면 3번째). 이 몫은 Studio의 가중치 없는 |E|² 몫이고, 같은 모드의
  엔진 에너지 비율(가둠 인자)은 0.91입니다.
- **문구.** Run study 옆 계획 줄은 *Closed window · near n_eff 2.46 · 2 modes*(round 28 G2부터 Modes to find와 함께), 다음 실행 입력은 *· search near 2.46*으로 끝나며, 실행
  목록, Compare 선택 목록과 제목, 상태 표시줄은 목표 없는 닫힌 실행의 *closed* 자리에 *closed near 2.46*을 씁니다.
- **실행과 파일.** 실행 설정에 목표가 남습니다: adapter `optical-shapes-v10`, `mode_count` 뒤의 `search_target`. 세션(그리고
  프로젝트 파일의 작업 공간 항목)은 그런 실행이 보관되어 있을 때만 **버전 11**로, 아니면 버전 10, 9, 7로 바이트까지 같게
  씁니다(main 13f07f4와 비교). 버전 11은 1.45 이하 모드가 있는 목표 실행을 거절하고, 버전 10까지 읽는 Studio는 *This session
  file is version 11, newer than this Studio reads (versions 6–10). Open it in a newer Studio.*로 거절합니다. study 서명에
  목표가 들어가므로 목표를 바꾸거나 끄면 실행이 필요하고, 같은 목표일 때만 *No need to run*이 나옵니다.
- **이번 묶음의 한계.** Modes to return과 목표는 모델 파일, 프로젝트 입력, 브라우저 초안에 저장되지 않고(입력은 버전 7, 8,
  9 그대로), Undo와 Redo도 이를 바꾸지 않습니다. 다시 연 세션의 실행은 목표를 지킵니다: 닫힌 목표 실행에서 **Use this run's
  inputs**를 누르면 실행의 목표로 Nearest to n_eff가 선택되고(*… Modes to return highest n_eff → nearest to 2.46 …*) *No need
  to run*이 다시 성립합니다. round 22(V6)부터 그 메시지는 Undo가 목표를 되돌린다고 말하지 않습니다: 다른 변경이 있으면 *The
  next run uses them; Undo takes back the other inputs. Modes to return is set and is not part of Undo.*로, 목표만 바뀌면 *The
  next run uses it. Modes to return is set and is not part of Undo.*로 끝납니다(그 전에는 *Search near n_eff off → 2.46*와
  *Undo takes them back*).
- 검사: `tests/simcase/studio_closed_target_page.cjs`(K9, K10, K12, K13과 대기 작업), `tests/simcase/test_studio_closed_target.py`
  (엔진 장의 K12), 작업 공간 브라우저 검사의 CW 단계.

### 광학 작업 공간의 열린 경계

슬라이스 P2부터 페이지는 [optical-shapes-v9](#열린-경계-문서optical-shapes-v9)의 열린 경계를 제공합니다.
이를 쓰면 실행의 손실에 창 밖으로의 누설이 포함됩니다.

**선택.**

- **Physics › Optical modes**에 *Outer boundary: Closed window (PEC) / Open boundary (PML)*가 있습니다.
  기본값은 Closed입니다. 도움말은 “Open boundary adds an absorbing layer (PML) outside the window, so
  light that leaves the window is lost. Loss then includes leakage. Shapes touching an open edge
  continue through the layer.”입니다. round 20부터 그 옆의 *Optical adapter scope* 안내는 어느 쪽을 골랐든 두 경계를
  모두 밝힙니다: *3 × 2.4 µm window, closed (PEC edges) or with an open boundary (PML 1 µm outside the open edges, PEC
  on the closed ones)*(닫힌 창일 때는 Open boundary 선택 옆에서 *PEC outer edges*라고 적었음).
- 이 선택은 Modes to find처럼 각 실행에 함께 보존되는 물리 설정입니다.
- Open이면 모든 변이 열립니다. **Geometry › Boundaries**에서 각 변을 다시 닫을 수 있습니다. 열린 변은
  *Optical left boundary · Open (PML)*로 읽히고, **Close this edge** 스위치로 닫거나 다시 엽니다. 닫힌
  변은 이전처럼(PEC) 읽힙니다. 모든 변이 닫히면 실행은 닫힌 창입니다.
- **Also compute group index**는 Open에서도 쓸 수 있습니다(slice P3). 이때 엔진의 n_g는 복소수이며,
  n_g 열은 Re n_g를 보입니다([모드 식별](#열린-경계의-모드-식별) 참조).

**매개변수.**

- PML 두께는 1 µm이며 읽기 전용 *PML 1 µm*로 보입니다. 두께 입력란은 없습니다.
- 강도 3, 차수 2, 최소 물리 비율 0.5는 고정이며 *Details*에 나열됩니다: *… · 32 candidates searched near
  n_eff, 16 near the second index*.
- **Search near n_eff**는 고칠 수 있습니다. 기본값은 1550 nm에서 (n_max + n_SiO2)/2를 0.01로 반올림한
  값입니다(실리콘이면 2.46, *2.460*으로 표시). 고친 값은 소수 셋째 자리로 보존되며 보이는 값이 그대로
  보내집니다. 1.45와 n_max 사이(양 끝 제외)여야 합니다.
- 두 번째 목표는 그 옆에 글로 보이며 고칠 수 없고, 보이는 목표를 따릅니다: *Also searches near 1.95, for
  modes close to the silica index.* (2.20 → 1.82). 도움말은 “Studio searches for modes near this index and
  near a second index halfway to the silica index (1.95). Modes are listed by n_eff, highest first. The default is
  halfway between the core and silica indices: (n_core + 1.444)/2.”입니다(round 18: 2.46이 어디서 오는지). 검색이 하나일 때도
  도움말은 기본값에 관한 같은 문장(*…: (n_core + 1.444)/2, rounded to 0.01.*)으로 끝납니다.
- 1.466 미만이면 검색은 하나입니다. 두 번째 목표는 보이지 않고 도움말은 P2의 문장(목표 하나로는 그로부터
  먼 모드, 특히 클래딩 굴절률 근처의 모드를 놓칠 수 있음)을 유지합니다.

**Study와 그림.**

- Study는 *Open boundary · PML 1 µm · searches near 2.46 and 1.95*(1.466 미만이면 *search near 1.465*)와
  선택 사항 **Also check the PML (N more solves)**(기본 꺼짐, N = Modes to find)를 보입니다. 두 검색의
  문구에서 목표는 소수 셋째 자리에서 끝의 0 하나를 뺀 값(2.46, 2.455, 2.50)이고 t_low는 소수 둘째
  자리입니다.
- 그림은 열린 변마다 창 밖에 *PML 1 µm* 라벨이 붙은 회색 띠를 그립니다. 창이 보이도록 띠는 1 µm보다
  좁게 그립니다. 단면 문구는 “… · open boundary (PML 1 µm) on N edges”로 끝납니다.

**열린 실행의 결과.**

- 표 제목은 *Modes (open boundary, PML 1 µm)*입니다. 손실 열은 **Loss (dB/cm)**이며, 도움말은 “Material
  absorption (k) and leakage into the PML of the open boundary”입니다.
- 손실은 같은 식(dB/cm = 20 · log10(e) · k0 · Im n_eff / 100)으로 유효숫자 4자리입니다(*29.15 dB/cm*). 숫자
  칸의 도움말은 측정한 메시 오차를 덧붙입니다: “At the default mesh this loss is about 3 % above the
  converged value (TE-like +2.8 %, TM-like +1.8 % on a strip over a substrate).”
- 0.01 dB/cm 미만이면 칸은 **< 0.01 dB/cm**입니다. 음의 Im n_eff와 엔진이 `numerically_unresolved`로
  표시한 값도 여기에 듭니다. 도움말은 “Below what this open boundary resolves for a 3 × 2.4 µm window
  (0.01 dB/cm). The mode does not leak measurably here.”입니다. Im n_eff가 없는 모드는 “—”입니다.
- 음의 Im n_eff로 |손실|이 0.01 dB/cm 이상이면 **not resolved (|loss| < X dB/cm)**로 읽히며, X는 |손실|을
  유효숫자 2자리로 올림한 값입니다(1550 nm에서 Im n_eff −2.67e-7, 0.094 dB/cm는 *not resolved (|loss| <
  0.095 dB/cm)*). 도움말은 “The solve gives a small negative Im n_eff within the PML's numerical noise; the
  loss is below about X dB/cm.”입니다. 음의 Im을 모두 *< 0.01 dB/cm*로 쓰던 P2의 규칙(V14)을 바꾼 것으로,
  엔진이 이런 모드를 PML의 한계 안에서 손실 없는 모드로 받아들일 수 있기 때문입니다. 0.01 dB/cm 미만의
  음의 Im은 *< 0.01 dB/cm*를 유지합니다.
- n_eff는 닫힌 실행처럼 Re를 보이고 Im을 유효숫자 3자리로 덧붙입니다: *2.44126325 + 8.28e-5i*.
- Polarization과 A_eff는 PML을 뺀 3 × 2.4 µm 물리 창에서 계산합니다. n_g는 Re n_g를 보입니다.
  [모드 식별](#열린-경계의-모드-식별)을 보세요.
- 표 아래 안내에 “Leakage depends on what lies outside the window: shapes touching an open edge
  continue through the PML.”이 붙습니다. 닫힌 실행의 안내에는 “For leakage, choose Open boundary in
  Physics › Optical modes.”가 붙습니다.
- 찾은 개수 줄은 늘 보입니다: *Found 2 of 2 modes near n_eff 2.46 and 1.95 (Studio's second search, halfway to
  the silica index). Move Search near n_eff to find other modes.*(round 27, D3: 두 번째 목표가 무엇인지 밝힘. 1.45 위 모드가
  없는 결과도 같은 말로 *No mode above n = 1.45 was found near n_eff 2.46 and 1.95 (Studio's second search, …). …*라고 함). 검색이 하나인 실행(1.466 미만, 또는 slice P2의 실행)은 이전처럼 *Found 2 of 2 modes near
  n_eff 2.460. Move Search near n_eff (Physics › Optical modes) to find other modes.*로 읽힙니다.
- Studio는 엔진의 모드 가운데 Re n_eff가 1.45보다 큰 것만 남깁니다.
- **Other candidates (n) — not shown as modes**는 탐색했지만 보이지 않는 후보마다 n_eff, 물리 비율, 이유를
  나열합니다. 이유는 *Mostly in the PML (a PML mode)*, *Gains power (not a passive mode)*, *Not converged
  (residual above 1e-8)*, *Beyond the modes asked for*, *Below the silica index (cladding radiation)*입니다.
  이 행에는 장 보기가 없습니다.
- 두 검색에서는 표에 **Search** 열(*near 2.46*, *near 1.95*)이 더해집니다. 두 번째 검색의 후보가 첫
  검색의 후보를 되풀이하면(엔진의 `duplicate_of`) 나열하지 않고 제목에서 셉니다: *Other candidates (41) —
  not shown as modes · 3 found by both searches*.
- 장 보기, 그 색 척도, 선 프로파일은 물리 창만 씁니다. 엔진은 열린 실행의 장을 그 안의 최대 |E|로
  정규화합니다(`physical_max_centroid_magnitude`).

**PML 점검.**

- 선택 사항이 켜져 있으면 Studio는 실행의 문서를 찾은 모드마다 한 번씩 다시 풉니다: PML 강도 6, 후보 16개,
  Search near n_eff는 그 모드의 Re n_eff(소수 여섯째 자리). 메시는 절점까지 같습니다. 점검은 한 번만
  검색합니다: 실행의 두 번째 검색은 빼므로 점검 문서는 slice P2의 문서와 바이트 단위로 같습니다.
- 이 풀이들의 후보를 모읍니다. 각 모드는 가장 가까운 적격 후보와 짝지어집니다. 적격 후보는 엔진 필터를
  통과하고(선택됨, 또는 개수를 넘어서만 제외됨) Re > 1.45인 후보입니다. 짝은 |Δn_eff| ≤ 2e-3일 때
  받아들입니다.
- |ΔRe| ≤ 5e-4이고 손실 변화가 max(2 %, 0.01 dB/cm) 이하이면 그 모드는 PML에 무관합니다.
- 표시 하한 아래에서는 점검 풀이가 아주 작은 손실에 실행의 풀이보다 큰 잔차를 남깁니다. 모드의 칸이
  *< 0.01 dB/cm*이고 점검 손실이 0.05 dB/cm 미만이면 점검은 판정하지 않습니다. 분해된 누설이 없다고만 말할
  뿐, 무관함을 보증하지 않습니다.
- 그러면 **PML check** 열은 다음 가운데 하나입니다.
  - *PML check: loss changes 0.016 %*(0.1 % 미만은 유효숫자 2자리);
  - **Depends on the PML**: *loss changes 12 %*(또는 *Re n_eff changes 7.0e-4*). 손실 칸은 기울임꼴이며,
    도움말은 “This loss changes with the PML; it is not a converged leakage loss.”입니다;
  - *PML check: no leakage resolved (both solves below 0.05 dB/cm)*(기울임꼴 없음);
  - *Not found in the check solve*. 도움말은 “The check solve did not find this mode near the search
    value; this does not by itself mean the mode depends on the PML.”입니다.
- 하한 아래이지만 점검 손실이 0.05 dB/cm 이상인 모드는 *Depends on the PML* 그대로입니다. 하한이 PML에 따라
  움직이기 때문입니다.
- 엔진의 `stability: "not_checked"`는 각 풀이에 그대로 참이며, 점검은 실행에 기록됩니다(`pml_check`). 점검은
  모든 풀이가 끝나야 저장됩니다. 페이지를 다시 불러오기 전에 끝난 풀이는 보존되지 않으므로, 그 점검은
  불완전하여 저장되지 않습니다.
- **점검을 고른 방법.** 점검 풀이 하나(강도 6, 실행의 목표 근처 후보 32개)는 템플릿과 누설 사례의 TM-like
  모드를 놓쳤습니다. 후보 64개로도 놓쳤습니다: 개수가 아니라 목표가 결정합니다. 엔진 수준, 한 스레드, 느리지
  않은 테스트 묶음이 함께 돌 때 잰 값입니다(시간은 상대 비교용).

  | 점검 | 템플릿 | 누설 사례 | 모든 모드를 다시 찾음 |
  |---|---|---|---|
  | 풀이 하나, 목표 근처 후보 32개 | 2.8 s | 35.4 s | 아니오(TM-like 놓침) |
  | 풀이 하나, 후보 64개 | 5.2 s | 91.8 s | 아니오 |
  | 모드마다 그 Re에서 풀이 하나, 후보 32개 | 5.0 s | 64.5 s | 예 |
  | 모드마다 그 Re에서 풀이 하나, 후보 16개(채택) | 2.6 s | 43.8 s | 예 |

  첫 풀이는 3.5 s와 36.3 s였습니다.
- **실패한 등록 결과.** 모드별 점검에서 템플릿의 TM-like 모드는 PML에 무관하다고 등록했습니다. 손실이
  0.00480에서 0.01706 dB/cm로 바뀌어 “Depends on the PML: loss changes 256 %”로 읽혔습니다. 하한 아래 손실
  규칙은 그 결과 뒤에 더했습니다. 측정 전에 등록한 대로 700 × 300 nm 템플릿 코어, 모드 4개에서 확인했습니다:
  모든 모드가 하한 아래이고 점검 손실은 많아야 0.00026 dB/cm입니다.
- 점검을 켠 결과:
  - 템플릿: 두 모드 모두 *no leakage resolved*;
  - 누설 사례: TE-like 29.1528 → 29.1517 dB/cm(*loss changes 0.0038 %*), TM-like 1005.96 → 1005.80 dB/cm
    (*0.016 %*), 둘 다 PML에 무관.

**Compare.**

- 각 쪽의 손실 머리글은 도움말에서 그 실행을 따르고(*Loss A (dB/cm)*: 흡수만, *Loss B (dB/cm)*: 누설 포함), 묶음은 둘째 줄 없이 *Loss (dB/cm)*입니다.
- 둘이 다르면 안내 “A counts material absorption only; B also counts leakage. Their difference is not a
  leakage loss.”가 붙습니다.
- 열린 실행이 있으면 표 위 줄이 각 실행을 *(closed)* 또는 *(open, PML 1 µm)*로 부릅니다.
- 열린 실행과의 짝짓기가 켜집니다(slice P3). 두 실행의 물리 창이 겹치는 영역 위 공통 격자에서 장을
  비교합니다. 짝지은 행은 머리글에 실행 이름을 적습니다. 예: *A · Run 1 (closed)*, *B · Run 2 (open,
  PML 1 µm)*. slice P2에서는 꺼져 있었습니다. 블라인드 점검 V13(닫힌 실행 대 열린 실행, η ≥ 0.99)이
  TE-like η = 0.9903, TM-like η = 0.9875로 실패했기 때문입니다. 진단과 그 점검을 대신한 점검은
  [모드 식별](#열린-경계의-모드-식별)에 있습니다.

**파일.**

- Open을 고른 모델 파일은 입력 버전 9입니다. 버전 8에 `model.openBoundary {edges: {left, right, bottom,
  top}: "open" | "closed", target}`을 더한 것이며, `target`(Search near n_eff, 소수 셋째 자리)은 고쳤을
  때만 씁니다.
- Open이 아니면 파일은 이전처럼 버전 7 또는 8을 바이트 그대로 씁니다. 슬라이스 P2 이전의 Studio 4b58fb7은
  버전 9 입력 파일을 *Unsupported model file format or version.*으로 거부합니다.
- 실행에 열린 경계가 있거나 입력이 Open을 고르면(입력 버전 9) 세션은 **버전 10**으로 씁니다. 그렇지 않으면
  이전처럼 버전 9 또는 7을 바이트 그대로 씁니다.
- 버전 10은 버전 9에 `optical-shapes-v9` 실행을 더한 것입니다. 그 `settings`에는 `adapter
  "optical-shapes-v9"`, `boundary "PML"`, `pml {"thickness": "1000 nm", "open_edges": [...], "target":
  "2.460"}`이 들어갑니다.
- 이런 실행은 엔진의 탐색 후보 기록 `open_boundary`도 보존하고, 점검을 했다면 `pml_check
  {"pml_strength": 6, "paired": [모드마다 {"re", "im"} 또는 null]}`도 보존합니다. 다이제스트는 둘 다
  포함합니다.
- slice T2는 settings도 파일 버전도 바꾸지 않습니다. 두 검색의 실행은 엔진의 기록
  `openphysics.pml-candidates/3`을 보존하며, 그 `searches`는 정확히 실행의 목표 근처 32개와 그 t_low 근처
  16개여야 합니다. 다른 /3 기록은 잘못된 열린 경계 기록으로 거부합니다. 기록이 /2인 실행(검색 하나:
  slice P2의 실행이나 1.466 미만의 목표)은 이전 문구 그대로 읽힙니다. slice T2 이전에 쓴 버전 10 파일은
  같은 값과 문구로 열리고, **Use this run's inputs** 다음의 실행은 두 검색의 문서를 만듭니다. 연구 서명은
  바뀌지 않으므로 그런 실행은 여전히 현재 입력으로 만든 실행으로 읽힙니다.
- 그 장은 위의 정규화를 따른다고 봅니다.
- **물리 창의 장만.** 열린 실행은 물리 창과 만나는 삼각형에 창의 긴 변의 1/150인 얇은 여유를 더해
  보존하므로 창 가장자리의 그림은 바뀌지 않습니다. 그 밖의 PML은 보존하지 않습니다. (장 보기는 창으로
  안티앨리어싱하여 자르므로, 창 바로 밖의 삼각형도 일부 덮는 가장자리 픽셀에 색을 더합니다. 3 × 2.4 µm 창에서
  20 nm인 이 여유는 그림이 그 변에 장치 픽셀 150개 이상을 쓰면 그 픽셀들을 덮으며, Results와 Compare는 늘
  그렇습니다.) 판정은 저장된 미터 좌표에서 경계를 포함한 분리축 판정이고, 삼각형은 엔진의 순서를 지키며,
  절점은 처음 쓰인 순서로 번호를 다시 매기고, 좌표와 표본 값은 하나도 바뀌지 않습니다. T16 실행(기판 위
  스트립, 네 변이 열림)은 삼각형 40,658개 중 12,253개를 보존합니다. 중심이 창 안에 있는 삼각형은 모두 그 안에 있으므로 물리 창, TE 비율,
  유효 면적, 짝짓기, 장 보기와 탐침은 전체 표본일 때와 같은 값을 읽습니다. **Export this run**의 실행 파일도
  같은 표본을 담고, 그 메시지가 그렇게 밝힙니다. 파일(세션, 프로젝트, 복구, 실행 파일)에서 읽은 실행은
  잘라 내지 않습니다: 이 변경 전에 쓴 파일은 전체 표본을 그대로 두고 바이트 단위로 같게 다시 씁니다.
  올바른 `physical_bounds`가 없는 실행은 표본을 모두 보존합니다. 한 작업의 두 사본(전체 표본과 잘라 낸
  표본)은 창 위의 표본이 같으면 같은 결과입니다. 파일 버전은 10 그대로이고 키는 더하지 않습니다.
- **모드가 놓인 곳(round 25, A4).** 열린 실행의 모드 표에도 닫힌 창의 안내 행이 붙습니다. 문턱(몫 0.5 초과, 창
  가장자리에 닿는 형상이면 닿는 변에서 300 nm 안에 |E|²의 0.01 이상)과 형상의 겹침 순서는 같고, 물리 창 위에서만
  잽니다: 중심이 3 × 2.4 µm 창 안에 있는 삼각형만 세므로, (예전 파일에서 읽은 실행에 남은) PML은 몫에도 그 합에도
  들지 않습니다. 코어 모드는 *Mode 3 is the core mode: 64 % of |E|² in the window (PML excluded) is in Core, which does not
  touch the window edge.*, 열린 변에 닿는 형상에 주로 있는 모드는 *Mode 2 is mostly in Substrate (93 % of |E|² in the window,
  PML excluded), which continues into the PML at the open window edge.*, 열린 실행의 닫힌 변이면 *…, which touches the closed
  bottom edge; its n_eff depends on that closed edge. Open it in Geometry › Boundaries to leave it open.*(둘 이상이면 *… bottom
  and left edges; … those closed edges. Open them …*)입니다. 안내는 |E|²가 놓인 곳만 말하고 모드가 갇혔는지 새는지는 말하지
  않습니다. 그것은 손실 열이 말합니다. Compare의 가장자리 안내 줄과 짝 없음 이유는 닫힌 창에만 씁니다.
- slice P3: 새 열린 실행은 엔진의 `te_polarization_fraction`과 `effective_area`(물리 창)도 보존합니다.
  군굴절률을 켜면 `group_index`를 `{"re", "im"}`로, `group_index_method`와 함께 보존합니다. 닫힌 실행의
  `group_index`는 목록 그대로입니다. slice P2가 쓴 실행에는 이 키들이 없습니다. Studio는 그 실행의 TE
  비율과 유효 면적을 저장된 장으로, `open_boundary.physical_bounds`가 주는 창에서 계산하고, 실행은
  그대로 저장합니다.
- [프로젝트 파일](#프로젝트-파일)은 이런 세션을 작업 공간 항목으로 담습니다: 그 reader는 버전 6, 7, 9, 10의 광학 세션을 받습니다.
- 버전 9 세션은 버전 9 입력을 담지 않습니다. Studio 4b58fb7은 버전 10 파일을 *This session file is version
  10, newer than this Studio reads (versions 6–9). Open it in a newer Studio.*로 거부합니다. 다중물리
  세션은 버전 8 그대로입니다.

**서버.** 작업 공간 요청은 `pml_strength` 3과 후보 32개(실행), 또는 6과 후보 16개(점검 풀이)를 담습니다.
점검 풀이는 모드를 겨누므로 목표는 1.45보다 큰 어떤 값이든 됩니다. 그 밖의 것은 이름을 밝혀 거부합니다:
“A PML check request (strength 6) searches 16 candidates, and a run (strength 3) searches 32.” 또는 열린
경계 문구. `/api/workspace/capabilities/v9`는 `pml_check_strength` 6과 `pml_check_search_mode_count` 16을
나열합니다. 이는 P1의 계약을 바꿉니다: P1은 강도 6과 32가 아닌 후보 수를 거부했습니다.

**검증**(Linux, Python 3.12, Node 22, 브라우저 점검 `tools/studio_browser/studio_workspace_browser.mjs`의
OB 단계):

- 템플릿, 모든 변 열림: 등록한 대로 두 손실 칸 모두 *< 0.01 dB/cm*(엔진은 TE-like Im n_eff −5.1e-12,
  `numerically_unresolved`, TM-like 1.36e-8, 0.0048 dB/cm를 줌). 다른 후보는 30개입니다;
- Geometry에서 만든 누설 사례(코어 아래 x −1500, y −1200, 3000 × 700 nm의 실리콘 기판, BOX 500 nm, 모든 변
  열림): 그 문서는 P1의 기판 위 스트립과 바이트 그대로 같습니다. 측정한 Linux 컨테이너에서는 *2.44126325 +
  8.28e-5i* / *29.15 dB/cm*와 *1.77279036 + 2.86e-3i* / *1006 dB/cm*로 P1의 값을 보입니다.
  - 처음 등록한 대로 점검은 모든 플랫폼에서 이 문자열을 확인했습니다. 등록이 값이 플랫폼에 무관하다고 잘못
    가정했고, CI가 실패했습니다: ubuntu-24.04는 TE Re 2.44128662(ΔRe 2.3e-5), macos-15는 TE “29.18 dB/cm”
    (+0.10 %)와 Re 2.44113899를 보였습니다.
  - 그 결과 뒤에 다시 등록했습니다: 화면 문자열은 같은 기계에서 같은 문서를 `simcase.run`으로 푼 결과를 페이지의
    형식 함수로 쓴 문자열과 정확히 같아야 합니다. 문서의 바이트 일치 점검은 그대로입니다.
  - CI의 값:

    | 플랫폼 | TE-like | TM-like |
    |---|---|---|
    | ubuntu-24.04 | 2.44128662 + 8.28e-5i, 29.15 dB/cm | 1.77280379 + 2.86e-3i, 1006 dB/cm |
    | windows-2022 | 2.44128662 + 8.28e-5i, 29.15 dB/cm | 1.77280379 + 2.86e-3i, 1006 dB/cm |
    | macos-15 | 2.44113899 + 8.29e-5i, 29.18 dB/cm | 1.77278771 + 2.86e-3i, 1006 dB/cm |

    PML 점검 판정은 모든 플랫폼에서 같습니다. 차이(Re 1e-4, 손실 0.1 %)는 기본 메시 오차(약 3 %)보다 훨씬
    작습니다;
- 같은 사례에서 Search near n_eff 1.600, 모드 4개는 등록한 대로 클래딩 굴절률 근처 모드 *1.48642654 +
  7.92e-3i* / *2789 dB/cm*를 찾습니다.

### 열린 경계의 모드 식별

slice P3는 열린 실행에 TE 비율, 유효 면적, 군굴절률, Compare의 짝짓기를 줍니다. 모두 **물리 창**에서
정의합니다. 물리 창은 중심이 엔진의 `physical_bounds` 안에 있는 삼각형들, 즉 PML을 뺀 3 × 2.4 µm
창입니다. 그곳에서 저장된 중심 장은 물리적인 E입니다. 닫힌 실행의 물리 창은 창 전체이므로 닫힌 식과
값은 모두 그대로입니다.

- **Polarization**(f_TE)은 닫힌 식을 물리 창에서 합한 것입니다. 도움말은 “TE = share of |E_x|² in
  |E_x|² + |E_y|², x horizontal, over the 3 × 2.4 µm window, PML excluded”입니다.
- **A_eff**는 같은 삼각형들에서 구한 (Σ A_T |E|²)² / Σ A_T |E|⁴입니다. 도움말은 “Effective area over
  the 3 × 2.4 µm window, PML excluded. For a strongly leaking mode it depends on the window.”입니다.
- 엔진이 두 값을 씁니다(`mode_postprocessing`, `integration_region: "physical_window"`). Studio는
  엔진의 값을 쓰고, slice P2가 저장한 실행은 저장된 장으로 같은 수를 계산합니다. *Run details*가
  출처를 밝힙니다: “computed by the engine (or by Studio) from the saved field on the physical window
  (PML excluded)”.
- 열린 경계에서 **n_g**는 복소수이며 열은 Re n_g를 보입니다. 도움말에는 “With an open boundary n_eff
  and n_g are complex: Re n_g is shown; Im n_g …. At the default mesh n_g is about 5e-3 low in the
  slab check; the error comes from n_eff and shrinks when the core mesh is refined.”가 붙습니다. PML
  점검의 풀이에는 군굴절률을 넣지 않습니다.
- **Compare**는 열린 실행을 두 물리 창이 겹치는 영역에서 짝짓습니다. 열린 실행의 표본은 물리 창의
  삼각형에서만 씁니다.

**검증**(`tests/simcase/test_open_boundary_mode_identity.py`, V11은
`tests/simcase/test_open_boundary_group_index.py`; Linux, Python 3.12, BLAS 스레드 1개):

| 점검 | 경우와 기준 | 결과 |
|---|---|---|
| V9 | 템플릿 열린 실행 대 닫힌 실행, \|Δf_TE\| ≤ 1e-3 | 1.70e-4(TE-like 0.98166 → 0.98149), 1.5e-5(TM-like): 통과 |
| V9 | V1 막(TE, PEC 옆벽) × 1, ½, ¼: 1 − f_TE ≤ 1e-3이고 감소; 반으로 나눈 단계는 블라인드 | 5.70e-4, 2.76e-4, 1.08e-4: 통과 |
| V10 | 템플릿 열린 실행 대 닫힌 실행, 상대 ΔA_eff ≤ 1e-2 | 7.2e-4, 9.9e-5: 통과 |
| V12 | 같은 표본에서 Node의 Studio 식 대 엔진 식, 상대 ≤ 1e-12; 블라인드 | 템플릿(창 안 삼각형 4,557개 중 2,283개)과 기판 위 스트립(40,658개 중 11,591개)에서 ≤ 3.4e-15: 통과. 창은 풀이기 자신의 물리 마스크와 같음 |
| V13a | 열린 템플릿 대 바깥 변이 PEC인 같은 메시, η ≥ 0.9999 | 1 − 4e-14, 1 − 2e-11: 통과 |
| V13b | × 1의 템플릿 닫힌 실행 대 열린 실행, 두 모드가 각자의 짝과 짝지어짐(η ≥ 0.8, 여유 ≥ 0.1) | 0.99033, 0.98754: 통과 |
| V13c | TE-like 1 − η(닫힘, 열림)가 × 1, ½, ¼에서 감소 | 9.67e-3, 3.15e-3, 9.44e-4: 통과. TM-like(보고만, 판정 없음): 1.25e-2, 3.94e-3, 1.12e-3. [이득 경계](pml_modes.md#이득-경계) 전에는 × ½와 × ¼에서 열린 실행이 그 모드를 돌려주지 않았음(아래 한계 참고) |
| V11a | V1 막의 dn_eff/dλ0 대 refsol, × 1, ½, ¼에서 상대 ≤ 1e-3(결과를 본 뒤 결정; 처음 등록한 “커지지 않음” 조건은 실패) | 5.61e-4, 7.29e-4, 7.29e-4: 통과; 기울기는 일정한 차이에서 멈춤(아래) |
| V11b | refsol 대비 Re·Im n_g 오차가 × 1, ½, ¼에서 감소 | Re 5.24e-3, 2.81e-3, 1.50e-3; Im 2.69 %, 1.06 %, 0.40 %: 통과 |
| V11c | 단일 지점 n_g 대 추적 sweep, 상대 ≤ 1e-12 | 같음(상대 차 0): 통과 |

- **처음 등록한 V11은 실패했습니다.** 기준은 × 1에서 \|ΔRe n_g\| ≤ 1e-3, Im 2 % 이내였고, 기준값은
  physmat 분산을 넣어 1549 nm와 1551 nm에서 구한 refsol 중앙 차분 3.706654 − 2.688e-4i였습니다.
  이 기준은 기본 메시 자신의 n_eff 오차보다 작았습니다. V1은 그 오차를 × ¼에서만 판정합니다. 결과를
  본 뒤 V11a–c로 바꾸었습니다.

  | 메시 | Re n_eff 오차 | Re n_g 오차 | Im n_g 오차 |
  |---|---|---|---|
  | × 1 | 4.76e-3 | 5.24e-3 | 2.69 % |
  | × ½ | 2.18e-3 | 2.81e-3 | 1.06 % |
  | × ¼ | 0.87e-3 | 1.50e-3 | 0.40 % |

  추적 sweep도 같은 n_g를 줍니다. 오차는 거의 모두 n_eff의 것입니다.
- **dn_eff/dλ0의 정체 구간(V11a).** FEM 기울기는 refsol 값에서 상대 7.3e-4쯤 떨어진 채 멈춥니다.
  Re n_g로는 약 6e-4이며, 기본 메시의 5.2e-3과 비교되는 크기입니다. × ½에서 시험한 경우(기울기의 상대
  오차):

  | 경우 | 기울기 오차 |
  |---|---|
  | 배포 메시 방식, × ½(× ¼) | 7.29e-4(7.29e-4) |
  | PML 강도 3 대신 6 | 7.29e-4 |
  | PML 1 µm 대신 2 µm | 6.84e-4 |
  | 두 모형 모두 Si·SiO2 상수 굴절률 | 6.82e-4 |
  | 두 모형 모두 2 nm 간격 | 7.29e-4 |
  | 먼 영역 크기와 요소 크기를 한 번 더 반으로 | 1.18e-3 |
  | 세밀화 거리 2 µm | 1.15e-3 |

  차이는 PML 강도, 분산, 차분 간격, 코어 메시에 따라 바뀌지 않습니다. PML을 2 µm로 하면 −6 %
  움직입니다. 코어에서 먼 메시를 세밀하게 하면 n_eff는 refsol에 가까워지지만 차이는 1e-3을 넘게
  커집니다. **원인은 찾지 못했습니다.** 1e-3 기준은 배포 메시 방식에서 성립하며, 클래딩을 세밀하게 한
  메시에서는 성립하지 않습니다.
- **처음 등록한 V13**(slice P2, η ≥ 0.99, 블라인드)은 0.9903과 0.9875로 실패했습니다. 원인은 PML이
  아니라 기본 메시의 이산화 오차입니다.
  - 닫힌 설계 하나의 서로 다른 두 메시도 그만큼 다릅니다(× 1 대 × ½: 0.9933, 0.9920).
  - 공통 격자는 η를 최대 6e-4만 움직입니다(간격 15에서 3.75 nm).

  결과를 본 뒤 V13a–c로 바꾸었습니다.
- **한계.**
  - [이득 경계](pml_modes.md#이득-경계) 전에는 세밀한 열린 메시에서 무손실 TM-like 모드가
    빠졌습니다. 아주 작은 Im n_eff가 반대 부호로 나와 엔진이 `negative_imaginary_index`로
    거절했기 때문입니다(템플릿의 TM-like 모드, × ½와 × ¼). 이 경계로 그 모드가
    `negative_within_pml_bound` 표시와 함께 반환됩니다.
  - 굽힌 도파로와 스칼라 정식화는 이 값들을 얻지 않습니다.
  - 누설이 강한 모드의 유효 면적은 창에 따라 달라집니다.

### 광학 세션 파일(버전 9)

모든 실행이 실수 모드 두 개와 장을 가진 세션은 이전과 바이트 단위로 같은 버전 7로 씁니다. 버전 7이 담을 수
없는 실행(모드 1개 또는 3–8개, 복소 유효 굴절률, 장이 없는 실행, 모드 3 이상을 보이는 보기)이 생기거나 입력이
[버전 8](#입력-파일의-study-설정버전-8)이면 버전 9로
씁니다. 버전 6·7 파일을 열어도 다시 쓰지 않습니다. 그 실행은 모드 두 개로 읽고, TE 비율과 유효 면적은
Studio가 저장 샘플에서 계산하며, 세션은 다시 버전 7로 써집니다. 버전 9 이전 Studio는 버전 9 파일을 *This
session file is version 9, newer than this Studio reads (versions 6–8). Open it in a newer Studio.*로
거부합니다. 다중물리 세션은 버전 8 그대로입니다. 브라우저 복구도 같은 텍스트를 보존하므로 같은 규칙을 따릅니다.

버전 9 파일은 정확히 다음 키를 가진 JSON 객체 하나입니다: `format`(`"openphysics-studio-session"`),
`version`(9), `application`(`"optical"`), `input`(버전 7 입력 파일), `runs`(최대 여섯 개), `selected`(실행의
`job` 또는 null), `comparison`(`job` 두 개 또는 null), `view`(모두 필수. 버전 7과 같되 `mode`는 0–7이며 선택한 실행의
모드 수보다 작음). `input`은 버전 8 입력 파일(study 설정)일 수도 있습니다. 입력이 버전 8인 세션은 모든 실행이
버전 7에 맞아도 버전 9로 쓰며, 그런 입력을 담은 버전 6·7 세션은 거부합니다(*A version 7 session holds an
input file of version 6 or 7.*, 버전 6도 마찬가지). 그래서 버전 6·7 파일에서 읽은 실행의 굴절률이 n = 1.45 위에서
순서대로가 아니면 Modes to find가 2가 아니거나 군굴절률 선택이 켜진 동안 저장할 수 없습니다. 거부는 그 실행을
밝히고 설정이 버전 9를 요구한다고 말합니다. 브라우저 복구는 계속됩니다. 그 노트북을 설정 없이 버전 7로
보존하고, 메시지 줄과 복구 세부 정보에 한 번 그렇게 알립니다(*Browser recovery kept this notebook without
Modes to find 3: …*). 입력 파일을 버전 7까지 읽는 Studio는 그런 버전 9 파일을 *Unsupported project format or
version.*으로 거부합니다. 실행마다 다음 키를 이 순서로 가지며, 다른 키는 이름을 밝혀 거부합니다.

| 키 | 형식 | |
| --- | --- | --- |
| `job`, `completedAt`, `label`, `pinned`, `origin`, `serverVersion`, `input` | 버전 7과 같음 | 필수 |
| `settings` | 버전 7과 같되 `adapter: "optical-shapes-v8"`, `mode_count` 1–8 | 필수 |
| `effective_index` | 수 k개 또는 `{"re": [k], "im": [k]}`. 1 ≤ k ≤ `mode_count`, Re n_eff 순서, 모든 Re가 1.45보다 큼 | 필수 |
| `field` | 모드 k개의 `{node_coordinates, triangles, real, imag}`(버전 7처럼 이 네 키만 읽음. `field` 안의 다른 키는 거부하지 않으며 digest가 덮고 다시 쓰지 않음) | 선택 |
| `te_polarization_fraction` | [0, 1]의 수 또는 null k개: 엔진의 값(`field` 없이 쓴 실행은 그 실행이 보이던 값) | 선택, `field`가 없으면 필수 |
| `effective_area` | 0보다 큰 m² 단위 수 또는 null k개: 엔진의 값(`field` 없이 쓴 실행은 그 실행이 보이던 값) | 선택, `field`가 없으면 필수 |
| `group_index`, `group_index_method` | 수 또는 null k개(null: 엔진이 대응시키지 못한 모드); 1–64자 텍스트(`group_index`와 함께만), `central_difference <간격> <추적기>` 형식, 예: `central_difference 1 nm electric-l2-assignment-v1` | 선택: Also compute group index로 실행한 경우 |
| `digest` | `"sha256:<hex>"` | 필수 |

digest는 digest를 뺀 실행을 키 정렬 JSON(버전 8의 수 규칙, 음의 0은 `-0.0`)으로 쓴 텍스트의 SHA-256이므로
실행의 다른 모든 키를 덮습니다. 바뀐 실행은 *Run 1 changed after it was saved (its check value does not
match).*로 거부하며, 모드 수가 8을 넘으면 *Run 1 asks for 9 modes; this Studio reads 1 to 8.*로 거부합니다.
Studio는 스스로 거부할 파일을 쓰지 않습니다. 버전 6·7 파일에서 읽은 실행의 굴절률이 n = 1.45 위에서 순서대로가 아니면 버전 7 세션에는 남을 수 있지만, 버전 9가 필요한 저장은 그 실행을 밝혀 거부합니다. 수는 버전 8처럼 쓰며, Studio가 읽은 실행(그때 origin은 `imported`)으로 쓴 파일은 다시 써도 바이트 단위로
같습니다. digest는 손상되거나 손으로 고친 파일을 찾아낼 뿐 인증이 아닙니다.

템플릿 메시(삼각형 2275개)에서 모드 8개인 실행 여섯 개는 약 9.4 MB, 모드당 약 0.2 MB입니다. 열린 실행은 물리 창만
보존합니다: T16 실행은 3.9 MB(PML 포함 13.4 MB), 모드 3개와 군굴절률을 더한 T16은 5.6 MB(19.0 MB)입니다. 측정은
`tools/studio_open_field_size.mjs`입니다. 2026-11-24에 T18(실리콘 기판 위 스트립, 코어 메시 30 nm)로 잰 크기: 모드 2개 닫힌
실행 2.10 MB, 모드 4개 3.78 MB, 모드 4개 closed near 2.46 3.75 MB, 모드 2개 열린 실행은 n_g와 상관없이 3.94 MB(장이 각각의
99 %, 장 없는 실행은 3–21 kB)여서, T22의 여섯 번째 실행이 세션을 22 MB로 만들었습니다. [단정밀도](#압축-필드단정밀도)로는 같은
장이 1.02, 1.74, 1.74, 1.11 MB입니다. [실행 보관](#실행-보관-값과-필드)부터
광학 모델은 장을 하나의 예산 안에서 보관하므로 세션이 한도를 넘지 않고, Save는 묻지 않으며, 브라우저 복구는 Save와 같은
텍스트를 씁니다. 아래의 질문, 거부, 복구 규칙은 탭이 파일보다 많이 담는 두 경우(그 절에서 설명)에만 남습니다.

한도를 넘는 세션은 다중물리 세션처럼 먼저 묻습니다. *Keep fields for selected and pinned runs*는 나머지
실행을 `field` 없이 n_eff·TE 비율·유효 면적과 함께 쓰고, Cancel은 아무것도 쓰지 않으며, 선택·고정 실행만으로도
한도를 넘으면 선택 실행과 고정 실행을 따로 밝혀 저장을 거부합니다: *The selected run (Run 6) and the pinned runs
(Run 4, Run 5) are 46.2 MB with their fields, over the 16.8 MB session limit. Unpin some of them.*(고정 실행이 하나면
*Unpin it.*). 그중 고정 실행이 없으면 *The selected run (Run 6) is 18.9 MB with its fields, over the 16.8 MB session
limit. Select a different run before saving, so this one is saved without its fields, or run it again with fewer
modes.*라고 합니다. 복구 오류도 *Recovery snapshot exceeds 16 MiB:* 뒤에 같은 말을 합니다. 결과로 세션이 한도를 넘으면 결과
메시지에 *Session is now 18.9 MB, over the 16.8 MB limit, and File › Save will refuse:*와 거부 문구, *Browser recovery is off.*가
붙고, 필드가 들어오지 않았는데 텍스트가 한도를 넘게 커졌을 때는 다음 결과의 줄이 *Session is now 17.0 MB, over the 16.8 MB limit.
Browser recovery keeps every run's values; the field plots of Run 6 are not kept. File › Save will ask whether to keep the field
plots of the selected and pinned runs only (Runs 1, 2 and 9).*입니다. round 24(B3)는 이 줄들의 단위를 MB 소수 한 자리 하나로
맞췄습니다(16.8 MB를 조금 넘는 크기는 소수 두 자리). 전체 텍스트가 한도를 넘으면 브라우저 복구는 묻지 않고 선택·고정 실행의 장을
보존하고, 그다음(round 23) 나머지 실행의 장을 새것부터 기록이 16 MiB 안에 머무는 동안 더하며, 헤더가 뺀 실행을 밝힙니다: *… ·
kept for recovery in this browser without the fields of Run 1 and Run 2*. 장을 뺀 기록을 복원하면 메시지에 *Fields not kept for
Run 1 and Run 2; their n_eff, TE fractions and effective areas were.*가 붙습니다.

### 광학 세션 파일(버전 12)

세션 버전 12(설계 *Stable run numbers and the project name after recovery*)부터 광학 실행은 파일과 브라우저
복구에서도 번호를 유지합니다. 버전 12는 버전 10의 열린 경계와 버전 11의 닫힌 창 탐색을 담은
[버전 9](#광학-세션-파일버전-9)에 실행마다 키 하나를 더한 것입니다: `number`, 탭 안의 실행 번호로 `job` 바로
다음에 오고 실행의 `digest` 안에 들어갑니다. 최상위 키는 버전 9와 같습니다. 버전 12는 버전 9~11이 담는 모든 실행을
담습니다.

- **언제 쓰는가.** 어떤 실행의 번호가 목록 안 자리와 다를 때만 씁니다. 예를 들어 한도가 Run 1을 내보낸 뒤나
  파일에서 실행을 추가한 뒤에는 Run 2~7을 버전 12로 씁니다. 목록 순서대로 1, 2, 3 … 으로 번호가 매겨진 세션은
  전처럼 버전 11, 10, 9, 7로 바이트 그대로 씁니다. File › Save(세션 파일 또는 프로젝트 파일의 광학 항목)와 브라우저
  복구는 같은 텍스트를 씁니다.
- **읽기.** File › Open, Open project, Restore는 저장된 번호를 유지하므로 실행 목록, 내보내기 줄과 그
  **Pin Run N** 버튼, Compare 선택 상자, *No need to run: Run N*, 복구 목록이 전과 같은 실행을 가리킵니다. 버전
  6, 7, 9~11 파일은 전처럼 파일 순서대로 1부터 번호를 매깁니다. 저장된 카운터는 없습니다: 다음 실행은 가장 큰
  번호 + 1을 받고(가장 큰 번호가 8인 파일 뒤의 다음 실행은 Run 9), 가장 큰 번호의 실행은 결코 내보내지 않습니다
  (한도는 새 실행을 남기고, **Keep Run N, drop … instead**와 Add runs from file은 다른 실행만 내보냄). 작업이
  다시 돌아온 실행은 번호와 자리를 유지합니다.
- **검사.** 실행을 읽기 전에 각 `number`는 있어야 하고(*Run 3: missing number.*, 자리로 밝힘), 안전한 정수
  범위 안의 1 이상 정수이며(*Run 3: invalid run number.*), 한 번만 쓰이고(*Two runs have the same number 7.*),
  목록 순서대로 엄격히 커져야 합니다(*Run 3 is numbered 5, not after Run 2's 7.*). 다른 상한은 없습니다. 저장 뒤
  고친 번호는 실행의 digest에 걸립니다(*Run 2 changed after it was saved (its check value does not match).*).
  그다음 실행 자체의 검사는 저장된 번호로 실행을 밝힙니다(*Run 6: invalid search target. …*). 버전 9~11은 여전히
  `number` 키를 거부합니다(*Run 1: unknown key "number".*).
- **이전 Studio.** 버전 11까지 읽는 Studio(main fc654fe)는 버전 12 파일을 이름을 밝혀 거부합니다: *This session
  file is version 12, newer than this Studio reads (versions 6–11). Open it in a newer Studio.*, 프로젝트 파일
  항목이면 앞에 *Optical waveguide: *가 붙습니다. 그런 파일을 담은 브라우저 복구 기록은 넘겨받지 않으므로(기록을
  넘겨받기 전에 읽음) 그 기록을 덮어쓰지 않습니다. 프로젝트 파일은 버전 1 그대로이고, 광학 문서·어댑터·요청·결과,
  다중물리 세션(버전 8), 실행 표 CSV도 바뀌지 않습니다.
- **번호 문장 없음.** 버전 12 이전에 쓴 세션은 실행 번호를 담지 않으며, 그 실행은 파일 안 자리로 번호가 매겨집니다.
  Studio는 그 번호가 정확할 때만 이전 버전을 씁니다. 그래서 열기나 복원의 어떤 메시지도 번호에 대해 말하지 않습니다
  (round 19의 *Runs are numbered from 1 in this tab; names and pins are kept.*는 없어짐).
- **Add runs from file**은 추가한 실행을 파일 순서대로 탭의 가장 큰 번호 다음부터 번호를 매기고, 번호가 바뀌면
  그렇게 밝힙니다: *Added Run 2 and Run 4 of design-b.json as Run 9 and Run 10.* 이미 탭에 있는 작업은 탭의 번호를
  유지합니다.

검사는 `tests/simcase/studio_session_numbers.cjs`(K1: 이전 광학 fixture, 다중물리 fixture, 프로젝트 fixture를
모두 읽고 다시 써서 바이트 그대로; K2: 실행 3, 5, 6, 7, 8, 9의 버전 12 fixture `optical-v12-numbers.json`과 그
거부; K3·K9: main fc654fe가 읽는 결과 `refusals-v12-fc654fe.json`), `tests/simcase/studio_session_numbers_page.cjs`
(K6: 결과·고정·교환·가져오기·저장·열기·복원 2400 단계의 시드 고정 무작위 순서; K7: 헤더 줄; K10: 버전 7, 11, 12 파일에 번호 문장 없음),
`tools/studio_browser/studio_project_browser.mjs`의 K4/K5 단계입니다.

### 실행 보관: 값과 필드

실행 보관(설계 *Keeping more runs*, round 24 B1)부터 광학 모델은 실행 최대 20개의 **값**을 보관하고, 그 **필드**는 하나의
예산 안에서 보관합니다. 예산은 탭, File › Save, 프로젝트 파일의 광학 항목, 브라우저 복구가 함께 쓰므로 탭이 보여 주는 것이
파일이나 복원이 되돌려 주는 것입니다. 전에는 실행 여섯 개를 통째로 보관했습니다: 일곱 번째 실행은 실행 하나를 값까지 내보냈고,
16 MiB를 넘는 탭은 Save가 묻고 복구가 빠뜨리는 필드를 보여 주었습니다.

- **값.** 실행의 값은 n_eff(실수부와 허수부), TE 비율, 유효 면적, n_g, 열린 실행의 후보입니다. 모든 실행이 값을 보관합니다.
  필드 없는 실행은 파일에서 3–21 kB이고, 그런 실행 20개는 0.5 MB보다 작습니다.
- **예산.** 16 MiB 세션에서 입력용으로 남겨 두는 16 KiB를 뺀 16,760,832바이트이며, 16.8 MB로 말합니다. 세션 텍스트에는 결과
  사이에 바뀌는 입력, 비교, 보기도 들어 있으므로, 16 KiB는 예산까지 찬 탭이 그런 편집 뒤에도 16 MiB 안에 머물게 합니다.
- **필드가 빠지는 때.** 필드가 들어올 때만입니다: 새 결과, 다시 계산한 필드, Add runs from file, File › Open이나 Restore,
  그리고 **Keep Run N, drop … instead**가 실행을 되돌릴 때. 실행을 선택하거나, 고정하거나, 고정을 풀거나, 이름을 붙이거나,
  비교해도 필드는 빠지지 않습니다. 그래서 탭은 지금 아래 순서가 고를 것보다 많은 필드를 담을 수 있지만, 예산보다 많이 담지는
  않습니다.
- **순서.** 필드가 들어오면 선택된 실행, 그다음 방금 필드가 들어온 실행(다시 계산했거나 되돌린 실행이 선택된 실행이 아닐 때),
  그다음 고정된 실행을 새것부터, 그다음 나머지 실행을 새것부터(실행 번호가 큰 것부터) 보관합니다. 각 필드는 세션이 예산 안에
  머무는 동안 더하고, 들어가지 않는 필드는 건너뛰고 그다음 오래된 것을 시도합니다. 고정은 실행의 값을 20개 한도의 내보내기에서
  지키고 그 필드를 고정되지 않은 실행보다 앞에 두지만, 필드를 보장하지는 않습니다.
- **문구.** 실행 전, 같은 형상·경계·Modes to find의 가장 새 실행이 새 필드의 크기를 알려 줄 때 **Run study** 옆 줄이 값만
  남을 실행을 밝힙니다: *If you run: Run 3 (closed · 4 modes · 700 × 300 nm) keeps its values, not its fields*와 **Pin Run 3**
  (둘 이상이면 *… and Run 5 (…) keep their values, not their fields*). 그런 실행이 없으면, 16.8 MB에 남은 공간이 지금 유지된
  가장 작은 필드보다 작을 때만 *If you run: older runs' fields may not be kept (16.8 MB limit) · pin a run to keep its fields first*
  (round 25, A1. 실행을 밝히지 않으므로 Pin 버튼 없음)를 보이고, 그 밖에는 아무 말도 하지 않습니다. 두 줄 모두 결과가 도착할 때
  적용할 크기로 셉니다: 필드가 아직 텍스트인 탭에서 필드를 모두 텍스트로 담을 수 없게 되는 결과는 먼저 모든 필드를 압축하므로
  ([압축 필드](#압축-필드단정밀도)), 줄은 단정밀도로도 남지 못할 실행만 밝힙니다(round 26, C1). 실행이
  계산하는 동안: *When this run finishes, Run 3 (…) keeps its values, not its fields*. 실행이 20개이면 위의 내보내기 문구가
  그대로입니다. 결과 뒤에는 Messages가 *Run 3 (…) keeps its values; its fields were not kept (16.8 MB limit).*와
  **Recompute Run 3's fields**를, 고정되지 않고 선택되지 않은 다른 실행의 필드가 그만큼 크면 **Keep Run 3's fields, not Run 4's
  (…)**를 둡니다. 그 버튼은 *Run 3's fields are back; Run 4 (…) keeps its values, not its fields.*로 답합니다. 고정된 실행의
  필드가 빠지면: *Run 2 (pinned) keeps its values; its fields were not kept: the selected and pinned runs' fields are 17.4 MB,
  over the 16.8 MB limit. Unpin a run to keep the newer fields first.* 실행 목록은 그런 실행에 *· values only*를 붙이고, 트리는
  *Runs · 9 of 20*, 실행 목록 아래 안내는 *Up to 20 runs are kept with their values. Fields are kept up to 16.8 MB. When a result
  or a recompute arrives, Studio keeps the selected run's fields first, then pinned runs', then the newest. Selecting a run does not
  bring its fields back; Recompute does. Pinned runs stay; when a 21st run arrives, the oldest unpinned run is replaced. …*입니다
  (round 25, A1: 필드는 필드가 도착할 때만 옮겨 갑니다). 복구가 탭을 그대로 담으므로 헤더는 *… kept for recovery in this browser*입니다.
- **필드 없는 실행.** Results는 모드 표, 후보, 입력 줄을 보이고, 필드 보기 자리에 *Run 4's fields are not kept; its n_eff, TE
  fractions and effective areas are kept. Fields are kept up to 16.8 MB. When a result or a recompute arrives, Studio keeps the
  selected run's fields first, then pinned runs', then the newest. Selecting a run does not bring its fields back; Recompute does.*
  (필드 없이 파일에서 읽은 실행은 *Run 4's fields were not kept in the session file. …*)와 **Recompute Run 4's fields**,
  이 탭에서 계산한 실행이면 *· about 2 min*(그 실행의 경과 시간. 열거나 복원한 실행에는 없음)을 둡니다. 필드 PNG 내보내기는
  *Recompute Run 4's fields first*라는 제목으로 기다리고, 실행 표 CSV는 동작합니다. Compare는 다른 입력과 모드를 번호 순으로 나열한
  값 표(*Modes of A and B listed by mode number, not matched by overlap*), *Run 4's fields are not kept, so its modes are listed by
  number and not plotted.*와 버튼을 보이며, 두 실행 모두 필드가 있으면 그림과 겹침에 따른 Δn_eff가 돌아옵니다. 그런 실행의
  *No need to run*은 *No need to run: Run 4 already has these values; its fields are not kept. Run study adds a copy with the
  same values.*이고, **Show Run 4**와 **Recompute Run 4's fields**가 있습니다.
- **Recompute Run N's fields**는 실행이 계산될 때의 문서를, **Use this run's inputs**가 설정하는 대로(Modes to find, 단계를 포함한
  군굴절률, 바깥 경계, Search near n_eff) 저장된 입력과 설정으로 다시 만들어 같은 검증·실행 요청으로 보냅니다. 새 실행이 아닙니다:
  번호를 쓰지 않고 목록에 들어가지 않으며, 현재 입력, Undo, 선택된 실행은 그대로입니다. 작업 패널은 *Recomputing Run 4's fields ·
  about 2 min*이고, **Stop waiting**은 실행과 같이 동작합니다. 실행이 저장한 모든 값을 다시 계산한 결과와 각각 상대 1e-12(1e-3보다
  작은 값은 절대 1e-15)로 비교합니다. 일치하면 필드를 job, 번호, 이름, 고정, 시각, 출처가 그대로인 같은 실행에 붙이고(*Run 4's
  fields recomputed from its stored inputs; its values match.*), 필드가 들어왔으므로 위 순서를 적용합니다. 그렇지 않으면 아무것도
  바꾸지 않습니다: *Run 4's fields were not recomputed: mode 1 n_eff came out 2.439316630, stored 2.439316632. Run 4 is unchanged.
  Use this run's inputs and Run study to make a new run.*(버전이 다르면 값 뒤에 *(stored by Studio 0.9.3; this is 0.9.4)*).
  서버가 이제 거부하는 문서는 *Run 4's fields cannot be recomputed:*와 서버의 말을 보입니다. 다시 계산은 같은 빌드와 같은 스레드
  설정에서 일치합니다: 그때 풀이는 비트 단위로 재현됩니다(측정: 단일 스레드, 그리고 기본 스레드끼리). 다른 스레드 수로 계산한
  실행은 일치하지 않을 수 있으며(열린 실행은 스레드 하나와 기본 스레드 사이에 최대 5e-11 달랐음), 그러면 Studio는 실행을 바꾸지
  않습니다.
- **탭이 파일보다 많이 담는 경우.** 두 경우이며, Save와 복구는 각각 [버전 9](#광학-세션-파일버전-9)의 질문, 거부, 복구 규칙으로
  알립니다: 선택된 실행 하나만으로 예산을 넘을 때(모드 8개 열린 실행이 가까이 갈 수 있음) 탭은 그 실행이 선택된 동안 필드를
  보관합니다. 그리고 마지막으로 필드가 들어온 뒤 세션이 입력용 16 KiB보다 더 커졌을 때입니다. 입력에는 한도가 있으므로(광학 형상
  8개, Joule 형상 8개, 재료 6개) 두 번째 경우는 드물며, 다음에 필드가 들어오면 예산 안에서 다시 고릅니다.
- **측정**(2026-11-25, `tools/studio_run_retention.mjs`): T18 혼합 결과 20개(닫힌 모드 2개, 닫힌 모드 4개, closed near 2.46,
  n_g가 있는 열린 실행; Run 2 고정)는 텍스트로 필드 4개를 보관합니다. 세션은 결과마다 최대 16.6 MB이고, 필드 없는 기록 20개는
  0.15 MB입니다. [압축 필드](#압축-필드단정밀도)로는 같은 결과 20개가 필드 11개(Run 2와 11~20)를 보관합니다.

검사는 `tests/simcase/studio_run_retention_fields.cjs`(순서, 문구, 번호에 대한 2000단계의 시드 고정 순서열, 파일·복구와 탭의
비교, 위 두 경우), `tests/simcase/studio_run_retention_recompute.cjs`, 도구의 `k1`과 `k5` 명령,
`tools/studio_browser/studio_workspace_browser.mjs`의 RT 단계(실행 보관)입니다.

### 압축 필드(단정밀도)

설계 *Compact field encoding*(라운드 25 A1)부터 필드를 단정밀도로 보관할 수 있어, [16.8 MB 예산](#실행-보관-값과-필드)에 더 많은
필드가 들어갑니다.

- **필요할 때만.** 탭의 모든 필드가 텍스트로 들어가는 동안에는 아무것도 바뀌지 않으며 파일도 전처럼 씁니다. 필드를 모두 텍스트로
  담을 수 없게 되는 첫 도착(결과, 재계산한 필드, Add runs from file, 또는 실행을 되돌리는 **Keep Run N, drop … instead**) 때 탭의
  모든 필드를 단정밀도로 보관하고, 줄어든 크기로 실행 보관의 순서를 적용합니다. Messages는 이를 알리지 않습니다(round
  27, D1. 25·26차에는 문장이 있었음). 실행 목록 아래 안내와 압축 실행의 장 보기 아래 줄이 해당하는 곳에서 알립니다. 그때부터
  저장한 파일은 광학 세션 버전 14이며, 이전 Studio는 이름을 들어 거부합니다. 그 뒤 들어오는 필드도 모두 같은 방식으로 보관하며, 탭은
  되돌아가지 않습니다. File › Open과 Restore는 필드를 모두 텍스트로 담을 수 있는 한 파일에 담긴 그대로 보관하므로, 열어서 바꾸지
  않고 다시 저장한 파일은 원래 바이트와 같습니다.
- **바뀌는 것.** 장 표본을 float32로 반올림합니다(유효숫자 약 7자리, 상대 오차 최대 2^-24, 약 6e-8). 노드 좌표와 삼각형은 그대로
  보관하므로 창, 잘라내기, 물리 창은 바뀌지 않습니다. n_eff, TE 비율, 유효 면적, n_g, 열린 실행의 후보는 실행이 전에 보여 준 값을
  실행과 함께 저장합니다. 장 보기, 탐침, 단면, Compare, PNG 내보내기는 float32 표본을 읽으므로, 복구하거나 연 파일은 탭이 보여 준
  것과 똑같이 보여 줍니다. T18 결과로 측정하면, 압축 필드에서 계산한 TE 비율과 면적은 최대 상대 7e-9, 정규화한 장 보기는 6e-8
  차이가 나며, 탐침의 6자리 표시는 삼각형의 약 1 %에서 마지막 자리가 1 다릅니다.
- **문구.** 압축 실행의 장 보기 아래 Results: *Field at single precision (float32). The values above are the engine's.* Export this
  run: *… with the run's inputs and fields (fields at single precision) …*(버전 14 파일). 탭에 압축 필드가 생기면 실행 목록 아래
  안내에 *When fields would not all fit, they are kept at single precision.*이 붙습니다. 단면 CSV의 머리글과 열은 그대로이며,
  relative_amplitude [1]은 정규화한 float32 표본입니다.
- **단정밀도로 담을 수 없는 필드**(±3.4e38를 넘는 표본, 또는 0이 되거나 1.2e-38 아래 비정규 수가 될 0이 아닌 표본)는 텍스트로
  남습니다. 엔진 장은 최대 1로 정규화되므로 합성하거나 고친 파일만 그런 필드를 담습니다.
- **전체 정밀도.** 탭이 압축되면 float64 필드는 남지 않습니다. **Recompute Run N's fields**는 내보낸 필드를 되찾고 모든 값을
  1e-12까지 검사한 뒤 다른 필드처럼 단정밀도로 보관합니다. float64 표본이 필요하면 **Use this run's inputs** 다음 Export solver
  JSON으로 문서를 내보내 simcase로 실행하십시오.
- **한계.** 버전 6이나 7 파일에서 처음 연 실행의 저장된 TE 비율과 유효 면적은 Studio가 그 파일의 장에서 계산한 값입니다. 저장한
  뒤에는 Studio가 이를 저장된 값으로 표시합니다. TE 비율이나 유효 면적이 수가 아닌 실행(프로젝트 고정 파일 `project-v1.json`의
  실행처럼 합성 파일에만 있음)이 있으면 압축 필드 전과 같이 탭에 필드 예산이 없고, 그 필드는 그대로 남습니다.
- **크기**(2026-11-25, 실리콘 기판 위 T18 스트립, 코어 메시 30 nm; 텍스트 → 단정밀도): 닫힌 모드 2개 2.25 → 1.02 MB, 닫힌 모드
  4개 4.10 → 1.74 MB, closed near 2.46 모드 4개 4.08 → 1.74 MB, 열린 모드 2개(n_g 유무와 관계없음) 3.92 → 1.11 MB(노드 6,263개,
  삼각형 12,253개). 압축 필드의 크기는 개수에서 정해집니다: 32·k·T + 4⌈16N/3⌉ + 4⌈12T/3⌉ 문자와 키(모드 k개, 노드 N개, 삼각형
  T개). T18 필드 여섯 개(텍스트 16.6 MB)인 탭의 변환은 Node에서 112 ms, 필드 11개(텍스트 13.6 MB)인 탭은 Chrome에서 68 ms였습니다. 브라우저에서
  닫힌 T18 실행 셋의 장 보기, 단면, 장 PNG는 변환 전후에 같았고, 31개 보기 중 하나에서 4픽셀이 색 1단계 달랐을 뿐입니다. Deflate는 측정했으나 쓰지 않습니다: 열린 필드에서
  1.05배, 닫힌 필드의 허수부에서 최대 2.8배(닫힌 필드 표본의 절반이 정확히 0).

검사는 `tests/simcase/studio_field_encoding_format.cjs`(형식, F1, F3, F4, F10), `tests/simcase/studio_field_encoding_tab.cjs`(F2:
필드가 들어가는 동안 변환 없음, main 499a0d3과 같은 텍스트; F11: 변환이 있는 2000단계의 시드 고정 순서열; F6과 F8: 압축 필드에서
Studio가 계산하는 것), `tests/simcase/test_studio_field_encoding.py`(F5: NumPy와 같은 문자열), `tools/studio_field_encoding.mjs`
(`f9`, `f14`, `f16`, `sizes`)입니다.

### 광학 세션 파일(버전 13)

버전 13은 실행을 최대 20개 담는 [버전 12](#광학-세션-파일버전-12)입니다: 실행 기록(`job` 다음의 `number`, 같은 키, 같은
digest)과 최상위 키가 같습니다. 버전 6~12는 실행을 최대 여섯 개 담습니다.

- **언제 쓰는가.** 세션의 실행이 여섯 개보다 많을 때만 씁니다. 실행이 여섯 개 이하인 세션은 전처럼 버전 12, 11, 10, 9, 7로
  바이트 그대로 쓰므로 이전 Studio도 그대로 읽습니다. 실행이 여섯 개 이하인 버전 13 파일(손으로 고친 것)도 읽습니다.
- **읽기.** File › Open, Open project, Restore, Add runs from file은 실행을 최대 20개 읽습니다. 실행 21개인 파일이나 실행 일곱
  개인 버전 12 파일은 *Unsupported session format or run count.*로 거부합니다. 번호 검사는 버전 12와 같습니다.
- **이전 Studio.** 버전 12까지 읽는 Studio(main 3f16709)는 실행 수를 세기 전에 버전 13 파일을 이름을 들어 거부합니다: *This
  session file is version 13, newer than this Studio reads (versions 6–12). Open it in a newer Studio.*(프로젝트 파일의 항목은 앞에
  *Optical waveguide: *). 그런 파일을 담은 브라우저 복구 기록은 넘겨받지 않습니다. 그런 Studio와 실행을 나누려면 최대 여섯 개를
  내보내십시오(Export this run, 또는 실행 여섯 개의 세션). 프로젝트 파일은 버전 1 그대로이고, 광학 문서, 어댑터, 결과,
  다중물리 세션(버전 8), 실행 표 CSV도 그대로입니다.

검사는 `tests/simcase/studio_run_retention_format.cjs`입니다(K2: 이전 고정 파일을 모두 바이트 그대로 다시 씀; K3: 실행 2와
4~11의 고정 파일 `optical-v13-nine-runs.json`; K4: main 3f16709가 읽는 것, `refusals-v13-3f16709.json`).

### 광학 세션 파일(버전 14)

버전 14는 실행이 압축 필드([압축 필드](#압축-필드단정밀도))를 담을 수 있는 [버전 13](#광학-세션-파일버전-13)입니다: 최상위 키, 실행
0~20개, 버전 13의 실행 기록과 digest가 같습니다. 필드는 버전 13의 중첩 숫자이거나, 다음 키를 이 순서로만 갖는 압축 필드입니다:

```json
"field": {
  "encoding": "f32-base64-v1",
  "counts": {"modes": 2, "nodes": 6263, "triangles": 12253},
  "node_coordinates": "<base64: nodes × 2 float64, little-endian, metres>",
  "triangles": "<base64: triangles × 3 uint32, little-endian>",
  "real": "<base64: modes × triangles × 3 float32, little-endian>",
  "imag": "<base64: the same for the imaginary parts>"
}
```

- **배치.** 각 배열은 지금의 중첩을 펼친 것입니다: 모드, 삼각형, x·y·z; 노드, x·y; 삼각형, 세 인덱스. Base64는 RFC 4648의 표준
  알파벳에 패딩을 붙이고 줄바꿈은 없습니다. NumPy의 `astype('<f4')`, `'<f8'`, `'<u4'`와 표준 라이브러리 base64는 같은 문자열을
  씁니다.
- **저장된 값.** 압축 필드를 가진 실행은 TE 비율과 유효 면적도 저장합니다.
- **언제 쓰는가.** 압축 필드를 가진 채 보관된 실행이 있을 때만 씁니다. 그 밖에는 버전 13, 12, 11, 10, 9, 7로 바이트 그대로
  씁니다. 압축 필드가 없는 버전 14 파일도 읽습니다. 압축 필드는 읽은 문자열 그대로 다시 쓰므로, 읽고 다시 쓴 버전 14 파일은 원래
  바이트와 같습니다.
- **거부**(각각 실행을 밝힘): *Run 5's field is encoded as "…", which this Studio does not read.*; *Run 5's compact field must
  hold encoding, counts, node_coordinates, triangles, real, imag in this order, and nothing else.*; *Run 5's compact field counts
  must be whole numbers: modes 1 to 8, nodes 3 to 250000, triangles 1 to 500000.*; *Run 5's compact field holds 1 modes; the run
  has 2.*; *Run 5's compact field real is not canonical base64.*; *Run 5's compact field triangles holds 36 bytes; its counts give
  24.*; *Run 5's compact field imag holds a value that is not a finite number.*; *Run 5's compact field triangle 2 names node 5,
  outside 0–4.*; *Run 5's compact field triangle 1 repeats a node.*; *Run 5 has a compact field and no saved TE fractions and
  effective areas.*; 버전 13 이하 파일에서는 *Run 3: a compact field is read from a version 14 session file only.* 해독한 필드는
  그 뒤 중첩 숫자 필드의 모든 검사를 거칩니다.
- **이전 Studio.** 버전 13까지 읽는 Studio(main 499a0d3)는 버전 14 파일을 이름을 들어 거부합니다: *This session file is version
  14, newer than this Studio reads (versions 6–13). Open it in a newer Studio.*(프로젝트 파일의 항목은 앞에 *Optical waveguide: *).
  그런 파일을 담은 브라우저 복구 기록은 넘겨받지 않습니다. 프로젝트 파일은 버전 1 그대로이며(광학 항목은 버전 14를 읽음), 복구
  기록도 버전 1 그대로입니다. 광학 문서, 어댑터, 서버 응답, 결과, 다중물리 세션(버전 8)은 바뀌지 않습니다.

### Compare의 모드 짝짓기

Compare는 실행 A와 B의 모드를 장으로 짝지으므로, 설계 사이에 순위가 바뀌어도(예: 코어를 넓혀 두
번째 TE-like 모드가 TM-like 모드를 앞지르는 경우) 한 행은 같은 모드를 잇습니다. 짝짓기는 두 닫힌 실행에서
켜져 있고(열린 실행이 있으면 꺼짐: [열린 경계](#광학-작업-공간의-열린-경계)) 각 행에 순위가 그대로 보입니다.

- **공통 격자.** 두 실행의 메시는 다를 수 있고 각 실행은 자기 중심 샘플만 갖고 있으므로, Studio는 둘을
  한 격자에서 샘플합니다. 두 계산창의 교집합 위의 균일한 셀 중심이고, 간격은 ½ · min(A의 코어 메시,
  B의 코어 메시), 점은 많아야 400 × 400개입니다. 점은 자신을 포함한 삼각형의 중심 E_t = (E_x, E_y)를
  취하며, 한 실행의 어느 삼각형에도 들지 않는 점은 모든 합에서 뺍니다.
- **겹침.** η(a, b) = |Σ_g conj(E_A,a)·E_B,b|² / (Σ_g |E_A,a|² · Σ_g |E_B,b|²)이며, 엔진의 스윕 추적처럼
  가로 장만 씁니다. η는 모드의 임의 위상과 크기에 의존하지 않습니다. 축퇴 쌍([모드 표](#모드-표)처럼
  n_eff 차이 1e-3 이하)은 두 2-모드 공간 사이 주각(principal angle) 코사인 제곱의 평균으로 한 단위로
  짝지으며, 그 Δn_eff는 쌍 평균의 차이입니다. 쌍과 단일 모드의 값은 많아야 0.5이므로 짝지어지지 않습니다.
- **배정.** Studio는 모든 모드 쌍의 η를 계산하고 η 합이 가장 큰 일대일 배정을 고릅니다(모든 배정을
  시도하며, 실행마다 모드는 많아야 8개). η ≥ 0.8이고 η가 그 행과 그 열의 다음으로 큰 값보다 0.1 이상 클
  때 짝을 받아들입니다. 추적기의 기본값 `mode_tracking_threshold`와 `mode_tracking_margin_threshold`입니다.
- **표.** 짝지어진 모드마다 행 하나가 *1 ↔ 1*(쌍은 *1–2 ↔ 1–2*. 접근 가능한 이름은 전체 *A mode 1 ↔ B mode 1*이고
  제목은 겹침과 Δn_eff를 덧붙임)로 시작하고, 양쪽의 편광(낱말과 TE 백분율), 소수 2자리
  겹침, A와 B의 n_eff, Δn_eff (B − A), A 대비 Δ %, 그리고 A와 B의 A_eff(µm²)가 나옵니다(짝지어진 축퇴 쌍은
  두 모드 값의 *mean*을 보이며, 도움말은 각 모드의 값이 쌍 안의 회전까지만 정의된다고 밝힙니다), 그 뒤에 A와 B의
  흡수 손실(*Loss A (dB/cm)*, *Loss B (dB/cm)*)이 짝지어진 행과 짝이 없는 행 모두에 나옵니다:
  저장된 지수에서 얻은 모드 표의 값이며, 짝지어진 쌍은 두 모드 dB/cm의 *mean*이고, 광 어댑터의 재료는
  무손실이라 광학 실행은 *0 dB/cm*입니다. 그 뒤에 *n_g A*와 *n_g B*가 나옵니다(모드 표의 값, 짝지어진 쌍은
  두 모드 값의 *mean*, 실행에 값이 없으면 모드 표의 도움말과 함께 **—**). 머리글은 짧게 묶입니다:
  *Polarization*, *n_eff*, *A_eff (µm²)*, *Loss (dB/cm)*, *n_g*는 각각 **A** 열과 **B** 열 위에,
  *Modes*, *Overlap*, *Δn_eff (B − A)*, *Δ % (of A)*는 한 열 위에 있고, 표 위 줄이 실행 A와 B를 밝힙니다.
  Polarization 칸은 두 줄로, 종류 다음에 비율이 나옵니다(*TE-like* / *98.2 % TE*). 1440 × 900에서는 모든 열이
  표 상자에 들어갑니다. 상자가 더 좁으면(휴대폰) 첫 열은 그대로 보이고 나머지 열은 상자 안에서 옆으로 스크롤되며,
  상자 오른쪽 가장자리의 그림자와 *Scroll sideways for all 14 columns ›* 줄이 숨은 열이 있음을 알립니다.
  페이지는 옆으로 넘치지 않습니다. 짝이 없는
  모드는 *1 ↔ —* 또는 *— ↔ 2*로 시작하고 제목과 접근 가능한 이름이 전체 *A mode 2: no match in B
  (best overlap 0.43, with B mode 2)*이며, Overlap 열에 가장 좋은 겹침을 두 줄로 보이고(*best 0.43 (< 0.8, not matched)*, round 17; 가장 좋은 값이 0.8 이상이지만 다음 값보다 0.1 넘게 크지 않으면 *(margin < 0.1, not matched)*; 규칙 자체는 그대로) Δn_eff를 보이지 않고, 그 뒤에 짝이 없는 B 모드가 이어집니다.
  표 아래: “Matched by field overlap ≥ 0.8 on a common grid. A low overlap means the mode changed shape
  between designs.”
- **장 선택.** *Matched modes*는 짝지어진 쌍을 나열하고(*A mode 1 ↔ B mode 1 · overlap 0.99 · TE-like*,
  A와 B의 편광 낱말이 같으면 한 번, 다르면 *A TE-like, B hybrid*; 닫힌 선택은 창 너비를 채워 쌍 전체가
  보임. 짝지어진
  축퇴 쌍의 각 모드는 *pair, any rotation*), 두 그림과 단면 그래프는 고른 쌍을 보여 줍니다. 짝이 하나도
  없으면 선택이 꺼지고 두 그림은 각 실행의 모드 1을 *not matched*로 표시해 보여 줍니다. 이 선택은 저장하지
  않으므로 세션 파일은 이전과 똑같이 써집니다.
- **이전 파일.** 짝짓기는 저장된 샘플만 쓰므로 버전 6·7 세션 파일의 모든 광 실행에서 동작하며 파일에
  아무것도 더하지 않습니다.
- **한계.** η는 조각별 상수인 중심 샘플에서 구하므로, 크기 h인 메시에서 폭 w인 모드는 약 1.2 (h / w)²의
  이산화 오차를 갖습니다(30·25 nm 메시에서 폭 0.4 µm 모드는 약 1.5e-3). 메시를 줄이면 h²로 줄고, 0.8과
  0.1의 판정 간격보다 훨씬 작습니다. 차단에 가까운 모드는 설계 사이에 모양이 바뀔 수 있으며, 그때 낮은
  겹침은 짝을 억지로 만들지 않고 그 사실을 보여 줍니다. 다중물리 Modes 페이지에는 Compare가 없으며 순위를
  그대로 씁니다.

검사는 `tests/simcase/studio_mode_matching.cjs`(두 메시 위 이동한 가우시안을 정확한 겹침과 비교, 격자와
메시 연구)와 `tests/simcase/test_studio_mode_matching.py`(실리콘 스트립과 400 × 400 nm 정사각형 코어의
엔진 실행을 Studio의 짝짓기에 넣음)입니다.

## 범위와 검증

실험적 편집기이며 CAD나 범용 멀티피직스 솔버가 아닙니다. 광 흡수 → 열 → 변형과
형상 피드백은 아직 연결되지 않았습니다. 형상 그림과 결합 카드는 물리 검증의
근거가 아닙니다. 이 UI는 솔버나 수치 합격 기준을 바꾸지 않습니다.
[패키지 개요](overview.md)에 따라 서버는 로컬에서 사용하세요.

저장소 루트에서 관련 검사를 실행합니다.

```bash
node --test tests/simcase/*.cjs
python -m pytest -q tests/simcase/test_studio_workspace.py tests/simcase/test_studio.py
```

작업공간 검사는 버전·조건 협상, 숫자 입력, 편집 이력, 노트북·세션 검증, 장 데이터,
HTTP 자산을 다룹니다. 배포 검사에서도 설치 자산을 복사해 작업공간 JavaScript
검사를 실행합니다. 이 검사는 필수 전체 CI나 독립 물리 검증을 대체하지 않습니다.

## 입력 복구와 재료 검토

유효한 입력 변경은 별도 브라우저 복구 기록에 자동 저장됩니다. 새로고침 후
**Restore recent inputs from this browser**로 교체 확인을 거쳐 복원하며 계산은 실행하지 않습니다.
브라우저 origin별 최신 기록 하나를 탭끼리 공유합니다. 잘못된 중간 입력,
완료된 장 데이터, Undo 이력은 복구하지 않습니다. 자동 복구 기록은 파일 저장
완료로 취급하지 않습니다. 저장소 오류는 파일 저장 대안과 함께 표시합니다.
결과와 비교를 보존하려면 세션 파일을 저장하세요.

광학 Materials에서는 코어에 실리콘/질화규소, 배경에 실리카를 제공합니다.
가져온 미지원 재료는 그대로 표시하고 수정 전 실행을 차단합니다. 광학 재료는
실제 솔버에 전달하며, 개념 미리보기의 지정은 설정 라벨입니다. Study에서 현재
코어 치수와 재료를 확인하고 해당 편집 화면으로 이동할 수 있습니다.

다운로드 요청만으로 브라우저가 디스크에 파일을 저장했다고 확인할 수는 없습니다.
휴대 가능한 백업으로 사용하기 전에 브라우저의 다운로드 완료를 확인하세요. 입력·세션
표시는 마지막 저장/열기 스냅샷 또는 다운로드 요청과의 변경 여부이며, 변경 없음이
다운로드 완료를 보증하지 않습니다. 브라우저 복구는 저장소에 반영된 상태를 별도로 표시합니다.

## 실행·대기 중단·재개

작업 패널은 제출한 치수·재료, 작업 ID, 경과 시간(m:ss), 실행이 푸는 것, 결과 로딩 상태를 표시합니다. 예:
*Computing job 1a2b3c4d · 12:40 · Open boundary · 2 modes · searches near 2.46 and 1.95 · PML check (up to 2 more solves)*, *PML check · mode 1 of 2*.
서버는 작업 중 단계를 보고하지 않으므로 단계는 보이지 않습니다. Messages가 이 상태를 모두 되풀이하며 그것을 알리는
유일한 라이브 영역입니다. 작업 패널의 문구는 라이브 영역이 아니므로 화면 낭독기는 상태마다 한 번만 읽습니다(round 25, A6;
전에는 둘 다 갱신마다 알렸음).
**Stop waiting**은 브라우저의 조회만 중단하며 서버 계산은 계속될 수 있습니다.
**Resume job**은 현재 설계를 수정하거나 같은 탭을 새로고침한 뒤에도 실행 당시
입력에 연결된 같은 작업을 회수합니다. 대기 작업은 입력 자동 복구 및 세션 파일과
별개인 session storage에 기록하며 저장 실패를 알립니다. 서버 실행 식별자가
달라지면 재시작된 서버에서 이전 작업을 재개하지 않습니다.
작업이 사라졌거나 서버가 바뀌었거나 솔버가 실패를 보고하면 **Resume job**을
비활성화합니다. **Detach job**으로 연결을 해제한 뒤 새 계산을 시작하세요.
일시적인 연결 실패라면 같은 작업의 결과 조회를 재개할 수 있습니다.
어느 경우에도 보관된 결과와 현재 모델 입력은 바뀌지 않습니다.

탭당 작업 하나를 추적합니다. 새 계산 전 기존 작업을 재개하거나 **Detach job**으로
연결을 해제하세요. 연결 해제도 서버 계산을 취소하지 않습니다. 서버가 작업이 실행 중이라고 답하는 동안은
얼마나 걸리든 계속 기다립니다(바쁜 컴퓨터에서 열린 경계 계산은 15분쯤 걸릴 수 있음). 서버가 답하지 않을 때만,
즉 상태 요청이 3분 동안 실패하면 *The server has not answered for three minutes. Resume to check this job again.*이
나옵니다. 그때까지 실패한 요청은 0.7초마다 다시 시도하며 패널은 서버가 답하지 않은 시간을 덧붙입니다. 요청 실패는 기존 결과를 교체하지 않고 중단 후
늦게 도착한 응답은 무시합니다. 완료 비율을 추측하지 않고 경과 시간을 표시합니다.
서버 계산 취소와 서버 작업의 영구 저장은 아직 없습니다. 서버 재시작이나 탭 종료
전 완료된 세션을 파일로 저장하세요.

## 장 샘플 조회

Results 또는 Compare에서 그림 내부를 클릭하거나 x/y 좌표(nm)를 입력하고
**Inspect point**를 누릅니다. 십자 표시와 수치는 모델 입력과 같은 nm 물리 좌표를 사용하고, 장·메시·단면
그림의 축도 nm이며 눈금은 둥근 값에 놓입니다. 세션 파일은 이 위치를 µm 단위 양 문자열로 그대로 보관합니다. Compare는
두 메시의 같은 위치를 조회합니다. 값은 해당 위치를 포함하는 삼각형의 정규화된
저장 중심 샘플이며 보간한 점별 장 값이 아닙니다. 삼각형 번호와 중심 좌표를 함께
표시하고, 메시 밖이면 샘플이 없음을 알립니다. 공유 경계에서는 마지막으로 그린
삼각형을 일관되게 선택하고 퇴화한 셀은 제외합니다.

모드·성분 변경 시 그림과 같은 벡터 정규화 기준으로 값을 갱신합니다.
**Clear point**는 표시를 지웁니다. 조회 위치는 뷰 상태이며 세션 JSON과 브라우저 노트북 복구에
저장합니다. 장 PNG에는 선택한 표시와 좌표를 포함합니다. 이 조회는
수렴 검증이나 물리적인 절대 장 크기를 의미하지 않습니다.

## 실행 이름과 결과 보존

**Run name**에 최대 80자 이름을 입력하고 Enter를 누르거나 입력란을 벗어나면 선택한 실행에
이름이 붙습니다. 이름을 붙이면 실행이 고정되며, 입력란 아래 안내에 그렇게 적혀 있습니다.
이름은 **Runs** 목록·비교·세션 JSON·CSV에 포함되며 실행 당시 입력과 장 데이터를 바꾸지 않습니다.
Runs 목록은 각 실행을 이름, 크기, 파장, 완료 시각으로 표시하고, 작업 id·출처·simcase 버전·입력
변경 번호는 Results의 **Run details**에 있습니다. **Export this run**은 선택한 결과와 원래 입력만
포함한 독립 세션 파일을 내보냅니다.
여섯 실행 한도에서 고정하지 않은 오래된 결과가 제외되기 전에 개별 보존할 수 있습니다.
저장 표시(헤더와 하단)는 세션 변경과 입력만 저장한 파일을 구분합니다. 입력 파일·브라우저 draft
저장은 결과 노트북을 저장한 것으로 표시하지 않으며, 개별 결과 내보내기도 전체
노트북을 저장한 것으로 처리하지 않습니다. **Export field PNG**는 Results 그림을 그리므로
Compare에서는 사용할 수 없고, 버튼 아래 문구가 Results에서 실행을 열라고 안내합니다.

실행 취소는 설계 입력에 적용합니다. 텍스트 입력 밖에서 Ctrl/Cmd+Z로 되돌리고
Ctrl/Cmd+Shift+Z 또는 Ctrl+Y로 다시 실행합니다. 텍스트 필드는 기본 텍스트 편집을
유지합니다. 실행 이름과 비교 선택은 세션 메타데이터이며 입력 Undo 대상이 아닙니다.

## 메시 미리보기와 활성 인터페이스

광학 모델에서 **Mesh → Generate mesh**를 누르면 모드 계산 없이 기존 서버 메시
생성기를 호출합니다. 실제 삼각형과 영역 색, 노드·요소 수, 최소각, 평균 품질을
표시합니다. Full window 또는 Core region을 선택하며 nm 축에 x/y 동일 축척을
사용합니다. 설계를 바꾸면 이전 메시를 남기되 이전 입력이라고 표시하고 명시적
재생성 시 갱신합니다. 생성 실패는 마지막 정상 미리보기를 보존합니다.
미리보기는 탭에만 보관하고 세션 JSON에 저장하지 않습니다. 광학 실행은 같은 입력
계약으로 메시를 다시 생성하므로 메시 재사용이나 수렴 인증으로 해석하지 않습니다.

광학 전용 트리는 Geometry, Materials, Optical modes, Mesh, Study를 표시하고, 실행이 생기면 *Results · run N*
그룹(N은 보이는 실행)을 더해 Results를 여는 *Runs · N of 6*과, 실행이 둘 이상이면 Compare를 여는 *Compare*를
보여 줍니다. 6은 실행 목록의 안내(*Up to six runs are kept*)가 밝히는 실행 한도이며 둘 다 같은 상수에서 옵니다.

모든 모델의 모델 빌더는 *Model tree*라는 이름의 ARIA 트리입니다. 그룹 제목(*Component 1*, *Physics*,
*Analysis*; 다중물리 모델은 *Couplings*, *Study*, 마지막 실행의 결과)은 그룹을 열고 닫는 수준 1의 트리 항목이고,
그 노드는 수준 2(결과 페이지 포함), 다른 노드 아래의 노드(재료, 반복 단계)는 수준 3이며, 두 항목이 같은 이름을 갖지
않습니다. 노드는 그 설정이나 페이지가 보일 때만 고른 것으로 표시됩니다(`aria-selected`): Results에서 광학 트리는
*Runs*를, 다중물리 트리는 보이는 결과 페이지를 표시하며, Compare에서 광학 트리는 *Compare*를(그 페이지에서는
트리가 숨겨짐) 표시하고 다중물리 트리는 아무것도 표시하지 않습니다. 트리의 탭 정지는 고른 노드 하나입니다(트리에 초점이 있는 동안에는 화살표가 옮김). **Up**과 **Down**은 보이는 항목 사이를,
**Home**과 **End**는 처음과 끝으로 옮기고, **Enter**나 **Space**는 노드를 고르거나(클릭과 같음) 그룹을 열고
닫으며, **Right**는 그룹을 열거나 그 안으로, **Left**는 그룹을 닫거나 노드에서 한 수준 위의 부모 항목으로 옮깁니다.
Connections에서는 결합 인터페이스가 없음을 알리고 애플리케이션 선택으로 연결합니다.
예전 입력 파일이 여는 개념 미리보기는 더 넓은 설정 트리를 유지하며 아무것도 실행하지 않습니다. Heated silicon waveguide는 따로 실행할 수 있는 모델입니다.

## 광학 작업 흐름 안내

Geometry, Materials, Mesh, Study, Results 단계 막대는 현재 입력을 기준으로
잘못된 입력, 실행 불가, 대기 작업, 이전 입력의 메시/결과를 구분합니다.
메시 미리보기는 선택 사항이며 Run은 자체 메시를 생성합니다. Ready to run은
입력/연결 상태이고 수치 검증이나 수렴 인증이 아닙니다. Run complete는 보관 결과 중 하나가
현재 입력과 정확히 같다는 뜻입니다. Results는 현재 입력과
일치하는 보관 결과가 있으면 가장 최근 것을 엽니다. 단계 이동은 솔버를 실행하지
않고 이전 결과도 유지합니다. Results 단계는 Results 화면에서만 강조되고 Compare에서는
강조되지 않습니다. 보고 있는 실행의 입력이 현재 입력과 다르면 Results 단계는 *Current inputs differ from this run*을
일반 글자색으로 보여 줍니다: 문제가 아니라 정보입니다. 하단 Study sequence 줄은 일반 텍스트이며, 노드 선택은 단계 막대와 모델 트리로 합니다.

접속 상세, 입력 복구, 레이아웃 도움말은 펼칠 수 있는 패널에 모았습니다.
접속 실패 시 패널이 자동으로 열립니다. 숫자 오류 설명은 입력 필드 이름과 분리했고,
단계 상태가 갱신되어도 키보드 포커스를 유지합니다. 이 단계 안내는 광학 애플리케이션에
표시됩니다.

## 제출 문서 점검과 내보내기

Study → Check inputs는 공개 문서 검증 API를 호출하며 메시 생성이나 계산을
시작하지 않습니다. 보고서는 입력 스냅샷과 서버 식별자를 보존하며, 입력 변경 또는
다른 서버 연결 후에는 이전 근거로 표시합니다. 보고서는 이전의 자유 문장 notes 대신 서버가 돌려준
코드 있는 진단(심각도·코드·경로·메시지: 오류·경고·안내)을 모두 보여 줍니다. 통신 실패 시 이전 보고서와 새 오류를
함께 유지합니다. 문서 수용은 재료 정확도·메시 수렴·솔버 정확도 인증이 아니며,
Run은 별도로 캡처한 문서를 다시 검증합니다.

Export solver JSON은 실제 simcase `openphysics: "0.3"` 입력(기하는 nm `length_unit`, 다른 길이는
양 문자열)을 내보냅니다. simcase Python/CLI API로 읽을 수 있고, workspace 프로젝트/세션
형식이나 계산 결과는 아닙니다. 펼칠 수 있는 문서에도 같은 내용이 보이며, 잘못된
편집 입력이 있으면 마지막 유효 입력을 표시하고 내보내기를 차단합니다.

서버는 이 요청을 원시 바이트로 읽습니다. 숫자는 쓴 자릿수를 유지하고, 중복 키·`NaN`·`Infinity`·
UTF-8이 아닌 텍스트·짝 없는 서러게이트 이스케이프가 든 문자열은 코드와 함께 거부합니다.
workspace의 validate, mesh, run 요청에는 연결한 서버 식별자가 포함됩니다.
재시작되거나 교체된 서버는 모델 해석/작업 시작 전에 오래된 요청을 거부하며, 기존 작업은
다른 서버 프로세스로 이동하지 않습니다. Run이 재시작된 서버를 만나면 페이지가 곧바로 새 서버에
다시 연결하고 Run을 다시 누르라고 안내합니다. 입력과 보관한 결과는 그대로입니다. 서버에 아예
연결할 수 없으면 그 이유와 함께 Run이 꺼지고, 페이지가 3초마다 다시 확인하다가 같은 주소로
Studio를 다시 켜면 저절로 다시 연결합니다. **Check connection**으로 언제든 다시 시도할 수
있습니다. 식별자 query가 없는 기존 클라이언트 API는 유지됩니다.

## 단면 그래프

Results와 Compare의 Line profile and CSV를 펼쳐 가로(y 고정) 또는 세로(x 고정)
단면을 선택하고 고정 좌표를 nm로 입력한 뒤 Show profile을 누릅니다. 비교하는 두
실행은 같은 선과 0–1 상대 척도를 사용하되 각 모드의 max|E| 정규화 분모는 유지합니다.
모드/성분을 바꾸면 그래프도 갱신합니다. 단면 설정은 뷰 상태이며 세션과 브라우저 노트북 복구에
저장합니다.

각 계단 구간은 해당 삼각형에 저장된 중심 값을 표시합니다. 장 보간·평활화·절대
광파워 추정은 수행하지 않으며, Compare에서는 *Matched modes*에서 고른 쌍을 보여 줍니다. 공유/겹친 경계는 마지막으로 그린 삼각형을
따르며 메시가 없는 구간은 연결하지 않습니다. CSV(`studio-profile.csv`)에는 작업·출처·후보·성분·
축, 고정 좌표, 구간 시작/끝, 삼각형 번호, 중심 좌표, 정규화 값을 기록하며, 모든 양의 열은
`name [unit]` 머리글과 SI 값입니다(`fixed_coordinate [m]`, `start [m]`, `end [m]`,
`centroid_x [m]`, `centroid_y [m]`, `relative_amplitude [1]`). 패널의 입력과 표시는 나노미터입니다. 구간 끝점 한 점의 값에 대해
별도 point probe와 같다고 주장하지 않습니다.

정사각형의 정확한 가로/세로 구간, 역방향 삼각형, 중첩, 빈 영역 기준을 시험했습니다.
실제 비교 CSV 구간은 복소 벡터 norm과 삼각형 내부 좌표를 독립 검산했습니다.

## 노트북 자동 복구

탭에 계산 또는 가져온 결과가 생기면 유효 입력·선택·이름 변경을 브라우저
IndexedDB에 보관합니다. 현재 입력, 최대 여섯 완료 실행, 이름, 비교 및 장 보기
설정을 포함합니다. 연속 변경은 묶고 저장은 순서대로 수행하며, 세션 파일에 실행이 없는 동안 저장 표시는
브라우저 사본의 상태(*updating browser recovery*, *kept for recovery in this browser*,
*browser recovery unavailable*)를, 세션 파일이 생기면 그 파일을 보여 줍니다. round 17부터 복구를 할 수 없으면
까닭을 알 때 까닭과 할 일을 밝힙니다: 고른 실행과 고정한 실행이 장과 함께 16 MiB를 넘으면(열린 실행이 물리 창만 보존하기 전에는 기판 위 스트립의
고정한 열린 실행 둘이 각각 13.4 MB로 넘었습니다. 지금 그런 실행은 3.9 MB입니다) *browser recovery unavailable: session over 16 MiB · File › Save keeps your work*,
브라우저가 공간 부족으로 쓰기를 거부하면 *browser recovery unavailable: this browser’s storage is full · File ›
Save keeps your work*입니다. round 18부터 Messages도 복구가 꺼질 때마다 한 번 알립니다: *Browser recovery is off: this
session is over 16 MiB. File › Save keeps your work.* 또는 *Browser recovery is off: this browser’s storage is full.
File › Save keeps your work.*(실행 결과 메시지가 있으면 같은 줄 뒤에). 빈 새 탭은 기존 노트북을
지우지 않습니다.

새로고침 후 모델 카드(Optical waveguide 또는 Heated silicon waveguide 아래 **Restore from this browser**),
시작 화면의 **Continue where you left off** 카드(저장된 모든 세션, 최신순), 또는 Workspace tools →
**Restore last session from this browser**로 마지막 세션을 복원합니다. 전체 기록을 검증한 후 기존 교체 확인창을 표시하며, 결과는 새 계산이
아닌 `recovered`로 표기합니다. 입력 Undo 이력은 새로 시작하고 파일/세션을 저장할
때까지 미저장 상태를 유지합니다. 솔버는 실행하지 않습니다. 입력만 복구하는 기능과
대기 작업 복구는 별도입니다.

복구하지 않고 새 작업을 시작해도 저장된 세션은 버리지 않습니다. 페이지를 연 뒤 첫 자동
저장이 저장돼 있던 세션을 이전 세션 목록으로 옮깁니다(최신순, 최대 세 개). 이 저장은 보기, 고른 실행,
Compare 선택과 실행의 출처를 빼고 비교해 세션을 한 번만 둡니다(이전에는 세션 파일을 열거나 복구하면 모든
실행의 출처가 바뀌어, 새 페이지의 첫 저장이 같은 실행의 저장된 사본을 또 하나의 이전 세션으로 남겼습니다). 쓰는 세션이 저장된 세션과 같으면(같은 파일을 다시 열었을 때) 저장된
기록을 옮기지 않고 바꾸며, 둘 중 어느 것의 이전 사본(탭이 다른 모델로 갔다 돌아온 뒤 바뀌지 않은
모델을 다시 저장할 때)도 지웁니다. 남은 사본은 목록이 숨깁니다. 브라우저 복구는 목록을 위해 노트북을 연 세션 파일의 이름도 보관합니다. **Restore earlier
session from this browser**가 각 세션의 모델, 실행 수, 실행 이름과 시각을 보여 주고, 같은 교체 확인창을 거쳐 복구합니다. 이전
세션을 복구하면 다음 저장 때 지금 세션이 이전 세션으로 남습니다.

[세션 버전 12](#광학-세션-파일버전-12)부터 두 모델의 기록은 탭의 프로젝트에 이름이 있으면 그 이름도 브라우저 전용
선택 키 `project: {name, from}`으로 담습니다(`name`은 프로젝트 이름 규칙을 따르고, `from`은 파일 이름에서 온 이름이면
`file`, Rename으로 정한 이름이면 `user`). 이름 없는 프로젝트에는 쓰지 않고, 잘못된 값은 무시하며, 기록은 버전 1
그대로입니다(이전 Studio는 이 키를 무시). 복원은 기록이 프로젝트 파일(`savedFile.projectName`, 둘 다 있으면 이쪽이
우선)을 밝히지 않을 때 이를 씁니다: 프로젝트는 프로젝트 파일 없이 그 이름을 받으므로 File › Save는 그 이름의 파일
(`both-models.json`)을 제안하고 묻습니다. 다음 변경까지 헤더는 파일 없이 연 기록이면 *both-models · recovered from this
browser · not saved to a file · kept for recovery in this browser*, 연 프로젝트 파일과 더는 같지 않은 기록이면 *both-models ·
recovered from this browser · changed since both-models.json, not saved · kept for recovery in this browser*(round 23, E5, HQ
결정 2026-11-24-openphysics-studio-round23-choices: 전에는 여기서도 파일이 없었던 것처럼 *not saved to a file*였음)이고,
기록이 연 프로젝트 파일과 아직 같았으면 *both-models · recovered
from this browser · as opened from both-models.json · kept for recovery in this browser*입니다. 프로젝트 파일을 밝힌
기록은 전과 같고(*… · both-models.json · saved …*), 이름 없는 이전 기록도 전과 같습니다(*Untitled project · …*).
다음 변경 뒤에도 파일에서 온 기록(같았든 아니든)의 프로젝트는 모든 복구 상태에서 그 파일을 밝힙니다: *both-models ·
changed since both-models.json, not saved · updating browser recovery*, *… · kept for recovery in this browser*,
*… · kept for recovery in this browser without the fields of Run 6*(round 24, B2: 전에는 상태 표시줄의 *Changed since
session file both-models.json* 옆에서 *not saved to a file*였음). 파일 없이 연 기록은 보통 헤더이고(*both-models · not
saved to a file · …*), 자기 프로젝트 파일이 있는 프로젝트는 그 말을 씁니다(*… · both-models.json · changed since opened ·
…*). 두 기록의 프로젝트 이름이 다른 쌍 복원은
추가 메시지 없이 더 새 기록의 이름을 씁니다.

최신 스냅샷은 같은 브라우저 origin의 한 건이며 탭 간 공유됩니다. 저장할 때 같은 데이터베이스
트랜잭션 안에서 이전에 읽은 revision을 확인합니다. 이 탭을 열거나 복구한 뒤 다른
탭이 저장했다면 해당 기록을 덮지 않고 자동 저장을 중단합니다. Save session으로
현재 탭을 파일에 보관한 뒤 Restore last session from this browser로 최신 노트북을 검토·복구하세요.
검토 취소나 Retry recovery storage로 이 보호를 우회하지 않습니다.

현재 탭의 노트북을 유지하려면 **Use current notebook for recovery**를 선택하고
기존 복구본과 현재 결과 수를 검토한 뒤 명시적으로 교체하세요. 현재 입력·결과·Undo는
그대로 유지하며 가져오기나 계산을 하지 않습니다. 읽을 수 없는 복구 기록도 교체할 수
있습니다. 양쪽 노트북을 보존하려면 먼저 Save session으로 파일을 저장하세요. 검토 중
작업공간 변경·저장 진행·다른 탭의 새 저장이 발생하면 교체하지 않고 재검토를 요구합니다.
용량/데이터베이스 오류는 이 기능으로 해결되지 않으므로 파일에 보관하세요. 빈 노트북으로
완료된 복구본을 교체할 수 없습니다.

Studio 업데이트
후 이전 버전 탭은 새로고침하세요. 이전 실행 코드는 공유 기록을 덮을 수 있습니다.
백업 보관함은 아니며 용량/트랜잭션 실패 시 이전 완료 기록을
유지하며 Retry recovery storage로 최신 요청 상태를 재시도합니다. 대기/저장 중에
탭을 닫으면 최근 변경을 잃을 수 있습니다. 브라우저 데이터 삭제·비공개 모드·다른
포트에서는 복구할 수 없을 수 있으므로 Save session / Export this run으로 파일을
보관하세요. 세션 16 MiB/결과 여섯 개 한도를 유지하며 잘못된 입력 초안, Undo 이력,
메시와 사전 점검 보고서는 포함하지 않습니다. probe·단면 위치는 포함합니다.


복구 업데이트를 예약할 때 입력·실행 메타데이터·선택·보기 상태를 캡처합니다. 이후
모델을 편집하거나 빈 세션을 열어도 이미 예약한 스냅샷의 내용은 바뀌지 않습니다.
큰 결과 배열은 읽기 전용으로 유지하고 지연 시간 뒤 직렬화하므로 입력할 때마다
장 배열 전체를 복사하지 않습니다.

## 기준 실행 고정

실행에 이름을 붙이면 고정되어 새 실행이 교체하지 않습니다. 별도의 Pin 버튼은 없으며 **Unpin this run**으로
해제하고, Run name에서 Enter를 누르면 이름 붙은 실행을 다시 고정합니다. 새 결과는
고정하지 않은 가장 오래된 실행을 교체하며 총 여섯 개 한도는 유지합니다. 여섯 개
모두 고정하면 하나를 해제할 때까지 Run을 차단하되 문서 점검과 메시 미리보기는
허용합니다. 고정 상태는 세션·브라우저 복구·실행 표 CSV에 저장하며 입력·장·입력 Undo
이력을 바꾸지 않습니다. 같은 작업을 재조회해도 기존 이름과 고정 상태를 유지합니다.
보관 실패 시 이전 노트북과 선택 결과는 그대로 유지합니다. 고정은 파일 백업이
아니므로 브라우저 데이터를 지우기 전에 파일로 내보내세요.

## 모델을 교체하지 않고 실행 가져오기

Results/Compare → **Add runs from file (inputs unchanged)**에서 세션 파일 또는 **Export this run**으로 내보낸 개별 실행 파일을 읽습니다.
추가·일치·교체될 비고정 실행 수를 검토한 뒤 적용합니다. 추가한 실행은 파일 순서대로 탭의 가장 큰 실행 번호 다음부터
번호를 받고, 번호가 바뀌면 메시지가 밝히며(*Added Run 2 and Run 4 of design-b.json as Run 9 and Run 10.*), 이미 탭에
있는 작업은 탭의 번호를 유지합니다([버전 12](#광학-세션-파일버전-12)). 현재 모델 입력과 입력 Undo는
보존하고 가져온 선택 결과를 보관 결과와 비교합니다. 새 결과는 `imported`로 표시합니다.
입력과 노트북을 모두 교체하려면 Open session을 사용합니다.

작업 ID가 같은 경우 입력·설정·유효 굴절률·장 배열·서버 버전이 일치해야 기존 이름,
고정 상태, 출처를 유지하며 재사용합니다. 내용이 충돌하면 전체 가져오기를 거부합니다.
가져오는 실행과 고정 기준 결과를 여섯 개 한도에 맞추려고 조용히 버리지 않습니다.
한도를 넘으면 기준 고정을 해제하거나 개별 실행 파일(**Export this run**)을 내보내 가져오세요. 검토 후에는
현재 노트북의 오래된 비고정 실행이 교체될 수 있습니다. 대기 작업이 있으면 실행
가져오기를 차단합니다.

선택 화면이 갱신되어도 트리·형상·재료·실행 조작의 키보드 포커스를 유지합니다.
확인 대화상자가 열려 있으면 입력 Undo/Redo 단축키가 뒤의 모델을 변경하지 않습니다.
광학 PEC 경계를 선택하면 해당 경계 이름을 광학 인터페이스 속성 위에 유지합니다.

단면 패널을 열면 해당 선이 현재 보기 범위 안에 있을 때 각 장 그림에 주황 점선으로
표시합니다. 장 그림이 코어 주변 보기여도 단면 그래프는 전체 계산 영역을 사용합니다.
Export profile PNG에는 축·정규화·모드·단면 위치·작업 ID·형상·재료·출처를 포함하며,
장 PNG에도 활성 단면 위치를 표기합니다. 비교 실행 제목이 여러 줄로 바뀌어도 두
그림의 좌표 행을 나란히 유지합니다.

세션 뷰 메타데이터에 probe 좌표/표시 여부와 단면 방향/고정 좌표/펼침 상태도
보존합니다. 좌표는 `"0.15 um"` 같은 양 문자열이며 단위 없는 숫자는 거부합니다.
이 설정은 모델 수정 번호를 바꾸거나 솔버를 실행하지 않습니다.
해당 선택 필드가 없는 세션은 (0, 0.15) µm의 숨긴 probe와 y=0.15 µm의
접힌 가로 단면을 기본으로 복원합니다. 잘못되거나 영역 밖인 저장 뷰 값은 현재
입력·결과를 변경하기 전에 가져오기 전체를 거부합니다.


파일·세션·브라우저 복구 읽기는 하나의 최신 요청을 공유합니다. 새 선택이나 취소는
이전의 대기 중 읽기와 뒤늦은 오류를 무효화합니다. 읽는 동안 입력·보기·실행 이력·작업
상태가 바뀌면 소스를 다시 선택하세요. 교체 확인창에는 소스·이전/새 치수·코어 재료·
결과 수·Undo 동작을 표시합니다. 확인 시 작업공간 상태를 다시 검사하므로 검토 중
계산이 완료돼도 오래된 확인창으로 새 결과를 조용히 버리지 않습니다.
Add runs from file은 계속 현재 모델 입력을 유지합니다.

## 설치된 물리

상태줄의 Workspace tools 옆에 있고 리본의 **Physics → Installed**로도 여는(Escape로 닫음)
**Installed physics**(설치된 물리)는 Studio와 함께 설치된
물리 공급자([물리 공급자](providers.md))를 나열합니다. 각 공급자의 이름·버전·배포판·상태·
물리 종류를 보여 주며 내장 공급자(`openphysics-fem`, 배포판 `simcase`)가 맨 앞에 옵니다.
불러오지 못한 공급자는 *Unavailable*(사용 불가)로 표시하고, 그 오류를
`simcase.providers.providers()`가 보고한 그대로 보여 줍니다(예:
`ImportError: No module named 'my_physics'`). 다른 공급자와 내장 물리는 계속 동작합니다.
목록은 패널을 열 때 `GET /api/providers`에서 읽습니다.

목록은 데이터일 뿐입니다. 공급자가 준 문자열은 모두 텍스트로 표시하며(2000자보다
긴 문자열은 표시할 때 자릅니다), 페이지는 공급자의 코드(JavaScript나 HTML)를 절대
불러오지 않습니다. 이 경로는 위 항목과 종류 이름만 보내고, 그 밖의 manifest 내용과
entry point 대상은 보내지 않습니다. 오류 텍스트는 `providers()`가 보고한 그대로
보내므로 가져오기에 실패한 모듈 같은 파일 이름이 들어 있을 수 있습니다. Studio는
기본적으로 이 컴퓨터에만 제공됩니다([패키지 개요](overview.md) 참고). 목록 자체를 읽지
못하면 패널에 그렇게 표시하고 자세한 내용은 서버 로그에 남깁니다.
이 패널은 작업공간 capability 계약을 바꾸지 않습니다(지금은 모드 1–8개 실행 때문에
`/api/workspace/capabilities/v8`).
설치된 공급자를 아직 작업공간의 물리로 제공하지는 않으며, 이 목록은 설치 상태만 보여 줍니다.

검사: `tests/simcase/test_studio_providers.py`(내장 공급자만, 주입한 공급자, 사용 불가
공급자, 목록 실패, 빈·긴·악의적 문자열이 든 경로 출력을 배포된 페이지 모듈이 읽는지)와 `tests/simcase/studio_workspace_providers.cjs`(이스케이프와 응답 계약).
