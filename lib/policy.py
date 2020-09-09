import uuid
import os
import json
import re

import pandas as pd

from .logger import LoggerFactory

logger = LoggerFactory.getLogger(__name__)

#-----------------------
# Policies
#-----------------------
class PolicyFactory():
    def __init__(self, agentGroup, tenantId, tenantName, shared, enabled, basePrecedence, agentPrecedence, owner, group, beautify, baseThreshold):
        self.agentGroup = agentGroup
        self.tenantId = tenantId
        self.tenantName = tenantName
        self.shared = shared
        self.enabled = enabled
        self.basePrecedence = basePrecedence
        self.agentPrecedence = agentPrecedence
        self.owner = owner
        self.group = group
        self.beautify = beautify
        self.baseThreshold = baseThreshold

    def generatePolicies(self, agentConfigurations):
        logger.info("Generating policies ...")
        policies = []
        tags = {}

        baseCount = 0
        taggedCount = 0
        agentCount = 0

        (configurationMatrix, configurations, baseConfigurations) = self.optimize(agentConfigurations)

        # generate the base policies
        for id, configIds in baseConfigurations.items():
            if self.beautify: id = re.sub("_CONTAINER$", "", id)

            logger.info(f"Generating base policy 'BASE-{self.agentGroup}-{id}' ...")
            policy = self.createPolicy(f'TAG EQUALS "BASE-{id}" AND TAG EQUALS "{self.agentGroup}"', f"BASE-{self.agentGroup}-{id}",
                self.tenantId, self.tenantName, self.shared, self.enabled, self.basePrecedence, self.owner, self.group,
                "Auto generated base policy")
            policies.append(policy)

            for configId in configIds:
                configurations[configId].generate(policy, self)

            baseCount = baseCount + 1

        # loop through configurations and see which ones are not covered by the base policies
        for agentId in configurationMatrix.iloc[:,2:]:
            agentConfigIds = set(configurationMatrix.loc[configurationMatrix[agentId] == True, agentId].index)

            # loop through base configs and see if they cover the agent
            for id, baseConfigIds in baseConfigurations.items():
                if self.beautify: id = re.sub("_CONTAINER$", "", id)

                if baseConfigIds.issubset(agentConfigIds):
                    agentConfigIds = agentConfigIds.difference(baseConfigIds)

                    # add agents to tags
                    if not agentId in tags: tags[agentId] = []
                    tags[agentId].extend([f"BASE-{id}", f"{self.agentGroup}"])

            # if we still have config ids we'll create an agent policy
            if agentConfigIds:
                (agent, port) = agentId.split(":")
                policy = self.createPolicy(f'agentName EQUALS \"{agent}\" AND agentPort NUMBER_EQUALS \"{port}\"',
                    f"HOST-{agent}-{port}",
                    self.tenantId, self.tenantName, self.shared, self.enabled, self.agentPrecedence, self.owner, self.group,
                    "Auto generated agent policy")
                policies.append(policy)
                for configId in agentConfigIds:
                    configurations[configId].generate(policy, self)

                agentCount = agentCount + 1


        logger.info(f"Generated {len(policies)} policies. ({baseCount} base policies, {agentCount} agent policies, {len(tags)} tagged agents)")
        return policies, tags

    def optimize(self, agentConfigurations):
        baseConfigs = {}

        (configurationMatrix, configurations) = self.createConfigurationMatrix(agentConfigurations)

        startColumn = configurationMatrix.columns[2]
        for monitorType in configurationMatrix["__monitorType__"].unique():
            logger.info(f"Optimizing policies for monitor '{monitorType}' ...")
            matrix = configurationMatrix.loc[configurationMatrix.__monitorType__==monitorType,startColumn:]
            logger.info(f"Found {len(matrix)} unique configurations for monitor '{monitorType}'.")


            configIds = self.getBaseConfigIds(matrix)
            if configIds != None:
                baseConfigs[monitorType] = configIds

        return configurationMatrix, configurations, baseConfigs

    def createConfigurationMatrix(self, agentConfigurations):
        # build agent config matrix
        uniqueConfigurations = []
        columns = {}
        # columns['__configid__']={}
        columns['__solution__']={}
        columns['__monitorType__']={}

        agents = []

        for agentConfiguration in agentConfigurations:
            agent = agentConfiguration.agent
            port = agentConfiguration.port

            agentId = f"{agent}:{port}"

            if not agentConfiguration in uniqueConfigurations:
                uniqueConfigurations.append(agentConfiguration)
                
                index = uniqueConfigurations.index(agentConfiguration)

                # columns["__configid__"][index] = agentConfiguration.configuration.getId()
                columns["__solution__"][index] = agentConfiguration.solution
                columns["__monitorType__"][index] = agentConfiguration.monitorType
            
            index = uniqueConfigurations.index(agentConfiguration)
            
            if not agentId in columns: columns[agentId]={}
            columns[agentId][index]=True

        logger.info(f"Optimizing policies for {len(columns) - 2} agents ...")
        logger.info(f"Found {len(uniqueConfigurations)} unique configurations.")

        configurationMatrix=pd.DataFrame()
        for header in columns:
            configurationMatrix[header]=pd.Series(columns[header])
            
        configurationMatrix = configurationMatrix.fillna(False)

        return configurationMatrix, uniqueConfigurations

    def getBaseConfigIds(self, matrix, threshold = 10):
        # get cardinal for agent

        allCols = matrix.columns.tolist()
        newSearch = matrix.columns[1:].tolist()

        duplicates = pd.Series(0, index = allCols)

        for col1 in allCols:
            searchCols = newSearch
            newSearch = []

            for col2 in searchCols:
                if matrix[col1].equals(matrix[col2]):
                    duplicates[col1] = duplicates[col1] + 1
                else:
                    if col2 != searchCols[0]: newSearch.append(col2)

        # get agent with highest cardinal
        top=5
        result = duplicates.sort_values(ascending=False).head(top)
        # logger.info(f"top {top} duplicate agents with same configuration:")
        # for index, value in result.items():
        #     logger.info(f"AgentId '{index}' has {value} duplicates.")

        percent = result[0]/len(matrix.columns)*100
        percentStr = "{:5.2f}".format(percent)

        if percent >=  self.baseThreshold:
            logger.info(f"Found base with {result[0]} duplicates ({percentStr}%) on agent '{result.index[0]}'.")
            return set(matrix.loc[matrix[result.index[0]] == True, result.index[0]].index)
        else:
            logger.info(f"No significant number of duplicates found ({percentStr} < {self.baseThreshold}). No base policy created.")
            return None

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
    def savePolicies(policies, path):
        logger.info(f"Writing polycies to directory '{path}' ...")
        os.makedirs(path, exist_ok = True)

        for policy in policies:
            with open(f"{path}{os.path.sep}{policy['name']}.mo", 'w') as fp:
                json.dump([policy], fp, indent = 4)

    @staticmethod
    def saveTags(tags, path):
        logger.info(f"Writing tags to directory '{path}' ...")
        os.makedirs(path, exist_ok = True)

        for agentId, tags in tags.items():
            (agent, id) = agentId.split(":")
            
            with open(f"{path}{os.path.sep}{agent}_{id}.cfg", 'w') as fp:
                fp.write(f"PATROL_CONFIG{os.linesep}")

                first = True
                for tag in tags:
                    if first:
                        first = False
                    else:
                        fp.write(f",{os.linesep}")

                    fp.write(f'"/AgentSetup/Identification/Tags/TAG/{tag}” = {{ REPLACE = "Auto generated tag" }}')

                fp.write(f'{os.linesep}')
