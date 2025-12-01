import playwright_stealth
import inspect

print("Inspecting playwright_stealth...")
print(f"Type of playwright_stealth: {type(playwright_stealth)}")

for attr in dir(playwright_stealth):
    if attr.startswith("__"): continue
    val = getattr(playwright_stealth, attr)
    print(f"Attribute: {attr}, Type: {type(val)}")
    if attr == 'stealth':
        print("  Inspecting playwright_stealth.stealth...")
        for sub_attr in dir(val):
            if sub_attr.startswith("__"): continue
            print(f"    Sub-Attribute: {sub_attr}")

try:
    from playwright_stealth import stealth_sync
    print("Successfully imported stealth_sync from playwright_stealth")
except ImportError:
    print("Failed to import stealth_sync from playwright_stealth")

try:
    from playwright_stealth import stealth
    print(f"Imported stealth. Callable? {callable(stealth)}")
except ImportError:
    print("Failed to import stealth")
