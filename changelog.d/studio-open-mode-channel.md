# Added

## English

- Studio: **the guided / leaky category of an open-boundary mode** (pure functions, not yet shown). `workspace-mode-channel.mjs` reads, from data every open run stores (Re n_eff, the input shapes, the open edges, the wavelength; no field), the bounds n_lo and n_hi of the material profile each open edge continues through the PML, and calls a mode *leaky into* a region (some n_lo above Re n_eff + 0.02), *guided* (every n_hi below Re n_eff − 0.02) or *no claim* (a layer reaching an open edge only sideways, or Re n_eff within 0.02 of an edge index). A guided mode whose Im n_eff exceeds the engine's gain bound gets no text; a leaky one within it says the solve resolves no leakage loss. A closed run gets nothing. `tests/simcase/studio_mode_channel.cjs` checks the unit cases and the texts. [Open boundary in the optical workspace](docs/packages/simcase/workspace.md#open-boundary-in-the-optical-workspace).

## 한국어

- Studio: **열린 경계 모드의 도파/누설 분류**(순수 함수, 아직 화면에 나오지 않음). `workspace-mode-channel.mjs`는 모든 열린 실행이 저장하는 데이터(Re n_eff, 입력 도형, 열린 가장자리, 파장; 필드는 쓰지 않음)로 각 열린 가장자리가 PML을 지나 이어지는 재료 단면의 n_lo, n_hi 경계를 읽고, 모드를 어떤 영역으로 *누설*(어떤 n_lo가 Re n_eff + 0.02보다 큼), *도파*(모든 n_hi가 Re n_eff − 0.02보다 작음), *판단 없음*(옆으로만 열린 가장자리에 닿는 층, 또는 Re n_eff가 가장자리 굴절률과 0.02 이내)으로 나눕니다. Im n_eff가 엔진의 이득 경계를 넘는 도파 모드에는 문구가 없고, 한계 안의 누설 모드는 이 풀이가 누설 손실을 분해하지 못한다고 말합니다. 닫힌 실행에는 아무것도 없습니다. `tests/simcase/studio_mode_channel.cjs`가 단위 사례와 문구를 확인합니다. [광학 작업 공간의 열린 경계](packages/simcase/workspace.md#광학-작업-공간의-열린-경계).
