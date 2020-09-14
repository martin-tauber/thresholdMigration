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
of it running on the machine where you are running this script. The script will generate json files which contain policy definitions
these files would need to be transfered to a machine where you can import them into truesight using the cmamigration utility deployed
with the truesight installation

# Migrating Thresholds
## Export the thresholds from the Truesight Presentation server

To migrate thresholds you first need to export the thresholds you want to migrate using the export utility provided by TrueSight. See ???
for more information about how to export the thresholds from truesight.

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

The primary goal of the tool is to create monitoring policies that then can be imported into the TrueSight presentation server. These 
policies will be stored in the out/policies directory. The tool has a build in opimizer component which will generate two types of policies.
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



## Getting help

Use the 

    ./cmautil.py migrate -h

command to get additional help on how to override default behaiviour of the migration utility