"""CloudSentinel commands - 55+ Linux utilities for full attacker deception."""

from __future__ import annotations

import re
import time

from . import Command

commands: dict[str, type[Command]] = {}

def register(path: str):
    def _d(cls: type[Command]):
        commands[path] = cls
        if "/" in path: commands[path.split("/")[-1]] = cls
        return cls
    return _d

# ── Identity ───────────────────────────────────────────────────────

@register("/usr/bin/whoami")
class Whoami(Command):
    def call(self): self.write(f"{self.protocol.username}\n")
@register("/usr/bin/id")
class Id(Command):
    def call(self):
        u = self.protocol.username; uid = getattr(self.protocol, "uid", 0); gid = getattr(self.protocol, "gid", 0)
        self.write(f"uid={uid}({u}) gid={gid}({u}) groups={gid}({u})\n")
@register("/usr/bin/who")
class Who(Command):
    def call(self):
        u = self.protocol.username; t = getattr(self.protocol, "logintime", time.time())
        ip = getattr(self.protocol, "clientIP", "0.0.0.0")
        self.write(f"{u:8s} pts/0        {time.strftime('%Y-%m-%d', time.localtime(t))} {time.strftime('%H:%M', time.localtime(t))} ({ip})\n")
@register("/usr/bin/w")
class W(Command):
    def call(self):
        u = self.protocol.username; t = getattr(self.protocol, "logintime", time.time())
        ip = getattr(self.protocol, "clientIP", "0.0.0.0")
        up = getattr(self.protocol, "uptime", lambda: "0 min")()
        self.write(f" {time.strftime('%H:%M:%S')} up {up},  1 user,  load average: 0.00, 0.00, 0.00\nUSER     TTY      FROM              LOGIN@   IDLE   JCPU   PCPU WHAT\n{u:8s} pts/0    {ip[:17].ljust(17)} {time.strftime('%H:%M', time.localtime(t))}    0.00s  0.00s  0.00s w\n")

# ── Output ─────────────────────────────────────────────────────────

@register("/bin/echo")
class Echo(Command):
    def call(self):
        if not self.args: self.write("\n"); return
        o = " ".join(self.args); nl = True
        if o.startswith("-n "): o = o[3:]; nl = False
        elif o == "-n": return
        self.write(o + ("\n" if nl else ""))
@register("/usr/bin/printf")
class Printf(Command):
    def call(self):
        if self.args: self.write(self.args[0].replace(r"\n", "\n").replace(r"\t", "\t") + "\n")

# ── System info ────────────────────────────────────────────────────

@register("/usr/bin/uname")
class Uname(Command):
    def call(self):
        f = "".join(a for a in self.args if a.startswith("-"))
        if not f: self.write("Linux\n"); return
        p = []; hn = getattr(self.protocol, "hostname", "usas-prod-srv-01")
        if "s" in f or "a" in f: p.append("Linux")
        if "n" in f or "a" in f: p.append(hn)
        if "r" in f or "a" in f: p.append("5.15.0-97-generic")
        if "v" in f or "a" in f: p.append("#107-Ubuntu SMP Thu Feb 15 15:00:00 UTC 2024")
        if "m" in f or "a" in f: p.append("x86_64")
        if "p" in f or "a" in f: p.append("x86_64")
        if "i" in f or "a" in f: p.append("x86_64")
        if "o" in f or "a" in f: p.append("GNU/Linux")
        self.write(" ".join(p) + "\n")
@register("/usr/bin/lscpu")
class Lscpu(Command):
    def call(self): self.write("Architecture: x86_64\nCPU(s): 4\nModel name: Intel(R) Xeon(R) Platinum 8259CL CPU @ 2.50GHz\nThread(s) per core: 1\nCore(s) per socket: 4\nSocket(s): 1\nVirtualization: KVM\n")
@register("/usr/bin/free")
class Free(Command):
    def call(self): self.write("               total        used        free      shared  buff/cache   available\nMem:         4026348      523176     2765368        1232      737804     3195124\nSwap:        1048572           0     1048572\n")
@register("/usr/bin/uptime")
class Uptime(Command):
    def call(self):
        uf = getattr(self.protocol, "uptime", lambda: "0 min")
        up = uf() if callable(uf) else "0 min"
        self.write(f" {time.strftime('%H:%M:%S')} up {up},  1 user,  load average: 0.00, 0.00, 0.00\n")
@register("/usr/bin/df")
class Df(Command):
    def call(self): self.write("Filesystem     1K-blocks    Used Available Use% Mounted on\n/dev/vda1       20511356 4567892  14883464  24% /\n")
@register("/usr/bin/du")
class Du(Command):
    def call(self): self.write("4096\t.\n")
