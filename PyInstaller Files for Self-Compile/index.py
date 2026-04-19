# import runpy
import os
import subprocess
script_dir = os.path.dirname(os.path.abspath(__file__))
print("Choose a Utility: ")
print("1. Multi-operation Fast Calculator")
print("2: Simple Fast Calculator")
print("3: Simple Int Calculator")
print("4: Puppy Companion")
print("5: App Launcher")
Util=int(input("Utility No.: "))
if Util==1:
    subprocess.Popen(["Full Calculator Fast.exe"], creationflags=subprocess.CREATE_NEW_CONSOLE)
    # target_path = os.path.join(script_dir, "Full Calculator Fast.py")
elif Util==2:
    subprocess.Popen(["Simple Fast Calculator.exe"], creationflags=subprocess.CREATE_NEW_CONSOLE)
elif Util==3:
    subprocess.Popen(["Simple Int Calculator.exe"], creationflags=subprocess.CREATE_NEW_CONSOLE)
elif Util==4:
    subprocess.Popen(["puppy.exe"], creationflags=subprocess.CREATE_NEW_CONSOLE)
elif Util==5:
    subprocess.Popen(["App Launcher.exe"], creationflags=subprocess.CREATE_NEW_CONSOLE)