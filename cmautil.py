#!/usr/bin/env python3

import os
import re
import json
import argparse
import traceback
from lib.logger import LoggerFactory

from lib.thresholds import InstanceThresholdMigrator, FileThresholdSet
from lib.kmrepository import KMRepository
from lib.policy import PolicyFactory
from lib.config import MigrateConfig, CacheRepositoryConfig, GenerateSolutionTemplateConfig, ckey, cdefault, Config
from lib.ruleset import RuleSetFactory, RulesetMigrator
from lib.solution import SolutionPackManager

def parseArguments():
    parser = parser = argparse.ArgumentParser(description='The CMA migration utility allows you to migrate external sources to TrueSight monitoring policies. ')
    parser.add_argument('--load', action="store", dest="load",
        help="load configuration from file. This option will load the command line arguments stored with the save command. If you " +
            "specify additional command line parameters, they will overrider the values loaded from the configuration file. ")

    parser.add_argument('--save', action="store", dest="save",
        help="save configuration in file. Stores all the command line arguments in a file. These values then can be loaded again " +
            "using the --load option.")

    cmdParsers = parser.add_subparsers( dest="cmd", help='sub-command help' )

    #------------------
    # Migrate
    #------------------
    migrateCmd = cmdParsers.add_parser('migrate', help="The 'migrate' command allows you to migrate external sources to TrueSight monitoring policies. " +
        "Currently the command supports migrating server thresholds exported from TrueSight Infrastructure Servers. "
        "Use 'migrate -h' to get more information on the migrate command.")

    migrateCmd.add_argument("-t", "--thresholds", action="store", dest=ckey.thresholds, nargs="+",
        help=f"name of the file which which contains the thresholds exported from tsps. The default file name is \'{cdefault.thresholds}\'")

    migrateCmd.add_argument("--pconfig", action="store", dest=ckey.pconfig, nargs="+",
        help=f"pconfig file that should be migrated to cma.")

    migrateCmd.add_argument('-r','--repositorydir', action="store", dest=ckey.repositoryDir,
        help=f"path to the bmc repository. The default path is \'{cdefault.repositoryDir}\'. The repository is needed to gather information about solutions to be able to create policies. "+
            "the solution is delivered with 'cached' versions of the repository. A cached version is a stripped version of the repository only containing the information needed " +
            "by the tool. Since cached versions are delivered with the tool you normally don't need to use this option. Use this option if you don't have a cached version of the "+
            "repository you would like to use.")

    migrateCmd.add_argument('--cachedir', action="store", dest=ckey.cacheDir, required=False,
        help=f"path to the repository cache directory. The default path is \'{cdefault.cacheDir}\'. This is the directory were the tool is searching for the cached versions of the "+
            "TrueSight KM repository. Also see (--repository and --version).")

    migrateCmd.add_argument('--version', action="store", dest=ckey.repositoryVersion,
        help=f"Version of the repository to be used. If no version is specified, the latest version found in the repository cache will be used.")

    migrateCmd.add_argument("-o", "--policydir", action="store", dest=ckey.policyDir,
        help=f"path to the directory where the generated policies should be stored. The default is \'{cdefault.policyDir}\'.'")

    migrateCmd.add_argument("--tagsdir", action="store", dest=ckey.tagsDir,
        help=f"path to the directory where the generated policies should be stored. The default is \'{cdefault.tagsDir}\'.'")

    migrateCmd.add_argument("--agentinfo", action="store", dest=ckey.agentInfo,
        help=f"this argument takes a filename which contains agent information. The file must be in csv format with the hostname in the first column and the other " +
            f"columns containing information about the host. For exampld there could be a column 'environemt' which has the values 'Production' and 'test'. "+
            f"These values are given to the policy optimizer to help him find comunalities. You can specify any columns afer the fist column in the file which must be " +
            f"the hostname. This parameters is optional, but it strongly helps the optimizer to find meaningful policies.")        

    migrateCmd.add_argument("--agentgroup", action="store", dest=ckey.agentGroup,
        help=f"The name of the agent group migrated. The name is used during policy creation. Policies created will contain this name. For example a base policy created for windows " +
            f"service would be named BASE-<AGENTGROUP>-NT_SERVICE_CONTAINER by default. The default is \'{cdefault.agentGroup}\'.")

    migrateCmd.add_argument("--optimizethreshold", action="store", dest=ckey.optimizeThreshold, type=int,
        help=f"specifies the percentage of duplicates to be found for a base policy to be creates. The default is \'{cdefault.optimizeThreshold}\'.")

    migrateCmd.add_argument("--minagents", action="store", dest=ckey.minAgents, type=int,
        help=f"specifies the minimum number of agents a base policy must cover. If the number of configurations in the base policy is below this number, "
            f"no base policy will be created. The default is \'{cdefault.minAgents}\'.")

    migrateCmd.add_argument("--beautify", action="store_true", dest=ckey.beautify,
        help=f"when creating policy names the monitor name is used. Often the monitor name will have an ending like '_CONTAINER'. If you specify this option, the ending will be " +
            f"removed. The defaukt is that the name is not beautified.")

    migrateCmd.add_argument("--force", action="store_true", dest=ckey.force,
        help=f"Forces the creation of the policies. Normally policies are not created if the solution is not found in the repository. " +
            "If you specify this flag the policy will be created anyway with default values for the solution and the release. Use this flag " + 
            "with caution since the generated policies will not successfully load. You will need to manually modify the policy to be able " + 
            "to load it into the TrueSight presentation server.")

    # policy
    migrateCmd.add_argument("--tenantid", action="store", dest=ckey.tenantId,
        help=f"Tenant id to be used in policy generation. The default tenant id is \'{cdefault.tenantId}\'.")

    migrateCmd.add_argument("--tenantname", action="store", dest=ckey.tenantName,
        help=f"Tenant name to be used in policy generation The default tenant name is \'{cdefault.tenantName}\'.")

    migrateCmd.add_argument("--baseprecedence", action="store", dest=ckey.basePrecedence,
        help=f"precedence to be used for creating base policies. The default precedence \'{cdefault.basePrecedence}\'.")

    migrateCmd.add_argument("--agentprecedence", action="store", dest=ckey.agentPrecedence,
        help=f"precedence to be used for creating agent policies generation. The default precedence \'{cdefault.agentPrecedence}\'.")

    migrateCmd.add_argument("--shared", action="store_true", dest=ckey.shared, 
        help=f"share the generated policy. The default is that the policy is not shared")

    migrateCmd.add_argument("--enabled", action="store_true", dest=ckey.enabled, 
        help=f"enable the generated policy. The default is that the policy is not enabled")

    migrateCmd.add_argument("--owner", action="store", dest=ckey.owner,
        help=f"name of the owner of the policy. The default owner is \'{cdefault.owner}\'.")

    migrateCmd.add_argument("--group", action="store", dest=ckey.group,
        help=f"name of the group to be used in the generated policy. The default group is \'{cdefault.group}\'.")

    #------------------
    # Cache
    #------------------

    cacheCmd = cmdParsers.add_parser('cache', 
        help="Manage the km repo. This command is used to create caches of the KM Repository which can be distributed with the product " +
            "KM Repository caches are slim version of the KM repository which just contain the information the utility needs.")

    cacheCmd.add_argument('-r','--repository', action="store", dest=ckey.repositoryDir,
        help=f"path to the bmc repository. The default path is \'{cdefault.repositoryDir}\'. The repository is needed to gather information about solutions to be able to create policies.")

    cacheCmd.add_argument('--cache', action="store", dest=ckey.cacheDir, required=False,
        help=f"path to the repository cache directory. The default path is \'{cdefault.cacheDir}\'.")

    cacheCmd.add_argument('--version', action="store", dest=ckey.repositoryVersion,
        help=f"Version of the repository to be used. If no version is specified, the latest version found in the repository cache will be used.")

    #------------------
    # KMRepo
    #------------------

    solutionCmd = cmdParsers.add_parser('solution', 
        help="create a solution template. A solution tamplate is used to migrate pconfig entries to to CMA. The is the bases for a solution. It must be modified in order to work.")

    solutionCmd.add_argument('-r','--repository', action="store", dest=ckey.repositoryDir,
        help=f"path to the bmc repository. The default path is \'{cdefault.repositoryDir}\'. The repository is needed to gather information about solutions to be able to create policies.")

    solutionCmd.add_argument('--cache', action="store", dest=ckey.cacheDir, required=False,
        help=f"path to the repository cache directory. The default path is \'{cdefault.cacheDir}\'.")

    solutionCmd.add_argument('--version', action="store", dest=ckey.repositoryVersion,
        help=f"Version of the repository to be used. If no version is specified, the latest version found in the repository cache will be used.")

    solutionCmd.add_argument("--monitor", action="store", dest=ckey.monitor, required = True,
        help="the monitor which should be used to create the solution template for.")

    return parser.parse_args()