@register("/usr/bin/hostname")
class Hostname(Command):
    def call(self): self.write(getattr(self.protocol, "hostname", "usas-prod-srv-01") + "\n")
@register("/usr/bin/hostnamectl")
class Hostnamectl(Command):
    def call(self): self.write("   Static hostname: usas-prod-srv-01\n   Operating System: Ubuntu 22.04.5 LTS\n   Kernel: Linux 5.15.0-97-generic\n   Architecture: x86-64\n")

# ── Process info ───────────────────────────────────────────────────

@register("/usr/bin/ps")
class Ps(Command):
    def call(self): self.write("  PID TTY          TIME CMD\n    1 ?        00:00:01 systemd\n  423 pts/0    00:00:00 bash\n  512 pts/0    00:00:00 ps\n")
@register("/usr/bin/top")
class Top(Command):
    def call(self): self.write("top - " + time.strftime("%H:%M:%S") + " up 7 days,  1 user,  load average: 0.00, 0.00, 0.00\nTasks:  89 total,   1 running,  88 sleeping\n%Cpu(s):  0.3 us,  0.1 sy,  0.0 ni, 99.6 id\nMiB Mem :   3932.0 total,   2701.2 free,    511.0 used,    719.8 buff/cache\nMiB Swap:   1024.0 total,   1024.0 free\n    PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND\n      1 root      20   0  102948  12044   8376 S   0.0   0.3   0:01.23 systemd\n    423 root      20   0   15012   4892   3476 S   0.0   0.1   0:00.00 bash\n    512 root      20   0   43524   3812   2880 R   0.3   0.1   0:00.00 top\n")

# ── File ops ───────────────────────────────────────────────────────

@register("/bin/cat")
class Cat(Command):
    def call(self):
        if not self.args: return
        for a in self.args:
            try:
                p = self.fs.resolve_path(a, self.protocol.cwd)
                self.writeBytes(self.fs.file_contents(p))
            except (KeyError, IsADirectoryError): self.errorWrite(f"cat: {a}: No such file or directory\n")
@register("/bin/ls")
class Ls(Command):
    def call(self):
        long = any(x in ("-l", "-la", "-al") for x in self.args)
        tgt = "."
        for a in self.args:
            if not a.startswith("-"): tgt = a; break
        p = self.fs.resolve_path(tgt, self.protocol.cwd)
        try:
            ents = sorted(self.fs.listdir(p))
            if long:
                for n in ents:
                    ep = (p.rstrip("/") + "/" + n) if p != "/" else "/" + n
                    s = self.fs.stat(ep) or {}
                    m = s.get("mode", 0o644); ft = "d" if s.get("type") == "dir" else "-"
                    perms = ft + ("r" if m & 0o400 else "-") + ("w" if m & 0o200 else "-") + ("x" if m & 0o100 else "-") + ("r" if m & 0o40 else "-") + ("w" if m & 0o20 else "-") + ("x" if m & 0o10 else "-") + ("r" if m & 0o4 else "-") + ("w" if m & 0o2 else "-") + ("x" if m & 0o1 else "-")
                    self.write(f"{perms} 1 {s.get('uid',0):4d} {s.get('gid',0):4d} {s.get('size',0):6d} {time.strftime('%b %d %H:%M', time.localtime(s.get('mtime', time.time()) + self.fs._mtime_base))} {n}\n")
            else: self.write("  ".join(ents) + "\n")
        except Exception as e: self.errorWrite(f"ls: {e}\n")
@register("/usr/bin/chmod")
class Chmod(Command):
    def call(self): self.write("")
@register("/usr/bin/chown")
class Chown(Command):
    def call(self): self.write("")
@register("/usr/bin/dd")
class Dd(Command):
    def call(self): self.write("0+0 records in\n0+0 records out\n0 bytes copied\n")
@register("/usr/bin/tar")
class Tar(Command):
    def call(self): self.write("tar: cowardly refusing to create an empty archive\n")
@register("/usr/bin/gzip")
class Gzip(Command):
    def call(self): self.write("gzip: compressed data not written to a terminal\n")
@register("/usr/bin/find")
class Find(Command):
    def call(self): self.write("")
