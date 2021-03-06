import json
import os
from lib.logger import LoggerFactory

logger = LoggerFactory.getLogger(__name__)

class SolutionPack():
    def __init__(self, filename, repository):
        with open(filename) as jsonFile:
            config = json.load(jsonFile)

        self.solution = config['solution']
        self.profile = config['profile'] 
        self.monitorType = config['monitorType']
        self.release = config['release'] 
        self.prefix = config["prefix"] 
        self.patterns = config["patterns"]

        if not self.monitorType in repository.monitors: raise Exception(f"Monitor type {self.monitorType} of solution pack '{filename}' not found is repository.")

        self.configuration = repository.monitors[self.monitorType]["configuration"]


class SolutionPackManager():
    def __init__(self, path, repository):
        self.solutionPacks = []
        self.repository = repository
        for subdir, dirs, files in os.walk(path):
            for file in files:
                try:
                    if file[-5:] == ".json":
                        filename = f"{subdir}{os.path.sep}{file}"
                        logger.info(f"Loading solution pack {filename} ...")

                        solutionPack = SolutionPack(filename, repository)
                        self.solutionPacks.append(solutionPack)

                except Exception as error:
                    raise RuntimeError(f"An unexpected error occured while creating solution pack from file '{filename}'. ({error})")


    @staticmethod
    def generateSolutionPackTemplate(kmRepository, monitorType, path):
        template = {}

        if not monitorType in kmRepository.monitors:
            raise RuntimeError(f"Monitor '{monitorType}' not found in repository.")

        meta = kmRepository.monitors[monitorType]
        if not "configuration" in meta:
            raise RuntimeWarning(f"Monitor '{monitorType}' does not have anything to configure.")

        template["solution"] = meta["solution"]
        template["release"] = meta["release"]
        template["profile"] = "<???>"
        template["monitorType"] = meta["monitorType"]
        template["prefix"] = ""
        template["patterns"] = SolutionPackManager.generatePatterns(meta["configuration"])

        filename = f"{template['solution']}_{template['monitorType']}.tpl"
        os.makedirs(path, exist_ok = True)

        logger.info(f"Writing Solution template to file '{path}{os.path.sep}{filename}' ...")
        with open(f"{path}{os.path.sep}{filename}", 'w') as fp:
            json.dump(template, fp, indent=4)


    @staticmethod
    def generatePatterns(attributes, prefix = ""):
        patterns = []
        for key in attributes:
            attribute = attributes[key]
            pattern = {}
            if attribute['type'] == "List":
                patterns.extend(SolutionPackManager.generatePatterns(attribute["attributes"], f"{prefix}/{attribute['id']}/%{attribute['indexedBy']}%"))

            else:
                patterns.append({
                    "pattern": None,
                    "path": f"{prefix}/{attribute['id']}"
                })

        return patterns