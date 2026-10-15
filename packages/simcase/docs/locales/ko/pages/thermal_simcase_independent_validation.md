# Headless 열전도 문서의 독립 검증

## 현재 최종 Linux 상태 — 2026-10-16

이 현재 안내는 아래 6080/4ec 역사 절의 현재형 상태 설명보다 우선합니다. 과거 절·수식·기준·실패는 해당 정확 후보의 근거로 보존하며 현재 결과로 소급하지 않습니다.

독립 제출은 명시 생산 **929ac8eb90d5598724ad066e7f8b8fc579ea8cd8**를 정상 merge한 `codex/openphysics-thermal-simcase-independent-validation`의 **9b43ae368e89e7e840541d21201e56a311a465b3**입니다. 이 추가 안내는 문서만 변경합니다. 해당 생산 후보 대비 독립 제출은 전용 파일8개를 추가하고 생산232개 blob을 모두 보존했습니다. 아래는 생산 담당의 시험 요약이 아니라 독립 검증 담당의 실행 근거입니다.

재구성한 Work cloud Linux에서 최종 전용 source **139개**, 실제 sdist→wheel installed **139개**가 통과했습니다. installed는 `python -I`, checkout 밖 복사 시험과 외부 confcutdir를 사용했습니다. 각각 실패·skip0, 기존 Starlette deprecation warning1개였습니다. 실행 파일과 simcase, simcase.thermal, galerkin, galerkin.thermal, meshine, physmat의6개 module origin이 설치 venv 안에 있는지 확인했습니다. 설치 serializer와 배포 HTML bytes를 정확 Git blob과 대조했습니다. 독립 지연 응답 Node는 **source8 + installed8** 통과, 실패·skip0입니다. 실제 배포 스크립트를 VM/DOM harness에서 실행한 것이며 실제 브라우저 수용 검증은 아닙니다.

정확929 Linux 재실행에서 초기의 의도적 결과 손상 저장 반례5개와 후속 constructor·필수 artifact 검사가 해결됨을 확인했습니다. 원시 배열9개·두 field flag·원 K/f/반력/열수지·고정 수렴·SI 기준·CLI 종료·기존/교체/foreign 출력 보호·제한된 two-writer 검사를 유지했습니다. 추가 실제 installed CLI의 save_fields=false 실행은 exit0, NPZ 없이 model/summary/log만 생성하고 해석적60 W/m 열수지와 일치했습니다. 허용치 완화나 skip/xfail로 과거 실패를 통과로 바꾸지 않았습니다.

sdist7개에서 wheel7개를 생성했습니다. 기존 sdist asset gate7개와 wheel runtime/static byte 비교는 통과했습니다. 통합 `ci/check_distributions.py`는 **twine 부재로 실패**했으므로 full strict 배포 검증 통과를 주장하지 않습니다. 새 의존성은 설치하지 않았습니다. 환경 복구 뒤 전체 root 수치시험은 반복하지 않았으며 이 전용 결과로 새 전체 결합 빌드를 인증하지 않습니다.

같은 hostname이었지만 원 scratch에 접근할 수 없게 됐습니다. 옛 미업로드 raw log·venv·미commit 작업은 **미회수**입니다. 따라서 아래 “All original failure logs remain retained”와 이에 대응하는 번역은 과거 실행 당시 관측이며 현재 raw log 접근 가능성을 뜻하지 않습니다. 원격 commit 소스·기록된 카운트·실패 trace는 남았습니다. 원격 blob을 검증해 정확929 source를 재구성했고 위 결과는 새 로그를 생성한 새 실행입니다. 작은 근거 기록은 명령·환경·hash·카운트·소실 한계를 구분합니다. 그 기록이나 재실행은 사라진 원 raw log가 아닙니다. 초기 CI 취소와 모든 과거 실패도 소급 성공시키지 않습니다.

후속 생산 **94bd34b5711521d805bdce4bee17852895041344**는929 대비 생산 fault-injection 시험과 한·영 guide만 변경합니다. 생산 `simcase/thermal.py`는 blob **7823d39f451cad1c6b53d2f8dde7899fd854321c**로 byte 동일합니다. 독립 Linux 리뷰에서 엄격해진 fault5개는 source·실제 installed **5 + 5개 통과**했습니다. 기존 독립 저장·CLI 선별 시험은 별도로 **34 + 34개 통과**, 각105개 deselected이며139개 전체 재실행이 아닙니다. 새 assertion은 의도한 주입 오류와 교체 완료 단계를 요구합니다. fixture rename/replace의 OSError를 cleanup 수용 통과로 세면 안 됩니다.