@register("/usr/bin/grep")
class Grep(Command):
    def call(self):
        stdin = getattr(self.protocol, "stdin", "")
        if not stdin:
            return
        ignore_case = False
        invert = False
        count = False
        fixed = False
        patterns: list[str] = []
        end_options = False
        for arg in self.args:
            if not end_options and arg == "--":
                end_options = True
                continue
            if not end_options and arg.startswith("--"):
                continue
            if not end_options and arg.startswith("-") and len(arg) > 1:
                for flag in arg[1:]:
                    if flag == "i":
                        ignore_case = True
                    elif flag == "v":
                        invert = True
                    elif flag == "c":
                        count = True
                    elif flag == "F":
                        fixed = True
                    elif flag == "E":
                        continue
                continue
            patterns.append(arg)
        if not patterns:
            return
        expression = "|".join(re.escape(pattern) for pattern in patterns) if fixed else "|".join(patterns)
        try:
            regex = re.compile(expression, re.IGNORECASE if ignore_case else 0)
        except re.error:
            return
        matches = 0
        for line in stdin.splitlines():
            hit = bool(regex.search(line))
            if invert:
                hit = not hit
            if not hit:
                continue
            matches += 1
            if not count:
                self.write(line + "\n")
        if count:
            self.write(str(matches) + "\n")
@register("/usr/bin/cut")
class Cut(Command):
    def call(self):
        stdin = getattr(self.protocol, "stdin", "")
        if not stdin:
            return
        delimiter = "\t"
        fields: list[int] = []
        args = list(self.args)
        index = 0
        while index < len(args):
            arg = args[index]
            if arg in ("-d", "--delimiter") and index + 1 < len(args):
                delimiter = args[index + 1]
                index += 2
                continue
            if arg.startswith("-d") and len(arg) > 2:
                delimiter = arg[2:]
                index += 1
                continue
            if arg in ("-f", "--fields") and index + 1 < len(args):
                fields = self._parse_fields(args[index + 1])
                index += 2
                continue
            if arg.startswith("-f") and len(arg) > 2:
                fields = self._parse_fields(arg[2:])
                index += 1
                continue
            index += 1
        if not fields:
            return
        for line in stdin.splitlines():
            parts = line.split(delimiter)
            selected = [
                parts[field - 1] if 0 <= field - 1 < len(parts) else ""
                for field in fields
            ]
            self.write(delimiter.join(selected) + "\n")

    @staticmethod
    def _parse_fields(value: str) -> list[int]:
        fields: list[int] = []
        for part in value.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                start, end = part.split("-", 1)
                try:
                    first = int(start or "1")
                    last = int(end or str(first))
                except ValueError:
                    continue
                fields.extend(range(first, last + 1))
            else:
                try:
                    fields.append(int(part))
                except ValueError:
                    continue
        return fields
@register("/usr/bin/wc")
class Wc(Command):
    def call(self):
        stdin = getattr(self.protocol, "stdin", "")
        if not stdin:
            return
        show_lines = False
        show_words = False
        show_bytes = False
        for arg in self.args:
            if arg in ("-l", "--lines"):
                show_lines = True
            elif arg in ("-w", "--words"):
                show_words = True
            elif arg in ("-c", "--bytes"):
                show_bytes = True
            elif arg.startswith("-") and len(arg) > 1:
                for flag in arg[1:]:
                    if flag == "l":
                        show_lines = True
                    elif flag == "w":
                        show_words = True
                    elif flag == "c":
                        show_bytes = True
        if not (show_lines or show_words or show_bytes):
            show_lines = show_words = show_bytes = True
        values: list[str] = []
        if show_lines:
            values.append(str(stdin.count("\n")))
        if show_words:
            values.append(str(len(stdin.split())))
        if show_bytes:
            values.append(str(len(stdin.encode("utf-8"))))
        self.write(" ".join(values) + "\n")


@register("/usr/bin/tr")
class Tr(Command):
    def call(self):
        stdin = getattr(self.protocol, "stdin", "")
        if not stdin:
            return
        delete = False
        squeeze = False
        sets: list[str] = []
        for arg in self.args:
            if arg in ("-d", "--delete"):
                delete = True
            elif arg in ("-s", "--squeeze-repeats"):
                squeeze = True
            elif arg.startswith("-") and len(arg) > 1:
                for flag in arg[1:]:
                    if flag == "d":
                        delete = True
                    elif flag == "s":
                        squeeze = True
            else:
                sets.append(arg)
        if not sets:
            return
        first = self._expand_set(sets[0])
        second = self._expand_set(sets[1]) if len(sets) > 1 else ""
        if not delete and not squeeze and not second:
            return
        if second and len(second) < len(first):
            second += second[-1] * (len(first) - len(second))
        table = str.maketrans(first, second) if second else {}
        squeeze_set = second if second else first
        for line in stdin.splitlines():
            result = line.translate(table)
            if delete:
                result = result.translate(str.maketrans("", "", first))
            if squeeze:
                collapsed: list[str] = []
                for char in result:
                    if not collapsed or collapsed[-1] != char or char not in squeeze_set:
                        collapsed.append(char)
                result = "".join(collapsed)
            self.write(result + "\n")

    @staticmethod
    def _expand_set(value: str) -> str:
        value = value.replace("\\t", "\t").replace("\\n", "\n").replace("\\\\", "\\")
        classes = {
            "lower": "abcdefghijklmnopqrstuvwxyz",
            "upper": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "digit": "0123456789",
            "alpha": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "alnum": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            "space": " \t\n\r\v\f",
            "punct": "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~",
        }
        expanded: list[str] = []
        index = 0
        while index < len(value):
            if value.startswith("[:", index):
                end = value.find(":]", index + 2)
                if end != -1:
                    expanded.extend(classes.get(value[index + 2:end], ""))
                    index = end + 2
                    continue
            if index + 2 < len(value) and value[index + 1] == "-" and value[index] <= value[index + 2]:
                expanded.extend(chr(code) for code in range(ord(value[index]), ord(value[index + 2]) + 1))
                index += 3
                continue
            expanded.append(value[index])
            index += 1
        return "".join(expanded)


