import uuid
import os
import json
import re

from .logger import LoggerFactory
from lib.agentinfo import AgentInfoFactory
from lib.optimizer import PolicyOptimizer

logger = LoggerFactory.getLogger(__name__)

#-----------------------
# Policies
#-----------------------
class PolicyFactory():
    def __init__(self, agentGroup, tenantId, tenantName, shared, enabled, basePrecedence, agentPrecedence, owner, group, beautify = False, optimizeThreshold = 20, agentInfo = None):
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
        self.optimizeThreshold = optimizeThreshold

        self.optimizer = PolicyOptimizer(agentInfo)

    def generatePolicies(self, agentConfigurations):
        logger.info("Generating policies ...")
        policies = []
        tags = {}

        baseCount = 0
        taggedCount = 0
        agentCount = 0

        (configurationMatrix, configurations, baseConfigurations) = self.optimizer.optimize(agentConfigurations, self.optimizeThreshold)

        # generate the base policies
        for id, configIds in baseConfigurations.items():
            if self.beautify: id = re.sub("_CONTAINER$", "", id)

            policyName = f'BASE-{self.agentGroup}-{id}' if self.agentGroup else f'BASE-{id}'

            logger.info(f"Generating base policy '{policyName}' ...")
            policy = self.createPolicy(f'TAG EQUALS "BASE-{id}"', policyName,
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
                    tags[agentId].extend([f"BASE-{id}"])

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
        logger.info(f"Writing policies to directory '{path}' ...")
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
