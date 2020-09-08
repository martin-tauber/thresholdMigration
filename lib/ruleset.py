import os
import sys
import shlex
import re

from lib.logger import LoggerFactory

from lib.configuration import MonitoringConfiguration, MonitoringConfigurationFactory, AgentConfiguration


logger = LoggerFactory.getLogger(__name__)

class RulesetMigrator():
    def __init__(self, ruleset, solutionPackManager, kmRepository):
        self.rulesets= []
        self.rulesets.append(ruleset)
        self.solutionPackManager = solutionPackManager
        self.kmRepository = kmRepository
        self.monitoringConfigurationFactory = MonitoringConfigurationFactory(kmRepository)

    def migrate(self):
        configurationMap = {}
        for ruleset in self.rulesets:
            logger.info(f"Migrating Ruleset  '{ruleset.source}' ...")
            for rule in ruleset.rules:
                self.migrateRule(rule, configurationMap)

        configurations = []
        for id, configuration in configurationMap.items():
            configurations.append(AgentConfiguration(
                agent = ruleset.agent,
                port = ruleset.port,
                configuration = configuration
            ))
            
        return configurations
        

    def migrateRule(self, rule, configurationMap):
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

                            self.set(configurationMap, solutionPack.monitorType, solutionPack.profile, path, value)

    def set(self, configurations, monitorType, profile, path, value):
        if monitorType in configurations:
            configuration = configurations[monitorType]
        else:
            configuration = self.monitoringConfigurationFactory.create(monitorType, profile)
            configurations[monitorType] = configuration

        configuration.set(path, value)


class RuleSet():
    def __init__(self, filename):
        logger.info(f"Parsing Ruleset '{filename}' ...")
        self.rules = []
        self.source = filename

        # get agent and port from filename
        match = re.match(r'(.+)_([^_]+)', os.path.basename(os.path.splitext(filename)[0]))
        self.agent = match[1]
        self.port = match[2]

        content = open(filename, 'rt').read()
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


class RuleSetFactory():
    def __init__(self, path):
        self.rulesets = []
        for subdir, dirs, files in os.walk(path):
            for file in files:
                try:
                    filename = subdir + file
                    ruleset = RuleSet(filename)
                    self.rulesets.append(ruleset)

                except Exception as error:
                    raise RuntimeError(f"An unexpected error occured while creating ruleset for file '{filename}'. ({error})")
