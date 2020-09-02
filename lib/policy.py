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
        self.tenantId = tenantId
        self.tenantName = tenantName
        self.shared = shared
        self.enabled = enabled
        self.precedence = precedence
        self.owner = owner
        self.group = group

    def generatePolicies(self, agentConfigurations):
        logger.info("Generating policies ...")
        policies = []
        tags = {}

        baseCount = 0
        taggedCount = 0
        agentCount = 0

        (configurationMatrix, configurations, id) = self.optimize(agentConfigurations)
        logger.info(f"base based in '{id}'")
        for agentId in configurationMatrix:
            if agentId == id:
                # generate base policy
                policy = self.createPolicy(f'TAG EQUALS "BASE"', "BASE",
                    self.tenantId, self.tenantName, self.shared, self.enabled, self.precedence, self.owner, self.group,
                    "Auto generated base policy")
                policies.append(policy)
                baseCount = baseCount + 1

                i=0
                for hasConfig in configurationMatrix[agentId]:
                    if hasConfig:
                        configurations[i].generate(policy)
                    i = i + 1

            if configurationMatrix[id].equals(configurationMatrix[agentId]):
                tags[agentId]="BASE"
                taggedCount = taggedCount + 1
                continue

            else:
                # generate agent policy
                (agent, port) = agentId.split(":")
                policy = self.createPolicy(f'agentName EQUALS \"{agent}\" AND agentPort NUMBER_EQUALS \"{port}\"',
                    f"{agent}-{port}-Thresholds",
                    self.tenantId, self.tenantName, self.shared, self.enabled, self.precedence, self.owner, self.group,
                    "Auto generated agent policy")
                policies.append(policy)
                agentCount = agentCount + 1

                i = 0
                for hasConfig in configurationMatrix[agentId]:
                    if hasConfig:
                        configurations[i].generate(policy)
                    i = i + 1


        logger.info(f"Generated {len(policies)} policies. ({baseCount} base policies, {agentCount} agent policies, {taggedCount} tagged agents)")
        return policies, tags

    def optimize(self, agentConfigurations):
        (configurationMatrix, configurations) = self.createConfigurationMatrix(agentConfigurations)

        id = self.getBaseId(configurationMatrix)

        return configurationMatrix, configurations, id

    def createConfigurationMatrix(self, agentConfigurations):
        # build agent config matrix
        uniqueConfigurations = []
        columns = {}
        for agentConfiguration in agentConfigurations:
            agent = agentConfiguration.agent
            port = agentConfiguration.port
            
            if not agentConfiguration.configuration in uniqueConfigurations:
                uniqueConfigurations.append(agentConfiguration.configuration)
                
            index = uniqueConfigurations.index(agentConfiguration.configuration)
            
            if not f"{agent}:{port}" in columns: columns[f"{agent}:{port}"]={}
            columns[f"{agent}:{port}"][index]=True

        logger.info(f"Optimizing policies for {len(columns)} agents ...")
        logger.info(f"Found {len(uniqueConfigurations)} unique configurations.")

        configurationMatrix=pd.DataFrame()
        for header in columns:
            configurationMatrix[header]=pd.Series(columns[header])
            
        configurationMatrix = configurationMatrix.fillna(False)

        return configurationMatrix, uniqueConfigurations

    def getBaseId(self, configurationMatrix):
        # get cardinal for agent

        allCols = configurationMatrix.columns.tolist()
        newSearch = configurationMatrix.columns[1:].tolist()

        duplicates = pd.Series(0, index = allCols)

        for col1 in allCols:
            searchCols = newSearch
            newSearch = []

            for col2 in searchCols:
                if configurationMatrix[col1].equals(configurationMatrix[col2]):
                    duplicates[col1] = duplicates[col1] + 1
                else:
                    if col2 != searchCols[0]: newSearch.append(col2)

        # get agent with highest cardinal
        top=5
        logger.info(f"top {top} duplicate agents with same configuration:")
        result = duplicates.sort_values(ascending=False).head(top)
        for index, value in result.items():
            logger.info(f"AgentId '{index}' has {value} duplicates.")

        return result.index[0]
    

    def createPolicy(self, agentSelectionCriteria, name, tenantId, tenantName, shared, enabled, precedence, owner, group, description):
        logger.debug(f"Generating agent policy '{name}' ...")
        return {
            "agentSelectionCriteria": agentSelectionCriteria,
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
        for policy in policies:
            with open(f"{path}{os.path.sep}{policy['name']}.mo", 'w') as fp:
                json.dump([policy], fp, indent = 4)


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

