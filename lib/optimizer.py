import pandas as pd

from .logger import LoggerFactory

from lib.agentinfo import AgentInfoFactory

logger = LoggerFactory.getLogger(__name__)

class PolicyOptimizer():
    def __init__(self, agentInfo):
        self.agentInfo = AgentInfoFactory.getAgentInfo(agentInfo) if agentInfo != None else None


    def optimize(self, agentConfigurations, threshold, minAgents):
        baseConfigs = {}

        (c, configurations) = self.createConfigurationMatrix(agentConfigurations)

        if len(configurations) == 0 or len(c.columns) == 2:
            logger.warn("Nothing found to optimize.")
            return c, configurations, baseConfigs

        if self.agentInfo != None:
            # generate the group by dataframe
            g = pd.DataFrame()
            for attribute in self.agentInfo["header"]:
                g[attribute] = c.loc[f"_{attribute}_"][2:]
            
            # loop through the groups
            for name, group in g.groupby(self.agentInfo["header"]):
                gc = self.filter(c, self.agentInfo["header"], list(name) if type(name) is tuple else [name])

                logger.info(f"Optimizing agent group *** {name} ***")

                startColumn = gc.columns[2]
                for monitorType in gc["_monitorType_"][len(self.agentInfo["header"]):].unique():
                    matrix = gc.loc[gc._monitorType_==monitorType,startColumn:]

                    configIds = self.optimizeMatrix(matrix, monitorType, threshold, minAgents)
                    if configIds != None:
                        idx = "-".join(list(name).append(monitorType)) if type(name) is tuple else f"{name}-{monitorType}"
                        baseConfigs[idx] = configIds
        else:
            startColumn = c.columns[2]
            for monitorType in c["_monitorType_"].unique():
                matrix = c.loc[c._monitorType_==monitorType,startColumn:]

                configIds = self.optimizeMatrix(matrix, monitorType, threshold, minAgents)
                if configIds != None:
                    baseConfigs[monitorType] = configIds


        return c, configurations, baseConfigs


    def filter(self, matrix, attributes, values):
        cols = []
        i=0
        for attribute in attributes:
            # get the row of the attribute
            s=matrix.loc[[f"_{attribute}_"],:].squeeze()[2:]
            # add the list of columns 
            cols.append(set(s[s == values[i]].index))
            i = i + 1

        c = ['_solution_', '_monitorType_']
        c.extend(list(set.intersection(*cols)))

        return matrix[c]


    def optimizeMatrix(self, matrix, name, threshold, minAgents):
        # sort the columns by occurence of true
        sortedColumns = (matrix[matrix.columns.tolist()] == True).sum(axis = 0)
        sortedColumns = sortedColumns.loc[sortedColumns > 0].sort_values(ascending = False).index.tolist()

        logger.info(f"Found {len(sortedColumns)} relevant agent(s) and {len(matrix)} configuration(s) for '{name}'.")

        # sort the rows by occurence of true
        sortedRows = (matrix[matrix.columns.tolist()] == True).sum(axis = 1).sort_values(ascending = False).index.tolist()

        # rearange the matrix
        matrix = matrix.reindex(sortedColumns, axis = 1).reindex(sortedRows)

        # get the maximum square containing true values
        maxx = len(matrix.columns)
        maxy = len(matrix.index)
        x = 0
        y = 0

        while (matrix.iloc[y,x] == True and y + 1 < maxy):
            y = y + 1

        gx = x
        gy = y

        while (y >= 0):
            while (x + 1 < maxx and matrix.iloc[y,x + 1] == True):
                x = x + 1
                if (gx + 1) * (gy + 1) < (x + 1) * (y + 1):
                    gx = x
                    gy = y

            y = y - 1

        quality = (gy + 1) * (gx + 1) / (maxx * maxy) * 100
        logger.info(f"Found optimal configuration set containing {gy + 1} configuration(s), covering {gx + 1} agent(s). Total coverage {quality} %.")

        if quality < threshold:
            logger.info(f"No significant configuration set found ({quality} < {threshold}). No base policy created.")
            return None

        if gx + 1 < minAgents:
            logger.info(f"No significant number of agents found ({gx + 1} < {minAgents}). No base policy created.")
            return None

        return set(matrix.index[:gy + 1].tolist())



    def createConfigurationMatrix(self, agentConfigurations):
        # build agent config matrix
        uniqueConfigurations = []
        columns = {}
        # columns['__configid__']={}
        columns['_solution_']={}
        columns['_monitorType_']={}

        # set the cell for the agent info attribute to blank for special variables
        if self.agentInfo:
            for attribute in self.agentInfo["header"]:
                columns['_solution_'][f"_{attribute}_"] = ""
                columns['_monitorType_'][f"_{attribute}_"] = ""

        agents = []

        for agentConfiguration in agentConfigurations:
            agent = agentConfiguration.agent
            port = agentConfiguration.port

            agentId = f"{agent}:{port}"

            if not agentConfiguration in uniqueConfigurations:
                uniqueConfigurations.append(agentConfiguration)
                
                index = uniqueConfigurations.index(agentConfiguration)

                # columns["__configid__"][index] = agentConfiguration.configuration.getId()
                columns["_solution_"][index] = agentConfiguration.solution
                columns["_monitorType_"][index] = agentConfiguration.monitorType
            
            index = uniqueConfigurations.index(agentConfiguration)
            
            if not agentId in columns:
                columns[agentId]={}
                # fill the attribute row for the agent with the agentinfo attributes
                if self.agentInfo:
                    info = self.agentInfo["data"][agent] if agent in self.agentInfo["data"] else None
                    i = 0
                    for attribute in self.agentInfo["header"]:
                        columns[agentId][f"_{attribute}_"] = info[i] if info != None else None

                        i = i + 1                   

            columns[agentId][index]=True

        logger.info(f"Optimizing policies for {len(columns) - 2} agents ...")
        logger.info(f"Found {len(uniqueConfigurations)} unique configurations.")

        configurationMatrix=pd.DataFrame()
        for header in columns:
            configurationMatrix[header]=pd.Series(columns[header])
            
        configurationMatrix = configurationMatrix.fillna(False)

        return configurationMatrix, uniqueConfigurations
