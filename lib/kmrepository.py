import os
import re
import json
import glob

from xml.etree import cElementTree as ElementTree

from lib.logger import LoggerFactory

logger = LoggerFactory.getLogger(__name__)

#-----------------------
# KMRepository
#-----------------------
class KMRepository():
    def __init__(self, repositoryDir = None, cacheDir = None, version = None):
        self.monitors = {}
        if repositoryDir != None:
            self.loadFile(repositoryDir)
        elif cacheDir != None:
            self.loadCache(cacheDir, version)
        else:
            raise RuntimeError("Argument Error. KMRepository constructor can only contain either 'repositoryDir' or 'cache' argument.")

    def loadFile(self, repositoryDir):
        logger.info(f"Loading TrueSight repository located in directory '{repositoryDir}' ...")
        pattern = re.compile(f".*[{os.path.sep}]([^{os.path.sep}]*)[{os.path.sep}]([^{os.path.sep}]*)[{os.path.sep}]lib[{os.path.sep}]knowledge$")

        # walk through the bmc_products directory and find all the lib/knowledge/*.xml files
        for dirname, dirs, files in os.walk(repositoryDir):
            match = pattern.match(dirname)
            if match:
                for file in files:
                    if file.endswith(".xml"):
                        logger.info(f"parsing {dirname}{os.path.sep}{file} ...")
                        root = ElementTree.parse(f"{dirname}{os.path.sep}{file}").getroot()

                        monitor = {
                            "monitorType": file[:-4],
                            "solution": match[1],
                            "description": root.attrib["description"] if "description" in root.attrib else None,
                            "majorVersion": root.attrib["majorVersion"] if "majorVersion" in root.attrib else None,
                            "minorVersion": root.attrib["minorVersion"] if "minorVersion" in root.attrib else None,
                            "package": root.attrib["package"] if "package" in root.attrib else None,
                            "productcode": root.attrib["productcode"] if "productcode" in root.attrib else None,
                            "release": match[2]
                        }

                        self.monitors[file[:-4]] = monitor

                        elConfigurationParameter = root.find("./Applications/Application/KMConfigurationMetadata/ConfigurationParameters/ConfigurationParameter")
                        if elConfigurationParameter != None: 
                            if elConfigurationParameter[0].tag == "AttributeSet":
                                (id, attribute) = self.parseAttributeSet(elConfigurationParameter[0], {})
                                monitor["configuration"] = attribute
                            else:
                                (id, attribute) = self.parseAttribute(elConfigurationParameter[0])
                                monitor["configuration"] = {
                                    id: attribute
                                }

                        monitor["parameters"] = {} 
                        elParameters = root.find("./Applications/Application/Parameters")
                        if elParameters != None:
                            for elChild in elParameters.getchildren():
                                monitor["parameters"][elChild.attrib["name"]] = {
                                    "output": elChild.attrib["output"] if "output" in elChild.attrib else None,
                                    "title": elChild.attrib["title"] if "title" in elChild.attrib else None,
                                    "type": elChild.attrib["type"] if "type" in elChild.attrib else None,
                                    "active": elChild.attrib["active"] if "active" in elChild.attrib else None
                                }


    def parseAttributeSet(self, node, set):
        for elChild in node.getchildren():
            if elChild[0].tag == "AttributeSet":
                self.parseAttributeSet(elChild[0], set)
            else:
                (id, attribute) = self.parseAttribute(elChild[0])
                set[id] = attribute

        return (node.attrib["id"] if "id" in node.attrib else None, set)

    def parseAttribute(self, child):
        attribute = {}
        if child.tag == "AttributeSet":
            self.parseAttributeSet(child, attribute)
            return (None, None)

        elif child.tag == "List":
            attribute["type"] = child.tag
            attribute["id"] = child.attrib["id"]
            attribute["label"] = child.attrib["label"]
            attribute["description"] = child.attrib["description"] if "description" in child else None
            attribute["indexedBy"] = child.attrib["indexedBy"]
            (id, attributeSet) = self.parseAttributeSet(child[0], {})
            attribute["attributes"] = attributeSet

            return (child.attrib["id"], attribute)
        elif child.tag in ["String", "AccountName", "Boolean"]:
            attribute["type"] = child.tag
            attribute["id"] = child.attrib["id"]
            attribute["label"] = child.attrib["label"]
            attribute["desciption"] = child.attrib["description"] if "description" in child else None
            attribute["isMandatory"] = child.attrib["isMandatory"] if "isMandatory" in child else False
            attribute["default"] = child.attrib["default"] if "default" in child.attrib else None
            attribute["isStorageSecure"] = child.attrib["isStorageSecure"] if "isStorageSecure" in child.attrib else False

            return (child.attrib["id"], attribute)
        elif child.tag in ["Enum", "MultiSelect"]:
            attribute["type"] = child.tag
            attribute["id"] = child.attrib["id"]
            attribute["label"] = child.attrib["label"]
            attribute["desciption"] = child.attrib["description"] if "description" in child else None
            attribute["isMandatory"] = child.attrib["isMandatory"] if "isMandatory" in child else False
            attribute["default"] = child.attrib["default"] if "default" in child.attrib else None
            attribute["isStorageSecure"] = child.attrib["isStorageSecure"] if "isStorageSecure" in child.attrib else False
            attribute["enumerators"] = {}

            for enumerator in child.find("./Enumerators"):
                id = enumerator.attrib["id"] if "id" in enumerator.attrib else enumerator.attrib["value"]
                attribute["enumerators"][id] = {
                    "label": enumerator.attrib["label"],
                    "value": enumerator.attrib["value"]
                }

            return (child.attrib["id"], attribute)

        elif child.tag == "Counter":
            attribute["type"] = child.tag
            attribute["id"] = child.attrib["id"]
            attribute["label"] = child.attrib["label"]
            attribute["minValue"] = child.attrib["minValue"]
            attribute["maxValue"] = child.attrib["maxValue"]

            attribute["desciption"] = child.attrib["description"] if "description" in child else None
            attribute["isMandatory"] = child.attrib["isMandatory"] if "isMandatory" in child else False
            attribute["default"] = child.attrib["default"] if "default" in child.attrib else None
            attribute["isStorageSecure"] = child.attrib["isStorageSecure"] if "isStorageSecure" in child.attrib else False

            return (child.attrib["id"], attribute)
        else:
           raise RuntimeError(f"Found unexpected tag '{child.tag}' ")


    def loadCache(self, cacheDir, version):
        logger.info(f"Loading KM repository from cache '{cacheDir}{os.path.sep}{version}' ...")
        with open(f"{cacheDir}{os.path.sep}{version}") as fp:
            self.monitors = json.load(fp)

    def save(self, path, filename):
        logger.info(f"Writing KM repsoitory to cache '{path}{os.path.sep}{filename}' ...")
        os.makedirs(path, exist_ok = True)
        with open(f"{path}{os.path.sep}{filename}", 'w') as fp:
            json.dump(self.monitors, fp, indent=4)

    def getConfiguration(self, monitorType, path):
        meta = self.monitors[monitorType]
        attribute = meta["configuration"]

        skip = False
        for segment in path.split("/")[1:]:
            if not skip:
                attribute = attribute[segment]
                if attribute["type"] == "List": skip = True
            else:
                skip = False

        return attribute

    def getRealName(self, monitorType, parameter):
        if not monitorType in self.monitors: raise RuntimeError(f"Monitor Type '{monitorType}' not found in repository.")

        p1 = parameter.lower()

        for p2 in self.monitors[monitorType]["parameters"]:
            if p1 == p2.lower(): return p2

        raise RuntimeError(f"Parameter '{parameter} for monitor type {monitorType} not found in repository.")

    @staticmethod
    def get(repositorydir = None, cachedir = None, version = None):
        if repositorydir != None:
            kmRepository = KMRepository(f"{repositorydir}{os.path.sep}bmc_products{os.path.sep}kmfiles")

        elif version != None:
            kmRepository = KMRepository(cachedir)
            kmRepository.loadCache(f"{cachedir}{os.path.sep}{version}")

        else:
            # get the highest version
            l = glob.glob(f"{cachedir}{os.path.sep}*")
            l.sort(reverse=True)

            version  = os.path.basename(os.path.normpath(l[0]))
            kmRepository = KMRepository(cacheDir=cachedir, version=version)

        return kmRepository