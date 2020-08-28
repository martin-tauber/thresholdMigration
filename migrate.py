#!/usr/bin/env python3
import csv
import os
import re
import json
import argparse
import logging
import uuid

from xml.etree import cElementTree as ElementTree

#-----------------------
# Logger
#-----------------------
class LoggerFactory():
    def __init__(self):
        pass

    def getLogger(self, name):
        logger = logging.getLogger(name)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        logger.setLevel(logging.DEBUG)

        return logger


LoggerFactory = LoggerFactory()

#-----------------------
# Thresholds
#-----------------------
class InstanceThresholdMigrator():
    def __init__(self, thresholds):
        self.thresholds = thresholds.set

        self.conditionMap = {
            ">": "GREATER_THAN",
            "<": "SMALLER_THAN",
            "=": "EQUALS",
            "<=": "SMALLER_OR_EQUALS",
            ">=": "GREATER_OR_EQUALS"
        }

        self.absoluteConditionMap = {
            ">": "ABOVE",
            "<": "BELOW"
        }

        self.baselineMap = {
            "Not Enabled": "notEnabled",
            "Auto": "auto",
            "Hourly Baseline": "hourly",
            "Daily Baseline": "daily",
            "Weekly Baseline": "weekly",
            "Hourly And Daily": "hourlyAndDaily",
            "Hourly And Daily Baseline": "hourlyAndDaily",
            "All Baselines": "all"
        }

        self.basetypeMap = {
            "Not Enabled": "notEnabled",
            "Auto": "auto",
            "Hourly": "hourly",
            "Daily": "daily",
            "Weekly": "weekly",
            "Hourly And Daily": "hourlyAndDaily",
            "All Baselines": "all"
        }

    def migrate(self):
        logger.info(f"Migrating {len(self.thresholds)} instance thresholds ...")

        configurations = []
        
        for threshold in self.thresholds:
            configurations.append({
                "agent": threshold["agent"],
                "port": threshold["port"],
                "solution": None,
                "monitorType": threshold["monitorType"],
                "attribute": threshold["attribute"],
                "configurationType": "serverThresholdConfiguration",
                "details" : {
                    "absoluteDeviation" : threshold["absoluteDeviation"],
                    "autoClose": threshold["autoClose"],
                    "comparison": self.absoluteConditionMap[threshold["condition"]] if threshold["thresholdType"] == "absolute" else self.conditionMap[threshold["condition"]] ,
                    "durationInMins": threshold["duration"],
                    "minimumSamplingWindow": threshold["minSampleWindow"],
                    "outsideBaseline": self.baselineMap[threshold["outsideBasline"]],
                    "percentDeviation": threshold["deviation"],
                    "predict": threshold["predict"],
                    "severity": threshold["severity"],
                    "threshold": threshold["value"]
                },
                "instanceName": threshold["instance"],
                "type": threshold["thresholdType"]
            })

        return configurations

class ThresholdSet():
    def __init__(self):
        selt.set = []
        
class FileThresholdSet(ThresholdSet):
    def __init__(self, filename):
        self.set = []
        self.filename = filename

    def load(self):
        logger.info(f"Loading Server Thresholds from '{self.filename}' ...")

        with open(self.filename) as input:
            reader = csv.reader(input)
            for row in reader:
                if row[19] == "false":
                    self.set.append({
                        "agent": row[0].split(':')[0],
                        "port": row[0].split(':')[1],
                        "monitorType": row[1],
                        "device": row[2],
                        "instance": row[3],
                        "attribute": row[4],
                        "severity": row[5].upper(),
                        "duration": row[6],
                        "condition": row[7],
                        "value": row[8],
                        "uom": row[9],
                        "outsideBasline": row[10],
                        "autoClose": row[11],
                        "predict": row[12],
                        "minSampleWindow": row[13] if row[13] != "" else None,
                        "baselineType": row[14],
                        "absoluteDeviation": row[15] if row[15] != "" else None,
                        "deviation": row[16],
                        "suppressEvents": row[17],
                        "thresholdType": row[18].lower()
                    })

