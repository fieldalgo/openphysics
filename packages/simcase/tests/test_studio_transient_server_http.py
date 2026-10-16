# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Producer regression coverage for shared thermal admission and transport pins."""
from dataclasses import replace
import pytest
from simcase.studio import thermal_api as thermal


def attached(jobs, job="thermal-one"):
    lease = jobs.reserve()
    jobs.attach(lease, job, "result-one", thermal.ThermalInput(None, 1, 2))
    return lease


def test_ingress_permit_is_nonblocking_and_old_release_is_harmless():
    gate = thermal.AdmissionGate("ingress_capacity_exceeded")
    first = gate.acquire()
    with pytest.raises(thermal.ThermalAPIError) as error:
        gate.acquire()
    assert error.value.status == 429
    first.release()
    second = gate.acquire()
    first.release()
    with pytest.raises(thermal.ThermalAPIError):
        gate.acquire()
    second.release()


def test_running_status_snapshot_stays_pinned_when_terminal_replaces_status():
    jobs = thermal.ThermalJobs()
    lease = attached(jobs)
    pin = jobs.pin("thermal-one")
    original = pin.payload
    assert b'"running"' in original
    assert sum(map(len, jobs._snapshots.values())) == len(original)
    jobs.complete(lease, b"{}", [])
    jobs.release(lease)
    assert b'"done"' in jobs.status("thermal-one")
    assert pin.payload == original
    assert sum(map(len, jobs._snapshots.values())) == len(original)
    pin.release()
    pin.release()
    assert not jobs._snapshots


def test_evicted_terminal_pin_retains_byte_charge_until_reader_release():
    jobs = thermal.ThermalJobs()
    lease = attached(jobs)
    jobs.complete(lease, b"{}", [])
    jobs.release(lease)
    pin = jobs.pin("thermal-one", result=True)
    size = jobs._record_bytes(pin.record)
    with jobs._lock:
        jobs._discard("thermal-one")
    assert not jobs._records
    assert jobs._retained_bytes() == size
    assert pin.payload == b"{}"
    pin.release()
    assert jobs._retained_bytes() == 0


def test_pinned_bytes_can_prevent_new_admission_without_early_release():
    limits = replace(thermal.ThermalLimits(), terminal_bytes=thermal.ThermalLimits().payload_bytes
                     + thermal.ThermalLimits().status_bytes, terminal_jobs=2)
    jobs = thermal.ThermalJobs(limits)
    lease = attached(jobs)
    jobs.complete(lease, b"x"*limits.payload_bytes, [])
    jobs.release(lease)
    pin = jobs.pin("thermal-one", result=True)
    with pytest.raises(thermal.ThermalAPIError) as error:
        jobs.reserve()
    assert error.value.status == 429
    assert jobs._retained_bytes() > 0
    pin.release()
    next_lease = jobs.reserve()
    jobs.release(next_lease)
    assert jobs._active == jobs._pending == jobs._reserved_bytes == 0
