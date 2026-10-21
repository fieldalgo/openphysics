# Headless 열전도 문서의 독립 검증

**한눈에 보기**

- **확인하는 것:** 이동한 직사각형의 닫힌 형태 2차 열원 해로 headless `thermal.steady2d` 문서 경로(문서·실행·저장 배열)를 독립 수용 검증합니다. Oracle은 저장된 raw 배열에서 강성·하중·열유속·잔차를 재구성하며, metadata로 기대 정답을 만들지 않습니다.
- **고정 기준:** n=8/16/32/64의 마지막 두 구간에서 온도 L2 차수 ≥ 1.8, 벡터 열유속 차수 ≥ 0.9가 필요합니다. 독립 6×6·8×8 내부 적분을 비교하고, 배열·강성·하중·반력·열량 기준은 ≤ 1e-10, m/mm/µm 동치는 ≤ 1e-9입니다.
- **범위:** headless 열전도 문서만 다루며 열전도 plotting, Studio 열 UI, heat-to-mechanical 연성은 범위 밖입니다. 특정 커밋의 결과는 그 커밋의 CI 실행에서 확인하세요.

## 근거

이 페이지는 기준과 재현 방법을 정의합니다. 특정 커밋의 결과는 그 커밋의 CI
종료값·로그·artifact입니다. 아래 명령은 검사를 재현하는 절차이며 그 자체가 통과
결과는 아닙니다.

[영문 원문](../../../../../packages/simcase/thermal_simcase_independent_validation.md)

## 시험이 확인하는 것

이 전용 시험은 실제 공개 Document/run/ThermalRunResult API, 원래 약형 대수, 저장된 숫자 배열, 설치 CLI와 출력 소유권을 검사합니다. 생산 summary나 기존 열전도 참조 helper를 수치 정답으로 쓰지 않습니다.

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

해석적 절점 P1 표본과 synthetic storage는 수학 준비이며 제품 해석이 아닙니다. 이 시험은 실제 runner의 장과 installed artifact를 별도로 얻으며 synthetic 보간 근거로 실제 실행을 대체하지 않습니다.

## 측정값

다음은 gate가 아닌 측정 참고값입니다. n8/16/32/64의 정규화 오차는 대략 T=[2.93423e-4,7.33557e-5,1.83389e-5,4.58473e-6], flux=[7.42307e-3,3.71154e-3,1.85577e-3,9.27884e-4]이며 차수 2/1을 줍니다.

## 전용 파일과 실행

기존 의존성을 사용해 저장소 루트에서 실행합니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m pytest tests/simcase/test_thermal_simcase_independent_validation.py \
  --basetemp=/absolute/own/records/unused-pytest-directory -q -s
