"""SAFE-LOOP admission coordinator: deterministic in-process prototype.
No SDN enforcement or live network telemetry. Capacity refresh is a caller-supplied observation.
"""
from dataclasses import dataclass
from threading import RLock
from time import monotonic

@dataclass(frozen=True)
class Observation:
    capacity_mbps: float
    measured_at: float
    version: int

@dataclass(frozen=True)
class Decision:
    admitted: bool
    reason: str
    observation_version: int
    reserved_mbps: float

class Coordinator:
    def __init__(self, background_mbps, max_age_s=5, refresh=None, clock=monotonic):
        if background_mbps < 0 or max_age_s < 0: raise ValueError('invalid parameters')
        self.background = background_mbps
        self.max_age = max_age_s
        self.refresh = refresh
        self.clock = clock
        self.lock = RLock()
        self.observation = None
        self.reservations = {}

    def update(self, observation):
        if observation.capacity_mbps <= 0: raise ValueError('capacity must be positive')
        with self.lock:
            if self.observation and observation.version <= self.observation.version:
                raise ValueError('nonmonotonic telemetry version')
            self.observation = observation

    def admit(self, request_id, demand_mbps):
        if not request_id or demand_mbps <= 0: raise ValueError('invalid request')
        with self.lock:
            if request_id in self.reservations:
                return Decision(True,'idempotent',self.observation.version,sum(self.reservations.values()))
            obs = self.observation
            if obs is None or self.clock()-obs.measured_at > self.max_age or obs.measured_at > self.clock():
                if self.refresh is None:
                    return Decision(False,'deferred_no_fresh_observation',obs.version if obs else -1,sum(self.reservations.values()))
                fresh = self.refresh()
                if not isinstance(fresh,Observation) or fresh.capacity_mbps <= 0 or fresh.measured_at > self.clock() or self.clock()-fresh.measured_at > self.max_age or (obs and fresh.version <= obs.version):
                    return Decision(False,'deferred_invalid_refresh',obs.version if obs else -1,sum(self.reservations.values()))
                self.observation = fresh
                obs = fresh
            committed = sum(self.reservations.values())
            if self.background + committed + demand_mbps > obs.capacity_mbps + 1e-9:
                return Decision(False,'insufficient_capacity',obs.version,committed)
            self.reservations[request_id] = demand_mbps
            return Decision(True,'reserved',obs.version,committed+demand_mbps)

    def release(self, request_id):
        with self.lock:
            return self.reservations.pop(request_id,None) is not None
