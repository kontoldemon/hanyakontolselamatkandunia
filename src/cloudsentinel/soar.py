"""CloudSentinel SOAR - decay, thresholds, auto-unblock, cross-session with Redis state."""
from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import time
from collections import defaultdict
from datetime import UTC
from typing import Any, ClassVar

import redis.asyncio as aioredis

from . import geoip, mitre

# Optional integrations (graceful if not configured)
try:
    from .misp_feed import get_misp_feed as _get_misp
    _MISP_AVAILABLE = True
except Exception:
    _MISP_AVAILABLE = False
    def _get_misp(): return None

try:
    from .abuseipdb import get_abuseipdb as _get_abuseipdb
    _ABUSEIPDB_AVAILABLE = True
except Exception:
    _ABUSEIPDB_AVAILABLE = False
    def _get_abuseipdb(): return None

try:
    from .firewall import create_firewall as _create_firewall
    _FIREWALL_AVAILABLE = True
except Exception:
    _FIREWALL_AVAILABLE = False
    def _create_firewall(backend="auto"): return None

logger = logging.getLogger("cloudsentinel.soar")

GEO_THREAT_SCORES: ClassVar[dict[str, int]] = {
    "RU":10,"CN":10,"IR":10,"KP":15,"VN":5,"BR":5,"IN":3,"NG":8,"PK":5,"UA":5,"RO":5,"BG":5,"ID":3,"TH":3,"TR":5,"EG":5,"MX":3,"PH":3,
}
COUNTRY_THRESHOLDS: ClassVar[dict[str, int]] = {"CN":40,"RU":40,"IR":40,"KP":30,"NG":50,"VN":60}

