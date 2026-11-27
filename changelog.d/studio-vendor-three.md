# Added

## English

- `simcase`: **Studio serves three.js 0.186.1 (MIT) from its own origin, for the coming 3D view.** `three.module.js`, `three.core.js` and the three.js `LICENSE` are vendored unmodified from the npm package under `simcase/studio/static/vendor/three-0.186.1/`, shipped in the simcase wheel and sdist, and served only by name at `/vendor/three-0.186.1/<file>` with `no-store` and `nosniff`. The page policy stays `script-src 'self'`, with no CDN and no import map. The license check now compares the folder with the recorded sizes and SHA-256 values, and check W16 confirms the served bytes and that a page loading three.js makes no request to another origin. No page uses it yet. [Browser-served files](docs/third-party.md#browser-served-files).

## 한국어

- `simcase`: **Studio가 다가올 3D 보기를 위해 three.js 0.186.1(MIT)을 자기 origin에서 보냅니다.** `three.module.js`, `three.core.js`, three.js `LICENSE`를 npm 패키지에서 수정 없이 `simcase/studio/static/vendor/three-0.186.1/`에 넣어 simcase wheel과 sdist에 담고, `/vendor/three-0.186.1/<file>`에서 이름이 기록된 파일만 `no-store`, `nosniff`를 붙여 보냅니다. 페이지 정책은 그대로 `script-src 'self'`이고 CDN도 import map도 쓰지 않습니다. 라이선스 검사가 이제 이 폴더를 기록된 크기·SHA-256과 대조하고, 검사 W16이 보낸 바이트와 three.js를 읽는 페이지가 다른 origin에 요청하지 않음을 확인합니다. 아직 이를 쓰는 페이지는 없습니다. [브라우저로 보내는 파일](third-party.md#브라우저로-보내는-파일).
