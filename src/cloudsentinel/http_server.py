"""HTTP Deception Listener for CloudSentinel — SOAR-integrated."""

from __future__ import annotations

import asyncio
import structlog
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .pipeline import EventEnvelope, EventPipeline

logger = structlog.get_logger("cloudsentinel.http")


def create_http_honeypot(pipeline: EventPipeline, soar: Any = None) -> FastAPI:
    """Creates an HTTP honeypot catching automated exploitation with SOAR scoring."""

    app = FastAPI(title="CloudSentinel HTTP Honeypot", docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def log_requests(request: Request, call_next: Any):
        start_time = time.time()
        session_id = uuid.uuid4().hex
        client_host = request.client.host if request.client else "0.0.0.0"
        client_port = request.client.port if request.client else 0
        body = b""
        try:
            body = await request.body()
        except Exception:
            pass
        response = await call_next(request)
        url_path = str(request.url)
        risk = 5
        mitre_techniques = ["T1190"]
        if any(x in url_path.lower() for x in ("wp-login", "wp-admin", "xmlrpc")):
            risk = 15
            mitre_techniques.append("T1110")
        elif any(x in url_path.lower() for x in ("admin", "login", "config", ".env", ".git")):
            risk = 12
            mitre_techniques.append("T1082")
        elif any(x in url_path.lower() for x in ("manager/html", "jenkins", "tomcat")):
            risk = 20
        elif any(x in url_path.lower() for x in (".php", ".asp", ".jsp", ".aspx", "shell", "cmd")):
            risk = 25
            mitre_techniques.append("T1505.003")
        payload = {
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "body": body.decode("utf-8", errors="replace")[:1000],
            "status_code": response.status_code,
            "risk_score": risk,
            "mitre_techniques": mitre_techniques,
        }
        if soar is not None:
            event = {
                "eventid": "http.request",
                "session": session_id,
                "src_ip": client_host,
                "src_port": client_port,
                "timestamp": start_time,
                "input": f"{request.method} {url_path}",
                "cloudsentinel_risk_score": risk,
                "cloudsentinel_mitre_techniques": mitre_techniques,
            }
            try:
                soar_result = await soar.process_event(session_id, event)
                payload["soar_action"] = soar_result.get("cloudsentinel_soar_action", "none")
                payload["soar_risk_score"] = soar_result.get("cloudsentinel_risk_score", risk)
            except Exception:
                pass
        envelope = EventEnvelope(
            event_type="http.request",
            session_id=session_id,
            src_ip=client_host,
            src_port=client_port,
            timestamp=start_time,
            payload=payload,
        )
        asyncio.create_task(pipeline.emit(envelope))
        return response

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
    async def catch_all(request: Request, path: str):
        path_lower = path.lower()
        if "wp-login" in path_lower or "wp-admin" in path_lower:
            return HTMLResponse(content=WP_LOGIN_HTML, status_code=200)
        if "manager/html" in path_lower or "jenkins" in str(request.headers).lower():
            return HTMLResponse(
                content=TOMCAT_401_HTML, status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Tomcat Manager Application"'},
            )
        if "phpmyadmin" in path_lower:
            return HTMLResponse(content=PHPMYADMIN_HTML, status_code=200)
        if ".env" in path_lower:
            return JSONResponse(
                content={
                    "APP_ENV": "production",
                    "DB_HOST": "10.0.0.50",
                    "DB_PASSWORD": "honeypot_fake_credential_2026",
                    "REDIS_URL": "redis://internal-redis:6379",
                },
                status_code=200,
            )
        return JSONResponse(
            content={"error": "Not Found"},
            status_code=404,
        )

    return app


WP_LOGIN_HTML = '''<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en-US">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <title>Log In &lsaquo; WordPress</title>
    <meta name="viewport" content="width=device-width" />
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
               background: #f0f0f1; display: flex; justify-content: center; padding-top: 8%; }
        #login { width: 320px; background: #fff; padding: 26px 24px; border: 1px solid #c3c4c7;
                 box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
        #login h1 { text-align: center; margin-bottom: 1.5em; }
        #login form { margin-top: 20px; }
        #login label { font-size: 14px; color: #3c434a; display: block; margin-bottom: 3px; }
        #login input[type="text"], #login input[type="password"] {
            width: 100%; padding: 3px 8px; font-size: 24px; line-height: 2; min-height: 40px;
            border: 1px solid #8c8f94; margin-bottom: 16px; box-sizing: border-box; }
        #login .button {
            background: #2271b1; border: none; color: #fff; padding: 0 14px;
            font-size: 14px; line-height: 2.7; min-height: 32px; cursor: pointer;
            float: right; border-radius: 3px; }
        #login .button:hover { background: #135e96; }
        #nav { text-align: center; margin-top: 24px; font-size: 13px; }
        #nav a { color: #50575e; text-decoration: none; }
    </style>
</head>
<body class="login">
<div id="login">
    <h1><a href="https://wordpress.org/">USAS Corporate Portal</a></h1>
    <form name="loginform" id="loginform" method="post">
        <p><label for="user_login">Username or Email Address</label>
        <input type="text" name="log" id="user_login" class="input" value="" size="20" /></p>
        <p><label for="user_pass">Password</label>
        <input type="password" name="pwd" id="user_pass" class="input" value="" size="20" /></p>
        <p class="submit"><input type="submit" name="wp-submit" id="wp-submit"
        class="button button-primary button-large" value="Log In" /></p>
    </form>
    <p id="nav"><a href="/wp-login.php?action=lostpassword">Lost your password?</a></p>
</div>
</body>
</html>
'''

TOMCAT_401_HTML = '''<html><head><title>401 Unauthorized</title></head>
<body><h1>401 Unauthorized</h1>
<p>This server could not verify that you are authorized to access.</p>
</body></html>'''

PHPMYADMIN_HTML = '''<html><head><title>phpMyAdmin</title></head>
<body><h1>Welcome to phpMyAdmin</h1>
<p>MySQL is running on localhost:3306</p></body></html>'''
