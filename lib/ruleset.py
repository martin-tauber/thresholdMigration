import os
import sys
import shlex
import re

from lib.logger import LoggerFactory

from lib.policy import MonitoringConfiguration

logger = LoggerFactory.getLogger(__name__)

class RulesetMigrator():
    def __init__(self, ruleset, solutionPackManager):
        self.rulesets= []
        self.rulesets.append(ruleset)
        self.solutionPackManager = solutionPackManager

    def migrate(self):
        configurations = {}
        for ruleset in self.rulesets:
            configurations = []

            logger.info(f"Migrating Ruleset  '{ruleset.source}' ...")

            for rule in ruleset.rules:
                self.migrateRule(rule, configurations)

    def migrateRule(self, rule, configurations):
        for solutionPack in self.solutionPackManager.solutionPacks:
            configuration = configurations.get(solutionPack.meta)

            for pattern in solutionPack.config["patterns"]:
                match = re.search(pattern["pattern"], rule["rulename"])
                if (match):
                    if "warn" in pattern:
                        logger.warn(f"{pattern['warn']} '{rule['rulename']}' ({solutionPack.solution}, {solutionPack.type}, {solutionPack.version}).")

                    if "path" in pattern:
                        try:
                            path = eval('f"{template}"'.format(template = pattern["path"]))
                        except Exception as error:
                            logger.error(f"An unexpected error occured while compiling path '{pattern['path']}' for pattern '{pattern['pattern']}' of solution '{solutionPack.config['solution']}' type '{solutionPack.config['type']}'.")
                            logger.error(error)

                        value = rule["value"]
                        if "value" in pattern:
                            try:
                                value = eval('f"{template}"'.format(template = pattern["value"]))
                            except Exception as error:
                                logger.error(f"An unexpected error occured while compiling value '{pattern['value']}' for pattern '{pattern['pattern']}' of solution '{solutionPack.config['solution']}' type '{solutionPack.config['type']}'.")
                                logger.error(error)

                        self.set(solutionPack, path, value)

    def set(self, solutionPack, path, value):
        configuration = self.getConfiguration(solutionPack["monitorType"])

#        for segment in path.split("/")[1:]:


class RuleSet():
    def __init__(self, filename):
        logger.info(f"Parsing Ruleset '{filename}' ...")
        self.rules = []
        self.source = filename

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
                logger.error(f"Found unexpected token '{error.foundToken}' in '{filename}' at {error.lineno}. Expected '{error.expectedToken}'.")

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
                logger.error(f"Found unexpected token '{token}' in '{filename}' at {lexer.lineno}. Expected ','.")
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
                    logger.error(f"An unexpected error occured while creating ruleset for file '{filename}'.")
                    logger.error(error)