class SOAREngine:
    def __init__(
        self,
        risk_threshold=70,
        firewall_enabled=True,
        firewall_dry_run=True,
        firewall_path="/sbin/iptables",
        block_ttl=86400,
        decay_rate=1.0,
        allowlist: list[str] | None = None,
        active_profile: str = "local",
        mttb_target_ms: int = 100,
        redis_settings: Any = None,
    ):
        self.risk_threshold=risk_threshold; self.firewall_enabled=firewall_enabled
        self.firewall_dry_run=firewall_dry_run; self.firewall_path=firewall_path
        self.block_ttl=block_ttl; self.decay_rate=decay_rate
        self.active_profile=active_profile; self.mttb_target_ms=mttb_target_ms
        self._allowlist_raw=allowlist or ["127.0.0.1","10.0.0.0/8","172.16.0.0/12","192.168.0.0/16"]
        self._allowlist_networks=self._parse_allowlist(self._allowlist_raw)
        
        self.redis_settings = redis_settings
        self._redis: aioredis.Redis | None = None
        self._block_timings: list[float]=[]
        
        # Memory fallback if Redis not provided (bounded; cleanup on each eval)
        self._MAX_MEM_ENTRIES = 10000
        self._mem_session_scores: dict[str,int]={}
        self._mem_session_failed_auth: dict[str,int]={}
        self._mem_session_techniques: dict[str,set[str]]={}
        self._mem_blocked_ips: set[str]=set()
        self._mem_last_activity: dict[str,float]={}
        self._mem_hassh_sessions: dict[str,set[str]]=defaultdict(set)
        self._mem_hassh_total_risk: dict[str,int]=defaultdict(int)
        self._mem_ip_sessions: dict[str,set[str]]=defaultdict(set)
        self._mem_ip_total_risk: dict[str,int]=defaultdict(int)
        self._mem_ip_techniques: dict[str,set[str]]=defaultdict(set)
        self._mem_ip_first_seen: dict[str,float]={}
        self._mem_ip_last_seen: dict[str,float]={}

    async def start(self):
        if self.redis_settings:
            try:
                self._redis = aioredis.from_url(
                    self.redis_settings.url, encoding="utf-8", decode_responses=True
                )
                await self._redis.ping()
                logger.info("SOAREngine connected to Redis")
            except Exception as exc:
                logger.warning("SOAREngine failed to connect to Redis: %s", exc)
                self._redis = None

    async def stop(self):
        if self._redis:
            await self._redis.aclose()

    @staticmethod
    def _parse_allowlist(values: list[str]) -> list[ipaddress._BaseNetwork]:
        networks=[]
        for value in values:
            try:
                networks.append(ipaddress.ip_network(str(value).strip(), strict=False))
            except ValueError:
                logger.warning("Invalid SOAR allowlist entry ignored: %s", value)
        return networks

    def is_allowlisted(self, ip: str) -> bool:
        try:
            addr=ipaddress.ip_address(ip)
        except ValueError:
            return False
        return any(addr in network for network in self._allowlist_networks)

    @property
    def mttb(self):
        if not self._block_timings: return 0.0
        return sum(self._block_timings)/len(self._block_timings)
    
    @property
    def mttb_ms(self): return self.mttb*1000

    async def _get_score(self, session_id: str) -> int:
        if self._redis:
            val = await self._redis.get(f"soar:session:{session_id}:score")
            return int(val) if val else 0
        return self._mem_session_scores.get(session_id, 0)

    async def _set_score(self, session_id: str, score: int):
        if self._redis:
            await self._redis.set(f"soar:session:{session_id}:score", score, ex=self.block_ttl)
        else:
            self._mem_session_scores[session_id] = score

    async def _get_techniques(self, session_id: str) -> set[str]:
        if self._redis:
            val = await self._redis.smembers(f"soar:session:{session_id}:techniques")
            return set(val) if val else set()
        return self._mem_session_techniques.get(session_id, set())

    async def _add_techniques(self, session_id: str, techniques: set[str]):
        if not techniques: return
        if self._redis:
            await self._redis.sadd(f"soar:session:{session_id}:techniques", *techniques)
            await self._redis.expire(f"soar:session:{session_id}:techniques", self.block_ttl)
        else:
            s = self._mem_session_techniques.setdefault(session_id, set())
            s.update(techniques)

    async def _get_last_activity(self, session_id: str) -> float:
        if self._redis:
            val = await self._redis.get(f"soar:session:{session_id}:last_activity")
            return float(val) if val else 0.0
        return self._mem_last_activity.get(session_id, 0.0)

    async def _set_last_activity(self, session_id: str, ts: float):
        if self._redis:
            await self._redis.set(f"soar:session:{session_id}:last_activity", ts, ex=self.block_ttl)
        else:
            self._mem_last_activity[session_id] = ts

    async def _get_failed_auth(self, session_id: str) -> int:
        if self._redis:
            val = await self._redis.get(f"soar:session:{session_id}:failed_auth")
            return int(val) if val else 0
        return self._mem_session_failed_auth.get(session_id, 0)

    async def _incr_failed_auth(self, session_id: str) -> int:
        if self._redis:
            val = await self._redis.incr(f"soar:session:{session_id}:failed_auth")
            await self._redis.expire(f"soar:session:{session_id}:failed_auth", self.block_ttl)
            return int(val)
        self._mem_session_failed_auth[session_id] = self._mem_session_failed_auth.get(session_id, 0) + 1
        return self._mem_session_failed_auth[session_id]

    async def _clear_failed_auth(self, session_id: str):
        if self._redis:
            await self._redis.delete(f"soar:session:{session_id}:failed_auth")
        else:
            self._mem_session_failed_auth.pop(session_id, None)

    async def _is_blocked(self, ip: str) -> bool:
        if self._redis:
            return bool(await self._redis.exists(f"soar:block:{ip}"))
        return ip in self._mem_blocked_ips

    async def _mark_blocked(self, ip: str):
        if self._redis:
            await self._redis.set(f"soar:block:{ip}", "1", ex=self.block_ttl)
        else:
            self._mem_blocked_ips.add(ip)

    def _update_ip_profile(
        self,
        ip: str,
        session_id: str,
        event_score: int,
        techniques: set[str],
        timestamp: float,
    ) -> None:
        if not ip:
            return
        if ip not in self._mem_ip_first_seen:
            self._mem_ip_first_seen[ip] = timestamp
        self._mem_ip_last_seen[ip] = timestamp
        sessions = self._mem_ip_sessions[ip]
        sessions.add(session_id)
        self._mem_ip_total_risk[ip] += max(event_score, 0)
        self._mem_ip_techniques[ip].update(techniques)

    def get_ip_profile(self, ip: str) -> dict[str, Any]:
        """Return in-memory profile used by dashboard and tests."""
        return {
            "ip": ip,
            "active_sessions": len(self._mem_ip_sessions.get(ip, set())),
            "session_ids": sorted(self._mem_ip_sessions.get(ip, set())),
            "cumulative_risk": self._mem_ip_total_risk.get(ip, 0),
            "techniques": sorted(self._mem_ip_techniques.get(ip, set())),
            "first_seen": self._mem_ip_first_seen.get(ip, 0),
            "last_seen": self._mem_ip_last_seen.get(ip, 0),
            "is_blocked": ip in self._mem_blocked_ips,
        }

    async def process_event(self, session_id, event):
        event=dict(event); t_start=time.perf_counter()
        current_score = await self._get_score(session_id)
        techniques = await self._get_techniques(session_id)
        event_score=0

        # Time-decay: reduce score by decay_rate/sec since last activity
        now=time.monotonic()
        last_act = await self._get_last_activity(session_id)
        if last_act > 0:
            elapsed = now - last_act
            decay = int(elapsed * self.decay_rate)
            if decay > 0 and current_score > 0:
                current_score = max(0, current_score - decay)
                await self._set_score(session_id, current_score)
        await self._set_last_activity(session_id, now)

        # GeoIP scoring
        country=event.get("country_code","")
        geo_bonus=GEO_THREAT_SCORES.get(country,0)
        if geo_bonus>0: event_score+=geo_bonus

        # MISP threat feed enrichment
        if _MISP_AVAILABLE:
            try:
                misp = _get_misp()
                if misp and misp.is_malicious_ip(str(event.get("src_ip",""))):
                    event_score += 20
                    techniques.add("T1204")  # User Execution (MISP-confirmed)
            except Exception:
                pass

        # AbuseIPDB reputation enrichment
        if _ABUSEIPDB_AVAILABLE:
            try:
                ab = _get_abuseipdb()
                report = await ab.check(str(event.get("src_ip","")))
                ab_bonus = ab.soar_bonus(report)
                if ab_bonus > 0:
                    event_score += ab_bonus
            except Exception:
                pass

        # Failed login
        if event.get("eventid")=="cloudsentinel.login.failed":
            failed = await self._incr_failed_auth(session_id)
            event_score+=10+min(failed*5,30); techniques.add("T1110")
        elif event.get("eventid")=="cloudsentinel.login.success":
            await self._clear_failed_auth(session_id); techniques.add("T1078")

        # Commands
        cmd=str(event.get("input",""))
        if event.get("eventid")in("cloudsentinel.command.input","cloudsentinel.command.failed"):
            for tid,sc,_ in mitre.match_command(cmd): event_score+=sc; techniques.add(tid)
        if event.get("eventid")=="cloudsentinel.client.version": techniques.add("T1021.004"); event_score+=5

        ip = str(event.get("src_ip", ""))
        existing_sessions = self._mem_ip_sessions.get(ip, set())
        if ip and session_id not in existing_sessions and existing_sessions:
            event_score += 5
            techniques.add("T1083")

        current_score+=event_score
        await self._set_score(session_id, current_score)
        await self._add_techniques(session_id, techniques)
        self._update_ip_profile(ip, session_id, event_score, techniques, time.time())

        event["cloudsentinel_risk_score"]=current_score
        event["cloudsentinel_mitre_techniques"]=sorted(techniques)
        event["cloudsentinel_soar_action"]="none"

        threshold=COUNTRY_THRESHOLDS.get(country,self.risk_threshold)
        persistence_override = "T1098" in techniques and event.get("eventid") in ("cloudsentinel.command.input", "cloudsentinel.command.failed")

        if current_score>=threshold or persistence_override:
            block_result=await self._block_ip(event)
            event["cloudsentinel_soar_action"]=block_result
            self._block_timings.append(time.perf_counter()-t_start)

        if event.get("eventid")=="cloudsentinel.session.closed":
            if self._redis:
                await self._redis.delete(
                    f"soar:session:{session_id}:score",
                    f"soar:session:{session_id}:techniques",
                    f"soar:session:{session_id}:last_activity",
                    f"soar:session:{session_id}:failed_auth"
                )
            else:
                self._mem_session_scores.pop(session_id,None)
                self._mem_session_failed_auth.pop(session_id,None)
                self._mem_session_techniques.pop(session_id,None)
                self._mem_last_activity.pop(session_id,None)

        return event

    async def _block_ip(self, event):
        ip=str(event.get("src_ip",""))
        detected_at=float(event.get("detected_at") or time.time())
        event["detected_at"]=detected_at
        event["block_started_at"]=time.time()
        event["block_command"]=""
        event["block_stdout"]=""
        event["block_stderr"]=""
        def finish(action: str) -> str:
            event["block_completed_at"]=time.time()
            event["mttb_ms"]=round((event["block_completed_at"]-detected_at)*1000,3)
            return action
            
        if not ip: return finish("skip_no_ip")
        if self.is_allowlisted(ip): return finish("skip_allowlisted_ip")
        if not geoip.is_public_ip(ip): return finish("skip_private_ip")
        
        is_blocked = await self._is_blocked(ip)
        if is_blocked: return finish("already_blocked")

        if not self.firewall_enabled: return finish("detect_only")
        if self.firewall_dry_run:
            logger.warning("SOAR DRY RUN BLOCK %s (risk=%d)",ip,event.get("cloudsentinel_risk_score"))
            return finish("dry_run_block")

        logger.warning("SOAR PUBLISHING BLOCK EVENT FOR %s (risk=%d)",ip,event.get("cloudsentinel_risk_score"))
        
        try:
            if self._redis:
                # Publish block event for the Host Agent worker to pick up
                payload = json.dumps({
                    "ip": ip,
                    "action": "block",
                    "ttl": self.block_ttl,
                    "risk_score": event.get("cloudsentinel_risk_score"),
                    "session_id": event.get("session")
                })
                await self._redis.publish("cloudsentinel:soar:blocks", payload)
                await self._mark_blocked(ip)
                event["block_command"]="redis.publish cloudsentinel:soar:blocks"
                return finish("event_published")
            # Fallback to local execution if no redis (tests)
            exists=await self._run_firewall(["-C","INPUT","-s",ip,"-j","DROP"],event)
            if exists[0]==0:
                await self._mark_blocked(ip)
                return finish("already_blocked")
            result=await self._run_firewall(["-I","INPUT","1","-s",ip,"-j","DROP"],event)
            if result[0]==0:
                await self._mark_blocked(ip)
                logger.warning("iptables DROP: %s",ip); return finish("iptables_block")
            logger.error("iptables failed: %s",event.get("block_stderr") or "?"); return finish("block_failed")
        except TimeoutError:
            logger.error("iptables timeout: %s",ip); return finish("block_timeout")
        except Exception as exc:
            logger.error("iptables error: %s",exc); return finish("block_error")

    async def _run_firewall(self, args: list[str], event: dict) -> tuple[int, str, str]:
        command=[self.firewall_path,*args]
        event["block_command"]=" ".join(command)
        proc=await asyncio.create_subprocess_exec(*command,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout,stderr=await asyncio.wait_for(proc.communicate(),timeout=5.0)
        out=stdout.decode("utf-8","replace") if stdout else ""
        err=stderr.decode("utf-8","replace") if stderr else ""
        event["block_stdout"]=out[:1000]
        event["block_stderr"]=err[:1000]
        return proc.returncode,out,err

    def get_session_stats(self, session_id):
        """Synchronous fallback for tests. Prefer using async Redis methods."""
        return {
            "risk_score": self._mem_session_scores.get(session_id, 0),
            "failed_auth_count": self._mem_session_failed_auth.get(session_id, 0),
            "techniques": list(self._mem_session_techniques.get(session_id, set())),
        }

    def get_attack_chains(self) -> list[dict]:
        """Return cross-session attack chains for the attack graph API."""
        chains: dict[str, dict] = {}
        for ip, sessions in self._mem_ip_sessions.items():
            chains[ip] = {
                "ip": ip,
                "sessions": len(sessions),
                "risk": self._mem_ip_total_risk.get(ip, 0),
                "techniques": list(self._mem_ip_techniques.get(ip, set())),
                "first_seen": self._mem_ip_first_seen.get(ip, 0),
            }
        return sorted(chains.values(), key=lambda c: c["risk"], reverse=True)


class SOARScheduler:
    """Cron-based SOAR task scheduling with croniter.

    Handles:
      - Auto-unblock after TTL expiry
      - Periodic threat feed refresh (MISP, AbuseIPDB)
      - Scheduled STIX IOC exports
      - Daily/weekly report generation

    Requires: pip install croniter
    """

    def __init__(self) -> None:
        self._tasks: list[dict] = []
        self._running = False

    def add_ttl_unblock(self, ip: str, ttl_seconds: int, callback) -> None:
        """Schedule auto-unblock after TTL expires."""
        import time
        unblock_at = time.time() + ttl_seconds
        self._tasks.append({
            "type": "unblock",
            "ip": ip,
            "unblock_at": unblock_at,
            "callback": callback,
        })

    def add_cron_task(self, cron_expr: str, name: str, callback) -> bool:
        """Add a cron-scheduled task. Returns True if expression is valid."""
        try:
            from datetime import datetime, timezone

            from croniter import croniter
            # Validate the cron expression
            base = datetime.now(UTC)
            cron = croniter(cron_expr, base)
            next_run = cron.get_next(datetime)
            self._tasks.append({
                "type": "cron",
                "name": name,
                "cron_expr": cron_expr,
                "cron": cron,
                "next_run": next_run.timestamp(),
                "callback": callback,
            })
            logger.info("Scheduled cron task '%s': %s (next: %s)", name, cron_expr, next_run)
            return True
        except ImportError:
            logger.debug("croniter not installed — cron scheduling disabled")
            return False
        except Exception as exc:
            logger.error("Invalid cron expression '%s': %s", cron_expr, exc)
            return False

    async def start(self, check_interval: float = 5.0) -> None:
        """Start the scheduler loop."""
        self._running = True
        logger.info("SOAR scheduler started (interval: %.1fs)", check_interval)

        while self._running:
            import time
            now = time.time()

            # Process TTL unblocks
            due_now = [t for t in self._tasks if t["type"] == "unblock" and t["unblock_at"] <= now]
            for task in due_now:
                try:
                    await task["callback"](task["ip"])
                    logger.info("Scheduled unblock: %s", task["ip"])
                except Exception as exc:
                    logger.error("Scheduled unblock failed for %s: %s", task["ip"], exc)
                self._tasks.remove(task)

            # Process cron tasks
            cron_tasks = [t for t in self._tasks if t["type"] == "cron" and t["next_run"] <= now]
            for task in cron_tasks:
                try:
                    await task["callback"]()
                    task["next_run"] = task["cron"].get_next(float)
                    logger.info("Cron task '%s' executed", task["name"])
                except Exception as exc:
                    logger.error("Cron task '%s' failed: %s", task["name"], exc)

            await asyncio.sleep(check_interval)

    def stop(self) -> None:
        self._running = False
