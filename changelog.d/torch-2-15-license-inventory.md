# Changed

## English

- License inventory: torch 2.15.0+cpu declares `ISC` and `Zlib` in addition to its earlier expression (libuv's ISC-licensed parts in tensorpipe and asmjit in fbgemm, whose license texts the wheel now ships), and installs GNU libgfortran (`torch/lib/libgfortran.so.5`, GPL-3.0-or-later WITH GCC-exception-3.1), which none of torch's libraries lists as a dependency. The entry records the 2.15.0 expression and a reviewed `libgfortran` record, and keeps accepting the pinned 2.14.1's narrower declaration as a reviewed `metadata_spdx`, so the latest-dependencies canary passes its license step again; the pins are unchanged. [Third-party software](docs/third-party.md).

## 한국어

- 라이선스 목록: torch 2.15.0+cpu는 이전 식에 `ISC`와 `Zlib`를 더해 선언하고(tensorpipe 안 libuv의 ISC 부분과 fbgemm 안 asmjit. 휠이 이제 그 라이선스 문서를 담음), torch의 어느 라이브러리도 의존성으로 적지 않은 GNU libgfortran(`torch/lib/libgfortran.so.5`, GPL-3.0-or-later WITH GCC-exception-3.1)을 설치합니다. 항목은 2.15.0의 식과 검토한 `libgfortran` 기록을 담고, 고정한 2.14.1의 더 좁은 선언은 검토한 `metadata_spdx`로 계속 받아들이므로 최신 의존성 카나리아의 라이선스 단계가 다시 통과합니다. 고정 버전은 바뀌지 않습니다. [제3자 소프트웨어](third-party.md).
