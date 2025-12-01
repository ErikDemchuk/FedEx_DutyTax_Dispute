try:
    import playwright_stealth
    print("playwright_stealth imported successfully.")
    print(f"Dir: {dir(playwright_stealth)}")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
