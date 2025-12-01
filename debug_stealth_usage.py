from playwright_stealth.stealth import Stealth

# Test the Stealth class
stealth_instance = Stealth()
print(f"Created Stealth instance: {stealth_instance}")
print(f"Has use_sync? {hasattr(stealth_instance, 'use_sync')}")
print(f"Has apply_stealth_sync? {hasattr(stealth_instance, 'apply_stealth_sync')}")

# Check if use_sync is callable
if hasattr(stealth_instance, 'use_sync'):
    print(f"use_sync is callable: {callable(stealth_instance.use_sync)}")
