import glob
import os
import re

dir_path = r"C:\Users\RADZ\project io\FYP\sensor\cloudsentinel"
files = glob.glob(os.path.join(dir_path, "*.py"))

for file_path in files:
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        print(f"Skipping {os.path.basename(file_path)} due to encoding.")
        with open(file_path, encoding="cp1252") as f:
            content = f.read()

    # Skip files that don't import logging unless they use loguru
    if "import logging" not in content and "from loguru import logger" not in content:
        continue

    if os.path.basename(file_path) == "observability.py":
        continue

    original_content = content
    content = re.sub(r"^import logging\s*$", "import structlog", content, flags=re.MULTILINE)
    content = re.sub(r"^from loguru import logger\s*$", "import structlog\nlogger = structlog.get_logger()", content, flags=re.MULTILINE)
    content = re.sub(r"logging\.getLogger\(([^)]*)\)", r"structlog.get_logger(\1)", content)

    if content != original_content:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Updated logging in {os.path.basename(file_path)}")
        except Exception:
            # write back with original encoding
            with open(file_path, "w", encoding="cp1252") as f:
                f.write(content)
            print(f"Updated logging in {os.path.basename(file_path)} (cp1252)")
