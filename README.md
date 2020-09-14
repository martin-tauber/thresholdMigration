# TrueSight Threshold Migration
The threshold migration utiltiy migrates instance thresholds exported from the TrueSight Presentation Server to policies.

# Prerequisites
This script is written in python using version 3.x. You need to run this script on a machine where python 3.x is installed.
You also need to make sure that you have the following python modules installed:

* xml
* json
* shlex
* uuid
* codecs
* pandas
* numpy

If you are using a standard python installation, then use 

    python -m pip install <packagename>

to install the missing package. If you are using anacoda then use

    pip install <packagename>

to install the missing packages.

# Installation
You just need to clone this repository onto your machine using

    git clone https://github.com/martin-tauber/thresholdMigration.git 

The python script is independent of the operating system. So you can install it on any operating system where python is runnning.
It is also independent of the truesight installation, which means you don't need to have a truesight installation or any components
of it running on the machine where you are running this script. The script will generate json files which contain policy definitions.
These files then can be transfered to a machine where you can import them into TrueSight using the cmamigration utility deployed
with the truesight installation.

If you don't have git installed on your machine and you don't want to install git, go to the website
https://github.com/martin-tauber/thresholdMigration.git click on the *code* button and choose download zip from the pulldown menu.
Extract the file in a directory of you choice and you are all set.

# Migrating Thresholds
## Export the thresholds from the Truesight Presentation server

To migrate thresholds you first need to export the thresholds you want to migrate using the export utility provided by TrueSight. See ???
for more information about how to export the thresholds from truesight. You can the unzip the file in your prefered directory in the
machine where you want to run the script.

## Running the tool

To migrate thresholds run the following command

    ./cmautil.py migrate --thresholds <path>

where *path* is the path to the file you exported from the TrueSight presentation server. The *path* parameter can point to a file or a 
directory. If it points to a directory all the files in the directory are migrated. You can also specify more than one *path* following
the --thresholds switch. The all the files and directories specified will be migrated.

## Understanding the output

The migration utility will generate policy and agent configuration files. These files by default are located in the out/policies and 
out/tags directory. You can override the default directory for the output with the following command line options:

    --policydir <path>
    --tagsdir <path>

The *--policydir* specifies where the generated policies should be stored. The *--tagsdir* specifies for the configuration files containing
the agent tags are stored.

The primary goal of the tool is to create monitoring policies that can be imported into the TrueSight presentation server. These 
policies will be stored in the out/policies directory. The tool has a build in optimizer component which will generate two types of policies.
The first type is the 'BASE' policy. BASE policies are created by finding the biggest set of equal thresholds for one monitor type.
BASE policies will be applied to all the agents which run that configuration. For every agent which runs a BASE policy a configuration
file is generated in the tags directory. The configuraion file will contain all the tags for that agent. The file is in pconfig format to
make it easier to distrubute the configuration to the agents. Base policies will have a prefix "BASE-".

The second type of policy which is generated in the agent policy. The agent policy will contain all the configurations. which are not covered
by a base policy. Agent policies will be named by the agent and port number.

## Setting policy defaults

The tool generates policies and makes certain assumptions about default values. For example it assumes that the tenant id is "*". You can override
these assumptions from the command line. (use ./cmautil.py migrate -h to get more details and the values that are set my default). The following
defaults can be overwritten using the command line:

    --tenantid <tenantid>
    --tenantname <tenantname>
    --owner <owner>
    --group <group>
    --shared
    --enabled

The *--shared* and the *--enabled* flag will set the policies created to be shared and enabled. If these flags are not specified the generated
policies will not be shared and be disabled.

You can also specify the precedence of the policies being generated. As we are creating two types of policies (base and agent policies) you can
specify the precedence from the command line:

    --baseprecedence
    --agentprecedence

you don't need to speciy the full switch name as long as the part you typed is unique. So you can for example type --base instead of --baseprecedence

## Understanding the optimizer

The optimizer tries to find communalities in policy configurations. For the threshold configuration it is going to find threshold configurations 
which are equal and the agents which these thresholds apply to. It will then find the largest set of agent/configuration combinations and define
this as the base. From the base, the base policies are then generated. The policy generator will then check every agent to see if it's cvonfiguration
is covered by the base policies. If they are covered a file for this agent is generated in the tags directory and the Tag for the policy is added.
If the configurations for the agent are not covered an agent policy is generated. The agent policy will directly address the agent in the agent 
selection criteria of the policy.

To measure the quality of the base policies created the optimzer uses the *coverage*. The coverage is the percentage of agent/configuration combinations covered by the policy compared to the overall agent/configuration combinations. By default a coverage larger than 20% is considered to
be a good coverage. If the coverage of a base policy is not good, it is going to be ignored.

You can use the following command line option to change the threshold percentage for good policies. 

    --optimizethreshold <percent>

To prevent generating base policies that have a good coverage but are applied only to a very small amount of agents, the following command line
option can be used:

    --minagents <numberOfAgents>

With this command line option you specify the minimum number of agents a base policy must cover. If it is less the base policy is ignored.

### Configuration grouping







## Getting help

Use the 

    ./cmautil.py migrate -h

command to get additional help on how to override default behaiviour of the migration utility