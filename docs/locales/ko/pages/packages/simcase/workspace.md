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

작업대는 상단 명령 리본, 왼쪽 모델 트리와 인접한 Settings, 오른쪽의 넓은
Graphics, 하단 Study/Messages 영역으로 구성됩니다. 리본은 Project, Edit,
Model setup, Physics, Compute로 묶습니다. **Geometry**, **Materials**, **Mesh**, **Study**는
모델 트리와 같은 설정을 엽니다. **Physics → Installed**는 [설치된 물리](#설치된-물리)를 엽니다.
Compute에는 고른 애플리케이션의 실행 명령(**Run optical study**, **Run heat study**,
**Run Joule heating study**)이 있습니다. 광학 작업 순서는 모델을 가리지 않는 별도 줄에 표시합니다.
하단 영역은 해석 순서와 Messages를 보여 주며, Joule 가열을 실행한 뒤 Results에서는
**Solver log**가 함께 나옵니다.

**Save session**과 **Open session**은 완료된 광학 실행과 비교를 포함한 세션 전체, 또는 실행을 포함한
다중물리 모델을 저장하고 엽니다. 리본, 헤더, Messages 모두 이 저장을 모든 모델(광학, 열, Joule 가열,
다중물리)에서 "Save session" 한 이름으로 부릅니다. **More**에
입력 전용 파일(**More › Save inputs only**, **Open inputs file**), 브라우저 초안, Reset design이 있습니다. 하단 상태줄의
**Workspace tools**에서 연결, 복구, Reset layout에 접근하고, 그 옆에 **Installed physics**가 있습니다.
둘 다 상태줄 위로 열리며 한 번에 하나만 열리고, Escape로 열린 것을 닫습니다. Models를
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

## 첫 광학 해석

1. **Models → Optical waveguide**를 선택합니다(시작 화면이며 탭 이름은 **Models**). (Heated silicon waveguide 카드는
   대신 열과 광을 결합한 모델을 엽니다. [다중물리 모델](#다중물리-모델-열--광-모드)을 보십시오.)
2. **Geometry**에서 코어를 숫자로 편집하거나 코어·가장자리를 드래그합니다.
   슬랩·슬롯·클래딩·구멍은 사각형·원·다각형을 추가해 만들고 형상마다 재료를 고릅니다.
   실리카 배경은 유지됩니다. 사각형의 **Width**를 바꾸면 가로 중심이 유지되고(Left x가
   변화량의 절반만큼 움직임) **Height**를 바꾸면 아래 변이 유지되므로, y = 0에 놓인 코어는
   그 자리에서 가운데를 지킵니다. 계산창을 벗어나는 크기는 기존 규칙대로 거부됩니다. 이전에
   저장한 프로젝트는 저장된 좌표를 그대로 씁니다. 단계 표시줄의 **4. Study**에는 *Ready to run*이,
   현재 입력의 결과가 생기면 *Run complete*가 나오고, 옆의 파장(예: **λ 1550 nm**)은 파장 입력란을
   여는 버튼입니다. 필요하면 **Physics › Optical modes**에서 파장을(설정 제목도 *Optical modes*이며,
   **Study → Edit wavelength**, 파장도 함께 보여 주는 Study 실행 설정의 **Edit in Optical modes**,
   단계 표시줄의 파장이 그 입력란 하나에 포커스를 둔 채 엽니다), **Mesh**에서
   코어 메시 크기를 바꿉니다.
3. 필요하면 **Mesh**를 생성하고 **Study → Check inputs**로 문서를 점검합니다.
   두 동작은 광학 장을 계산하지 않습니다. 필요 시 솔버 JSON도 확인·내보내기 합니다.
4. **Run optical study**를 누릅니다. 기다리는 동안 모델을 바꿔도 결과는 실행 당시
   입력을 유지합니다. Stop waiting은 상태 조회만 중단합니다. 입력을 바꾸면 완료 메시지가
   바뀌므로, 완료 메시지가 바뀐 입력을 설명하는 일은 없습니다. 도크 제목과 상태 표시줄은 같은
   실행을 가리킵니다: 실행 뒤에는 *Run 1 · solved from the current inputs*(상태 표시줄은
   *press Run to solve again*을 덧붙임), 편집 뒤에는 *Inputs changed since run 1 · press Run to
   update*, 실행 전에는 *Nothing is computed until you press Run*과 *Optical adapter ready ·
   explicit Run required*입니다. 실행 번호는 실행 목록에서의 자리이며 가장 오래된 것이 1입니다.
   이 탭이 계산하지 않은 현재 실행은 그 출처를 밝힙니다: Open session 뒤에는 *Run 2 · read from
   file, not recomputed*, 복구 뒤에는 *Run 2 · recovered from this browser, not recomputed*이며
   상태 표시줄은 *press Run to compute it here*를 덧붙입니다. 실행 목록 항목의 시각은 초까지 나옵니다.
   입력 오류, 진행 중인 계산이나 작업, 지원하지 않는 입력처럼 Run을 막는 것이 있으면 도크 제목은
   상태 표시줄의 문구를 그대로 씁니다.
5. **Run name**을 입력하고 Enter를 누릅니다. 이름을 붙인 실행은 고정되어 새 실행이 교체하지
   않습니다. 별도의 Pin 버튼은 없으며, **Unpin this run**으로 해제하고 Run name에서 Enter를 누르면 이름 붙은
   실행을 다시 고정합니다. 모델을 변경해
   다시 실행한 뒤 **Compare**에서 A/B, 후보, 성분, probe와 단면을 선택합니다.
   두 장(field) 그림이 먼저 나오고, 제목은 쪽과 실행으로 이루어집니다(A 쪽의 *A*라는 이름의 실행은
   이름을 두 번 쓰지 않음). 그 아래 표에는 후보 순위마다 A와 B의 n_eff, Δ (B − A), A 대비 Δ %가
   나오고, 열 머리글에 각 실행(이름, 크기, λ)이 표시됩니다. n_eff는 어디서나(결과, 후보 목록,
   Compare) 소수 8자리입니다.
6. 첫 번째 저장 버튼인 **Save session**으로 모델·보관 결과·보기 설정의 파일을 저장합니다.
   파일 이름은 응용과 현지 날짜·시각으로 정해지며(예:
   `optical-waveguide-session-2026-11-21-1305.json`) 브라우저 다운로드로 넘어갑니다. Studio는
   파일을 브라우저에 넘길 뿐 실제로 보관됐는지 알 수 없으므로(다운로드는 취소될 수 있음)
   Messages에 *Session file … sent to the browser's downloads (check your Downloads folder)*가
   나옵니다. 저장 표시는 헤더에 하나만 있고 하단(footer)은 같은 문구를 그대로 보여 줍니다. 다음 편집이나
   실행 전까지 *Session file … sent to your browser's Downloads · 시각*이 표시되며, 파일이 저장됐다고는
   하지 않습니다. **More › Save inputs only**는 결과 없이
   모델만 저장합니다. 완료한 실행이 세션 파일에 없으면 *Not saved to a file · kept for recovery in
   this browser*(기록 중에는 *· updating browser recovery*, 쓸 수 없으면 *· browser recovery
   unavailable*), 세션 파일 저장 뒤 바뀌었으면 *Changed since session file … (시각) · kept for
   recovery in this browser*가 표시됩니다. **Open session** 뒤에는 헤더에 파일 이름과 함께 *Opened …*가, 복구
   뒤에는 *Recovered from this browser*가 나옵니다. 브라우저 복구는 마지막 세션 파일 이름과
   시각을 함께 보관하므로 복구한 세션에는 그 파일을 지난 기록으로 *Recovered from this browser (last saved
   to a file: … at 13:05)*처럼 덧붙입니다(저장 뒤 바뀐 작업이면 *…; changed since)*, 저장한 적이 없으면
   *· not saved to a file*).
   둘 다 다음 변경이나 다른 파일 열기까지 유지됩니다. 헤더에는 revision 번호가 없습니다. Width를 홀수 nm만큼 바꾸면 Left x가
   0.5 nm 단위가 됩니다. 중심은 정확히 유지되고 Messages가 Left x가 옮겨진 곳을 알려 주며(*Width set
   to 600 nm. Left x moved to −300 nm to keep the centre.*), 입력한 값은 드래그 간격에 맞춰지지 않습니다(크기
   입력란 아래 **More about width and height**). 로컬 복구를 사용하려면 *kept for recovery in this
   browser*를 확인합니다(마지막 갱신 시각은 **Workspace tools**에 나옴). 새로고침하거나 Studio를 다시
   켜면 시작 화면의 **Continue where you left off** 카드에 **Recover (this browser only): Last
   session in this browser …**와 이전 세션, **Open session file (portable)…**, **Start new**가 나오고,
   세션 파일은 컴퓨터 사이를 옮길 수 있는 사본이며 브라우저 복구는 이 브라우저에만 남는다고 알려 줍니다.
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
   광학 실행이 있는 채로 가열 모델을 열면 Messages가 그 실행이 남는 곳(이 탭, 그리고 그것을 가진
   브라우저 복구나 세션 파일)과 **Models › Optical waveguide**로 되돌아갈 수 있음을 알려 줍니다.
   복구 항목은 모두 모델, 실행 수, 실행 이름(이름이 없으면 *Run N*)을 보여 줍니다. 예:
   *Optical waveguide · 2 runs · design A, Run 2*. 시작 화면은 한 단어, model을 씁니다: **Models** 탭, *Choose a starting model*,
   *Model library · Choose a model*.

현재 모델을 유지하고 결과만 추가하려면 **Add runs from file (inputs unchanged)**을, 모델과 노트북을
모두 교체하려면 **Open session**을 사용합니다. *Result for these inputs*와 *Inputs changed
since this result* 표시는 결과의
설계 출처를 나타내며, 서로 다른 설계의 후보 번호는 동일 모드를 보장하지 않습니다.

## 모델 편집

애플리케이션을 고르고 모델 트리나 그림에서 물체·경계를 선택한 뒤 속성을
편집합니다. 광학 애플리케이션은 실제 2D 모드 계산을 실행합니다.
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
[-1.5, 1.5, -1.2, 1.2] µm, PEC 경계, 후보 두 개는 고정됩니다. 결과마다 사용한
형상·파장·코어 메시를 표시합니다.

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

**Models → Steady heat conduction**을 고르면 JSON 없이 정상 열전도 문제를 편집합니다.
판은 왼쪽 아래 모서리가 (0, 0)인 균질 직사각형 하나이며 크기는 mm, 열전도도 k [W/(m·K)]와
균일 열원 Q [W/m³]는 상수입니다. 그림에서 변을 선택하거나 **Heat transfer**를 열어 변마다
조건 하나를 줍니다. 단열(열유속 0), 고정 온도 [K], 안쪽 방향 열유속 [W/m²](양수는 판 안으로
들어옴, 문서의 `inward_heat_flux`), h [W/(m²·K)]와 주위 온도 [K]의 대류 중에서 고릅니다. **Mesh**는 x·y 방향 구조 분할 수를
정하고 노드·삼각형 수를 이 서버의 한도와 함께 보여 줍니다.

온도 수준이 정해지고(어느 변에 고정 온도나 h > 0인 대류), 이웃한 고정 온도 변이 모서리에서
같고, 메시가 서버 한도 안이면 실행할 수 있으며 그렇지 않으면 이유를 표시합니다. 잘못된 값은
강조된 초안으로 남아 고치거나 되돌리기 전까지 실행·저장을 막습니다. **Run heat study**는
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

**Models → Joule heating**을 고르면 JSON 없이 이름 붙은 재료 영역의 정상 Joule 가열을
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
**Run Joule heating study**는 문서(**Study**에 표시)를 만들어 Studio의
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

**Models → Heated silicon waveguide**(“Heat → optical modes · coupled”)를 고르면
[다중물리 문서](multiphysics_document.md)가 열립니다. 한 형상, 한 메시 위의 두 물리를 결합 하나로
잇고 **Run** 한 번으로 풉니다. 템플릿은 6 × 4.5 µm 창 안의 `physmat:SiO2` 위에 놓인
500 × 220 nm `physmat:Si` 코어와, 코어 1.1 µm 위의 2 µm × 100 nm 히터입니다. **Heat 1**은 아래
변을 300 K로 두고 히터 영역을 가열하며, **Modes 1**은 1550 nm 광 모드를 찾습니다. 결합
**Heat 1 temperature → Modes 1 temperature**는 삼각형마다 세 절점 온도의 평균을 넘기고, 광 계산은
그곳에서 n = n₀ + (dn/dT)(T − T_ref)를 씁니다. 히터는 손실 없는 임시 굴절률을 가진 로컬
기록이며, 금속 손실은 이후 작업입니다.

작업 공간은 문서 자체를 편집하므로 양식이 없는 키도 그대로 둡니다. **More › Open inputs file**(또는
**Open session**)로 배포된 [가열 슬랩 예제](../../../../../../examples/simcase/multiphysics_heated_slab.json) 같은
다중물리 문서를 열 수 있습니다.

- **모델 트리.** 컴포넌트 하나(Geometry 1, 쓰인 재료마다 항목 하나인 Materials, 모든 물리가
  공유하는 Mesh 1), 풀이 순서의 자리를 표시한 배지를 단 물리(순환은 주황 번호 하나를 공유),
  결합마다 말로 이름 붙은 항목이 있는 **Couplings**, 도출된 풀이 순서와 반복 단계가 있는
  **Study 1**. Settings는 쉬운 이름을 보여 주고, 파일이 쓰는 이름(물리 type, “Name in file”, 형식 줄,
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
  예를 들어 *Modes 1 effective index (single numbers, not a map)*처럼 회색으로 나옵니다. 전달은 이번 릴리스의
  유일한 방식인 Same mesh입니다. 분명히 이을 수 있는 입력(Heat 1에서 받는 Modes 1 온도)이 있으면
  Messages가 결합을 제안하지만, 직접 추가하기 전에는 아무것도 결합되지 않습니다. 그동안 Modes 1은
  트리, Connections 노드, Settings, Messages에 경고를 답니다: “Temperature input has no source:
  uses n₀ at T_ref (300 K)”. 결합된 온도가 없으면 광 풀이는 굴절률을 바꾸지 않으므로 모든 재료가
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
- **Run**은 **Run optical study**와 같은 ▶와 함께 모든 물리를 풀이 순서대로 풉니다. ▶는 빈 대체
  텍스트를 가진 장식이라 화면 낭독기는 이름(“Run”, “Run optical study”)만 읽습니다. Study 도크는 물리나 반복 단계마다 상태(Waiting,
  Solving…, Done in 0.3 s, 마지막 변화와 함께 Iteration 7 of up to 30, Did not settle, Not run)를
  보여 주고, Connections도 열려 있는 동안 같은 상태를 보여 줍니다. **Stop run**은 엔진의 다음
  단계에서 실행을 멈춥니다. 풀고 있는 물리가 끝난 뒤, 반복 단계 안에서는 지금 반복이 끝난
  뒤입니다. 실패하거나 멈춘 실행은 부분 결과를 남기지 않습니다. Messages가 실패한 물리를
  밝히고, 앞선 완전한 실행은 그대로 남습니다. 스윕은 검사만 하고 실행하지 않습니다(실행 이유에
  적힙니다). 실행 뒤 편집하면 도크와 Connections의 행이 **Out of date (last run: Done in 0.3 s)**가
  되고, 도크 제목은 “Run 1 · the model changed since; press Run to update”, 하단은 “Model edited
  since run 1 · press Run to update”입니다. 실행이 현재 모델의 것인지는 내용으로 정하므로, 손으로
  되돌린 편집(결합을 지웠다가 다시 추가, 또는 Undo)은 다시 현재가 됩니다. 그때 Messages, 도크
  제목, 하단은 같은 문장 “Model matches run 1 again: its results are current. Run makes a new run with the
  same inputs”를 보여 주어 Run이 무엇을 하는지 밝힙니다. 세션 파일에서 읽었거나 이 브라우저에서
  복구한 실행에는 풀이 시간이 없습니다: 행은 **From file** 또는 **From this browser**(반복 단계는 *Settled in 7 iterations · from file*처럼
  반복 횟수를 유지), 도크 제목은
  “Run 1 · read from file, not recomputed”(또는 “recovered from this browser, not recomputed”)이고
  하단은 “press Run to compute it here”를 덧붙입니다. 탭에서 만든 실행은 위 문구를 그대로 씁니다.
- **Also solve without heater**(Run 옆, 약 1초)는 광 모드가 결합된 온도를 받는 모델을 열 때 켜져
  있습니다. 결합 실행 뒤 Studio가 같은 실행 경로로 광 모델을 온도 입력 없이 따로 풀어 히터 없는
  열을 채웁니다. 내용이 같은 열이 이미 있으면 건너뜁니다. 광 온도를 정하는 결합이 없는 동안에도
  이 옵션은 그 자리에 남아 꺼진 채 “needs a temperature coupling”이라고 이유를 밝힙니다.
  결합이 돌아오면(다시 추가, Undo 또는 Redo) 옵션은 고른 대로 돌아오고, Messages에
  “Also solve without heater” is ticked again이 덧붙습니다.
- **Results**는 물리마다 한 쪽과 **Coupling check**를 둡니다. 쓰인 풀이 순서와, 결합마다 보낸
  것(“1,726 node temperatures, 300.0–319.0 K”), 받은 것(“3,334 triangle means (mean of 3
  nodes)”), 검사 결과(“Passed · max |received − sent| = 0 K”)를 보여 줍니다. Heat 1은 온도 지도를,
  Modes 1은 답인 n_eff 표를 먼저 보여 주고, 그 아래에 결합 입력의 지도인 코어의 온도와 굴절률(또는
  서버가 문서 값으로 계산한 변화 n − n₀ = (dn/dT)(T − T_ref))을 보여 줍니다. n_eff 표의 행은
  *Candidate 1*, …이고, 표 아래 문장은 광 애플리케이션과 같은 주의 “Candidates are ranked by
  effective index and are not matched between designs.”와 모델이 요청한 모드 수 “This model asks
  for 1 mode: Modes 1 › Modes to find”(그 설정으로 가는 링크, 편집 뒤에는 “This run asked for …”)를 보여 줍니다.
  n_eff 표에는 “n_eff without heater”와 “Δn_eff (coupled − without heater)”가 부호와 n_eff와 같은
  소수 8자리로 나옵니다(템플릿은 +0.00215086). 표 아래 문장이 기준을 밝힙니다: “without heater =
  Modes 1 alone with no temperature input: every material keeps n₀, its index at T_ref = 300 K”.
  이 열은 따로 푼 광 모델(실행 문서에서 결합, 반복, 열광학 키를 뺀 것을 키 정렬로 비교)이 보이는
  실행의 것과 같을 때 유효합니다. 아니면 “(other model)”로 표시하고 Δn_eff를 비우며,
  **Run Modes 1 alone**으로 새로 풉니다. 결과는 자기 실행을 밝히며 모델을 고쳐도 바뀌지 않습니다.
- **실행.** 실행은 광학과 같은 규칙과 문구로 최대 여섯 개를 보관합니다. Results › Runs에
  “Run N · 이름 · 시각” 목록, **Run name**(Enter로 고정), **Unpin this run**이 있습니다. 고정한
  실행은 남고, 새 실행이 오면 고정하지 않은 가장 오래된 실행을 바꿉니다. 실행을 고르면 그 결과와
  최신 여부 줄이 보이며 모델은 바뀌지 않습니다. 여섯 개가 모두 고정되면 Run이 먼저 하나를 풀라고 합니다.
- **파일.** **Save session**은 모델과 실행, 실행 이름과 고정, 히터 없는 결과를 한 파일
  `<model-name>-session-YYYY-MM-DD-HHMM.json`에 씁니다(모델 이름을 소문자로, 다른 문자는 하이픈으로,
  최대 40자, 아니면 `multiphysics`). 형식은
  [다중물리 모델의 세션 파일](#다중물리-모델의-세션-파일버전-8)에 있습니다. **Open session**은 이런
  파일, 광학 세션, 또는 모델 파일 하나만도 엽니다(“Opened model file …: it holds the model but no
  runs.”). **More › Save inputs only**는 문서만 모델 파일로 쓰고, **More › Open inputs file**은 모델
  파일을 엽니다. 제목은 광학과 같은 문구를 씁니다: “Not saved to a file · kept for recovery in this
  browser”, “Session file … sent to your browser's Downloads · 10:15”, “Opened …”, “Recovered from
  this browser”. 세션 파일에 없는 실행을 가진 모델을 떠나기 전(다른 모델 카드, 템플릿 다시 열기,
  파일이나 입력 열기) Studio가 먼저 묻습니다: “Leave this model? 3 runs are only in this tab and in
  browser recovery. Save session first to keep them in a file.” 버튼은 **Cancel**, **Save session**,
  **Leave**입니다.
  세션 파일에 없는 광 실행이 있을 때 다중물리 모델을 열면 같은 방식으로 그 실행을 밝히고 **Save
  session, then continue**를 제안합니다. 그 실행은 탭에 남아 광 모델로 돌아오면 다시 보입니다.
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
  모델이며(어느 실행과도 다를 수 있음) Save inputs only가 쓰는 그대로 씁니다.
- `runs`는 완료 순서대로 최대 여섯 실행입니다. `job`은 서버의 작업 식별자(`mp-`와 16진수 12자리),
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
  계속 “Loaded from file, not recomputed. Studio checks the file for damage, not who made it.”으로
  표시합니다. 복구한 결과는 “Recovered from this browser, not recomputed.”입니다. 광학 세션 파일에는
  다이제스트가 없으므로 연 결과는 “Loaded from file, not recomputed. Studio checks that the file is
  well formed, not who made it.”으로 표시합니다.
- **크기.** 파일은 최대 16 MiB이며 읽기 전에 검사하고, 그 안의 문서는 각각 최대 1 MiB입니다. Save
  session은 파일이 맞으면 모든 실행을 맵과 함께 씁니다(템플릿 메시 실행 여섯 개는 약 2.5 MB). 맞지
  않으면 아무것도 쓰지 않고 크기를 밝혀 묻습니다: “Session is 22 MB; the limit is 16 MiB. Keep the
  maps of the selected and pinned runs only? …”. **Keep maps for selected and pinned runs**는 나머지를
  `"maps": "not kept"`로 쓰고, **Cancel**은 아무것도 쓰지 않습니다. 고른 실행과 고정한 실행만으로도
  한도를 넘으면 Save session은 거부하고 그 실행을 밝힙니다(“Run 3 alone is 18 MB, over the 16 MiB
  session limit. Unpin it or keep it in a smaller-mesh model.”). 맵을 말없이 버리지 않습니다.

**열기.** 결과는 다시 계산하지 않고 파일에서 읽습니다. 알림은 “Opened … Its results were read from the
file, not recomputed; input undo starts here.”이고, 실행에는 “from file”(또는 “recovered”)이 붙으며,
열기는 어떤 실행도 시작하지 않습니다. 모든 검사는 탭의 무엇이든 바꾸기 전에 돌고, 하나라도 실패하면
검사를 밝힌 메시지로 파일 전체를 거부하며 모델, 실행, 실행 취소는 그대로입니다:

- 크기와 JSON(맨 앞의 바이트 순서 표시는 지움), 실행 최대 여섯, 고유한 작업 식별자와 실행 번호, 올바른
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
  today's check: …”), Studio가 실행하는 문서인지, 그리고 지금 모델은 Open inputs file과 같이 읽음(그
  문제는 Messages에 나옴). 서버가 없으면 파일을 열지 않습니다.

8보다 큰 버전은 이름을 밝혀 거부합니다(“This session file is version 9, newer than this Studio reads
(versions 6–8). Open it in a newer Studio.”). 다른 `application`(“This session file holds a “…” model,
which this Studio does not read.”), 다른 결과(“Run 2 was saved as result “multiphysics-run-v2”, which
this Studio does not read.”), 다른 문서 봉투(서버 읽기기의 거부를 실행 이름과 함께)도 마찬가지입니다.
버전 6과 7 세션 파일은 이전처럼 열리고, 버전 1–5는 이전의 거부를 유지합니다. 버전 8 이전의 Studio는
버전 8 파일이나 복구 기록을 “Unsupported session format or run count.”로 거부하고 작업공간을
유지하므로, 다중물리 세션에는 이 Studio 이상이 필요합니다.

**브라우저 복구**는 다중물리 모델을 광학 세션과 같은 저장소에 같은 한도로 보관합니다(최신 하나와 이전
세 개, 각각 최대 16 MiB, 변경 0.7초 뒤 기록, 탭 사이 충돌 규칙). 모델에 실행이 있거나 연 뒤 편집했을
때부터 Save session이 쓸 버전 8 글로 기록합니다. 16 MiB를 넘으면 대화 상자 없이 고른 실행과 고정한
실행의 맵만 두고, 표시는 “kept for recovery in this browser without the maps of 2 runs · Save session to
keep them”입니다. 그래도 한도를 넘으면 새로 쓰지 않고(“browser recovery unavailable: session over 16
MiB”) 이전 기록이 남습니다. **Recover last session**과 **Recover earlier session · Heated silicon
waveguide · 3 runs · Run 1, Run 2, Run 3 · 시각**은 Open session과 같은 검사를 합니다.

모듈 검사는 `tests/simcase/studio_workspace_multiphysics_session.cjs`에 있습니다(버전 8 이전 Studio가
쓴 버전 6, 7 광학 파일이 `tests/simcase/studio_session_fixtures/`에 있고, 이전처럼 열리며 바이트
단위로 같게 쓰임). `tests/simcase/test_studio_multiphysics_session.py`는 Python hashlib과 자체 쓰기기로
다이제스트를 다시 계산합니다. 브라우저 검사는 템플릿, 0.12 µm 메시, 실행 두 개 세션을 저장·열기·다시
저장하고(두 번째 파일은 바이트 단위로 같고, 모든 배열은 서버 응답과 Float64로 같음), 0.08 µm 메시 실행
여섯 개로 16 MiB 한도, 거부, 브라우저 복구를 검사합니다. 버전 8에 없는 것: 광학과 다중물리 실행을 섞은
세션, 실행 사이의 메시 공유, 파일에서 실행 추가, 결합 실행의 모드 장.

## 결과와 파일

고정한 기준 실행을 유지하면서 성공한 실행 최대 여섯 개를 보관합니다. 후보의 장 분포를 보거나 두 실행을
비교할 수 있습니다. 후보 번호는 모드 추적 결과가 아닙니다. 장 색상은 후보마다
벡터 크기를 따로 정규화한 값이며, 광학 전력이나 공통 물리 색상 척도가 아닙니다.

입력 JSON은 설계를, 세션 JSON은 검증된 결과까지 저장합니다. 열기로 복원하며
입력 파일은 64 KiB, 세션은 16 MiB로 제한합니다. CSV·PNG 내보내기도 제공합니다.
작업공간 형식은 headless simcase JSON 문서와 다릅니다. 새로고침 후에는
Recover last session으로 완료된 브라우저 스냅샷을, Open session으로 파일을 명시적으로
복원합니다. 저장 대기 중인 변경은 백업이 아닙니다.

입력 파일은 버전 7입니다: 버전 6(단위·이름 일괄 변경)에 Joule 가열 입력(`model.joule`, 길이 mm,
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
모든 형상을 설명하는 `shapes` 열(페이지처럼 nm)·후보 번호에는 단위가 없습니다.

광학 세션 파일은 버전 7이며 입력은 버전 7 입력 파일입니다(버전 6 세션도 계속 읽고, 그 입력은 버전 6 입력
파일로 읽습니다. 다중물리 모델은 [버전 8](#다중물리-모델의-세션-파일버전-8)로 저장합니다). 버전 6은 단위·이름 일괄 변경 이후의 형식입니다. 작업공간은 형식 0.3 문서(`"1550 nm"` 같은
양 문자열의 길이, 정확한 `physmat:` 이름의 재료)를 만들고, 실행 기록마다 결과의
`effective_index`(exp(−iωt)의 Re와 Im)와 미터 단위 `node_coordinates`를 가진 장 표본을 보존합니다.
버전 1–5 세션은 이전 이름과 문서 길이 단위의 결과를 담고 있어, 다른 뜻으로 읽지 않도록 버전을
밝혀 메시지와 함께 거부합니다. 버전 6 세션의 입력은 버전 6 입력 파일과 같습니다. 설계를 다시 넣어
실행하고 새 세션을 저장하세요.

실행 전에 `/api/workspace/capabilities/v7`을 확인합니다. 계약 버전 7(버전 6과 내용이 같으며 버전 7
입력·세션 파일을 저장하는 작업공간용. 버전 6은 버전 5와 내용이 같으며 버전 6 파일과 문서 검사의 코드
있는 `diagnostics`용)과
`optical-shapes-v7` 어댑터는 nm 단위 계산창, 최대 형상 여덟 개·다각형 꼭짓점 열두 개,
형상 종류와 `physmat:` 이름을 가진 재료 열 가지, 파장 1400–1700 nm와 코어 메시 20–60 nm
범위(양 문자열), 고정된 계산창·경계·후보 조건(`mode_count`), `optical: true`, `coupled: false`,
`simcase_version`을 알립니다. 계약이 없거나 다르면 실행을 차단하며
**Check connection**으로 재시도합니다. 실행 시 보고된 simcase 패키지 버전을
실행 당시 형상·파장·코어 메시와 함께 기록하고 세션 JSON에도 보존합니다. 이전 capability
엔드포인트(`/api/workspace/capabilities`와 `/v2`–`/v6`)는 같은 경로와 schema 버전으로 유지합니다. 모든 어댑터가 이제 형식 0.3 문서를 쓰고
새 결과 이름을 읽으므로 각각 계열의 다음 어댑터 버전(`optical-fixed-v2`, `optical-rectangle-v4`와
`-v5`, `optical-shapes-v6`와 `-v7`)을 알리고 값은 양 문자열입니다. 전체 엔진 의존성이나 Git
이력을 나타내는 정보는 아닙니다.

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
**Recover recent inputs**로 교체 확인을 거쳐 복원하며 계산은 실행하지 않습니다.
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

작업 패널은 제출한 치수·재료, 작업 ID, 경과 시간, 결과 로딩 상태를 표시합니다.
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
연결을 해제하세요. 연결 해제도 서버 계산을 취소하지 않습니다. 3분 후 조회를
멈추며 다시 재개할 수 있습니다. 요청 실패는 기존 결과를 교체하지 않고 중단 후
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

후보·성분 변경 시 그림과 같은 벡터 정규화 기준으로 값을 갱신합니다.
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

광학 전용 트리는 Geometry, Materials, Optical modes, Mesh, Study를 표시합니다.
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
강조되지 않습니다. 하단 Study sequence 줄은 일반 텍스트이며, 노드 선택은 단계 막대와 모델 트리로 합니다.

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
실행은 같은 선과 0–1 상대 척도를 사용하되 각 후보의 max|E| 정규화 분모는 유지합니다.
후보/성분을 바꾸면 그래프도 갱신합니다. 단면 설정은 뷰 상태이며 세션과 브라우저 노트북 복구에
저장합니다.

각 계단 구간은 해당 삼각형에 저장된 중심 값을 표시합니다. 장 보간·평활화·절대
광파워 추정·모드 추적은 수행하지 않습니다. 공유/겹친 경계는 마지막으로 그린 삼각형을
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
*browser recovery unavailable*)를, 세션 파일이 생기면 그 파일을 보여 줍니다. 빈 새 탭은 기존 노트북을
지우지 않습니다.

새로고침 후 시작 화면의 **Continue where you left off** 카드에서 마지막 세션을 고르거나
Connection, recovery and layout help → Recover last session으로 복원합니다. 전체 기록을 검증한 후 기존 교체 확인창을 표시하며, 결과는 새 계산이
아닌 `recovered`로 표기합니다. 입력 Undo 이력은 새로 시작하고 파일/세션을 저장할
때까지 미저장 상태를 유지합니다. 솔버는 실행하지 않습니다. 입력만 복구하는 기능과
대기 작업 복구는 별도입니다.

복구하지 않고 새 작업을 시작해도 저장된 세션은 버리지 않습니다. 페이지를 연 뒤 첫 자동
저장이 저장돼 있던 세션을 이전 세션 목록으로 옮깁니다(최신순, 최대 세 개). **Recover earlier
session**이 각 세션의 모델, 실행 수, 실행 이름과 시각을 보여 주고, 같은 교체 확인창을 거쳐 복구합니다. 이전
세션을 복구하면 다음 저장 때 지금 세션이 이전 세션으로 남습니다.

최신 스냅샷은 같은 브라우저 origin의 한 건이며 탭 간 공유됩니다. 저장할 때 같은 데이터베이스
트랜잭션 안에서 이전에 읽은 revision을 확인합니다. 이 탭을 열거나 복구한 뒤 다른
탭이 저장했다면 해당 기록을 덮지 않고 자동 저장을 중단합니다. Save session으로
현재 탭을 파일에 보관한 뒤 Recover last session으로 최신 노트북을 검토·복구하세요.
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
추가·일치·교체될 비고정 실행 수를 검토한 뒤 적용합니다. 현재 모델 입력과 입력 Undo는
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
Export profile PNG에는 축·정규화·후보·단면 위치·작업 ID·형상·재료·출처를 포함하며,
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
이 패널은 작업공간 capability 계약을 바꾸지 않습니다(지금은 Joule 가열 입력 때문에
`/api/workspace/capabilities/v7`).
설치된 공급자를 아직 작업공간의 물리로 제공하지는 않으며, 이 목록은 설치 상태만 보여 줍니다.

검사: `tests/simcase/test_studio_providers.py`(내장 공급자만, 주입한 공급자, 사용 불가
공급자, 목록 실패, 빈·긴·악의적 문자열이 든 경로 출력을 배포된 페이지 모듈이 읽는지)와 `tests/simcase/studio_workspace_providers.cjs`(이스케이프와 응답 계약).
