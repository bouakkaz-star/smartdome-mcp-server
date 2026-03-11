import sys
import traceback
try:
    import app.main
    print("IMPORT SUCCESS")
except Exception as e:
    print("IMPORT_FAILED:")
    traceback.print_exc()
