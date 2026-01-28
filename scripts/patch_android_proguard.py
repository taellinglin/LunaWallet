from __future__ import annotations

import re
from pathlib import Path

GRADLE_PATH = Path("build/flutter/android/app/build.gradle")
GRADLE_KTS_PATH = Path("build/flutter/android/app/build.gradle.kts")
PROGUARD_PATH = Path("build/flutter/android/app/proguard-rules.pro")

PROGUARD_RULES = """
# Keep Flet classes
-keep class io.flet.** { *; }
-dontwarn io.flet.**

# Keep Flutter generated classes
-keep class io.flutter.** { *; }
-dontwarn io.flutter.**
""".lstrip()


def _enable_release_minify(text: str) -> str:
    # Ensure release block has minifyEnabled/shrinkResources/proguardFiles
    release_pattern = re.compile(r"(buildTypes\s*\{\s*release\s*\{)([\s\S]*?)(\n\s*\})", re.MULTILINE)
    match = release_pattern.search(text)
    if not match:
        return text

    header, body, tail = match.groups()

    # Normalize existing settings
    def _replace_or_add(body_text: str, key: str, value: str) -> str:
        pattern = re.compile(rf"\b{re.escape(key)}\b\s+.*", re.MULTILINE)
        if pattern.search(body_text):
            return pattern.sub(f"{key} {value}", body_text)
        return body_text + f"\n        {key} {value}\n"

    body = _replace_or_add(body, "minifyEnabled", "true")
    body = _replace_or_add(body, "shrinkResources", "true")

    # Ensure proguardFiles line exists
    if "proguardFiles" not in body:
        body += "\n        proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'\n"

    return release_pattern.sub(f"{header}{body}{tail}", text)


def _enable_release_minify_kts(text: str) -> str:
    # Kotlin DSL: ensure release { isMinifyEnabled = true; isShrinkResources = true; proguardFiles(...) }
    release_pattern = re.compile(r"(buildTypes\s*\{\s*release\s*\{)([\s\S]*?)(\n\s*\})", re.MULTILINE)
    match = release_pattern.search(text)
    if not match:
        return text

    header, body, tail = match.groups()

    def _replace_or_add(body_text: str, key: str, value: str) -> str:
        pattern = re.compile(rf"\b{re.escape(key)}\b\s*=\s*.*", re.MULTILINE)
        if pattern.search(body_text):
            return pattern.sub(f"{key} = {value}", body_text)
        return body_text + f"\n        {key} = {value}\n"

    body = _replace_or_add(body, "isMinifyEnabled", "true")
    body = _replace_or_add(body, "isShrinkResources", "true")

    if "proguardFiles" not in body:
        body += "\n        proguardFiles(getDefaultProguardFile(\"proguard-android-optimize.txt\"), \"proguard-rules.pro\")\n"

    return release_pattern.sub(f"{header}{body}{tail}", text)


def main() -> int:
    if GRADLE_PATH.exists():
        text = GRADLE_PATH.read_text(encoding="utf-8")
        updated = _enable_release_minify(text)
        if updated != text:
            GRADLE_PATH.write_text(updated, encoding="utf-8")
            print("Patched build.gradle for minify/shrinkResources/proguard.")
        else:
            print("No changes needed in build.gradle.")
    elif GRADLE_KTS_PATH.exists():
        text = GRADLE_KTS_PATH.read_text(encoding="utf-8")
        updated = _enable_release_minify_kts(text)
        if updated != text:
            GRADLE_KTS_PATH.write_text(updated, encoding="utf-8")
            print("Patched build.gradle.kts for minify/shrinkResources/proguard.")
        else:
            print("No changes needed in build.gradle.kts.")
    else:
        print(f"ERROR: {GRADLE_PATH} or {GRADLE_KTS_PATH} not found. Run 'flet build apk' first.")
        return 1

    PROGUARD_PATH.write_text(PROGUARD_RULES, encoding="utf-8")
    print(f"Wrote {PROGUARD_PATH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
