import uuid
import os
import json

import pandas as pd

from .logger import LoggerFactory

logger = LoggerFactory.getLogger(__name__)

#-----------------------
# Policies
#-----------------------
class PolicyFactory():
    def __init__(self, tenantId, tenantName, shared, enabled, precedence, owner, group):
        self.configurations = []

        self.tenantId = tenantId
        self.tenantName = tenantName
        self.shared = shared
        self.enabled = enabled
        self.precedence = precedence
        self.owner = owner
        self.group = group

    def generatePolicies(self):
        logger.info("Generating policies ...")
        policies = {}
#        self.getBasePolicies()
        for configuration in self.configurations:
            # no agent policy for this agent has been created
            agent = f"{configuration.agent}:{configuration.port}"
            if not agent in policies:
                policies[agent] = self.createAgentPolicy(configuration.agent, configuration.port,
                    self.tenantId, self.tenantName, self.shared, self.enabled, self.precedence, self.owner, self.group,
                    "Auto generated agent policy")

            configuration.generate(policies[agent])

        logger.info(f"Generated {len(policies)} policies.")
        return policies

    def getBasePolicies(self):
        # build agent config matrix
        uniqueConfigurations = []
        a = {}
        for configuration in self.configurations:
            agent = configuration.agent
            port = configuration.port
            
            del configuration["agent"]
            del configuration["port"]
            if not configuration in uniqueConfigurations:
                uniqueConfigurations.append(configuration)
                
            index = uniqueConfigurations.index(configuration)
            
            if not f"{agent}-{port}" in a:
                a[f"{agent}-{port}"]={}
                
            a[f"{agent}-{port}"][index]=True

        df=pd.DataFrame()
        for i in a:
            df[i]=pd.Series(a[i])
            
        df.fillna(False)

        # get cardinal for agent
        cardinal={}
        cols = df.columns.tolist()

        for col1 in df:
            cardinal[col1] = -1
            if col1 in cols: cols.remove(col1)
            for col2 in cols:
                if df[col1].equals(df[col2]):
                    if cardinal[col1] == -1: cardinal[col1]=0
                    cardinal[col1] = cardinal[col1] + 1
                    cols.remove(col2)

        # get agent with highest cardinal
        max = -2
        for a in cardinal:
            if cardinal[a]>max:
                max = cardinal[a]
                maxa = a    



    def createAgentPolicy(self, agent, port, tenantId, tenantName, shared, enabled, precedence, owner, group, description):
        name = f"{agent}-{port}-Thresholds"
        logger.debug(f"Generating agent policy '{name}' ...")
        return {
            "agentSelectionCriteria": f"agentName EQUALS \"{agent}\" AND agentPort NUMBER_EQUALS \"{port}\"",
            "associatedUserGroup": group,
            "description": description,
            "enabled": enabled,
            "id": str(uuid.uuid4()),
            "name": name,
            "owner": owner,
            "precedence": precedence,
            "shared": shared,
            "tenant": {
                "id": tenantId,
                "name": tenantName
            },
            "type": "monitoring"
        }

    @staticmethod
    def save(policies, path):
        logger.info(f"Writing polycies to directory '{path}' ...")
        os.makedirs(path, exist_ok = True)
        for policy in policies.values():
            with open(f"{path}{os.path.sep}{policy['name']}.mo", 'w') as fp:
                json.dump([policy], fp, indent = 4)        

class Configuration():
    def __init__(self, agent, port):
        self.agent = agent
        self.port = port

    def generate(self, policy):
        pass

class SolutionConfiguration(Configuration):
    def __init__(self, agent, port, solution, release, monitorType, attribute):
        super().__init__(agent, port)

        self.solution = solution
        self.release = release
        self.monitorType = monitorType
        self.attribute = attribute

class InstanceThresholdConfiguration(SolutionConfiguration):
    absoluteDeviation = ""

    def __init__(self, agent, port, solution, release, monitorType, attribute, absoluteDeviation, autoClose, comparison,
            durationInMins, minimumSamplingWindow, outsideBaseline, percentDeviation, predict, severity, threshold, instanceName, type):

        super().__init__(agent, port, solution, release, monitorType, attribute)

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

    def generate(self, policy):
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

