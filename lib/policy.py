import uuid
import os
import json

from .logger import LoggerFactory

logger = LoggerFactory.getLogger(__name__)

#-----------------------
# Policies
#-----------------------
class PolicyFactory():
    def __init__(self, kmRepository, tenantId, tenantName, shared, enabled, precedence, owner, group):
        self.configurations = []
        self.kmRepository = kmRepository
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
        for configuration in self.configurations:
            # no agent policy for this agent has been created
            agent = f"{configuration['agent']}:{configuration['port']}"
            if not agent in policies:
                policies[agent] = self.createAgentPolicy(configuration["agent"], configuration["port"],
                    self.tenantId, self.tenantName, self.shared, self.enabled, self.precedence, self.owner, self.group,
                    "Auto generated agent policy")

            # configuration is a server threshold configuration
            if configuration["configurationType"] == "serverThresholdConfiguration":
                configuration["solution"] = self.kmRepository.monitors[configuration["monitorType"]]["solution"]
                configuration["release"] = self.kmRepository.monitors[configuration["monitorType"]]["release"]

                self.generateServerThresholdConfiguration(policies[agent], configuration)

        logger.info(f"Generated {len(policies)} policies.")
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
            "details": {
                "absoluteDeviation": configuration["absoluteDeviation"],
                "autoClose": configuration["autoClose"],
                "comparison": configuration["comparison"],
                "durationInMins": configuration["durationInMins"],
                "minimumSamplingWindow": configuration["minimumSamplingWindow"],
                "outsideBaseline": configuration["outsideBaseline"],
                "percentDeviation": configuration["percentDeviation"],
                "predict": configuration["predict"],
                "severity": configuration["severity"],
                "threshold": configuration["threshold"]
            },
            "instanceName": configuration["instanceName"],
            "matchDeviceName": False,
            "type": configuration["type"]
        })


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


