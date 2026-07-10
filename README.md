# App-Launcher(Python)
Windows App Launcher. Run the App Launcher from start menu and whenever u press Alt+X, It would pop-up. Very less CPU and Memory Usage

I made it because existing launchers use way too much resources and my laptop doesnt have that many to give so this runs efficiently and is instant and solves my purpose...

### Hotkey to Launch is Alt+X
When u start the app, it would start as a background process, nothing would be visble. The app would become visible when u press Alt+X


<img src="image.png">

## [Download Pre Built Binary](https://github.com/SpaceCoderPro/App-Launcher/releases)

### If u find any issues, plss report them in the issues tab so I can follow up...

## Compilation Instructions for .exe
Download all files in the Pyinstaller folder then run the below commands
```
pyinstaller --noconsole --onefile --collect-all customtkinter --hidden-import=tkinter --hidden-import=tkinter.filedialog --hidden-import=tkinter.messagebox "App Launcher.pyw"
```
## To run with python installed on your computer
Download all files in the root folder then run "App Launcher.pyw"

## Libraries to Install
```
pip install tkinter pynput pywin32
```
