import PySimpleGUI as sg #GUI lib
import io #For binary stuff
import mss #Screenshot lib
from PIL import Image #for image formats
from flask import Flask, request #For networking
from flask import send_file #For sending file through http
import threading #For multi-threading
import time
import random
import base64
import shutil

#Project PY files
import constants as const
import directoryFunctions as dirFuncs
import config as con

#Get monitor count
import win32api 
monitorCount = len(win32api.EnumDisplayMonitors())
possibleMonitors = range(1, monitorCount + 1)
print(f"Found monitors: {list(possibleMonitors)}")

#Create working directory
if not dirFuncs.workingDirExists():
    dirFuncs.createWorkingDir()


dirFuncs.createSendDir()

#Load default values from config
con.configSetDefaults()
configSettings = con.configRead()

key = configSettings["key"]
refreshDelay = int(configSettings["refresh_rate"])
screenShotsToStore = int(configSettings["screenShotsToStore"])
jpgQuality = int(configSettings["jpgQuality"])
port = int(configSettings["port"])
monitorToCapture = int(configSettings["monitor"])
if (monitorToCapture > monitorCount):
    monitorToCapture = monitorCount
    configSettings["monitor"] = str(monitorToCapture)
    con.configRewrite()

myDir = const.WORKING_DIR + const.IMAGE_CAPTURE_FILE_NAME
captureSendInc = 0

#Thread locks used to prevent sending images while saving it to disk. Prevents clients recieving truncated images
lock = threading.Lock()

#The Flask Server (A Thread)
app = Flask(__name__)
def HTTPServer():
    global app
    @app.route("/")
    def sendImage():
        global captureSendInc
        with lock:
            print ("Image request received. Checking auth...")
            authHead = request.headers.get("Authorization").split()
            authHead = str(base64.b64decode(authHead[1]))
            if (authHead == "b\":" + key + '"'):
                print ("Auth passed! Sending image...")
                captureSendInc += 1
                if (captureSendInc > screenShotsToStore):
                        captureSendInc = 0
                shutil.copy(myDir, f"{const.TRANSFER_DIR}\\capture{captureSendInc}.jpg")
                time.sleep(0.2)
                return send_file(f"{const.TRANSFER_DIR}\\capture{captureSendInc}.jpg", mimetype='image/gif')
            else:
                return str("204")

    @app.route("/delay")
    def delay():
        print ("Delay request received. Checking auth...")
        authHead = request.headers.get("Authorization").split()
        authHead = str(base64.b64decode(authHead[1]))
        if (authHead == "b\":" + key + '"'):
            print ("Auth passed! Responding...")
            return str(refreshDelay)
        else:
            return ('', 204)

    if __name__ == "__main__":
        app.run(debug=False, host="0.0.0.0", port = port)

serverThread = threading.Thread(target = HTTPServer)
serverThread.daemon = True
serverThread.start()

#Capturing and updating image within the window (A Thread)
def captureAndDisplay():
    while True:
        lock.acquire()
        with mss.mss() as mssInst:
            mon = mssInst.monitors[monitorToCapture] #Get monitor for next function
            screenshot = mssInst.grab(mon) #grab screenshot from monitor
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX") #Get byte data from captured image
        img.save(myDir)
        lock.release()

        aspect = img.size[0] / img.size[1]

        window.size = (window.size) #stops the window auto resizing based on element size

        w = window.size[0] - 20
        h = window.size[1] - 50

        #Retain aspect ratio at all times
        if w < h:
            h = w / aspect
        else:
            w = h * aspect
        img = img.resize((int(w), int(h)), resample = Image.NEAREST)
        
        bio = io.BytesIO() #Create binary stream
        img.save(bio, format="PNG") #save image to binary stream in png format
        window["-IMAGE-"].update(data = bio.getvalue()) #update image display with image data from binary stream
        time.sleep(refreshDelay / 1000)
        

#Layout of window
layout = [
    [sg.Text("Capture Delay(ms):", background_color="#262626"), sg.Input(size = (6, 1), default_text = refreshDelay, key = "-DELAY-"),
    sg.Text("Capture Monitor:", background_color="#262626"), sg.Combo(values = list(possibleMonitors), default_value = monitorToCapture, size = (2, monitorCount), key = "-MONITOR-", enable_events = True),
    sg.Text("Port:", background_color="#262626"), sg.Input(size = (8, 1), default_text = str(port), key = "-PORT_INPUT-"), #, sg.Button('Submit Network Settings', visible = True, key = "-NETWORK_SUBMIT-")
    sg.Text("Password: ", background_color="#262626"), sg.Input(size = (14, 1), key = "-PASSWORD-")],
    
    [sg.Image(key = "-IMAGE-", subsample = 2, size = (640, 480), pad = (0, 0))]
]
window = sg.Window(f"{const.APP_NAME}: Server", layout, resizable = True, background_color = "#262626", button_color="#262626", icon = const.APP_ICON, use_default_focus = False, finalize = True)
window["-DELAY-"].bind("<Return>", "Enter") #Bind enter key to trigger event on delay input
window["-PORT_INPUT-"].bind("<Return>", "Enter")
window["-PASSWORD-"].bind("<Return>", "Enter")

#must start capture thread after window exists as it relies on the window
captureThread = threading.Thread(target = captureAndDisplay)
captureThread.daemon = True
captureThread.start()

#Event Loop for the window and sending images to clients on window timeout / refresh
while True:
    event, values = window.read()

    if (event == "Exit" or event == sg.WIN_CLOSED):
        break
    
    elif (event == "-DELAY-" + "Enter"):
        val = int(values["-DELAY-"])
        if (val < const.REFRESH_RATE_MIN): #restrict to 100 ms
            val = const.REFRESH_RATE_MIN
            window["-DELAY-"].update(val)
        refreshDelay = val

        configSettings["refresh_rate"] = str(refreshDelay)
        con.configRewrite()

        sg.popup(f"Refresh Delay set to {refreshDelay} milliseconds.\n\nThis value also caps the minimum request rate for any connected clients.", background_color="#262626", title="Request Delay set")

    elif (event == "-MONITOR-"):
        monitorToCapture = values["-MONITOR-"]
        configSettings["monitor"] = str(monitorToCapture)
        con.configRewrite()

        print("Monitor set to: " + str(monitorToCapture))
    
    elif (event == "-PORT_INPUT-" + "Enter"):
        port = int(values["-PORT_INPUT-"])
        configSettings["port"] = str(port)
        con.configRewrite()
        sg.popup(f"Connection port set successfully!")
    
    elif (event == "-PASSWORD-" + "Enter"):
        password = values["-PASSWORD-"]

        random.seed(password)
        key = str(base64.urlsafe_b64encode(random.randbytes(128)))

        configSettings["key"] = key
        con.configRewrite()

        sg.popup(f"Password set to: {password}\n\nInput will be cleared after closing this window for security.", background_color="#262626", title="Password set")
        window["-PASSWORD-"].update("")


window.close()
