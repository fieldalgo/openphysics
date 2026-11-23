# Changed

## English

- Studio: an open run's loss cell reads *not resolved (|loss| < X dB/cm)* for a negative Im n_eff whose |loss| is 0.01 dB/cm or more, X rounded up to 2 significant digits, with help saying the solve gives a small negative Im n_eff within the PML's numerical noise. Negative values below 0.01 dB/cm keep *< 0.01 dB/cm*; positive losses are unchanged. [Open boundary in the optical workspace](docs/packages/simcase/workspace.md#open-boundary-in-the-optical-workspace).

## 한국어

- Studio: 열린 실행의 손실 칸은 음의 Im n_eff로 |손실|이 0.01 dB/cm 이상이면 *not resolved (|loss| < X dB/cm)*(X는 유효숫자 2자리로 올림)로 읽히고, 도움말은 풀이가 PML의 수치 잡음 안의 작은 음의 Im n_eff를 냈다고 적습니다. 0.01 dB/cm 미만의 음의 값은 *< 0.01 dB/cm*를 유지하고 양의 손실은 바뀌지 않습니다. [광학 작업 공간의 열린 경계](packages/simcase/workspace.md#광학-작업-공간의-열린-경계).
