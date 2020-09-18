import pandas as pd
import threading
import queue
import time

from itertools import combinations

from .logger import LoggerFactory

from lib.agentinfo import AgentInfoFactory

logger = LoggerFactory.getLogger(__name__)

class PolicyOptimizer():
    def __init__(self, agentInfo, minAgents, depth, threads, timeout):
        self.agentInfo = AgentInfoFactory.getAgentInfo(agentInfo) if agentInfo != None else None
        self.minAgents = minAgents
        self.depth = depth
        self.threads = threads
        self.timeout = timeout

        self.totalQuality = 0


    def optimize(self, agentConfigurations, threshold):
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

                    configIds = self.optimizeMatrix(matrix, monitorType, threshold)
                    if configIds != None:
                        idx = "-".join(list(name).append(monitorType)) if type(name) is tuple else f"{name}-{monitorType}"
                        baseConfigs[idx] = configIds
        else:
            startColumn = c.columns[2]
            for monitorType in c["_monitorType_"].unique():
                matrix = c.loc[c._monitorType_==monitorType,startColumn:]

                configIds = self.optimizeMatrix(matrix, monitorType, threshold)
                if configIds != None:
                    baseConfigs[monitorType] = configIds

        quality = self.totalQuality / ((c.iloc[:,2:].sum()).sum()) * 100
        logger.info(f"Total coverage of base policies {'{:.2f}'.format(quality)}%.")

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


    def optimizeMatrix(self, matrix, name, threshold):
        s = matrix.sum(axis = 1)
        m = matrix.loc[list(s.loc[s > 1].index),:]

        # sort the columns by occurence of true and remove columns that don't have any true value
        sortedColumns = (m[m.columns.tolist()] == True).sum(axis = 0)
        sortedColumns = sortedColumns.loc[sortedColumns > 0].sort_values(ascending = False).index.tolist()

        logger.info(f"***** {name} *****")
        logger.info(f"Found {len(sortedColumns)} relevant agent(s) and {len(matrix)} configuration(s) {len(m)} being relevant.")
        if len(sortedColumns) == 0 or len(m) == 0: return None

        allIds = set(m.index.tolist())

        q = Queue()
        result = Result()

        c = 0
        for i in range(1, min(len(allIds) + 1, self.depth + 1)):
            for combination in combinations(allIds, i):
                q.put(combination)
                c = c + 1
        
        logger.info(f"Verifying {c} combinations ...")

        # set the timer for the timeout
        start = time.time()
        
        # start the worker threads
        workers = []
        for i in range(0,self.threads):
            t = Worker(q, m, result)
            t.start()
            workers.append(t)

        # wait for worker threads to terminate
        for worker in workers:
            worker.join(10)
            if worker.is_alive():
                if  int(time.time()) - start > self.timeout * 60:
                    logger.info(f"Stopping optimization since timout ({self.timeout} mins) was reached.")
                    for w in workers:
                        w.shutdown = True

                    break


        baseIds = result.baseIds

        agentIds = allIds - baseIds
        numagents = m.loc[baseIds,:].all().value_counts()[True]

        quality = (len(baseIds) * numagents) / ((len(baseIds) * numagents) + (matrix.loc[agentIds,:].sum()).sum()) * 100
        logger.info(f"Found optimal configuration set containing {len(baseIds)} configuration(s), covering {numagents} agent(s). Total coverage {'{:.2f}'.format(quality)}%.")

        self.totalQuality = self.totalQuality + (len(baseIds) * numagents)

        if quality < threshold:
            logger.info(f"No significant configuration set found ({quality} < {threshold}). No base policy created.")
            return None

        return baseIds

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

        logger.info(f"Optimizing policies for {len(columns) - 2} agents and {len(uniqueConfigurations)} unique configurations. Using {self.threads} threads and a depth of {self.depth}.")

        configurationMatrix=pd.DataFrame()
        for header in columns:
            configurationMatrix[header]=pd.Series(columns[header])
            
        configurationMatrix = configurationMatrix.fillna(False)

        return configurationMatrix, uniqueConfigurations

class Result():
    def __init__(self):
        self.maxCoverage = 0
        self.baseIds = None
        self.lock = threading.Lock()

    def set(self, maxCoverage, baseIds):
        self.lock.acquire()
        if maxCoverage > self.maxCoverage:
            self.maxCoverage = maxCoverage
            self.baseIds = baseIds

        self.lock.release()


class Worker(threading.Thread):
    def __init__(self, queue, matrix, result):
        threading.Thread.__init__(self)
        self.queue = queue
        self.matrix = matrix
        self.result = result
        self.shutdown = False

    def run(self):
        combination = self.queue.get()
        while not combination == None and not self.shutdown:
            m = self.matrix.loc[list(combination),:]
            s = m.all()
            c = s.value_counts()
            numagents = c[True] if True in c else 0

            coverage = len(combination) * numagents
            self.result.set(coverage, set(combination))

            combination = self.queue.get()


class Queue():
    def __init__(self):
        self.lock = threading.Lock()
        self.queue = queue.Queue(0)

    def get(self):
        self.lock.acquire()
        if not self.queue.empty():
            d = self.queue.get()
            self.lock.release()
            return d

        else:
            self.lock.release()
            return None

    def put(self, d):
        self.lock.acquire()
        self.queue.put(d)
        self.lock.release()