def migrateCmd(repositoryDir, cacheDir, version, policyDir, tagsDir, thresholdFilenames, pconfig, agentGroup, beautify, optimzeThreshold, minAgents, agentInfo,
        force, tenantId, tenantName, shared, enabled, basePrecedence, agentPrecedence, owner, group):

    # get the repository
    kmRepository = KMRepository.get(repositoryDir, cacheDir, version)

    if thresholdFilenames != None:
        # load the Threshold File
        thresholdSet = FileThresholdSet(thresholdFilenames)
        thresholdSet.load()

        # Migrate Thresholds
        instanceThresholdMigrator = InstanceThresholdMigrator(thresholdSet, kmRepository)
        agentConfigurations = instanceThresholdMigrator.migrate(force)

        # Generate Policies
        policyFactory = PolicyFactory(agentGroup, tenantId, tenantName, shared, enabled, basePrecedence, agentPrecedence, owner, group, beautify, optimzeThreshold, minAgents, agentInfo)
        (policies, tags) = policyFactory.generatePolicies(agentConfigurations)

        # Write Policies to file
        PolicyFactory.savePolicies(policies, policyDir)
        PolicyFactory.saveTags(tags, tagsDir)

    if pconfig != None:
        logger.info(f"Processing rulesets ...")
        solutionPackManager = SolutionPackManager(path="solutions", repository = kmRepository)
        rulesets = RuleSetFactory(pconfig)

        logger.info(f"loaded {len(rulesets)} rulesets.")

        rulesetMigrator = RulesetMigrator(rulesets, solutionPackManager, kmRepository)
        rulesetConfigurations = rulesetMigrator.migrate(force)
        logger.info(f"Found {len(rulesetConfigurations)} ruleset configurations.")

        # Generate Policies
        policyFactory = PolicyFactory(agentGroup, tenantId, tenantName, shared, enabled, basePrecedence, agentPrecedence, owner, group, beautify, optimzeThreshold, minAgents, agentInfo)
        (policies, tags) = policyFactory.generatePolicies(rulesetConfigurations)

        # Write Policies to file
        PolicyFactory.savePolicies(policies, policyDir)
        PolicyFactory.saveTags(tags, tagsDir)