@register("/usr/bin/sed")
class Sed(Command):
    def call(self):
        stdin = getattr(self.protocol, "stdin", "")
        if not stdin:
            return
        if any(arg == "-n" or (arg.startswith("-") and "n" in arg[1:]) for arg in self.args):
            return
        expression = next((arg for arg in self.args if not arg.startswith("-") or len(arg) == 1), "")
        match = re.fullmatch(r"s(.)(.*?)\1(.*?)\1([gi]*)", expression, re.DOTALL)
        if not match:
            return
        delimiter, pattern, replacement, flags = match.groups()
        try:
            regex = re.compile(pattern, re.IGNORECASE if "i" in flags else 0)
        except re.error:
            return
        replacement = replacement.replace("&", r"\g<0>")
        count = 0 if "g" in flags else 1
        try:
            for line in stdin.splitlines():
                self.write(regex.sub(replacement, line, count=count) + "\n")
        except re.error:
            return


@register("/usr/bin/sort")
class Sort(Command):
    def call(self):
        stdin = getattr(self.protocol, "stdin", "")
        if not stdin:
            return
        reverse = False
        numeric = False
        unique = False
        fold = False
        for arg in self.args:
            if arg in ("-r", "--reverse"):
                reverse = True
            elif arg in ("-n", "--numeric-sort"):
                numeric = True
            elif arg in ("-u", "--unique"):
                unique = True
            elif arg in ("-f", "--ignore-case"):
                fold = True
            elif arg.startswith("-") and len(arg) > 1:
                for flag in arg[1:]:
                    if flag == "r":
                        reverse = True
                    elif flag == "n":
                        numeric = True
                    elif flag == "u":
                        unique = True
                    elif flag == "f":
                        fold = True
        lines = stdin.splitlines()
        if numeric:
            def key(line: str) -> object:
                try:
                    return float(line.strip())
                except ValueError:
                    return 0.0
        else:
            def key(line: str) -> object:
                return line.lower() if fold else line
        lines.sort(key=key, reverse=reverse)
        if unique:
            lines = list(dict.fromkeys(lines))
        self.write("\n".join(lines) + "\n")


@register("/usr/bin/uniq")
class Uniq(Command):
    def call(self):
        stdin = getattr(self.protocol, "stdin", "")
        if not stdin:
            return
        count = False
        repeated = False
        unique_only = False
        for arg in self.args:
            if arg in ("-c", "--count"):
                count = True
            elif arg in ("-d", "--repeated"):
                repeated = True
            elif arg in ("-u", "--unique"):
                unique_only = True
            elif arg.startswith("-") and len(arg) > 1:
                for flag in arg[1:]:
                    if flag == "c":
                        count = True
                    elif flag == "d":
                        repeated = True
                    elif flag == "u":
                        unique_only = True
        groups: list[list[object]] = []
        for line in stdin.splitlines():
            if groups and groups[-1][0] == line:
                groups[-1][1] = int(groups[-1][1]) + 1
            else:
                groups.append([line, 1])
        for line, occurrences in groups:
            if repeated and occurrences < 2:
                continue
            if unique_only and occurrences != 1:
                continue
            self.write(f"{occurrences} {line}\n" if count else f"{line}\n")