#-----------------------
# Policies
#-----------------------
class PolicyFactory():
    def __init__(self, kmRepository, defaults = {}):
        self.configurations = []
        self.kmRepository = kmRepository
        self.defaults = defaults

    def generatePolicies(self):
        policies = {}
        for configuration in self.configurations:
            # no agent policy for this agent has been created
            agent = f"{configuration['agent']}:{configuration['port']}"
            if not agent in policies:
                policies[agent] = self.createAgentPolicy(configuration["agent"], configuration["port"])

            # configuration is a server threshold configuration
            if configuration["configurationType"] == "serverThresholdConfiguration":
                configuration["solution"] = self.kmRepository.monitors[configuration["monitorType"]]["solution"]
                configuration["release"] = self.kmRepository.monitors[configuration["monitorType"]]["release"]

                self.generateServerThresholdConfiguration(policies[agent], configuration)

        return policies

    def generateServerThresholdConfiguration(self, policy, configuration):
        agent = configuration["agent"]
        port = configuration["port"]
        if not "serverThresholdConfiguration" in policy:
            policy["serverThresholdConfiguration"] = {
                "solutionThresholds": []
            }

        # Generate solution
        found = False
        for solution in policy["serverThresholdConfiguration"]["solutionThresholds"]:
            if solution["solutionName"] == configuration["solution"] and solution["solutionVersion"] == configuration["release"]:
                found = True
                break

        if not found:
            solution = {
                "solutionName": configuration["solution"],
                "solutionVersion": configuration["release"],
                "monitors": [] 
            }

            policy["serverThresholdConfiguration"]["solutionThresholds"].append(solution)

        # Generate monitor
        found = False
        for monitor in solution["monitors"]:
            if monitor["monitorType"] == configuration["monitorType"]:
                found = True
                break

        if not found:
            monitor = {
                "monitorType": configuration["monitorType"],
                "attributes": []
            }

            solution["monitors"].append(monitor)

        # Generate attribute
        found = False
        for attribute in monitor["attributes"]:
            if attribute["attributeName"] == configuration["attribute"]:
                found = True
                break

        if not found:
            attribute = {
                "active": -1,
                "attributeName": configuration["attribute"],
                "regEx": False,
                "thresholds": []
            }

            monitor["attributes"].append(attribute)

        # Generate Threshold
        attribute["thresholds"].append({
            "details": configuration["details"],
            "instanceName": configuration["instanceName"],
            "matchDeviceName": False,
            "type": configuration["type"]
        })


    def createAgentPolicy(self, agent, port):
        name = f"{agent}-{port}-Thresholds"
        logger.info(f"Generating agent policy '{name}' ...")
        return {
            "agentSelectionCriteria": f"agentName EQUALS \"{agent}\" AND agentPort NUMBER_EQUALS \"{port}\"",
            "associatedUserGroup": self.defaults["associatedUserGroup"] if "associatedUserGroup" in self.defaults else "Administrators",
            "description": self.defaults["description"] if "description" in self.defaults else "Auto Generated Agent Policy",
            "enabled": self.defaults["enabled"] if "enabled" in self.defaults else False,
            "id": str(uuid.uuid4()),
            "name": name,
            "owner": self.defaults["owner"] if "owner" in self.defaults else "admin",
            "precedence": self.defaults["agentPrecedence"] if "agentPrecedence" in self.defaults else "399",
            "shared": self.defaults["shared"] if "shared" in self.defaults else False,
            "tenant": {
                "id": self.defaults["tenantId"] if "tenantId" in self.defaults else "*",
                "name": self.defaults["tenantName"] if "tenantName" in self.defaults else "*"
            },
            "type": "monitoring"
        }


#-----------------------
# KMRepository
#-----------------------

class KMRepository():
    def __init__(self, dirname):
        self.dirname = dirname
        self.monitors = {}

    def load(self):
        logger.info(f"Loading TrueSight repository located in directory '{self.dirname}' ...")
        pattern = re.compile(f".*[{os.path.sep}]([^{os.path.sep}]*)[{os.path.sep}]([^{os.path.sep}]*)[{os.path.sep}]lib[{os.path.sep}]knowledge$")

        # walk through the bmc_products directory and find all the lib/knowledge/*.xml files
        for dirname, dirs, files in os.walk(self.dirname):
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
                            "release": root.attrib["release"] if "release" in root.attrib else match[2]
                        }

#-----------------------
# Utils
# ----------------------