node --test tests/simcase/thermal_simcase_independent_stale.cjs
```

Python oracle·test 파일은 설치 검증을 위해 checkout 밖으로 복사합니다. 실제 wheel venv의 `python -I -m pytest`로 복사된 시험을 실행하며 confcutdir도 source 밖에 두고 담당자의 새 basetemp를 사용합니다. simcase,simcase.thermal,galerkin,galerkin.thermal,meshine,physmat의 module.__file__이 설치 venv 안에 있는지 검증하고 sys.executable을 기록합니다. CLI 시험은 실제 `sys.executable -I -m simcase` subprocess를 실행합니다. 기존 optional 시험 의존성을 명시적으로 재사용할 수 있지만 source-tree PYTHONPATH fallback이나 새 의존성은 필요하지 않습니다. 먼저 sdist->wheel로 빌드합니다.

Node 시험은 실제 배포 inline Studio 스크립트를 결정론적 DOM/canvas harness에서 실행하고 API 응답을 지연시킵니다. revision-token 변수 이름의 존재만 보는 대신 thermal JSON apply 뒤의 실제 상태를 검사합니다. 설치 시험을 복사한 경우 SIMCASE_INDEPENDENT_HTML을 실제 설치된 simcase/studio/static/index.html로 지정합니다. harness 실행을 실제 브라우저 통합 검증이라고 주장하지 않습니다. server capability 시험은 실제 FastAPI endpoint를 사용해 optical worker·mesh builder·새 job이 만들어지지 않는지 확인합니다.

## 포함한 대조

수치 대조는 실제 slab·양수/음수 mixed Q, 원래 행렬·하중·잔차·반력, 양쪽 부호 있는 열량·전체 60 W/m, 단위 불변성, 원 NPZ·metadata, 동일·상충 모서리와 source 수렴을 다룹니다. 원시 배열 9개를 두 field flag 모두에서 검사하며 CCW/index/중복 없는 ID/value-shape/bool/integer 대조를 함께 둡니다. save_fields=false이면 CLI는 NPZ 없이 model/summary/log를 생성합니다.

의도적인 mutable-result 손상은 거절해야 합니다. 유효한 문서를 해석한 뒤 공개 solution의 heat_flux/load/reaction/residual 중 한 원소를 NaN으로 바꾸거나, cell heat_flux를 (M,2) 대신 (M,)로 바꾸고 save(fresh)를 호출합니다. 기대 결과는 ValueError와 완료 summary 없음입니다. 이는 직렬화 검증이며 정상 열전도 해석이 NaN을 만든다는 근거가 아닙니다. 캐시된 유한 진단과 object dtype 거절만으로 유한하고 shape이 맞는 숫자 출력을 보장하지 못합니다.

지연 응답 Node 시험은 thermal JSON apply 뒤 늦은 기존 EM result가 resultData를, 늦은 mesh가 meshData를 다시 채우지 않고, 늦은 성공 validation이 원시 thermal 문서를 예전 EM으로 바꾸지 않을 것을 요구합니다. 서버의 headless 거절만으로 클라이언트 revision 안전성을 보장하지 않습니다.

save 보호는 기존 파일·빈/비어 있지 않은 디렉터리·dangling symlink 거절, 두 field flag, NPZ 이후·summary 이전 실패 정리, 예상하지 않은 파일과 incomplete 보존, 교체 target 보존과 제한된 two-writer 배타적 소유권 시험을 다룹니다. 저장 검사는 다음도 요구합니다.

1. 소유권 생성 도중 새 디렉터리의 os.open에서 OSError가 나면 배타적으로 소유한 빈 target을 정리합니다.
2. summary를 쓴 뒤 finish 전에 model.json이 제거되면 필수 소유 artifact 누락으로 save를 거절합니다.
3. save_fields=true일 때 fields.npz에도 같은 거절이 적용됩니다.

fault-injection assertion은 의도한 주입 오류와 교체 완료 단계를 요구합니다. fixture rename/replace의 OSError를 cleanup 수용 통과로 세면 안 됩니다. 이 검사를 skip/xfail하거나 허용치를 완화해 숨기지 않습니다. save·guard·validation 변경에는 관련 독립 source·installed 재실행이 필요합니다.

## 한계

**Windows는 미검증입니다.** Windows 수용에는 새 runner 근거가 필요하며, Windows 실패의 원인 진단에는 실제 errno/winerror/stage 근거가 필요합니다. Linux 실행과 정적 검토는 Windows 지원이나 수정 완료를 입증하지 않습니다.

결정론적 Linux interleaving 진단은 남은 pathname TOCTOU 한계를 보여 줍니다. cleanup의 소유 확인 뒤 unlink 전에 model.json을 교체하면 foreign replacement가 삭제됩니다. inode pin과 검사는 이미 교체된 파일의 시험 사례를 보호하지만 pathname 작업을 원자적으로 만들지는 않습니다. 지원하는 fresh-output 계약은 호출자가 배타적으로 통제하는 출력 경로를 요구합니다. save와 실패 시 cleanup이 모두 끝날 때까지 다른 writer가 출력을 변경하지 않도록 해야 합니다. 검사 전에 이미 관측한 교체의 보존과 check/use race 도중 교체의 보존은 다르며 후자는 보장하지 않습니다. 제한된 동시 save 시험은 새 target 획득의 배타성을 확인할 뿐 일반적인 외부 동시 writer 보호를 입증하지 않습니다. save 보호는 이식 가능한 atomic transaction을 인증하지 않습니다. 적대적 파일시스템 race·crash recovery·thermal Studio UI·heat-to-mechanical 연성은 이 수용 주장의 범위 밖입니다.