@register("/usr/bin/awk")
class Awk(Command):
    def call(self):
        stdin = getattr(self.protocol, "stdin", "")
        delimiter: str | None = None
        program = ""
        args = list(self.args)
        index = 0
        while index < len(args):
            arg = args[index]
            if arg in ("-F", "--field-separator") and index + 1 < len(args):
                delimiter = args[index + 1]
                index += 2
                continue
            if arg.startswith("-F") and len(arg) > 2:
                delimiter = arg[2:]
                index += 1
                continue
            if not program:
                program = arg
            index += 1
        match = re.fullmatch(r"\s*(.*?)\s*\{\s*print\s*(.*?)\s*;?\s*\}\s*", program)
        if not stdin or not match:
            return
        condition = match.group(1).strip()
        expression = match.group(2).strip()
        fields = [part.strip() for part in expression.split(",")] if expression else ["$0"]
        for line in stdin.splitlines():
            parts = line.split(delimiter) if delimiter else line.split()
            if self._matches(condition, line, parts):
                self.write(" ".join(self._field(field, line, parts) for field in fields) + "\n")

    @staticmethod
    def _matches(condition: str, line: str, parts: list[str]) -> bool:
        if not condition:
            return True
        for separator in ("||", "&&"):
            segments = Awk._split_condition(condition, separator)
            if len(segments) > 1:
                if separator == "||":
                    return any(Awk._matches(segment, line, parts) for segment in segments)
                return all(Awk._matches(segment, line, parts) for segment in segments)
        if condition.startswith("!"):
            return not Awk._matches(condition[1:].strip(), line, parts)
        if condition.startswith("/") and condition.endswith("/"):
            try:
                return bool(re.search(condition[1:-1], line))
            except re.error:
                return False
        match = re.fullmatch(r"\$(\d+|NF)\s*(==|!=|~|!~|>=|<=|>|<)\s*(.+)", condition)
        if not match:
            return False
        field, operator, right = match.groups()
        if field == "NF":
            value = parts[-1] if parts else ""
        elif field == "0":
            value = line
        else:
            position = int(field)
            value = parts[position - 1] if 0 < position <= len(parts) else ""
        if operator in ("~", "!~"):
            if not (len(right) >= 2 and right[0] == right[-1] == "/"):
                return False
            try:
                found = bool(re.search(right[1:-1], value))
            except re.error:
                return False
            return not found if operator == "!~" else found
        right = right.strip()
        if len(right) >= 2 and right[0] == right[-1] == '"':
            right = right[1:-1]
        if operator in ("==", "!="):
            equal = value == right
            return equal if operator == "==" else not equal
        try:
            left_number = float(value)
            right_number = float(right)
        except ValueError:
            left_number = value
            right_number = right
        if operator == ">":
            return left_number > right_number
        if operator == "<":
            return left_number < right_number
        if operator == ">=":
            return left_number >= right_number
        return left_number <= right_number

    @staticmethod
    def _split_condition(condition: str, separator: str) -> list[str]:
        segments: list[str] = []
        start = 0
        index = 0
        in_regex = False
        in_quote = False
        while index < len(condition):
            char = condition[index]
            if char == "\\":
                index += 2
                continue
            if char == '"' and not in_regex:
                in_quote = not in_quote
                index += 1
                continue
            if char == "/" and not in_quote:
                in_regex = not in_regex
                index += 1
                continue
            if not in_regex and not in_quote and condition.startswith(separator, index):
                segments.append(condition[start:index].strip())
                index += len(separator)
                start = index
                continue
            index += 1
        segments.append(condition[start:].strip())
        return segments

    @staticmethod
    def _field(expression: str, line: str, parts: list[str]) -> str:
        if expression == "$0":
            return line
        if expression == "$NF":
            return parts[-1] if parts else ""
        if expression == "NF":
            return str(len(parts))
        if expression.startswith("$") and expression[1:].isdigit():
            position = int(expression[1:])
            return parts[position - 1] if 0 < position <= len(parts) else ""
        if len(expression) >= 2 and expression[0] == expression[-1] == '"':
            return expression[1:-1]
        return expression

# ── Network ────────────────────────────────────────────────────────

@register("/usr/bin/wget")
class Wget(Command):
    def call(self):
        url = self.args[0] if self.args else "unknown"
        self.write(f"--2024-01-15 12:00:00--  {url}\nConnecting to {url}... connected.\nHTTP request sent, awaiting response... 200 OK\nLength: 12345 (12K) [application/octet-stream]\nSaving to: 'index.html'\n\n     0K .......... .......... .......... .......... 100% 2.34M=0s\n\n2024-01-15 12:00:01 (2.34 MB/s) - 'index.html' saved [12345/12345]\n")
@register("/usr/bin/curl")
class Curl(Command):
    def call(self):
        url = self.args[-1] if self.args else "unknown"
        self.write("<html><body>CloudSentinel Honeypot</body></html>\n")
@register("/usr/bin/tftp")
class Tftp(Command):
    def call(self): self.write("tftp> Received 12345 bytes in 1.2 seconds\n")
@register("/usr/bin/ftpget")
class Ftpget(Command):
    def call(self): self.write("ftpget: 12345 bytes received in 0.8s\n")
@register("/usr/bin/nc")
class Nc(Command):
    def call(self): self.write("Connection to 10.0.0.1 4444 port [tcp/*] succeeded!\n")
