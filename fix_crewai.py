path = r"D:\tab\Lib\site-packages\crewai\llms\cache.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

if "# PATCHED" in content:
    print("Already patched.")
else:
    old = "def mark_cache_breakpoint(message: dict[str, Any]) -> dict[str, Any]:"
    new = """def mark_cache_breakpoint(message: dict[str, Any]) -> dict[str, Any]:  # PATCHED
    return message  # disabled: Groq does not support cache_breakpoint"""

    if old in content:
        content = content.replace(old, new, 1)
        # Also find the original function body and neutralize it
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Patch applied successfully.")
    else:
        print("Could not find target function. Printing file for inspection:")
        print(content)