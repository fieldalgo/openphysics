# 보안

[English](../../../security.md) | **한국어**

의심되는 취약점은 GitHub의
[비공개 취약점 신고](https://github.com/fieldalgo/openphysics/security/advisories/new)를
사용하세요. 공개 이슈에 공격 상세, 인증정보나 기밀 모델을 넣지 마세요.
영향받는 커밋·패키지 버전, 운영체제, 재현 절차, 예상 영향과 민감정보를 제거한
최소 예제를 포함하세요.

OpenPhysics는 개발 중입니다. 보안 수정은 `main`에서 진행하며 과거 패키지
버전의 지원 기간을 보장하지 않습니다. 수치 검증은
[문서 색인](index.md)에, 시험하는 플랫폼은 [개발 안내](development.md)에 설명합니다.

## 브라우저 Studio

`simcase-studio`는 로컬 도구입니다. 기본적으로 loopback(`127.0.0.1`)에 바인딩하고,
계정과 암호화가 없으며 다중 사용자 서비스가 아닙니다. 신뢰할 수 없는 네트워크에
노출하지 마세요. loopback이 아닌 `--host`를 주면 경고를 출력합니다.

같은 브라우저에 열린 다른 웹 페이지도 로컬 서버에 접근을 시도할 수 있습니다.
서버는 어떤 경로도 실행하기 전에 이런 요청을 거부합니다.

- **Host 검사(DNS 재바인딩).** `Host` 헤더가 `127.0.0.1`, `localhost`, `::1`,
  명시한 `--host`, 또는 연결이 들어온 주소 그 자체이고 포트가 서버가 듣는 포트일 때만
  응답합니다. 그 밖에는 403입니다(형식이 잘못된 `Host`는 400). Studio는 `http://127.0.0.1:<port>`나
  `http://localhost:<port>`로 여세요.
- **Origin 검사(교차 사이트 요청).** GET, HEAD, OPTIONS가 아닌 요청(POST 등)의
  `Origin`이 Studio 페이지 자신의 origin이 아니면 403입니다. `Origin`이 없을 때도
  다른 origin의 `Referer`나 `Sec-Fetch-Site: cross-site`/`same-site`면 403입니다.
  이 헤더가 하나도 없는 요청(`curl`, Python 클라이언트 등)은 전과 같이 처리합니다.
  `Origin`과 `Sec-Fetch-Site`를 보내지 않고 `Referer`도 숨기는 오래된 브라우저도
  마찬가지입니다. 최신 브라우저는 모든 POST에 `Origin`을 보냅니다.
- **요청 본문.** 광학 경로(`/api/validate`, `/api/mesh`, `/api/run`,
  `/api/materials/preview`)는 `Content-Type: application/json`만 받고(아니면 415,
  본문을 되돌려 보내지 않음) 크기는 최대 1 MiB입니다(넘으면 413). 열전도 경로는
  자체 한도를 그대로 씁니다.
- **광학 작업.** 광학 작업은 동시에 최대 4개까지 실행합니다(넘으면 429). 끝난 광학
  작업은 최근 16개만 남기고 더 오래된 것은 메모리에서 지웁니다(지운 작업은 404로
  답하며, workspace의 Resume 버튼도 마찬가지입니다). 실패한 작업은 오류
  메시지만 알려 주고 traceback은 서버 로그에만 남깁니다.
- **페이지.** 서버 경로의 응답과 거부 응답 모두에 Content-Security-Policy를 붙입니다. 스크립트는 서버 자신과
  고전 편집기의 해시된 인라인 스크립트 하나만 허용하고, 플러그인과 프레임 삽입은
  막으며(`frame-ancestors 'none'`, `X-Frame-Options: DENY`), 네트워크 요청은 같은
  origin으로만 보냅니다. 인라인 스타일은 계속 허용합니다(`style-src 'unsafe-inline'`).
  고전 편집기는 문서의 글자(이름, 재료, 매개변수)를 글자로만 쓰므로 조작한 모델
  파일이 마크업을 끼워 넣을 수 없습니다. CDN에서 Swagger UI를 읽던 대화형 API
  페이지 `/docs`, `/redoc`은 껐습니다.

이 검사는 FastAPI 버전이나 브라우저의 Local Network Access 규칙에 기대지 않습니다.
공유 네트워크나 신뢰할 수 없는 네트워크에서 Studio를 안전하게 만들지는 않습니다.
포트에 닿는 누구나 작업을 실행할 수 있습니다.