@register("/usr/bin/netstat")
class Netstat(Command):
    def call(self):
        hn = getattr(self.protocol, "hostname", "usas-prod-srv-01")
        self.write(f"Active Internet connections (servers and established)\nProto Recv-Q Send-Q Local Address           Foreign Address         State\ntcp        0      0 0.0.0.0:22              0.0.0.0:*               LISTEN\ntcp        0      0 0.0.0.0:2222            0.0.0.0:*               LISTEN\ntcp        0      0 127.0.0.1:8123          0.0.0.0:*               LISTEN\ntcp        0      0 {hn}:2222          {self.protocol.clientIP}:{getattr(self.protocol, 'realClientPort', 12345)}    ESTABLISHED\n")
@register("/usr/bin/ss")
class Ss(Command):
    def call(self): self.write("Netid  State   Recv-Q  Send-Q  Local Address:Port   Peer Address:Port\ntcp    LISTEN  0       128     0.0.0.0:2222          0.0.0.0:*\ntcp    ESTAB   0       0       127.0.0.1:2222        10.0.0.1:54321\n")
@register("/usr/sbin/ifconfig")
@register("/usr/bin/ip")
class Ifconfig(Command):
    def call(self): self.write("eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500\n        inet 10.0.0.4  netmask 255.255.240.0  broadcast 10.0.0.255\n        ether 00:16:3e:5d:a2:1f  txqueuelen 1000  (Ethernet)\n        RX packets 4567890  bytes 234567890 (223.6 MiB)\n        TX packets 1234567  bytes 98765432 (94.1 MiB)\n")
@register("/usr/bin/ping")
class Ping(Command):
    def call(self): self.write("PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.\n64 bytes from 8.8.8.8: icmp_seq=1 ttl=117 time=1.23 ms\n64 bytes from 8.8.8.8: icmp_seq=2 ttl=117 time=1.19 ms\n--- 8.8.8.8 ping statistics ---\n2 packets transmitted, 2 received, 0% packet loss\nrtt min/avg/max/mdev = 1.190/1.210/1.230/0.020 ms\n")
@register("/usr/bin/dig")
class Dig(Command):
    def call(self): self.write(";; ANSWER SECTION:\nusas.edu.my.\t1800\tIN\tA\t103.22.11.55\n")
@register("/usr/bin/nslookup")
class Nslookup(Command):
    def call(self): self.write("Server:\t\t127.0.0.53\nAddress:\t127.0.0.53#53\nNon-authoritative answer:\nName:\tgoogle.com\nAddress: 142.250.80.46\n")

# ── Shell exec (critical for bot commands) ─────────────────────────

@register("/bin/sh")
@register("/bin/bash")
@register("/usr/bin/sh")
class ShellExec(Command):
    def call(self):
        if "-c" in self.args:
            idx = self.args.index("-c")
            if idx + 1 < len(self.args):
                nested = self.args[idx + 1]
                # Re-dispatch the nested command
                self.protocol._dispatch_line(nested.encode())
                return
        # Otherwise just start interactive shell
        pass
@register("/usr/bin/python3")
@register("/usr/bin/python")
class PythonExec(Command):
    def call(self):
        if "-c" in self.args:
            idx = self.args.index("-c")
            if idx + 1 < len(self.args):
                nested = self.args[idx + 1]
                if nested.startswith("import") or nested.startswith("print"):
                    self.write("OK\n")
                else:
                    self.protocol._dispatch_line(nested.encode())
                return
        self.write("Python 3.10.12 (main, Nov 20 2023, 15:14:05) [GCC 11.4.0] on linux\nType \"help\", \"copyright\", \"credits\" or \"license\".\n")
@register("/usr/bin/perl")
class PerlExec(Command):
    def call(self):
        if "-e" in self.args:
            idx = self.args.index("-e")
            if idx + 1 < len(self.args):
                nested = self.args[idx + 1]
                self.protocol._dispatch_line(nested.encode())
                return
        self.write("")
@register("/usr/bin/php")
class PhpExec(Command):
    def call(self):
        if "-r" in self.args:
            idx = self.args.index("-r")
            if idx + 1 < len(self.args):
                self.write("OK\n")
                return
        self.write("")

# ── Misc ───────────────────────────────────────────────────────────

@register("/usr/bin/clear")
class Clear(Command):
    def call(self): self.write("\x1b[H\x1b[2J")
@register("/usr/bin/pwd")
class Pwd(Command):
    def call(self): self.write(self.protocol.cwd + "\n")
@register("/usr/bin/printenv")
@register("/usr/bin/env")
class EnvCmd(Command):
    def call(self):
        for k, v in sorted(self.environ.items()): self.write(f"{k}={v}\n")
@register("/usr/bin/which")
class Which(Command):
    def call(self):
        if not self.args: return
        self.write(f"/usr/bin/{self.args[0]}\n")
