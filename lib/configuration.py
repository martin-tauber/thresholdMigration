import json

from lib.logger import LoggerFactory

logger = LoggerFactory.getLogger(__name__)

class AgentConfiguration():
    def __init__(self, agent, port, solution, release, monitorType, attribute):
        self.agent = agent
        self.port = port

        self.solution = solution
        self.release = release
        self.monitorType = monitorType
        self.attribute = attribute

        self.config = {}

    def __eq__(self, other):
        return self.config == other.config and self.solution == other.solution and self.release == other.release and self.monitorType == other.monitorType and self.attribute == other.attribute

    def __hash__(self):
        return hash(json.dumps(self.config, sort_keys=True))

class MonitoringConfiguration(AgentConfiguration):
    def __init__(self, agent, port, solution, release, monitorType, profile, meta):
        super().__init__(agent, port, solution, release, monitorType, None)
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
                profile = item
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
            if item["monitorType"] == self.monitorType:
                monitor = item
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


class InstanceThresholdConfiguration(AgentConfiguration):
    def __init__(self, agent, port, solution, release, monitorType, attribute, absoluteDeviation, autoClose, comparison,
            durationInMins, minimumSamplingWindow, outsideBaseline, percentDeviation, predict, severity, threshold, instanceName, type):

        super().__init__(agent, port, solution, release, monitorType, attribute)

        # Details
        self.config["absoluteDeviation"] = absoluteDeviation
        self.config["autoClose"] = autoClose
        self.config["comparison"] = comparison
        self.config["durationInMins"] = durationInMins
        self.config["minimumSamplingWindow"] = minimumSamplingWindow
        self.config["outsideBaseline"] = outsideBaseline
        self.config["percentDeviation"] = percentDeviation
        self.config["predict"] = predict
        self.config["severity"] = severity
        self.config["threshold"] = threshold

        self.config["instanceName"] = instanceName
        self.config["type"] = type

    def getId(self):
        return f"{self.solution}-{self.monitorType}-{self.attribute}-{self.instanceName}"

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
                "absoluteDeviation": self.config["absoluteDeviation"],
                "autoClose": self.config["autoClose"],
                "comparison": self.config["comparison"],
                "durationInMins": self.config["durationInMins"],
                "minimumSamplingWindow": self.config["minimumSamplingWindow"],
                "outsideBaseline": self.config["outsideBaseline"],
                "percentDeviation": self.config["percentDeviation"],
                "predict": self.config["predict"],
                "severity": self.config["severity"],
                "threshold": self.config["threshold"]
            },
            "instanceName": self.config["instanceName"],
            "matchDeviceName": False,
            "type": self.config["type"]
        })

class MonitoringConfigurationFactory():
    def __init__(self, kmRepository):
        self.kmRepository = kmRepository

    def create(self, agent, port, monitorType, profile):
        meta = self.kmRepository.monitors[monitorType]

        return MonitoringConfiguration(agent, port, meta["solution"], meta["release"], meta["monitorType"], profile, meta)