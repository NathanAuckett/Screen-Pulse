from re import L
from sqlite3 import connect
from turtle import update
import PySimpleGUI as sg
from PIL import Image, ImageTk, ImageEnhance #for image formats
import os
import threading
import time
from flask import request
import requests #For networking
import random
import base64
import cv2 #Provides negative option
import numpy as np

#Project PY files
import constants as const
import directoryFunctions as dirFuncs
import config

myDir = const.WORKING_DIR + const.IMAGE_RECIEVE_FILE_NAME
clientID = 0

#Create working directory
if not dirFuncs.workingDirExists():
    dirFuncs.createWorkingDir()
    print ("Created client Directory")

con = config.Config()
key = con.configDataGet("key", "default")
host = con.configDataGet("ip", "127.0.0.1")
port = int(con.configDataGet("port", const.DEFAULT_PORT))
sharpenFactor = float(con.configDataGet("sharpening", const.SHARPENING))
scaling = con.configDataGet("scaling", const.SCALING)
invert = con.configDataGet("invert", const.INVERT)
resample = con.configDataGet("resample", const.RESAMPLE)

connectedOnce = False
startingRefreshDelay = 1000 #Initial delay is fairly short as to quickly determine correct delay from server
connectionFailedRefreshDelay = 3000
connectionFailedCounter = 0
connectionFailedGiveup = int(con.configDataGet("failedAttempMax", const.FAILED_ATTEMPT_MAX)) #how many times the connection can fail before giving up
requestDelay = startingRefreshDelay
serverRefreshDelay = 2000
connectionTimeout = int(con.configDataGet("connectionTimeoutSeconds", const.CONNECTION_TIMEOUT_SECONDS))

controlsShowing = True
canRequest = True #This updates in the timer thread to keep more or less consistent timing even when waiting on longer receive times
refreshRateRequestTarget = 25
refreshRateRequestCount = refreshRateRequestTarget

zoomScale = float(con.configDataGet("zoom_scale", const.ZOOM_SCALE))
zoomXOff = int(con.configDataGet("xoff", const.XOFF))
zoomYOff = int(con.configDataGet("yoff", const.YOFF))
panSpd = 10
imgWidth = 0
imgHeight = 0

def strToSample(_resample):
    if _resample == "NEAREST":
        return Image.NEAREST
    elif _resample == "BILINEAR":
        return Image.BILINEAR
    elif _resample == "HAMMING":
        return Image.HAMMING
    elif _resample == "BICUBIC":
        return Image.BICUBIC
    elif _resample == "LANCZOS":
        return Image.LANCZOS
    else:
        return -1

def updateImage():
    global imgWidth
    global imgHeight
    if os.path.exists(myDir):
        try:
            img = cv2.imread(myDir)
            if (invert == "True"):
                img = cv2.bitwise_not(img)

            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) #Converts colour to RGB because CV2 is stupid and uses BGR
            img = Image.fromarray(img) #Convert to image object from CV2 array object
            
            aspect = img.size[0] / img.size[1]

            window.size = (window.size) #stops the window auto resizing based on element size

            if (controlsShowing):
                w = window.size[0] - 20
                h = window.size[1] - 100
            else:
                w = window.size[0]
                h = window.size[1] - 10

            if (scaling == "Fit"):
                #Retain aspect ratio at all times
                if w < h:
                    h = w / aspect
                else:
                    w = h * aspect

            imgWidth = w * zoomScale
            imgHeight = h * zoomScale

            img = img.resize((int(imgWidth), int(imgHeight)), resample = strToSample(resample))
            
            wdif = imgWidth - w
            hdif = imgHeight - h
            img = img.crop((wdif / 2 + zoomXOff, hdif / 2 + zoomYOff, imgWidth - wdif / 2 + zoomXOff, imgHeight - hdif / 2 + zoomYOff))

            enh = ImageEnhance.Sharpness(img)
            img = enh.enhance(sharpenFactor)

            img = ImageTk.PhotoImage(image = img)

            window["-IMAGE-"].update(data = img)
            print("Image updated!")
        except Exception as e:
            print(e)
    else:
        print("Receive image does not exist in directory!")

#Timer Thread/class
class Timer:
    def __init__(self):
        self.running = True
    
    def terminate(self):
        self.running = False

    def timer(self):
        global canRequest
        while (self.running):
            if (canRequest == False):
                time.sleep(requestDelay / 1000)
                canRequest = True

