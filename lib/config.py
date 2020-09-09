import json
import os

class CKey():
    #repository
    repositoryDir = "repositoryDir"
    repositoryVersion = "repositoryVersion"
    cacheDir = "cacheDir"

    policyDir = "policyDir"
    tagsDir = "tagsDir"
    agentGroup = "agentGroup"
    beautify = "beautify"
    baseThreshold = "baseThreshold"
    thresholds = "thresholds"
    pconfig = "pconfig"
    monitor = "monitor"

    # policy
    tenantId = "tenantId"
    tenantName = "tenantName"
    basePrecedence = "basePrecedence"
    agentPrecedence = "agentPrecedence"
    shared = "shared"
    enabled = "enabled"
    owner = "owner"
    group = "group"

ckey = CKey()

class CDefault():
    # repository
    repositoryDir = "bmc_products"
    repositoryVersion = None
    cacheDir = "cache"

    policyDir = f"out{os.path.sep}policies"
    tagsDir = f"out{os.path.sep}tags"
    agentGroup = "ALL"
    beautify = False
    baseThreshold = 30
    thresholds = None
    pconfig = None
    monitor = None

    # policy
    tenantId = "*"
    tenantName = "*"
    basePrecedence = "199"
    agentPrecedence = "899"
    shared = False
    enabled = False
    owner = "admin"
    group = "Administrators"

cdefault = CDefault()

class Config():
    keys = []
    default = {}
    value = {}

    def __init__(self, args):
        # initialize the defaults
        for key in self.keys:
            self.default[key] = getattr(cdefault, key)
            self.value[key] = self.default[key]

        # load configuration 
        if args.load != None:
            self.load(args.load)

        # override command line args
        for key in self.keys:
            if hasattr(args, key) and getattr(args, key) != None:
                self.value[key] = getattr(args, key)

    def setAttributes(self):
        # set the attributes of the config for easier access
        for key in self.value:
            setattr(self, key, self.value[key])

    def load(self, filename):
        with open(filename) as fp:
            config = json.load(fp)
            if config["type"] != type(self).__name__:
                raise RuntimeError(f"Configuration file is of incorrect type. Found \'{config['type']}\' expected '{type(self).__name__}'.")

            else:    
                for key in config["config"]:
                    self.value[key] = config["config"][key]

    def save(self, filename):
        path = os.path.dirname(os.path.normpath(filename))
        if path == "": path = "."

        filename  = os.path.basename(os.path.normpath(filename))

        os.makedirs(path, exist_ok = True)
        with open(f"{path}{os.path.sep}{filename}", 'w') as fp:
            json.dump({"type": type(self).__name__, "config": self.value}, fp, indent = 4)

    @staticmethod
    def getType(filename):
        with open(filename) as fp:
            config = json.load(fp)

        return config["type"]


class MigrateConfig(Config):
    keys = [ckey.repositoryDir, ckey.cacheDir, ckey.repositoryVersion, ckey.policyDir, ckey.tagsDir, ckey.agentGroup, ckey.beautify, ckey.baseThreshold, ckey.thresholds,
        ckey.pconfig, ckey.tenantId, ckey.tenantName, ckey.basePrecedence, ckey.agentPrecedence, ckey.shared, ckey.enabled, ckey.owner, ckey.group]

    def __init__(self, args):
        super().__init__(args)

        if (hasattr(args, ckey.repositoryDir)): self.value[ckey.repositoryDir] = args.repositoryDir     
        self.setAttributes()

class CacheRepositoryConfig(Config):
    keys = [ckey.repositoryDir, ckey.cacheDir, ckey.repositoryVersion]

    def __init__(self,args):
        super().__init__(args)
        self.setAttributes()

class GenerateSolutionTemplateConfig(Config):
    keys = [ckey.repositoryDir, ckey.cacheDir, ckey.repositoryVersion, ckey.monitor]

    def __init__(self,args):
        super().__init__(args)
        self.setAttributes()        

        if (hasattr(args, ckey.repositoryDir)): self.value[ckey.repositoryDir] = args.repositoryDir     
        self.setAttributes()