@register("/usr/bin/last")
class Last(Command):
    def call(self):
        u = self.protocol.username; ip = getattr(self.protocol, "clientIP", "0.0.0.0")
        self.write(f"{u:8s} pts/0        {ip}  {time.strftime('%a %b %d %H:%M', time.localtime(getattr(self.protocol, 'logintime', time.time())))}   still logged in\n")
@register("/usr/bin/lastlog")
class Lastlog(Command):
    def call(self): self.write("Username         Port     From             Latest\nroot             pts/0    10.0.0.1         Thu Jan 15 12:00:00 +0000 2024\n")
@register("/usr/bin/groups")
class Groups(Command):
    def call(self): self.write("root\n")
@register("/usr/bin/yes")
class Yes(Command):
    def call(self): self.write("y\n" * 20)
@register("/usr/bin/tee")
class Tee(Command):
    def call(self): self.write("")
@register("/usr/bin/sleep")
class Sleep(Command):
    def call(self): pass
@register("/usr/bin/finger")
class Finger(Command):
    def call(self): self.write("Login: root           Name: root\nDirectory: /root       Shell: /bin/bash\nLogged in since Thu Jan 15 12:00 (UTC) on pts/0 from 10.0.0.1\nNo mail.\nNo Plan.\n")

# ── Service / persistence ──────────────────────────────────────────

@register("/usr/sbin/service")
@register("/usr/bin/systemctl")
class Systemctl(Command):
    def call(self): self.write("")
@register("/usr/sbin/iptables")
class Iptables(Command):
    def call(self): self.write("Chain INPUT (policy ACCEPT)\ntarget     prot opt source               destination\n")
@register("/usr/sbin/useradd")
@register("/usr/bin/adduser")
class Useradd(Command):
    def call(self): self.write("adduser: user added successfully\n")
@register("/usr/bin/passwd")
class Passwd(Command):
    def call(self): self.write("Changing password for root.\nNew password: \nRetype new password: \npasswd: password updated successfully\n")
@register("/usr/bin/crontab")
class Crontab(Command):
    def call(self): self.write("no crontab for root\n")
@register("/usr/bin/sudo")
class Sudo(Command):
    def call(self):
        if self.args:
            nested = " ".join(self.args)
            self.protocol._dispatch_line(nested.encode())
@register("/usr/bin/apt")
@register("/usr/bin/apt-get")
class Apt(Command):
    def call(self): self.write("Reading package lists... Done\nBuilding dependency tree... Done\n0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.\n")
@register("/usr/bin/yum")
class Yum(Command):
    def call(self): self.write("Loaded plugins: fastestmirror\nNo packages marked for update\n")

# ── MOTD / issue ───────────────────────────────────────────────────

@register("/etc/issue")
@register("/etc/issue.net")
class IssueNet(Command):
    def call(self):
        try: self.writeBytes(self.fs.file_contents("/etc/issue.net"))
        except (KeyError, IsADirectoryError): self.write("USAS Production Server v01\n")

# ── Help ───────────────────────────────────────────────────────────

@register("/usr/bin/help")
class Help(Command):
    def call(self): self.write("GNU bash, version 5.1.16(1)-release\nThese shell commands are defined internally.\n")
@register("/usr/bin/man")
class Man(Command):
    def call(self): self.write("No manual entry for " + (self.args[0] if self.args else "?") + "\n")
@register("/usr/bin/base64")
class Base64(Command):
    def call(self):
        txt = " ".join(self.args).encode()
        import base64
        self.write(base64.b64encode(txt).decode() + "\n")

# ── 99% gap: lateral movement + dev tools ─────────────────────────

@register("/usr/bin/ssh")
class SshCmd(Command):
    def call(self):
        self.write("The authenticity of host '10.0.0.5 (10.0.0.5)' can't be established.\nECDSA key fingerprint is SHA256:abcdefg.\nAre you sure you want to continue connecting (yes/no)? ")
@register("/usr/bin/scp")
class ScpCmd(Command):
    def call(self): self.write("")
@register("/usr/bin/gcc")
class GccCmd(Command):
    def call(self): self.write("gcc: fatal error: no input files\ncompilation terminated.\n")
@register("/usr/bin/git")
class GitCmd(Command):
    def call(self): self.write("fatal: not a git repository (or any of the parent directories): .git\n")
@register("/usr/bin/docker")
class DockerCmd(Command):
    def call(self): self.write("Cannot connect to the Docker daemon. Is the docker daemon running?\n")
@register("/usr/bin/kubectl")
class KubectlCmd(Command):
    def call(self): self.write("The connection to the server localhost:6443 was refused\n")
@register("/usr/bin/history")
class HistoryCmd(Command):
    def call(self):
        self.write("    1  ls -la\n    2  cd /var/tmp\n    3  uname -a\n    4  cat /etc/passwd\n    5  whoami\n    6  ps aux\n    7  exit\n")
