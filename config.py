from configparser import ConfigParser
from distutils.command.config import config
import constants as const
import os

configPath = const.WORKING_DIR + const.CONFIG_NAME

class Config:
    def __init__(self):
        self.config = ConfigParser(allow_no_value=True)
        self.config.read(configPath)

    def configRewrite(self):
        with open(configPath, "w") as configfile:
            self.config.write(configfile)

    def configSetDefaults(self): #Can be depricated once Server is updated to new functionality
        if not os.path.exists(configPath):
            self.config["Settings"] = {
                "app_version" : str(const.APP_VER),
                "refresh_rate" : str(const.REFRESH_RATE_DEF),
                "screenShotsToStore": str(const.TRANSFER_FRAMES_MAX_DEFAULT),
                "jpgQuality": str(const.JPG_QUALITY),
                "sharpening" : str(const.SHARPENING),
                "scaling" : str(const.SCALING),
                "monitor" : "1",
                "ip" : const.DEFAULT_IP,
                "port" : str(const.DEFAULT_PORT),
                "key" : "default",
                "failedAttempMax" : str(const.FAILED_ATTEMPT_MAX),
                "connectionTimeoutSeconds" : str(const.CONNECTION_TIMEOUT_SECONDS),
                "invert": const.INVERT,
                "resample": const.RESAMPLE,
                "xoff": const.XOFF,
                "yoff": const.YOFF,
                "zoom_Scale": const.ZOOM_SCALE
            }
            
            self.configRewrite()

    #def configRead():
        #config.read(configPath)
        #return config["Settings"]

    def configDataGet(self, _key, _default):
        if (not self.config.has_section("Settings")):
            self.config["Settings"] = {}

        _default = str(_default)
        if (self.config.has_option("Settings", _key)):
            return self.config["Settings"][_key]
        else:
            print(f"Config option missing! [{_key}] Fetching default and adding option for next time.")
            self.config["Settings"][_key] = _default
            self.configRewrite()
            return _default

    def configDataWrite(self, _key, _data):
        if (not self.config.has_section("Settings")):
            self.config["Settings"] = {}
        
        self.config["Settings"][_key] = str(_data)
        self.configRewrite()

c = Config()