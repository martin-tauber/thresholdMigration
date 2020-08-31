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
from lib.config import MigrateConfig, CacheRepositoryConfig, ckey, cdefault, Config

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
    # KMRepo
    #------------------

    kmrepoCmd = cmdParsers.add_parser('kmrepo', 
        help="Manage the km repo. This command is used to create caches of the KM Repository which can be distributed with the product " +
            "KM Repository caches are slim version of the KM repository which just contain the information the utility needs.")

    kmrepoCmd.add_argument('-r','--repository', action="store", dest="repositoryDir",
        help=f"path to the bmc repository. The default path is \'{cdefault.repositoryDir}\'. The repository is needed to gather information about solutions to be able to create policies.")

    kmrepoCmd.add_argument('--cache', action="store", dest="cacheDir", required=False,
        help=f"path to the repository cache directory. The default path is \'{cdefault.cacheDir}\'.")

    kmrepoCmd.add_argument('--version', action="store", dest="version",
        help=f"Version of the repository to be used. If no version is specified, the latest version found in the repository cache will be used.")


    return parser.parse_args()


def migrateCmd(repositoryDir, cacheDir, version, outputPath, thresholdFilenames, tenantId, tenantName, shared, enabled, precedence, owner, group):
    # get the repository
    kmRepository = KMRepository.get(repositoryDir, cacheDir, version)

    # load the Threshold File
    thresholdSet = FileThresholdSet(thresholdFilenames)
    thresholdSet.load()

    # Migrate Thresholds
    instanceThresholdMigrator = InstanceThresholdMigrator(thresholdSet)
    configurations = instanceThresholdMigrator.migrate()

    # Generate Policies
    policyFactory = PolicyFactory(kmRepository, tenantId, tenantName, shared, enabled, precedence, owner, group)
    policyFactory.configurations.extend(configurations)
    policies = policyFactory.generatePolicies()

    # Write Policies to file
    PolicyFactory.save(policies, outputPath)

def kmrepoCmd(repositoryDir, cacheDir, version):
    kmRepository = KMRepository(f"{config.repositoryDir.value}{os.path.sep}bmc_products{os.path.sep}kmfiles")
    kmRepository.load()
    kmRepository.saveCache(config.cache.value, config.cache.version)


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
            config.tenantId,
            config.tenantName,
            config.shared,
            config.enabled,
            config.precedence,
            config.owner,
            config.group)

    elif args.cmd == "kmrepo":
        config = CacheRepositoryConfig(args)
        kmrepoCmd(config.repositoryDir, config.cacheDir, config.repositoryVersion)


    else: logger.error(f"Unknown command '{args.cmd}' used in command line.")

except Exception as exception:
    logger.error(f"An unexpected error occured during execotion.")
    logger.error(exception)
    logger.error(traceback.format_exc())

finally:
    logger.info("done.")