import os

import constants as const

def workingDirExists():
    if os.path.exists(const.WORKING_DIR):
        return True

    return False


def createWorkingDir():
    try:
        os.makedirs(const.WORKING_DIR)
        print ("Created working directory")
    except:
        print ("Failed to create working directory!")

def createSendDir():
    try:
        os.makedirs(const.TRANSFER_DIR)
        print ("Created transfer directory")
    except Exception as e:
        print (e)
