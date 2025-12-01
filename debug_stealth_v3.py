import playwright_stealth.stealth as stealth_module

print("Inspecting playwright_stealth.stealth...")
if hasattr(stealth_module, 'sync_api'):
    print("Found sync_api submodule.")
    print(f"Dir of sync_api: {dir(stealth_module.sync_api)}")
else:
    print("No sync_api found.")

if hasattr(stealth_module, 'Stealth'):
    print("Found Stealth class.")
    print(f"Dir of Stealth: {dir(stealth_module.Stealth)}")
