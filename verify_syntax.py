import re

def verify_file(filename):
    print(f"=== VERIFYING {filename} ===")
    with open(filename, "r", encoding="utf-8") as f:
        html = f.read()

    # Extract all declared IDs in HTML
    declared_ids = set(re.findall(r'id=["\']([a-zA-Z0-9_\-]+)["\']', html))
    print(f"Declared element IDs: {len(declared_ids)}")

    # Extract inline scripts
    scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
    for i, s in enumerate(scripts):
        # 1. Check getElementById calls
        used_ids = set(re.findall(r'document\.getElementById\(["\']([a-zA-Z0-9_\-]+)["\']\)', s))
        missing = [uid for uid in used_ids if uid not in declared_ids]
        if missing:
            print(f"ERROR: Missing element IDs in HTML: {missing}")
        else:
            print(f"All {len(used_ids)} getElementById IDs exist in HTML! [PASS]")

        # 2. Check balanced braces, brackets, parens
        stack = []
        in_str = None
        escaped = False
        in_line_comment = False
        in_block_comment = False

        j = 0
        while j < len(s):
            char = s[j]
            next_char = s[j+1] if j + 1 < len(s) else ""

            if in_line_comment:
                if char == "\n":
                    in_line_comment = False
                j += 1
                continue

            if in_block_comment:
                if char == "*" and next_char == "/":
                    in_block_comment = False
                    j += 2
                    continue
                j += 1
                continue

            if in_str:
                if char == in_str and not escaped:
                    in_str = None
                elif char == "\\":
                    escaped = not escaped
                else:
                    escaped = False
                j += 1
                continue

            if char == "/" and next_char == "/":
                in_line_comment = True
                j += 2
                continue

            if char == "/" and next_char == "*":
                in_block_comment = True
                j += 2
                continue

            if char in ('"', "'", "`"):
                in_str = char
                escaped = False
            elif char in ("{", "[", "("):
                stack.append((char, j))
            elif char in ("}", "]", ")"):
                if not stack:
                    print(f"ERROR: Unbalanced closing char '{char}' at index {j}")
                    break
                open_char, open_idx = stack.pop()
                expected = {"{": "}", "[": "]", "(": ")"}[open_char]
                if char != expected:
                    print(f"ERROR: Mismatched closing '{char}', expected '{expected}' opened at {open_idx}")
                    break
            j += 1

        if stack:
            print(f"ERROR: Unclosed items: {[c for c, _ in stack]}")
        else:
            print(f"Script {i+1}: All braces, brackets, and parentheses balanced! [PASS]")

verify_file("frontend/mobile.html")
print()
verify_file("frontend/index.html")
