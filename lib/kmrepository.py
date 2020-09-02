import os
import re
import json
import glob

from xml.etree import cElementTree as ElementTree

from .logger import LoggerFactory

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
            raise Exception("Argument Error. KMRepository constructor can only contain either 'repositoryDir' or 'cache' argument.")

    def loadFile(self, repositoryDir):
        logger.info(f"Loading TrueSight repository located in directory '{repositoryDir}' ...")
        pattern = re.compile(f".*[{os.path.sep}]([^{os.path.sep}]*)[{os.path.sep}]([^{os.path.sep}]*)[{os.path.sep}]lib[{os.path.sep}]knowledge$")

        # walk through the bmc_products directory and find all the lib/knowledge/*.xml files
        for dirname, dirs, files in os.walk(repositoryDir):
            match = pattern.match(dirname)
            if match:
                for file in files:
                    if file.endswith(".xml"):
                        root = ElementTree.parse(f"{dirname}{os.path.sep}{file}").getroot()

                        self.monitors[file[:-4]] = {
                            "monitorType": file[:-4],
                            "solution": match[1],
                            "description": root.attrib["description"] if "description" in root.attrib else None,
                            "majorVersion": root.attrib["majorVersion"] if "majorVersion" in root.attrib else None,
                            "minorVersion": root.attrib["minorVersion"] if "minorVersion" in root.attrib else None,
                            "package": root.attrib["package"] if "package" in root.attrib else None,
                            "productcode": root.attrib["productcode"] if "productcode" in root.attrib else None,
                            "release": match[2]
                        }
    def loadCache(self, cacheDir, version):
        logger.info(f"Loading KM repository from cache '{cacheDir}{os.path.sep}{version}' ...")
        with open(f"{cacheDir}{os.path.sep}{version}") as fp:
            self.monitors = json.load(fp)

    def save(self, path, filename):
        logger.info(f"Writing KM repsoitory to cache '{path}{os.path.sep}{filename}' ...")
        os.makedirs(path, exist_ok = True)
        with open(f"{path}{os.path.sep}{filename}", 'w') as fp:
            json.dump(self.monitors, fp, indent=4)

    @staticmethod
    def get(repositorydir = None, cachedir = None, version = None):
        if repositorydir != None:
            kmRepository = KMRepository(f"{repositorydir}{os.path.set}bmc_products{os.path.sep}kmfiles")

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