def kmrepoCmd(repositoryDir, cacheDir, version):
    kmRepository = KMRepository(f"{repositoryDir}{os.path.sep}bmc_products{os.path.sep}kmfiles")
    kmRepository.save(cacheDir, version)

def generateSolutionTemplateCmd(repositoryDir, cacheDir, version, monitor, path="solutions"):
    kmRepository = KMRepository.get(repositoryDir, cacheDir, version)
    SolutionPackManager.generateSolutionPackTemplate(kmRepository, monitor, path)


def save(args):
    if args.cmd == "migrate":
        config = MigrateConfig(args)
        config.save(args.save)
    elif args.cmd == "kmrepo":
        config = CacheRepositoryConfig(args)
        config.save(args.save)

    else: logger.error(f"Unknown command '{args.cmd}' used in command line.")

#-----------------------
# Main
#-----------------------

version = "1.0.0"

logger = LoggerFactory.getLogger(__name__)
logger.info(f"{__file__} CMA Utility Version {version} (c) 2020 BMC Software Inc.")

args = parseArguments()
try: 
    if args.cmd == None and args.load != None:
        type = Config.getType(args.load)
        if type == "MigrateConfig": args.cmd = "migrate"
        elif type == "CacheRepositoryConfig": args.cmd = "kmrepo"
        else:
            raise Exception(f"Found unexpected type '{type}' in configuration file '{args.load}'.")

    if args.save != None:
        save(args)

    elif args.cmd == "migrate":
        config = MigrateConfig(args)
        migrateCmd(config.repositoryDir,
            config.cacheDir,
            config.repositoryVersion,
            config.policyDir,
            config.tagsDir,
            config.thresholds,
            config.pconfig,
            config.agentGroup,
            config.beautify,
            config.optimizeThreshold,
            config.minAgents,
            config.agentInfo,
            config.force,
            config.tenantId,
            config.tenantName,
            config.shared,
            config.enabled,
            config.basePrecedence,
            config.agentPrecedence,
            config.owner,
            config.group)

    elif args.cmd == "cache":
        config = CacheRepositoryConfig(args)
        kmrepoCmd(config.repositoryDir, config.cacheDir, config.repositoryVersion)

    elif args.cmd == "solution":
        config = GenerateSolutionTemplateConfig(args)
        generateSolutionTemplateCmd(config.repositoryDir, config.cacheDir, config.repositoryVersion, config.monitor)


    else: logger.error(f"Unknown command '{args.cmd}' used in command line.")


except RuntimeError as error:
    logger.error(error)
    logger.debug(traceback.format_exc())

except RuntimeWarning as warning:
    logger.warning(warning)
    logger.debug(traceback.format_exc())

except Exception as exception:
    logger.error(f"An unexpected error occured during execution.")
    logger.error(exception)
    logger.error(traceback.format_exc())

finally:
    logger.info("done.")