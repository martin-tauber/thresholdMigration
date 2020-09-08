from .logger import LoggerFactory

logger = LoggerFactory.getLogger(__name__)

class AgentConfiguration():
    def __init__(self, agent, port, configuration):
        self.agent = agent
        self.port = port
        self.configuration = configuration        

class SolutionConfiguration():
    def __init__(self, solution, release, monitorType, attribute):
        self.solution = solution
        self.release = release
        self.monitorType = monitorType
        self.attribute = attribute

class MonitoringConfiguration(SolutionConfiguration):
    def __init__(self, solution, release, monitorType, profile, meta):
        super().__init__(solution, release, monitorType, None)
        self.profile = profile
        self.meta = meta

        self.config = self.init(meta["configuration"])

    def init(self, attributeSet):
        config = {}
        for id in attributeSet:
            if attributeSet[id]["type"] == "List":
                config[id]={}
            else:
                config[id] = attributeSet[id]["default"] if "default" in attributeSet[id] else None

        return config        

    def set(self, path, value):
        metaCursor = self.meta["configuration"]
        configCursor = self.config

        # Loop throu segments of path except for the last. Also skip the first since it is created by the initial "/"
        for segment in path.split("/")[1:-1]:
            if "type" in metaCursor and metaCursor["type"] == "List":
                if not segment in configCursor:
                    configCursor[segment]=self.init(metaCursor["attributes"])

                configCursor = configCursor[segment]
                metaCursor = metaCursor["attributes"]
                continue

            if not segment in metaCursor:
                raise Exception(f"trying to set '{path}' for monitor '{self.monitorType}. Found '{segment}' was expection on of {', '.join([*metaCursor])}.")

            metaCursor = metaCursor[segment]
            configCursor = configCursor[segment]

        # get the varname and check if it is valid
        varname = path.split("/")[-1:][0]
        if not varname in metaCursor:
            raise Exception(f"trying to set '{path}' for monitor '{self.monitorType}. Found '{segment}' was expection on of {', '.join([*metaCursor])}.")

        meta = metaCursor[varname]

        # get the type of the attribute. If no type is set we found an attribure set
        if "type" not in meta:
            raise Exception(f"path '{path}' of monitor '{self.monitorType}' does not point to a configuration attribute.")

        type = meta["type"]
        if type == "List":
            raise Exception(f"path '{path}' of monitor '{self.monitorType}' points to a list and to a configuration attribute.")

        if type == "Boolean":
            if not (value == "0" or value == "1"):
                raise Exception(f"Value for path '{path}' of monitor '{self.monitorType} is of type {type}. Value '{value}' Could not be set.'")

        configCursor[varname] = value


    def generate(self, policy, policyFactory):
        # ensure that policy has monitorConfiguration node 
        if not "monitorConfiguration" in policy:
            policy["monitorConfiguration"] = {
                "configurations": []
            }

        # find and create the profile for this monitoring configuration
        profile = None
        for item in policy["monitorConfiguration"]["configurations"]:
            if item["monitoringProfile"] == self.profile:
                profile = item["monitoringProfile"]
                break

        if profile == None:
            profile = {
                "defaultMonitoring": False,
                "monitoringProfile": self.profile,
                "solutionName": self.solution,
                "solutionVersion": self.release,
                "monitors": []
            }
            policy["monitorConfiguration"]["configurations"].append(profile)

        # find and create the monitor for this monitoring configuration
        monitor = None
        for item in profile["monitors"]:
            if item["monitorTyoe"] == self.monitorType:
                monitor = item["monitorType"]
                break

        if monitor == None:
            monitor = {
                "monitorType": self.monitorType,
                "configuration": []
            }
            profile["monitors"].append(monitor)

        # generate the configuration entries
        monitor["configuration"].extend(self.generateAttributeSet(self.meta["configuration"], self.config, "", policy, policyFactory))

    def generateAttributeSet(self, meta, attributeSet, path, policy, policyFactory):
        config = []
        for id, value in attributeSet.items():
            if meta[id]["type"] == "List":
                for key, item in value.items():
                    if meta[id]["indexedBy"] == "AUTO":
                        config.extend(self.generateAttributeSet(meta[id]["attributes"], item, path + "/" + id + "/" +
                        str(policyFactory.autoIndex(f"{policy['id']}{path}/{id}", key)), policy, policyFactory))
                    else:
                        config.extend(self.generateAttributeSet(meta[id]["attributes"], item, path + "/" + id + "/" +
                        key, policy, policyFactory))

            else:
                if value == None:
                    if meta[id]["isMandatory"]:
                        logger.warn(f"Value not set for mandatory configuration '{path}")
                else:
                    mapPath = path + "/" + id
                    if path == "":
                        details = None

                    else:
                        details = [{
                            "id": id,
                            "secure": meta[id]["isStorageSecure"],
                            "value": value,
                            "mapDetails": {
                                f"/{id}": value
                            },
                            "details": None
                        }]

                    config.append({
                        "id": id,
                        "secure": meta[id]["isStorageSecure"],
                        "value": value,
                        "mapDetails": {
                            mapPath: value
                        },
                        "details": details
                    })

        return config


