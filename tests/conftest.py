import os, sys
# Ensure the project root is on the Python path for imports
project_root = os.path.abspath(os.path.join(__file__, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
