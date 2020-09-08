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
                        configurations[i].generate(policy, self)
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
        # columns['__configid__']={}
        # columns['__solution__']={}
        # columns['__monitorType__']={}

        agents = []

        for agentConfiguration in agentConfigurations:
            agent = agentConfiguration.agent
            port = agentConfiguration.port

            agentId = f"{agent}:{port}"

            if not agentConfiguration.configuration in uniqueConfigurations:
                uniqueConfigurations.append(agentConfiguration.configuration)
                
                # index = uniqueConfigurations.index(agentConfiguration.configuration)

                # columns["__configid__"][index] = agentConfiguration.configuration.getId()
                # columns["__solution__"][index] = agentConfiguration.configuration.solution
                # columns["__monitorType__"][index] = agentConfiguration.configuration.monitorType
            
            index = uniqueConfigurations.index(agentConfiguration.configuration)
            
            if not agentId in columns: columns[agentId]={}
            columns[agentId][index]=True

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

    autoIndexMap = {}

    def autoIndex(self, key, value):
        if not key in self.autoIndexMap:
            self.autoIndexMap[key] = {
                "counter": 1,
            }

        if not value in self.autoIndexMap[key]:
            self.autoIndexMap[key][value] = self.autoIndexMap[key]["counter"]
            self.autoIndexMap[key]["counter"] = self.autoIndexMap[key]["counter"] + 1

        return self.autoIndexMap[key][value]

    @staticmethod
    def save(policies, path):
        logger.info(f"Writing polycies to directory '{path}' ...")
        os.makedirs(path, exist_ok = True)
        for policy in policies:
            with open(f"{path}{os.path.sep}{policy['name']}.mo", 'w') as fp:
                json.dump([policy], fp, indent = 4)