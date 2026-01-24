import re
import zipfile
from pathlib import Path

TARGET = Path("build/flutter/lib/main.dart")
APP_ZIP = Path("build/flutter/build/flutter_assets/app/app.zip")

OLD_SNIPPET = """    var appTempPath = (await path_provider.getApplicationCacheDirectory()).path;
    var appDataPath =
        (await path_provider.getApplicationDocumentsDirectory()).path;
"""

NEW_SNIPPET = """    var appTempPath = (await path_provider.getApplicationCacheDirectory()).path;
    String appDataPath;
    try {
      appDataPath =
          (await path_provider.getApplicationDocumentsDirectory()).path;
    } on MissingPlatformDirectoryException {
      // Linux can throw MissingPlatformDirectoryException if XDG user dirs are not set.
      // Fallback to application support directory to avoid crash.
      appDataPath =
          (await path_provider.getApplicationSupportDirectory()).path;
    } catch (_) {
      appDataPath =
          (await path_provider.getApplicationSupportDirectory()).path;
    }
"""


def main() -> int:
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found. Run 'flet build' first.")
        return 1

    text = TARGET.read_text(encoding="utf-8")

    already_patched = "MissingPlatformDirectoryException" in text
    if already_patched:
        print("Already patched.")

    if not already_patched and OLD_SNIPPET not in text:
        # Try a more flexible match in case formatting changes slightly
        pattern = re.compile(
            r"var appTempPath = \(await path_provider\.getApplicationCacheDirectory\(\)\)\.path;\s*"
            r"var appDataPath =\s*\(await path_provider\.getApplicationDocumentsDirectory\(\)\)\.path;",
            re.MULTILINE,
        )
        if not pattern.search(text):
            print("ERROR: Patch target not found in main.dart.")
            return 2
        text = pattern.sub(
            NEW_SNIPPET.rstrip("\n"),
            text,
        )
    elif not already_patched:
        text = text.replace(OLD_SNIPPET, NEW_SNIPPET)
    if not already_patched:
        TARGET.write_text(text, encoding="utf-8")
        print("Patched build/flutter/lib/main.dart")

    # Strip .venv and .git from app.zip if present
    if APP_ZIP.exists():
        removed = 0
        tmp_zip = APP_ZIP.with_suffix(".zip.tmp")
        with zipfile.ZipFile(APP_ZIP, "r") as zin, zipfile.ZipFile(
            tmp_zip, "w", compression=zipfile.ZIP_DEFLATED
        ) as zout:
            for item in zin.infolist():
                if item.filename.startswith(".venv/") or item.filename.startswith(".git/"):
                    removed += 1
                    continue
                data = zin.read(item.filename)
                zout.writestr(item, data)
        tmp_zip.replace(APP_ZIP)
        print(f"Stripped .venv/.git entries from app.zip: {removed}")
    else:
        print(f"WARNING: {APP_ZIP} not found. Skipping zip cleanup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
