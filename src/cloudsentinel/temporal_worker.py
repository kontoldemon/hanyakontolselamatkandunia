"""
CloudSentinel Temporal.io Worker — durable SOAR execution engine.

Temporal guarantees SOAR workflows survive sensor crashes, restarts,
and network partitions. Block actions are durable — if the sensor
goes down mid-block, Temporal replays and completes on restart.

Architecture:
  Sensor (server.py) → Temporal Client → Temporal Server → Worker → iptables

Requires: temporalio (already in requirements.txt)
          Temporal server (docker run temporalio/auto-setup:latest)
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import structlog

logger = structlog.get_logger("cloudsentinel.temporal")


@dataclass
class SOARBlockInput:
    ip: str
    reason: str = ""
    risk_score: int = 0
    mitre_techniques: list[str] | None = None
    hassh_md5: str = ""
    country_code: str = ""
    ttl_seconds: int = 86400


class TemporalSOARWorker:
    """Temporal worker that executes durable SOAR blocking workflows."""

    def __init__(
        self,
        temporal_host: str = "",
        temporal_namespace: str = "cloudsentinel",
        task_queue: str = "soar-blocks",
        firewall_path: str = "/sbin/iptables",
        allowlist: list[str] | None = None,
    ) -> None:
        self.temporal_host = temporal_host or os.getenv("TEMPORAL_HOST", "localhost:7233")
        self.namespace = temporal_namespace
        self.task_queue = task_queue
        self.firewall_path = firewall_path
        self.allowlist = allowlist or ["127.0.0.1", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
        self._client: Any = None
        self._worker: Any = None
        self._available = False

    async def start(self) -> None:
        """Connect to Temporal server and start the worker."""
        try:
            from temporalio import activity, workflow
            from temporalio.client import Client
            from temporalio.worker import Worker

            self._client = await Client.connect(
                self.temporal_host,
                namespace=self.namespace,
            )

            # Define activities inline to avoid circular imports
            @activity.defn
            async def block_ip_activity(ip: str, reason: str, ttl: int) -> dict:
                """Durable iptables block — replayed on crash."""
                proc = await asyncio.create_subprocess_exec(
                    self.firewall_path, "-A", "INPUT", "-s", ip, "-j", "DROP",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
                if proc.returncode == 0:
                    logger.info("Temporal: blocked %s (%s)", ip, reason)
                    return {"status": "blocked", "ip": ip}
                err = stderr.decode()[:200] if stderr else "unknown"
                logger.error("Temporal: block failed for %s: %s", ip, err)
                raise RuntimeError(f"iptables block failed: {err}")

            @activity.defn
            async def unblock_ip_activity(ip: str) -> dict:
                proc = await asyncio.create_subprocess_exec(
                    self.firewall_path, "-D", "INPUT", "-s", ip, "-j", "DROP",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=5.0)
                logger.info("Temporal: unblocked %s", ip)
                return {"status": "unblocked", "ip": ip}

            @activity.defn
            async def log_block_activity(input_data: dict) -> None:
                logger.info(
                    "Temporal SOAR: blocked %s risk=%d ttp=%s",
                    input_data.get("ip", "?"),
                    input_data.get("risk_score", 0),
                    input_data.get("mitre_techniques", []),
                )

            # Workflow definition
            @workflow.defn
            class SOARBlockWorkflow:
                @workflow.run
                async def run(self, input_data: SOARBlockInput) -> dict:
                    # Check allowlist first
                    import ipaddress
                    try:
                        addr = ipaddress.ip_address(input_data.ip)
                        for net_str in self.allowlist if hasattr(self, 'allowlist') else []:
                            if addr in ipaddress.ip_network(net_str, strict=False):
                                return {"status": "allowlisted", "ip": input_data.ip}
                    except ValueError:
                        pass

                    # Execute block
                    result = await workflow.execute_activity(
                        block_ip_activity,
                        args=[input_data.ip, input_data.reason, input_data.ttl_seconds],
                        start_to_close_timeout=timedelta(seconds=10),
                        retry_policy={"maximum_attempts": 3, "initial_interval": timedelta(seconds=1)},
                    )

                    # Log for audit
                    await workflow.execute_activity(
                        log_block_activity,
                        args=[{
                            "ip": input_data.ip,
                            "risk_score": input_data.risk_score,
                            "mitre_techniques": input_data.mitre_techniques or [],
                        }],
                        start_to_close_timeout=timedelta(seconds=5),
                    )

                    # Schedule auto-unblock after TTL
                    await asyncio.sleep(input_data.ttl_seconds)
                    await workflow.execute_activity(
                        unblock_ip_activity,
                        args=[input_data.ip],
                        start_to_close_timeout=timedelta(seconds=10),
                    )

                    return {"status": "blocked_and_released", "ip": input_data.ip}

            self._worker = Worker(
                self._client,
                task_queue=self.task_queue,
                workflows=[SOARBlockWorkflow],
                activities=[block_ip_activity, unblock_ip_activity, log_block_activity],
            )

            self._available = True
            logger.info("Temporal SOAR worker started on %s (queue: %s)", self.temporal_host, self.task_queue)

        except ImportError:
            logger.debug("temporalio not installed — using asyncio fallback")
            self._available = False
        except Exception as exc:
            logger.warning("Temporal connection failed: %s — falling back to local SOAR", exc)
            self._available = False

    async def run(self) -> None:
        """Run the worker (blocks until cancelled)."""
        if self._worker and self._available:
            await self._worker.run()

    async def enqueue_block(self, input_data: SOARBlockInput) -> str | None:
        """Enqueue a durable SOAR block workflow. Returns workflow_id."""
        if not self._available or not self._client:
            return None
        try:
            workflow_id = f"soar-block-{input_data.ip.replace('.', '-')}-{int(asyncio.get_event_loop().time())}"
            await self._client.start_workflow(
                "SOARBlockWorkflow",
                input_data,
                id=workflow_id,
                task_queue=self.task_queue,
            )
            logger.info("Temporal: enqueued block workflow %s for %s", workflow_id, input_data.ip)
            return workflow_id
        except Exception as exc:
            logger.error("Temporal: failed to enqueue block for %s: %s", input_data.ip, exc)
            return None

    async def stop(self) -> None:
        if self._worker:
            await self._worker.shutdown()
        if self._client:
            await self._client.close()
        self._available = False

    @property
    def available(self) -> bool:
        return self._available
