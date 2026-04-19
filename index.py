import runpy
import os
script_dir = os.path.dirname(os.path.abspath(__file__))
print("Choose a Utility: ")
print("1. Multi-operation Fast Calculator")
print("2: Simple Fast Calculator")
print("3: Simple Int Calculator")
print("4: Puppy Companion")
print("5: App Launcher")
Util=int(input("Utility No.: "))
if Util==1:
    target_path = os.path.join(script_dir, "Full Calculator Fast.py")
elif Util==2:
    target_path = os.path.join(script_dir, "Simple Fast Calculator.py")
elif Util==3:
    target_path = os.path.join(script_dir, "Simple Int Calculator.py")
elif Util==4:
    target_path = os.path.join(script_dir, "puppy.py")
elif Util==5:
    target_path = os.path.join(script_dir, "App Launcher.py")
runpy.run_path(target_path)