defaultRepositoryDir="bmc_products"
defaultTenantId="*"
defaultTenantName="*"
defaultPrecedence="399"
defaultFilename="thresholds.csv"
defaultOut="out"
defaultDirectory="."
defaultOwner="admin"
defaultGroup="Administrators"
                        
def parseArguments():
    parser = parser = argparse.ArgumentParser(description='Generate TrueSight monitoring policies from instance thresholds.')
    parser.add_argument('-r','--repository', action="store", dest="repositoryDir",
        help=f"path to the bmc repository. The default path is '{defaultRepositoryDir}'. The repository is needed to gather information about solutions to be able to create policies.")

    parser.add_argument("--tenantId", action="store", dest="tenantId",
        help=f"Tenant id to be used in policy generation. The default tenant id is '{defaultTenantId}'.")

    parser.add_argument("--tenantName", action="store", dest="tenantName",
        help=f"Tenant name to be used in policy generation The default tenant name is '{defaultTenantName}'.")

    parser.add_argument("-p", "--precedence", action="store", dest="precedence",
        help=f"precedence to be used in policy generation. The default precedence is '{defaultPrecedence}.")

    parser.add_argument("-f", "--file", action="store", dest="filename",
        help=f"name of the file which which contains the thresholds exported from tsps. The default file name is '{defaultFilename}'")

    parser.add_argument("-o", "--out", action="store", dest="out",
        help=f"path to the directory where the generated policies should be stored. The default is '{defaultOut}'.'")
    
    parser.add_argument("-d", "--directory", action="store", dest="directory",
        help=f"path to the directory where the exported threshold files reside. The default directory is '{defaultDirectory}'")

    parser.add_argument("--owner", action="store", dest="owner",
        help=f"name of the owner of the policy. The default owner is '{defaultOwner}'.")

    parser.add_argument("--shared", action="store_true", dest="shared", 
        help=f"share the generated policy. The default is that the policy is not shared")

    parser.add_argument("--enabled", action="store_true", dest="enabled", 
        help=f"enable the generated policy. The default is that the policy is not enabled")

    parser.add_argument("--group", action="store", dest="group",
        help=f"name of the group to be used in the generated policy. The default group is '{defaultGroup}'.")

    return parser.parse_args()

def getDefaults(args):
    defaults = {}
    defaults["repositoryDir"] = args.repositoryDir if args.repositoryDir else defaultRepositoryDir
    defaults["tenantId"] = args.tenantId if args.tenantId else defaultTenantId
    defaults["tenantName"] = args.tenantName if args.tenantName else defaultTenantName
    defaults["agentPrecedence"] = args.precedence if args.precedence else defaultPrecedence
    defaults["filename"] = args.filename if args.filename else defaultFilename
    defaults["out"] = args.out if args.out else defaultOut
    defaults["owner"] = args.owner if args.owner else defaultOwner
    defaults["shared"] = args.shared
    defaults["enabled"] = args.enabled
    defaults["associatedUserGroup"] = args.group if args.group else defaultGroup
 
    return defaults

def dump(policies, out):
    for policy in policies.values():
        with open(f"{policy['name']}.mo", 'w') as fp:
            json.dump([policy], fp)    

#-----------------------
# Main
#-----------------------


version = "1.0.0"

logger = LoggerFactory.getLogger(__name__)
logger.info(f"{__file__} Threshold Migration Utility Version {version} (c) 2020 BMC Software Inc.")

args = parseArguments()
defaults = getDefaults(args)

# Load the KM Repository
kmRepository = KMRepository("/Users/martin/Development/pcm2cma/in/bmc_products/kmfiles/")
kmRepository.load()

# load the Threshold File
thresholdSet = FileThresholdSet("/Users/martin/Downloads/clm-aus-018821_AllInstanceThresholdSettings_2020_08_25_23_22_25.csv")
thresholdSet.load()

# Migrate Thresholds
instanceThresholdMigrator = InstanceThresholdMigrator(thresholdSet)
configurations = instanceThresholdMigrator.migrate()

# Generate Policies
policyFactory = PolicyFactory(kmRepository, defaults)
policyFactory.configurations.extend(configurations)
policies = policyFactory.generatePolicies()

# Write Policies to file
dump(policies, defaults["out"])


logger.info("done.")