#Request thread/class
class Requester:
    def __init__(self):
        self.running = True
        self.connectionFailedCounter = 0
    
    def terminate(self):
        self.running = False
    
    def requestServer(self):
        global requestDelay
        global serverRefreshDelay
        global connectedOnce
        global canRequest
        global refreshRateRequestTarget
        global refreshRateRequestCount
        global connectionFailedGiveup
        global window
        global requesterInst
        global connectionTimeout

        timer = Timer()
        timerThread = threading.Thread(target = timer.timer)
        timerThread.daemon = True
        timerThread.start()

        window["-CONNECTION_STATUS-"].update("Conecting...")

        while (self.running):
            if (canRequest == False): #If we can't request yet, sleep for a second then check ahgain
                time.sleep(0.2)
            else:
                if (self.connectionFailedCounter < connectionFailedGiveup):
                    canRequest = False

                    #Fetch current refresh rate (every X times)
                    refreshRateRequestCount += 1
                    print(f"Refresh Rate Delay Counter: {refreshRateRequestCount}")
                    
                    if (refreshRateRequestCount >= refreshRateRequestTarget):
                        refreshRateRequestCount = 0
                        print("Requesting refresh rate.")
                        try:
                            r = requests.get("http://" + host + ":" + str(port) + "/delay", auth=('', key), timeout = connectionTimeout)
                            if (r != ('', 204)):
                                serverRefreshDelay = int(r.content.decode())
                                #requestDelay = int(configSettings["refresh_rate"])
                                requestDelay = int(con.configDataGet("refresh_rate", const.REFRESH_RATE_DEF))
                                if (requestDelay < serverRefreshDelay):
                                    requestDelay = serverRefreshDelay
                                    #configSettings["refresh_rate"] = str(requestDelay)
                                    con.configDataWrite("refresh_rate", requestDelay)
                                    #con.configRewrite()
                                    window["-DELAY-"].update(requestDelay)
                                    print("Request delay adjusted to suit server refresh")
                                
                                window["-CONNECTION_STATUS-"].update("Connected.")
                                connectedOnce = True
                                self.connectionFailedCounter = 0
                            else:
                                window["-CONNECTION_STATUS-"].update("Disconnected. Retrying...")
                                serverRefreshDelay = connectionFailedRefreshDelay
                                refreshRateRequestCount = refreshRateRequestTarget
                        except Exception as e:
                            print(e)
                            if (connectedOnce):
                                window["-CONNECTION_STATUS-"].update("Disconnected. Retrying...")
                                connectedOnce = False #This way the counter will be shown and the fail count begins on the next fail
                            else:
                                self.connectionFailedCounter += 1
                                window["-CONNECTION_STATUS-"].update(f"Connection failed({self.connectionFailedCounter}). Retrying...")
                            serverRefreshDelay = connectionFailedRefreshDelay
                            refreshRateRequestCount = refreshRateRequestTarget
                    
                    #Fetch latest image
                    try:
                        print("Requesting image...")
                        r = requests.get(f"http://{host}:{str(port)}", auth=('', key), timeout = connectionTimeout)
                        with open(myDir, 'wb') as out_file:
                            out_file.write(r.content)
                        
                        print("Image received. Updating image.")
                        updateImage()
                    except Exception as e:
                        print(e)
                        
                        if (connectedOnce):
                            window["-CONNECTION_STATUS-"].update("Disconnected. Retrying...")
                            connectedOnce = False #This way the counter will be shown and the fail count begins on the next fail
                        else:
                            self.connectionFailedCounter += 1
                            window["-CONNECTION_STATUS-"].update(f"Connection failed({self.connectionFailedCounter}). Retrying...")

                        if (self.connectionFailedCounter >= connectionFailedGiveup):
                            window["-CONNECTION_STATUS-"].update("Connection failed too many times. Giving up... Press Submit to retry.")
                            requesterInst = -1 #Tell rest of program that I'm gone
                            timer.terminate() #Terminate timer thread
                            self.terminate() #Terminate my own thread. We're giving up on this.
                        
                        requestDelay = connectionFailedRefreshDelay
                        refreshRateRequestCount = refreshRateRequestTarget