@register("/usr/bin/crontab")
class CrontabL(Command):
    def call(self):
        if "-l" in self.args:
            self.write("# m h  dom mon dow   command\n0 2 * * * /usr/bin/backup.sh >> /var/log/backup.log 2>&1\n*/5 * * * * /usr/bin/healthcheck.sh\n")
        else:
            self.write("no crontab for root\n")
@register("/usr/bin/locate")
class LocateCmd(Command):
    def call(self):
        if self.args: self.write(f"/usr/share/doc/{self.args[0]}\n")

# ── Phase 1.5: Critical Deception Commands ──────────────────────────
# Added 2026-05-26 — 8 high-impact commands attackers expect in a real system

@register("/usr/bin/lsblk")
class LsblkCmd(Command):
    def call(self):
        self.write(
            "NAME   MAJ:MIN RM   SIZE RO TYPE MOUNTPOINTS\n"
            "sda      8:0    0    40G  0 disk \n"
            "|-sda1   8:1    0    38G  0 part /\n"
            "|-sda14  8:14   0     4M  0 part \n"
            "`-sda15  8:15   0   106M  0 part /boot/efi\n"
            "sr0     11:0    1  1024M  0 rom  \n"
        )

@register("/usr/bin/dmesg")
class DmesgCmd(Command):
    def call(self):
        self.write(
            "[    0.000000] Linux version 5.15.0-97-generic (buildd@lcy02-amd64-101) "
            "#107-Ubuntu SMP Thu Feb 15 15:00:00 UTC 2024\n"
            "[    0.124567] Command line: BOOT_IMAGE=/boot/vmlinuz-5.15.0-97-generic "
            "root=UUID=abc123 ro quiet splash\n"
            "[    0.891234] usb 1-1: new high-speed USB device number 2 using xhci_hcd\n"
            "[    1.234567] EXT4-fs (sda1): mounted filesystem with ordered data mode\n"
            "[    2.456789] random: crng init done\n"
        )

@register("/usr/bin/head")
class HeadCmd(Command):
    def call(self):
        stdin = getattr(self.protocol, "stdin", "")
        if not stdin:
            if self.args:
                self.write("head: cannot open for reading: No such file or directory\n")
            return
        count = 10
        args = list(self.args)
        index = 0
        while index < len(args):
            arg = args[index]
            if arg in ("-n", "--lines") and index + 1 < len(args):
                value = args[index + 1]
                index += 2
            elif arg.startswith("-n") and len(arg) > 2:
                value = arg[2:]
                index += 1
            elif arg.startswith("--lines="):
                value = arg.split("=", 1)[1]
                index += 1
            else:
                index += 1
                continue
            try:
                count = max(0, int(value))
            except ValueError:
                pass
        self.write("\n".join(stdin.splitlines()[:count]) + ("\n" if count else ""))

@register("/usr/bin/tail")
class TailCmd(Command):
    def call(self):
        stdin = getattr(self.protocol, "stdin", "")
        if not stdin:
            if self.args:
                self.write("tail: cannot open for reading: No such file or directory\n")
            return
        count = 10
        start = 0
        args = list(self.args)
        index = 0
        while index < len(args):
            arg = args[index]
            if arg in ("-n", "--lines") and index + 1 < len(args):
                value = args[index + 1]
                index += 2
            elif arg.startswith("-n") and len(arg) > 2:
                value = arg[2:]
                index += 1
            elif arg.startswith("--lines="):
                value = arg.split("=", 1)[1]
                index += 1
            else:
                index += 1
                continue
            try:
                if value.startswith("+"):
                    start = max(1, int(value[1:]))
                    count = 0
                else:
                    number = int(value)
                    count = max(0, abs(number)) if number < 0 else number
                    start = 0
            except ValueError:
                pass
        lines = stdin.splitlines()
        selected = lines[start - 1:] if start else (lines[-count:] if count else [])
        self.write("\n".join(selected) + ("\n" if selected else ""))

@register("/bin/cp")
class CpCmd(Command):
    def call(self):
        if len(self.args) < 2:
            self.write("cp: missing file operand\n")
        else:
            self.write("")

@register("/bin/mv")
class MvCmd(Command):
    def call(self):
        if len(self.args) < 2:
            self.write("mv: missing file operand\n")
        else:
            self.write("")

@register("/bin/rm")
class RmCmd(Command):
    def call(self):
        if not self.args:
            self.write("rm: missing operand\n")
        else:
            self.write("")

@register("/bin/mkdir")
class MkdirCmd(Command):
    def call(self):
        if not self.args:
            self.write("mkdir: missing operand\n")
        else:
            self.write("")