class InstanceThresholdConfiguration(SolutionConfiguration):
    def __init__(self, solution, release, monitorType, attribute, absoluteDeviation, autoClose, comparison,
            durationInMins, minimumSamplingWindow, outsideBaseline, percentDeviation, predict, severity, threshold, instanceName, type):

        super().__init__(solution, release, monitorType, attribute)

        # Details
        self.absoluteDeviation = absoluteDeviation
        self.autoClose = autoClose
        self.comparison = comparison
        self.durationInMins = durationInMins
        self.minimumSamplingWindow = minimumSamplingWindow
        self.outsideBaseline = outsideBaseline
        self.percentDeviation = percentDeviation
        self.predict = predict
        self.severity = severity
        self.threshold = threshold

        self.instanceName = instanceName
        self.type = type

    def getId(self):
        return f"{self.solution}-{self.monitorType}-{self.attribute}-{self.instanceName}"

    # overriding the __eq__ function to be able to compare two configurations to see if they are equal if
    # all the attributes are equal
    def __eq__(self, other):
        return self.solution == other.solution and \
            self.release == other.release and \
            self.monitorType == other.monitorType and \
            self.attribute == other.attribute and \
                \
            self.absoluteDeviation == other.absoluteDeviation and \
            self.autoClose == other.autoClose and \
            self.comparison == other.comparison and \
            self.durationInMins == other.durationInMins and \
            self.minimumSamplingWindow == other.minimumSamplingWindow and \
            self.outsideBaseline == other.outsideBaseline and \
            self.percentDeviation == other.percentDeviation and \
            self.predict == other.predict and \
            self.severity == other.severity and \
            self.threshold == other.threshold and \
                \
            self.instanceName == other.instanceName and \
            self.type == other.type

    # overriding the __hash__ method to be able to add configurations to an array and ensure that no
    # duplicates are added to the array
    def __hash__(self):
        return hash((
            self.absoluteDeviation,
            self.autoClose,
            self.comparison,
            self.durationInMins,
            self.minimumSamplingWindow,
            self.outsideBaseline,
            self.percentDeviation,
            self.predict,
            self.severity,
            self.threshold,

            self.instanceName,
            self.type  
        ))


    def generate(self, policy, policyFactory):
        if not "serverThresholdConfiguration" in policy:
            policy["serverThresholdConfiguration"] = {
                "solutionThresholds": []
            }

        # Generate solution
        found = False
        for solution in policy["serverThresholdConfiguration"]["solutionThresholds"]:
            if solution["solutionName"] == self.solution and solution["solutionVersion"] == self.release:
                found = True
                break

        if not found:
            solution = {
                "solutionName": self.solution,
                "solutionVersion": self.release,
                "monitors": [] 
            }

            policy["serverThresholdConfiguration"]["solutionThresholds"].append(solution)

        # Generate monitor
        found = False
        for monitor in solution["monitors"]:
            if monitor["monitorType"] == self.monitorType:
                found = True
                break

        if not found:
            monitor = {
                "monitorType": self.monitorType,
                "attributes": []
            }

            solution["monitors"].append(monitor)

        # Generate attribute
        found = False
        for attribute in monitor["attributes"]:
            if attribute["attributeName"] == self.attribute:
                found = True
                break

        if not found:
            attribute = {
                "active": -1,
                "attributeName": self.attribute,
                "regEx": False,
                "thresholds": []
            }

            monitor["attributes"].append(attribute)

        # Generate Threshold
        attribute["thresholds"].append({
            "details": {
                "absoluteDeviation": self.absoluteDeviation,
                "autoClose": self.autoClose,
                "comparison": self.comparison,
                "durationInMins": self.durationInMins,
                "minimumSamplingWindow": self.minimumSamplingWindow,
                "outsideBaseline": self.outsideBaseline,
                "percentDeviation": self.percentDeviation,
                "predict": self.predict,
                "severity": self.severity,
                "threshold": self.threshold
            },
            "instanceName": self.instanceName,
            "matchDeviceName": False,
            "type": self.type
        })

class MonitoringConfigurationFactory():
    def __init__(self, kmRepository):
        self.kmRepository = kmRepository

    def create(self, monitorType, profile):
        meta = self.kmRepository.monitors[monitorType]

        return MonitoringConfiguration(meta["solution"], meta["release"], meta["monitorType"], profile, meta)