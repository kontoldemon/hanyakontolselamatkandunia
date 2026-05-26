"""CloudSentinel Interactive Shell - exec, pipe, redirect, TAB, TTY-logging."""
from __future__ import annotations
import asyncio, logging, shlex, time, uuid
from pathlib import Path
from typing import Any
from . import geoip
from .commands import Command
from .commands.base import commands as cmd_registry
from .vfs import VirtualFileSystem
logger = logging.getLogger("cloudsentinel.shell")

class HoneyPotInteractiveProtocol:
    def __init__(self, transport, vfs, username="root", uid=0, gid=0, home="/root", hostname="usas-prod-srv-01", ip="0.0.0.0", session_id=None):
        self.transport=transport; self.pp=transport; self.fs=vfs
        self.username=username; self.uid=uid; self.gid=gid; self.home=home
        self.cwd=home; self.hostname=hostname; self.realClientIP=ip; self.clientIP=ip
        self.sessionno=session_id or uuid.uuid4().hex[:12]
        self.logintime=time.time(); self.starttime=time.time()
        self.environ={"HOME":home,"LOGNAME":username,"SHELL":"/bin/bash","SHLVL":"1","TMOUT":"1800","UID":str(uid),"USER":username,"PWD":home,"?":"0"}
        self.environ["PATH"]="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" if uid==0 else "/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games"
        self.cmdstack=[]; self.line_buffer=b""; self._closed=False
        self._event_handler=None; self._exec_command=None; self._exit_code=0
        self._tty_log=[]; self._tty_dir=None
        if not vfs.exists(home): vfs.mkdir(home,uid,gid,4096,0o755)

    def _init_tty_log(self):
        try: self._tty_dir=Path(__file__).resolve().parent.parent.parent / "var" / "lib" / "cloudsentinel" / "tty" / self.sessionno; self._tty_dir.mkdir(parents=True,exist_ok=True)
        except: self._tty_dir=None
    def _save_tty_log(self):
        if not self._tty_dir: return
        try:
            with open(self._tty_dir/"tty.log","wb")as fh:
                for ts,data in self._tty_log: fh.write(f"[{ts:.3f}] ".encode()+data+b"\n")
            with open(self._tty_dir/"tty.raw","wb")as fh:
                for _,data in self._tty_log: fh.write(data)
        except Exception as exc: logger.debug("TTY save failed: %s",exc)

    async def run(self):
        self._init_tty_log(); self._send_motd(); self.show_prompt()
        try:
            while not self._closed:
                data=await self.transport.read(4096)
                if not data: break
                self._tty_log.append((time.time(),data)); self._handle_data(data)
        except Exception as exc: logger.debug("Shell %s ended: %s",self.sessionno,exc)
        finally: self._closed=True; self._save_tty_log()

    async def run_exec(self):
        self._init_tty_log(); cmd=self._exec_command or""
        logger.info("Exec %s: %s",self.sessionno,cmd)
        self._dispatch_line(cmd.encode("utf-8",errors="replace"))
        await asyncio.sleep(0.5)
        try: self.pp.close()
        except: pass
        self._save_tty_log()
        self.emit_event({"eventid":"cloudsentinel.session.closed","session":self.sessionno,"src_ip":self.realClientIP,"duration":f"{time.time()-self.logintime:.1f}"})

    def _handle_data(self, data):
        for byte in data:
            b=bytes([byte])
            if b==b"\x03":
                if self.cmdstack: self.cmdstack[-1].handle_CTRL_C()
                else: self.write(b"^C\r\n"); self.show_prompt()
                continue
            if b==b"\x04":
                if not self.cmdstack: self.write(b"logout\r\n"); self._closed=True; self.pp.close(); return
                continue
            if b==b"\t":
                self.write(b"\x07")  # Bell = no completions (real bash behavior)
                continue
            if b in(b"\x7f",b"\x08"):
                if self.line_buffer: self.line_buffer=self.line_buffer[:-1]; self.write(b"\b \b")
                continue
            if b in(b"\r",b"\n"):
                self.write(b"\r\n"if b==b"\r"else b"\n")
                if self.line_buffer: self._dispatch_line(self.line_buffer)
                else: self.show_prompt()
                self.line_buffer=b""; continue
            if 32<=byte<127: self.line_buffer+=b; self.write(b)

    def _dispatch_line(self, line):
        try: line_str=line.decode("utf-8",errors="replace").strip()
        except: self.show_prompt(); return
        if not line_str: self.show_prompt(); return

        self.emit_event({"eventid":"cloudsentinel.command.input","session":self.sessionno,"input":line_str,"username":self.username,"src_ip":self.realClientIP,"timestamp":time.time()})

        # Pipe chain: split on | and execute both sides
        if "|" in line_str:
            segments=[s.strip()for s in line_str.split("|")if s.strip()]
            for seg in segments: self._execute_single(seg.encode())
            self.show_prompt(); return

        # I/O redirect: strip > and < and execute command part
        if ">" in line_str or "<" in line_str:
            cmd_part=line_str.split(">")[0].split("<")[0].strip()
            if cmd_part: self._execute_single(cmd_part.encode())
            else: self._exit_code=0
            self.show_prompt(); return

        self._execute_single(line)

    def _execute_single(self, line):
        try: line_str=line.decode("utf-8",errors="replace").strip()
        except: return
        if not line_str: return
        try: parts=shlex.split(line_str)
        except ValueError: parts=line_str.split()
        if not parts: return
        cmd_name=parts[0]; args=parts[1:]

        if cmd_name in("cd","/usr/bin/cd"): self._handle_cd(args); return
        if cmd_name in("exit","logout"): self.write(b"logout\r\n"); self._closed=True; self.pp.close(); return

        cmd_cls=self._resolve_command(cmd_name); self._exit_code=0
        if cmd_cls is None:
            self.write(f"-bash: {cmd_name}: command not found\r\n".encode()); self._exit_code=127; self.environ["?"]=str(127)
            self.emit_event({"eventid":"cloudsentinel.command.failed","session":self.sessionno,"input":line_str,"username":self.username,"src_ip":self.realClientIP,"reason":"command_not_found","timestamp":time.time()})
            self.show_prompt(); return
        try:
            cmd=cmd_cls(self,*args); self.cmdstack.append(cmd); cmd.start()
        except Exception as exc:
            logger.error("Cmd %s failed: %s",cmd_name,exc)
            self.write(f"-bash: {cmd_name}: internal error\r\n".encode()); self._exit_code=1

    def _resolve_command(self, name):
        if name in cmd_registry: return cmd_registry[name]
        for prefix in("/usr/bin/","/bin/","/usr/sbin/","/sbin/"):
            if prefix+name in cmd_registry: return cmd_registry[prefix+name]
        return None

    def _handle_cd(self, args):
        target=self.home if not args else(self.home if args[0]=="-"else args[0])
        new_path=self.fs.resolve_path(target,self.cwd)
        if self.fs.isdir(new_path): self.cwd=new_path; self.environ["PWD"]=new_path
        else: self.write(f"-bash: cd: {target}: No such file or directory\r\n".encode())

    def show_prompt(self):
        if self.cwd==self.home: cd="~"
        elif self.cwd=="/": cd="/"
        elif self.cwd.startswith(self.home+"/"): cd="~"+self.cwd[len(self.home):]
        else: cd=self.cwd
        pc="#"if self.uid==0 else"$"
        self.write(f"\x1b[1;32m{self.username}@{self.hostname}\x1b[0m:\x1b[1;34m{cd}\x1b[0m{pc} ".encode())

    def write(self, data):
        if isinstance(data,str): data=data.encode("utf-8")
        try: self.pp.write(data)
        except: pass
    def write_stdout(self, data): self.write(data)
    def write_stderr(self, data): self.write(data)
    def _send_motd(self):
        try: self.write(self.fs.file_contents("/etc/motd")+b"\r\n")
        except: pass
    def uptime(self):
        delta=int(time.time()-self.starttime)
        d=delta//86400; h=(delta%86400)//3600; m=(delta%3600)//60
        if d: return f"{d} days, {h:2d}:{m:02d}"
        if h: return f"{h:2d}:{m:02d}"
        return f"{m} min"
    def emit_event(self, event):
        event.update(geoip.enrich(self.realClientIP))
        if self._event_handler: self._event_handler(event)
