# Headless 열전도 문서의 독립 검증

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
