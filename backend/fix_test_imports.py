import os

tests_dir = r"c:\Users\chiranjeevi madem\OneDrive\Документы\New folder\SmartbridgePlatform\backend\tests"

for filename in os.listdir(tests_dir):
    if filename.startswith("test_") and filename.endswith(".py"):
        filepath = os.path.join(tests_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace sys.path.append('.') with robust parent dir append
        fixed = content.replace("sys.path.append('.')", "import sys, os; sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))")
        fixed = fixed.replace("sys.path.append(\".\")", "import sys, os; sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))")
        
        if fixed != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(fixed)
            print(f"Fixed imports in {filename}")
