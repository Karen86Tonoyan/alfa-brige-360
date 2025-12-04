#!/usr/bin/env python3
"""
alfa_guard_ai.py

ALFA Guard AI – lekki, uczący się strażnik sejfu:
- zbiera zdarzenia (telemetrię) dot. odblokowań
- adaptuje poziom ryzyka na podstawie historii
- zwraca politykę: blokada, wymaganie MUZ, logowanie incydentu
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional


STATE_VERSION = "1.0"


@dataclass
class GuardEvent:
    ts: float             # timestamp
    kind: str             # "vault_unlock", "muz_unlock", "pairing", ...
    ok: bool              # True = sukces, False = porażka
    source: str           # np. "device-local", "remote", "adb", "unknown"
    meta: Dict[str, Any]  # dodatkowe dane (ip, user_agent, itp.)


@dataclass
class GuardState:
    version: str
    last_reset_ts: float
    failed_24h: int
    success_24h: int
    risk_level: float
    lockout_until: float  # timestamp; 0 = brak blokady
    night_failures: int
    day_failures: int

    @staticmethod
    def default(now: Optional[float] = None) -> "GuardState":
        if now is None:
            now = time.time()
        return GuardState(
            version=STATE_VERSION,
            last_reset_ts=now,
            failed_24h=0,
            success_24h=0,
            risk_level=0.0,
            lockout_until=0.0,
            night_failures=0,
            day_failures=0,
        )


class AlfaSecurityAI:
    """
    Klasa odpowiada za:
    - ładowanie i zapis stanu (alfa_guard_state.json)
    - rejestrowanie zdarzeń
    - adaptację poziomu ryzyka
    - zwracanie polityki bezpieczeństwa przy próbach odblokowania
    """

    def __init__(self, state_path: str = "alfa_guard_state.json"):
        self.state_path = state_path
        self.state: GuardState = self._load_state()

    # ---------- persistence ----------

    def _load_state(self) -> GuardState:
        if not os.path.exists(self.state_path):
            return GuardState.default()
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return GuardState(**data)
        except Exception:
            return GuardState.default()

    def _save_state(self) -> None:
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self.state), f, indent=2, ensure_ascii=False)

    # ---------- okno czasowe 24h ----------

    def _maybe_reset_window(self, now: Optional[float] = None) -> None:
        if now is None:
            now = time.time()
        if now - self.state.last_reset_ts > 24 * 3600:
            self.state.failed_24h = 0
            self.state.success_24h = 0
            self.state.night_failures = 0
            self.state.day_failures = 0
            self.state.last_reset_ts = now

    # ---------- rejestrowanie zdarzeń ----------

    def record_event(self, event: GuardEvent) -> None:
        """Rejestruje pojedyncze zdarzenie i aktualizuje statystyki."""
        now = event.ts
        self._maybe_reset_window(now)

        if event.kind in ("vault_unlock", "muz_unlock"):
            if event.ok:
                self.state.success_24h += 1
            else:
                self.state.failed_24h += 1
                hour = time.localtime(now).tm_hour
                if hour >= 23 or hour < 6:
                    self.state.night_failures += 1
                else:
                    self.state.day_failures += 1

        self._update_risk(now)
        self._save_state()

    # ---------- logika oceny ryzyka ----------

    def _update_risk(self, now: Optional[float] = None) -> None:
        """
        Prosty silnik uczenia:
        - rosnący risk_level przy wielu porażkach i nietypowych godzinach
        - opadający risk_level przy długim spokoju
        """
        if now is None:
            now = time.time()

        total = self.state.success_24h + self.state.failed_24h
        fail_rate = (self.state.failed_24h / total) if total > 0 else 0.0

        risk = fail_rate

        # Boost dla porażek w nocy
        if self.state.night_failures >= 3 and self.state.night_failures > self.state.day_failures:
            risk += 0.2

        # Samouzdrawianie
        hours_since_reset = (now - self.state.last_reset_ts) / 3600.0
        if self.state.failed_24h == 0 and hours_since_reset > 6:
            risk *= 0.5

        risk = max(0.0, min(1.0, risk))
        self.state.risk_level = risk

        # Blokada przy wysokim ryzyku
        if risk >= 0.8:
            self.state.lockout_until = now + 10 * 60
        elif risk < 0.5 and self.state.lockout_until < now:
            self.state.lockout_until = 0.0

    # ---------- interfejs dla sejfu ----------

    def decide_policy_for_unlock(self, kind: str, source: str = "device-local") -> Dict[str, Any]:
        """Zwraca politykę dla próby odblokowania."""
        now = time.time()
        locked = self.state.lockout_until > now

        policy: Dict[str, Any] = {
            "locked": locked,
            "require_muz": False,
            "log_incident": False,
            "risk_level": self.state.risk_level,
            "lockout_seconds_remaining": max(0, int(self.state.lockout_until - now)),
        }

        if locked:
            policy["log_incident"] = True
            return policy

        if kind == "vault_unlock":
            if self.state.risk_level >= 0.5:
                policy["require_muz"] = True
            if self.state.risk_level >= 0.7:
                policy["log_incident"] = True

        if kind == "muz_unlock":
            if self.state.risk_level >= 0.4:
                policy["log_incident"] = True

        return policy

    def on_unlock_attempt(
        self,
        kind: str,
        ok: bool,
        source: str = "device-local",
        meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Główne wejście: sejf woła to przy każdej próbie.
        Zwraca AKTUALNĄ politykę po zaktualizowaniu stanu.
        """
        if meta is None:
            meta = {}

        ev = GuardEvent(
            ts=time.time(),
            kind=kind,
            ok=ok,
            source=source,
            meta=meta,
        )
        self.record_event(ev)
        return self.decide_policy_for_unlock(kind, source=source)

    def force_reset(self) -> None:
        """Wymuszony reset stanu strażnika."""
        self.state = GuardState.default()
        self._save_state()

    def get_status(self) -> Dict[str, Any]:
        """Zwraca aktualny status strażnika."""
        return {
            "version": self.state.version,
            "risk_level": self.state.risk_level,
            "failed_24h": self.state.failed_24h,
            "success_24h": self.state.success_24h,
            "night_failures": self.state.night_failures,
            "day_failures": self.state.day_failures,
            "is_locked": self.state.lockout_until > time.time(),
            "lockout_remaining": max(0, int(self.state.lockout_until - time.time())),
        }