#Window Layout
sg.theme("DarkGrey5")
sg.theme_input_background_color("white")
sg.theme_input_text_color("black")
sg.theme_button_color("#242424")
column = [
    [sg.Text("Connection:"),
    sg.Text("IP:"), sg.Input(size = (14, 1), default_text = host, key = "-IP_INPUT-"),
    sg.Text("Port:"), sg.Input(size = (8, 1), default_text = str(port), key = "-PORT_INPUT-"),
    sg.Text("Password: "), sg.Input(size = (14, 1), key = "-PASSWORD-"),
    sg.Button('Submit', key = "-NETWORK_SUBMIT-"),
    sg.Text("Request Delay(ms):"), sg.Input(size = (6, 1), default_text = int(con.configDataGet("refresh_rate", const.REFRESH_RATE_DEF)), key = "-DELAY-"),
    ],
    [sg.Text("Image Settings:"),
    sg.Text("Scaling:"),  sg.Combo(values = ["Fit", "Fill"], default_value = scaling, size = (3, 2), key = "-SCALING-", enable_events = True),
    sg.Text("Resampling method:"),  sg.Combo(values = ["NEAREST", "BILINEAR", "HAMMING", "BICUBIC", "LANCZOS"], default_value = resample, size = (9, 5), key = "-RESAMPLE-", enable_events = True),
    sg.Text("Sharpening:"), sg.Input(size = [3, 1], default_text = sharpenFactor, key = "-SHARPENING-"),
    sg.Text("Image scale (1-5):"), sg.Input(size = [4, 1], default_text = zoomScale, key = "-ZOOM_SCALE-"),
    sg.Text("Hor offset:"), sg.Input(size = [4, 1], default_text = zoomXOff, key = "-XOFF-"),
    sg.Text("Vert offset:"), sg.Input(size = [4, 1], default_text = zoomYOff, key = "-YOFF-"),
    sg.Checkbox("Invert", default = invert == "True" , key = "-INVERT-", enable_events = True)
    ],
    [sg.Text("Press F1 to hide and show these controls."), sg.Text("Status:"), sg.Text(text = "Conecting...", key = "-CONNECTION_STATUS-")]
]

layout = [
    [sg.pin(sg.Column(column, key = "-CONTROLS-"), )],

    [sg.Image(key = "-IMAGE-", size = (1100, 600), pad = (0, 0))]
]

window = sg.Window(f"{const.APP_NAME}: Client", layout, grab_anywhere=True, use_default_focus = False, resizable = True, icon = const.APP_ICON, finalize = True)
window["-PASSWORD-"].bind("<Return>", "Enter") #Bind enter key to trigger event on delay input
window["-DELAY-"].bind("<Return>", "Enter")
window["-SHARPENING-"].bind("<Return>", "Enter")
window["-XOFF-"].bind("<Return>", "Enter")
window["-YOFF-"].bind("<Return>", "Enter")
window["-ZOOM_SCALE-"].bind("<Return>", "Enter")
window.bind("<Key-F1>", "F1")
window.bind("<Key-Left>", "Left")
window.bind("<Key-Right>", "Right")
window.bind("<Key-Up>", "Up")
window.bind("<Key-Down>", "Down")
window.bind("<Control-=>", "Plus")
window.bind("<Control-minus>", "Minus")

#Begin initial server thread
requesterInst = Requester()
requestThread = threading.Thread(target = requesterInst.requestServer)
requestThread.daemon = True
requestThread.start()

