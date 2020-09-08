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
from lib.ruleset import RuleSet, RulesetMigrator
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
    migrateCmd.add_argument('-r','--repository', action="store", dest=ckey.repositoryDir,
        help=f"path to the bmc repository. The default path is \'{cdefault.repositoryDir}\'. The repository is needed to gather information about solutions to be able to create policies. "+
            "the solution is delivered with 'cached' versions of the repository. A cached version is a stripped version of the repository only containing the information needed " +
            "by the tool. Since cached versions are delivered with the tool you normally don't need to use this option. Use this option if you don't have a cached version of the "+
            "repository you would like to use.")

    migrateCmd.add_argument('--cache', action="store", dest=ckey.cacheDir, required=False,
        help=f"path to the repository cache directory. The default path is \'{cdefault.cacheDir}\'. This is the directory were the tool is searching for the cached versions of the "+
            "TrueSight KM repository. Also see (--repository and --version).")

    migrateCmd.add_argument('--version', action="store", dest=ckey.repositoryVersion,
        help=f"Version of the repository to be used. If no version is specified, the latest version found in the repository cache will be used.")

    migrateCmd.add_argument("-o", "--out", action="store", dest=ckey.out,
        help=f"path to the directory where the generated policies should be stored. The default is \'{cdefault.out}\'.'")
    
    migrateCmd.add_argument("-t", "--thresholds", action="store", dest=ckey.thresholds, nargs="+",
        help=f"name of the file which which contains the thresholds exported from tsps. The default file name is \'{cdefault.thresholds}\'")

    migrateCmd.add_argument("--pconfig", action="store", dest=ckey.pconfig,
        help=f"pconfig file that should be migrated to cma.")

    # policy
    migrateCmd.add_argument("--tenantId", action="store", dest=ckey.tenantId,
        help=f"Tenant id to be used in policy generation. The default tenant id is \'{cdefault.tenantId}\'.")

    migrateCmd.add_argument("--tenantName", action="store", dest=ckey.tenantName,
        help=f"Tenant name to be used in policy generation The default tenant name is \'{cdefault.tenantName}\'.")

    migrateCmd.add_argument("-p", "--precedence", action="store", dest=ckey.precedence,
        help=f"precedence to be used in policy generation. The default precedence \'{cdefault.precedence}\'.")

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


def migrateCmd(repositoryDir, cacheDir, version, outputPath, thresholdFilenames, pconfig, tenantId, tenantName, shared, enabled, precedence, owner, group):
    # get the repository
    kmRepository = KMRepository.get(repositoryDir, cacheDir, version)

    if thresholdFilenames != None:
        # load the Threshold File
        thresholdSet = FileThresholdSet(thresholdFilenames)
        thresholdSet.load()

        # Migrate Thresholds
        instanceThresholdMigrator = InstanceThresholdMigrator(thresholdSet, kmRepository)
        agentConfigurations = instanceThresholdMigrator.migrate()

        # Generate Policies
        policyFactory = PolicyFactory(tenantId, tenantName, shared, enabled, precedence, owner, group)
        (policies, tags) = policyFactory.generatePolicies(agentConfigurations)

        # Write Policies to file
        PolicyFactory.savePolicies(policies, outputPath)
        PolicyFactory.saveTags(tags, outputPath)

    if pconfig != None:
        solutionPackManager = SolutionPackManager(path="solutions", repository = kmRepository)
        ruleset = RuleSet(pconfig)

        rulesetMigrator = RulesetMigrator(ruleset, solutionPackManager, kmRepository)
        rulesetConfigurations = rulesetMigrator.migrate()

        # Generate Policies
        policyFactory = PolicyFactory(tenantId, tenantName, shared, enabled, precedence, owner, group)
        (policies, tags) = policyFactory.generatePolicies(rulesetConfigurations)

        # Write Policies to file
        PolicyFactory.savePolicies(policies, outputPath)
        PolicyFactory.saveTags(tags, outputPath)

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
            config.out,
            config.thresholds,
            config.pconfig,
            config.tenantId,
            config.tenantName,
            config.shared,
            config.enabled,
            config.precedence,
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