**Windows는 미검증입니다.** 이전 보고된 Windows 실패2개의 원인은 이 리뷰에서 확정하지 않았으며 실제 errno/winerror/stage 근거가 필요합니다. Linux 실행과 정적 검토는 Windows 지원이나 수정 완료를 입증하지 않습니다. 최신 지시로 GitHub Actions 활성화·dispatch·재실행은 금지하며 Windows runner 검증은 중단·미검증입니다.

별도의 결정론적 Linux interleaving 진단에서 pathname TOCTOU 한계를 확인했습니다. cleanup의 소유 확인 뒤 unlink 전에 model.json을 교체하면 source·installed 모두 foreign replacement를 삭제했습니다. 두 번째 writer를 check/use 간격에 스케줄링한 것이며 Windows 실패2개의 원인 진단은 아닙니다. inode pin과 검사는 이미 교체된 파일의 시험 사례를 보호하지만 pathname 작업을 원자적으로 만들지는 않습니다. 생산 수정 완료를 주장하지 않습니다. 적대적 race·crash recovery·thermal Studio UI·heat-to-mechanical 연성은 이 수용 주장의 범위 밖입니다.

## 아래부터 역사적 근거

[영문 원문](../../../thermal_simcase_independent_validation.md)

아래 실행 수치·실패·미검증 서술은 영문 원문의 해당 후보 시점 기록이며 새 수용 결과를 뜻하지 않습니다.

이 전용 시험은 실제 공개 Document/run/ThermalRunResult API, 원래 약형 대수, 저장된 숫자 배열, 설치 CLI와 출력 소유권을 검사합니다. 생산 summary나 기존 열전도 참조 helper를 수치 정답으로 쓰지 않습니다. 생산 코드나 기존 시험·설정은 바꾸지 않습니다.

## 고정한 독립 방정식과 기준

평행이동한 직사각형은 [0.007,0.037] x [-0.004,0.016]m이고 L=.03m, H=.02m, k=12.5W/(m K), Q=100000W/m^3, 왼쪽280K·오른쪽315K입니다. xi=x-.007이면 직접 미분으로 다음을 얻습니다.

`T=280+35xi/L+Qxi(L-xi)/(2k)`,
`q=(-k35/L-Q(L-2xi)/2,0)`, `-div(k grad T)=Q`.

외향 열량은 왼쪽 +321.6666666667W/m, 오른쪽 -261.6666666667W/m, 위·아래 0이며 전체60W/m입니다. weak reaction은 내향이므로 반대 부호입니다. Q0 slab과 음수 Q 흡수원은 별도 대조입니다. 깊이를 지정하지 않은 상태의 W가 아니라 깊이당 열량입니다.

전용 oracle는 `[1,x,y]`를 역행렬로 풀어 P1 gradient를 구하고, 소거하지 않은 additive COO K_ij=k A gradNi dot gradNj와 f_i=Q A/3를 독립 조립한 뒤 residual=K(T-T_offset)-f를 평가합니다. 반력은 처방 절점의 residual이고 자유 절점에서는 0입니다. 상수 offset 평가로 원래 K/f 문제를 바꾸지 않고 절대 온도의 불필요한 상쇄를 피합니다. 원 cell flux는 -k grad(P1T)로 재구성합니다. 중복 없는 정렬된 처방 절점은 생산 태그 summary가 아니라 물리적 경계 좌표에서 도출합니다. 왼쪽·오른쪽은 서로 겹치지 않습니다. 일반적으로 모서리가 겹치는 태그 합으로 반력을 변별로 유일하게 분해할 수 없으며 전체 열량을 중복 계산해서는 안 됩니다.

제품 후보를 받기 전에 기준을 고정했습니다.

- 원래 `(nx,ny)=(n,n)`, n8/16/32/64를 유지합니다. 마지막 두 구간16->32와32->64 각각에서 온도 L2 차수>=1.8, 벡터 flux 차수>=.9가 필요합니다. 독립 내부6x6 Duffy 적분을8x8과 대조합니다. 횡방향 0 성분을 포함해 두 flux 성분 모두 중요합니다.
- 35K, k35/L, L과 0이 아닌 source·reaction 절댓값 열량 scale로 정규화합니다. 280K나 상쇄되는 slab 순열량으로 나누지 않습니다. 배열·원 K/f·반력·연속 열량 기준은<=1e-10, 동등한 m/mm/um의 물리적 배열 불변성은<=1e-9입니다. connectivity·ID는 정확히 비교합니다. 평행이동 원점까지 기하만 바꾸며 k/Q/온도/분할수는 고정 SI 입력입니다.
- 독립 원시 소비자는 allow_pickle=False로 읽고 layout·단위·shape·유한성·정수 CCW connectivity·중복 없는 고정 절점을 검증한 뒤 K/f/flux/residual을 재구성합니다. metadata는 배열을 뒷받침할 뿐 기대 물리 정답을 만들지 않습니다.
- 예상 거절 시험은 정상 assertion이며 skip/xfail이 아닙니다. 저장 실패는 무관한 내용을 보존해야 하고 완료된 잘못된 결과를 게시해서는 안 됩니다.

