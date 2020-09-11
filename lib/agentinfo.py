import csv

from lib.logger import LoggerFactory
logger = LoggerFactory.getLogger(__name__)

class AgentInfoFactory():

    @staticmethod
    def getAgentInfo(filename):
        logger.info(f"Loading agent information from file '{filename}'.")
        with open(filename) as fp:
            result = csv.reader(fp)

            agentInfo = {
                "header": None,
                "data": {}
            }
            first = True
            for row in result:
                if first:
                    agentInfo["header"] = row[1:]
                    first = False
                else:
                    agentInfo["data"][row[0]]=row[1:]

        return agentInfo
