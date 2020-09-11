import os
import sys
import shlex
import re
import codecs

from lib.logger import LoggerFactory

from lib.configuration import MonitoringConfiguration, MonitoringConfigurationFactory


logger = LoggerFactory.getLogger(__name__)

class RulesetMigrator():
    def __init__(self, rulesets, solutionPackManager, kmRepository):
        self.rulesets = rulesets
        self.solutionPackManager = solutionPackManager
        self.kmRepository = kmRepository
        self.monitoringConfigurationFactory = MonitoringConfigurationFactory(kmRepository)

    def migrate(self):
        configurations = []
        for ruleset in self.rulesets:
            configurationMap = {}
            logger.debug(f"Migrating Ruleset '{ruleset.source}' ...")
            for rule in ruleset.rules:
                self.migrateRule(rule, ruleset.agent, ruleset.port, configurationMap)
            
            configurations.extend(list(configurationMap.values()))

        return configurations
        
    def migrateRule(self, rule, agent, port, configurationMap):
        for solutionPack in self.solutionPackManager.solutionPacks:
            for pattern in solutionPack.patterns:
                if "pattern" in pattern and pattern["pattern"] != None:
                    match = re.search(pattern["pattern"], rule["rulename"])
                    if (match):
                        if "warn" in pattern:
                            logger.warn(f"{pattern['warn']} '{rule['rulename']}' ({solutionPack.solution}, {solutionPack.type}, {solutionPack.release}).")

                        if "path" in pattern:
                            try:
                                path = eval('f"' + '{template}'.format(template = pattern["path"]) + '"')
                            except Exception as error:
                                raise RuntimeError(f"An unexpected error occured while compiling path '{pattern['path']}' for pattern '{pattern['pattern']}' of solution '{solutionPack.config['solution']}' type '{solutionPack.config['type']}'. ({error})")

                            value = rule["value"]
                            if "value" in pattern:
                                try:
                                    value = eval('f"' + '{template}'.format(template = pattern["value"]) + '"')
                                except Exception as error:
                                    raise RuntimeError(f"An unexpected error occured while compiling value '{pattern['value']}' for pattern '{pattern['pattern']}' of solution '{solutionPack.solution}' type '{solutionPack.monitorType}'. ({error})")

                            self.set(configurationMap, agent, port, solutionPack.monitorType, solutionPack.profile, path, value)

    def set(self, configurations, agent, port, monitorType, profile, path, value):
        match = re.search(r"/ConfigureService/([^/]+)", path)
        if match:
            key = f"{monitorType}-{match[1]}"
        else:
            key = monitorType

        if key in configurations:
            configuration = configurations[key]
        else:
            configuration = self.monitoringConfigurationFactory.create(agent, port, monitorType, profile)
            configurations[key] = configuration

        configuration.set(path, value)


class RuleSet():
    def __init__(self, filename):
        logger.debug(f"Parsing Ruleset '{filename}' ...")
        self.rules = []
        self.source = filename

        search = f'([^{os.path.sep}]+)_([0-9]+)[^{os.path.sep}]*'

        # get agent and port from filename
        match = re.match(re.compile(search), os.path.basename(os.path.splitext(filename)[0]))
        if not match:
            raise RuntimeError(f"Ruleset file '{filename}' does not match file naming convention.")

        self.agent = match[1]
        self.port = match[2]

        with codecs.open(filename, 'r', encoding='utf-8', errors='ignore') as fdata:
            content = fdata.read()

        lexer = shlex.shlex(content, posix=True)

        # Ignore the initial PATROL_CONFIG
        firsttoken = lexer.get_token()
        if firsttoken != "PATROL_CONFIG":
            lexer.push_token(firsttoken)

        # Parse the ruleSet
        while True:
            try:
                # Parse the Rule
                rule = self._parseRule(lexer)
                self.rules.append(rule)

            except TokenException as error:
                raise RuntimeError(f"Found unexpected token '{error.foundToken}' in '{filename}' at {error.lineno}. Expected '{error.expectedToken}'.")

                # recover from error
                while True:
                    token = lexer.get_token()
                    if token == "}": break
                    if token == lexer.eof:
                        lexer.push_token(token)
                        break

            token = lexer.get_token()
            if token == lexer.eof: break
            if token != ",":
                raise RuntimeError(f"Found unexpected token '{token}' in '{filename}' at {lexer.lineno}. Expected ','.")
                break

    def _parseRule(self, lexer):
        rulename = lexer.get_token()
        self._expect(lexer, "=")
        self._expect(lexer, "{")

        operator = lexer.get_token()
        self._expect(lexer, "=")

        value = lexer.get_token()
        self._expect(lexer, "}")

        return { "rulename": rulename, "operator": operator, "value": value}

    def _expect(self, lexer, expected):
        found = lexer.get_token()
        if found != expected:
            lexer.push_token(found)
            raise TokenException(found, expected, lexer.lineno)

        return found


class TokenException(Exception):
    def __init__(self, foundToken, expectedToken, lineno):
        self.foundToken = foundToken
        self.expectedToken = expectedToken
        self.lineno = lineno


def RuleSetFactory(files):
    rulesets = []

    for file in files:
        if not os.path.exists(file):
            logger.warn(f"Ruleset file '{file}' does not exist.")
            continue

        if os.path.isfile(file):
            try:
                rulesets.append(RuleSet(file))
            except RuntimeError as error:
                logger.error(error)
            except RuntimeWarning as warning:
                logger.warn(warning)

        elif os.path.isdir(file):
            for subdir, dirs, files in os.walk(file):
                for filename in files:
                    try:
                        fullname = f"{subdir}{os.path.sep}{filename}"
                        rulesets.append(RuleSet(fullname))
                    except RuntimeError as error:
                        logger.error(error)
                    except RuntimeWarning as warning:
                        logger.warn(warning)

    return rulesets