#Window Event Loop
while True:
    event, values = window.read()

    if event == "Exit" or event == sg.WIN_CLOSED:
        con.configDataWrite("xoff", zoomXOff)
        con.configDataWrite("yoff", zoomYOff)
        con.configDataWrite("zoom_scale", zoomScale)

        break
    
    elif (event == "-NETWORK_SUBMIT-"):
        host = values["-IP_INPUT-"]
        con.configDataWrite("ip", host)
        port = int(values["-PORT_INPUT-"])
        con.configDataWrite("port", port)

        #Password setting
        password = values["-PASSWORD-"]
        if (password != ""):
            random.seed(password)
            key = str(base64.urlsafe_b64encode(random.randbytes(128)))
            
            con.configDataWrite("key", key)
        else:
            password = "UNCHANGED"

        #Confirmation
        sg.popup(f"Connection address set to: {host}:{port}\n\nPassword set to: {password}\n\nPassword input will be cleared after closing this window for security.", background_color="#262626", title="Connection settings set")
        window["-PASSWORD-"].update("")

        #Start new server thread
        if (requesterInst == -1):
            requesterInst = Requester() #Setting this to a new instance should wipe references to the old for garbage collection
            requestThread = threading.Thread(target = requesterInst.requestServer)
            requestThread.daemon = True
            requestThread.start()
            print("Request server started")
        else:
            print("Request server already running, not starting new requester")
    
    elif (event == "-DELAY-" + "Enter"):
        val = int(values["-DELAY-"])
        if (val < const.REFRESH_RATE_MIN): #restrict to 100 ms
            val = const.REFRESH_RATE_MIN
            window["-DELAY-"].update(val)
        requestDelay = val
        refreshRateRequestCount = refreshRateRequestTarget #We need to check with the server again to see if this delay is okay

        con.configDataWrite("refresh_rate", requestDelay)

        sg.popup(f"Request Delay set to {requestDelay} milliseconds.\n\nIf this value is lower than the server refresh rate, this value will automatically be adjusted to match the server.\n\nA higher value means lower CPU loads on your machine!", background_color="#262626", title="Request Delay set")

    elif (event == "-SHARPENING-" + "Enter"):
        val = float(values["-SHARPENING-"])
        if (val < 0): #restrict to 100 ms
            val = 0
            window["-SHARPENING-"].update(val)
        sharpenFactor = val

        con.configDataWrite("sharpening", sharpenFactor)
        updateImage()

        print(f"Sharpening set to: {sharpenFactor}")
    
    elif (event == "-SCALING-"):
        scaling = values["-SCALING-"]
        con.configDataWrite("scaling", scaling)
        updateImage()

        print(f"Scaling set to: {scaling}")

    elif (event == "-RESAMPLE-"):
        resample = values["-RESAMPLE-"]
        con.configDataWrite("resample", resample)
        updateImage()

        print(f"Resampling set to: {resample}")

    elif (event == "-INVERT-"):
        invert = values["-INVERT-"]
        if (invert):
            invert = "True"
        else:
            invert = "False"
        con.configDataWrite("invert", invert)
        updateImage()

    elif (event == "F1"):
        if (window["-CONTROLS-"].visible == True):
            window["-CONTROLS-"].update(visible = False)
            controlsShowing = False
        else:
            window["-CONTROLS-"].update(visible = True)
            controlsShowing = True

        window.refresh()
        updateImage()
    
    #Zoom and pan
    elif (event == "-XOFF-" + "Enter"):
        zoomXOff = int(values["-XOFF-"])
        zoomYOff = int(values["-YOFF-"])
        
        zoomScale = round(float(values["-ZOOM_SCALE-"]), 2)
        if (zoomScale < 1):
            zoomScale = 1
            window["-ZOOM_SCALE-"].update(zoomScale)

        if (zoomScale > 5):
            zoomScale = 5
            window["-ZOOM_SCALE-"].update(zoomScale)

        updateImage()
    
    elif (event == "-YOFF-" + "Enter"):
        zoomXOff = int(values["-XOFF-"])
        zoomYOff = int(values["-YOFF-"])
        
        zoomScale = round(float(values["-ZOOM_SCALE-"]), 2)
        if (zoomScale < 1):
            zoomScale = 1
            window["-ZOOM_SCALE-"].update(zoomScale)

        if (zoomScale > 5):
            zoomScale = 5
            window["-ZOOM_SCALE-"].update(zoomScale)

        updateImage()
    
    elif (event == "-ZOOM_SCALE-" + "Enter"):
        zoomXOff = int(values["-XOFF-"])
        zoomYOff = int(values["-YOFF-"])
        
        zoomScale = round(float(values["-ZOOM_SCALE-"]), 2)
        if (zoomScale < 1):
            zoomScale = 1
            window["-ZOOM_SCALE-"].update(zoomScale)

        if (zoomScale > 5):
            zoomScale = 5
            window["-ZOOM_SCALE-"].update(zoomScale)
        
        updateImage()

    elif (event == "Left"):
        zoomXOff -= panSpd
        window["-XOFF-"].update(zoomXOff)

        updateImage()
    elif (event == "Right"):
        zoomXOff += panSpd
        window["-XOFF-"].update(zoomXOff)

        updateImage()
    elif (event == "Up"):
        zoomYOff -= panSpd
        window["-YOFF-"].update(zoomYOff)
            
        updateImage()
    elif (event == "Down"):
        zoomYOff += panSpd
        window["-YOFF-"].update(zoomYOff)

        updateImage()
    elif (event == "Plus"):
        if (zoomScale < 5):
            zoomScale += 0.01
            if (zoomScale > 5):
                zoomScale = 5
            zoomScale = round(zoomScale, 2)
            window["-ZOOM_SCALE-"].update(zoomScale)

            updateImage()
    elif (event == "Minus"):
        if (zoomScale > 1):
            zoomScale -= 0.01
            if (zoomScale < 1):
                zoomScale = 1
            zoomScale = round(zoomScale, 2)
            window["-ZOOM_SCALE-"].update(zoomScale)

            updateImage()


window.close()