1단계 수학 준비는 제품 해석이 아니라 해석적 절점 P1 표본과 synthetic storage를 사용했습니다. 이 제품 시험은 실제 runner의 장과 installed artifact를 별도로 얻으며 synthetic 보간 근거로 실제 실행을 대체하지 않습니다.

## 전용 파일과 실행

기존 의존성을 사용해 저장소 루트에서 실행합니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m pytest packages/simcase/tests/test_thermal_simcase_independent_validation.py \
  --basetemp=/absolute/own/records/unused-pytest-directory -q -s
node --test packages/simcase/tests/thermal_simcase_independent_stale.cjs
```

Python oracle·test 파일은 설치 검증을 위해 checkout 밖으로 복사합니다. 실제 wheel venv의 `python -I -m pytest`로 복사된 시험을 실행하며 confcutdir도 source 밖에 두고 담당자의 새 basetemp를 사용합니다. simcase,simcase.thermal,galerkin,galerkin.thermal,meshine,physmat의 module.__file__이 설치 venv 안에 있는지 검증하고 sys.executable을 기록합니다. CLI 시험은 실제 `sys.executable -I -m simcase` subprocess를 실행합니다. 기존 optional 시험 의존성을 명시적으로 재사용할 수 있지만 source-tree PYTHONPATH fallback이나 새 의존성은 필요하지 않습니다. 먼저 sdist->wheel로 빌드합니다.

Node 시험은 실제 배포 inline Studio 스크립트를 결정론적 DOM/canvas harness에서 실행하고 API 응답을 지연시킵니다. revision-token 변수 이름의 존재만 보는 대신 thermal JSON apply 뒤의 실제 상태를 검사합니다. 설치 시험을 복사한 경우 SIMCASE_INDEPENDENT_HTML을 실제 설치된 simcase/studio/static/index.html로 지정합니다. harness 실행을 실제 브라우저 통합 검증이라고 주장하지 않습니다. server capability 시험은 실제 FastAPI endpoint를 사용해 optical worker·mesh builder·새 job이 만들어지지 않는지 확인합니다.

## 초기 후보의 근거와 미해결 실패

초기 생산 후보는 **6080eb86bbd70b668e9952c99ec21802af6ed5cd**, 부모는0a44797f73cf67bab14429c982144f0e0e4338aa입니다. 이 후보는 **미수용**입니다. 이후 이동하는 브랜치 head에 blob 대조와 관련 재실행 없이 이 상태를 승계하지 않습니다.

첫 관련 실행은84개 통과,1개 실패였습니다. 독립 시험이 metadata의 Dirichlet 태그-온도 매핑을 동명 원시 배열로 오인한 시험 오류였습니다. 허용되는 유한 태그 매핑을 검증하도록 assertion을 수정했으며 물리적 허용치는 바꾸지 않았습니다. 확장 실행은90개 통과,6개 실패였고, 실제 저장 상태 거절5개와 isolated 환경에서 기존 Shapely import가 빠진1개였습니다. 새 패키지 설치 없이 전용 venv에 기존 의존성 경로를 명시했습니다. 재실행은91개 통과,동일 저장 사례5개 실패였습니다. 최초 복사 installed-wheel 시험도 독립적으로91통과/5실패를 재현했습니다. 원래 실패 로그는 보존된 기록으로 남깁니다.

실제 slab·양수/음수 mixed Q, 원래 행렬·하중·잔차·반력, 양쪽 부호 있는 열량·전체60W/m, 단위 불변성, 원 NPZ·metadata, 동일·상충 모서리와 source 수렴의 수치 검사는 통과합니다. 실제 n8/16/32/64의 정규화 오차는 대략 T=[2.93423e-4,7.33557e-5,1.83389e-5,4.58473e-6], flux=[7.42307e-3,3.71154e-3,1.85577e-3,9.27884e-4]이며 차수2/1을 줍니다.

거절 실패5개에는 정확히 **의도적인 mutable-result 손상** 전제가 있습니다. 유효한 문서를 해석한 뒤 공개 solution의 heat_flux/load/reaction/residual 중 한 원소를 NaN으로 바꾸거나, cell heat_flux를(M,2) 대신(M,)로 바꾸고 save(fresh)를 호출합니다. 기대는 ValueError와 완료 summary 없음이지만, 실제6080은 잘못된 원시 배열과 완료 summary를 저장하고 .incomplete를 제거합니다. 이는 직렬화 검증 문제이며 정상 열전도 해석이 NaN을 만들었다는 근거가 아닙니다. 캐시된 유한 진단과 object dtype 거절만으로 유한하고 shape이 맞는 숫자 출력을 보장하지 못합니다.

실제 스크립트의 지연 응답 시험3개 모두6080에서 실패합니다. thermal JSON apply 후 늦은 기존 EM result가 resultData를, 늦은 mesh가 meshData를 다시 채우고, 늦은 성공 validation이 원시 thermal 문서를 예전 EM으로 바꿉니다. 서버의 headless 거절은 통과하지만 클라이언트 revision 안전성을 보장하지 않습니다. 초기 후보는 frontend guard 미완료 상태를 명시했으며, 이는 그 공개된 미완료 범위의 구체적 수용 실패입니다.

실제 save 보호는 기존 파일·빈/비어 있지 않은 디렉터리·dangling symlink 거절, 두 field flag, NPZ 이후·summary 이전 실패 정리, 예상하지 않은 파일과 incomplete 보존, 교체 target 보존과 제한된 two-writer 배타적 소유권 시험을 통과합니다. 이는 이식 가능한 atomic transaction, 적대적 파일시스템 race나 crash recovery를 인증하지 않습니다. 이후 save·guard·validation 변경은 관련 독립 재실행이 필요합니다.

전체 source, 추가 경계·CLI 대조와 최종 artifact 검사는 완료 시 별도로 보고합니다. 미완료 단계나 실패한 초기 후보를 green이라 부르지 않습니다. 이 시험은 headless 열전도 문서를 다루며 열전도 plotting, Studio 열 UI나 heat-to-mechanical 연성을 다루지 않습니다.

## 명시적 Linux 재수용 후보4ec9da9

후보4ec9da9fcba661958a12f37bc445a543cb4ffc1c는6080의 직접 자식입니다. 초기 실패 후보와 전용 시험을 보존하며 독립 브랜치에 정상 merge합니다. 읽기 전용 생산 delta는 열 직렬화 코드, inline Studio 스크립트, 공개 열전도 문서와 생산 시험입니다. 독립 시험은 새 문서의9개 배열 metadata 용어를 읽으며 물리적 shape·유한성·수치 기준은 바뀌지 않습니다.

이 정확한 Linux 후보에서 원래106개 Python 시험이 모두 통과하며 초기 저장 상태 반례5개도 포함됩니다. 동일한 실제 스크립트 stale-response3개도 통과합니다. 따라서 초기 실패는 **이 Linux 후보에서** 해결됐지만6080을 소급 통과시키지는 않습니다. 확장134개 시험에는9개 metadata 검증, 두 field flag에서9개 nonfinite 배열, CCW/index/중복 없는 ID/value-shape/bool/integer 대조와 기존 소유 파일 교체 후 보존을 추가했습니다. 결과는131통과/3실패이며 남은 실패는 수치 수렴이 아니라 이 후보에서 공개한 저장 미완료 업무입니다.

남은 구체적 검사는 다음3개입니다.

1. 소유권 생성 도중 새 디렉터리의 os.open에서 OSError를 주입합니다. 배타적으로 소유한 빈 target의 정리를 기대하지만 실제로는 incomplete marker 없이 빈 디렉터리가 남습니다.
2. summary를 쓴 뒤 finish 전에 model.json을 제거합니다. 필수 소유 artifact 누락으로 거절해야 하지만 실제 save는 성공하고 marker를 제거합니다.
3. save_fields=true일 때 fields.npz를 같은 방법으로 제거합니다. 필수 원시 archive가 없어도 save가 성공합니다.

이 검사를 skip/xfail하거나 허용치를 완화해 숨기지 않습니다. 이 후보 당시 directory-fd·dup pinning은 POSIX 전용이며 Linux 결과로 Windows 지원을 입증하지 않습니다. portable handle, constructor 실패 정리와 required-owned-file 검사는 별도의 생산 후속 변경입니다. 이후 정확한 blob에 대해 source·installed의 저장·metadata·CLI를 다시 검사해야 합니다. 이동 head를 임의 선택하거나4ec가 개선됐다는 이유로 나중 후보의 통과를 가정하지 않습니다.

원6080의 첫 전체 root 실행은 마지막10개 대조 추가 전 당시 독립96개를 수집했으며875통과/5실패/optional skip16과 하위 시험9통과였습니다. 모든106개는 source와 실제 installed venv에서 따로 실행해101통과/5실패였습니다. 나중10개가 최초 전체 수집에 들어갔다고 잘못 보고하지 않습니다. 기존 Studio vector8통과는6080의 독립 stale-response3실패와 다릅니다. 초기 independent branch CI38742590017은 정상 branch merge의 workflow concurrency로 취소됐으며 green 실행이 아닙니다. 앞선 시험·환경 오류도 위에 남겨 둡니다. 원래 raw/module/ownership 근거는6080에만 적용됩니다.
