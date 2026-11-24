// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The browser launch shared by the Studio browser checks: start the browser with a DevTools port
// and wait until it lists a page. A browser that does not answer within the wait is stopped and
// started once more, on a new port with a new profile directory; a second failure throws
// "Browser DevTools endpoint unavailable", so the check still fails. Each failed attempt is
// recorded in report.browserLaunch with the command line, the exit code or signal and the tail of
// the browser's stderr. Only the launch is retried: nothing after it is.

export const LAUNCH_WAIT_MS = 60000;
export const LAUNCH_ATTEMPTS = 2;
const TAIL = 4000;
const sleep = ms => new Promise(r => setTimeout(r, ms));

// The page target the DevTools endpoint lists, or null while it does not answer.
async function pageTarget(port) {
  try {
    const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
    return list.find(t => t.type === 'page') || null;
  } catch {
    return null;
  }
}

/**
 * Starts the browser and returns {target, port, child, attempt}.
 *   launch(command, argv, attempt): starts a process with piped stderr and returns it (the script's own
 *     launcher, which keeps and logs it);
 *   command: the browser; argv(port, attempt): its arguments for that DevTools port and attempt;
 *   freePort(): a free local port; report: the script's report (browserLaunch is added);
 *   waitMs, attempts: the wait per attempt and the number of attempts.
 */
export async function launchBrowser({launch, command, argv, freePort, report, waitMs = LAUNCH_WAIT_MS, attempts = LAUNCH_ATTEMPTS}) {
  report.browserLaunch = [];
  for (let attempt = 1; attempt <= attempts; attempt++) {
    const port = await freePort(), args = argv(port, attempt), started = Date.now();
    const child = launch(command, args, attempt);
    let stderr = '', exit = null, signal = null, closed = false;
    child.stderr?.on('data', x => { stderr = (stderr + x).slice(-TAIL); });
    child.on('error', e => { stderr = (stderr + String(e)).slice(-TAIL); });
    const done = new Promise(r => child.on('close', (code, sig) => { exit = code; signal = sig; closed = true; r(); }));
    let target = null;
    while (!target && Date.now() - started < waitMs) {
      target = await pageTarget(port);
      if (!target) await sleep(250);
    }
    if (target) {
      report.browserLaunch.push({attempt, ok: true, ms: Date.now() - started});
      return {target, port, child, attempt};
    }
    // no answer: stop this browser and keep what it said
    if (!closed) { child.kill(); await Promise.race([done, sleep(5000)]); }
    report.browserLaunch.push({attempt, ok: false, ms: Date.now() - started, command, args, exit, signal, stderrTail: stderr});
  }
  throw new Error(`Browser DevTools endpoint unavailable after ${attempts} launches of ${Math.round(waitMs / 1000)} s each (see report.json browserLaunch)`);
}

export const END_WAIT_MS = 10000;

/**
 * Ends a browser script: stops the processes it started that still run, prints its last line and
 * exits with process.exitCode (0 when unset).
 *   owned: the script's child processes; line: its last line, as it printed it before;
 *   waitMs: how long SIGTERM has before SIGKILL.
 * A browser, or one of its helper processes, can outlive SIGTERM and keep the script's pipes, and
 * with them the script, open. On 2026-11-24 the project script passed on macOS and then ran until
 * the CI job's 60-minute limit with a Chrome process left (PR #344). The explicit exit ends the
 * script even when a process it did not start itself still holds a pipe.
 */
export async function endScript(owned, line, waitMs = END_WAIT_MS) {
  const running = child => child.exitCode === null && child.signalCode === null;
  const closed = child => running(child) ? new Promise(r => child.once('exit', r)) : Promise.resolve();
  for (const child of owned) if (running(child)) child.kill();
  await Promise.race([Promise.all(owned.map(closed)), sleep(waitMs)]);
  for (const child of owned) if (running(child)) child.kill('SIGKILL');
  await new Promise(r => process.stdout.write(line + '\n', r));
  process.exit(process.exitCode ?? 0);
}
