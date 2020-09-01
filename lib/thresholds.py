import csv
import traceback
import pandas as pd
import numpy as np

from .logger import LoggerFactory
from lib.policy import InstanceThresholdConfiguration

logger = LoggerFactory.getLogger(__name__)

#-----------------------
# Thresholds
#-----------------------
class InstanceThresholdMigrator():
    def __init__(self, thresholds, kmRepository):
        self.thresholds = thresholds.set
        self.kmRepository = kmRepository

        self.conditionMap = {
            ">": "GREATER_THAN",
            "<": "SMALLER_THAN",
            "=": "EQUALS",
            "<=": "SMALLER_OR_EQUALS",
            ">=": "GREATER_OR_EQUALS"
        }

        self.absoluteConditionMap = {
            ">": "ABOVE",
            "<": "BELOW"
        }

        self.baselineMap = {
            "Not Enabled": "notEnabled",
            "Auto": "auto",
            "Auto Baseline": "auto",
            "Hourly Baseline": "hourly",
            "Daily Baseline": "daily",
            "Weekly Baseline": "weekly",
            "Hourly And Daily": "hourlyAndDaily",
            "Hourly And Daily Baseline": "hourlyAndDaily",
            "All Baselines": "all"
        }

        self.basetypeMap = {
            "Not Enabled": "notEnabled",
            "Auto": "auto",
            "Hourly": "hourly",
            "Daily": "daily",
            "Weekly": "weekly",
            "Hourly And Daily": "hourlyAndDaily",
            "All Baselines": "all"
        }

    def migrate(self):
        logger.info(f"Migrating {len(self.thresholds)} instance thresholds ...")

        configurations = []
        
        for threshold in self.thresholds:
            try:
                configurations.append(InstanceThresholdConfiguration(
                    agent = threshold["agent"],
                    port = threshold["port"],
                    solution = self.kmRepository.monitors[threshold["monitorType"]]["solution"],
                    release = self.kmRepository.monitors[threshold["monitorType"]]["release"],
                    monitorType = threshold["monitorType"],
                    attribute = threshold["attribute"],

                    # Details
                    absoluteDeviation = threshold["absoluteDeviation"],
                    autoClose = threshold["autoClose"],
                    comparison = self.absoluteConditionMap[threshold["condition"]] if threshold["thresholdType"] == "absolute" else self.conditionMap[threshold["condition"]] ,
                    durationInMins = threshold["duration"],
                    minimumSamplingWindow = threshold["minSampleWindow"],
                    outsideBaseline = self.baselineMap[threshold["outsideBaseline"]],
                    percentDeviation = threshold["deviation"],
                    predict = threshold["predict"],
                    severity = threshold["severity"],
                    threshold = threshold["value"],

                    instanceName = threshold["instance"],
                    type = threshold["thresholdType"]
                ))
            except Exception as error:
                logger.error("An unexpected exception occured while migrating instance threshold. Continuing processing but entry is ignored.")
                logger.error(f"agent: {threshold['agent']}, port: {threshold['port']}, monitorType: {threshold['monitorType']}, attribute: {threshold['attribute']}, instance: {threshold['instance']}, type: {threshold['thresholdType']}")
                logger.error(error)
                logger.error(traceback.format_exc())

        return configurations





class ThresholdSet():
    def __init__(self):
        self.set = []

        
class FileThresholdSet(ThresholdSet):
    def __init__(self, filenames):
        self.set = []
        self.filenames = filenames

    def load(self):

        for filename in self.filenames:
            logger.info(f"Loading Server Thresholds from '{filename}' ...")

            with open(filename) as input:
                reader = csv.reader(input)
                rowno = 0 
                for row in reader:
                    # skip header
                    if rowno == 0:
                        if len(row) != 20:
                            logger.warn(f"File does not seam to be an exported server threshold file. Number of columns found is {len(row)} expected 20. Skipping file.")
                            break

                        if row[0] == "PATROL Agent" and row[1] == "Monitor Type": continue
                    
                    if row[19] == "false":
                        try: 
                            self.set.append({
                                "agent": row[0].split(':')[0],
                                "port": row[0].split(':')[1],
                                "monitorType": row[1],
                                "device": row[2],
                                "instance": row[3],
                                "attribute": row[4],
                                "severity": row[5].upper(),
                                "duration": row[6],
                                "condition": row[7],
                                "value": row[8],
                                "uom": row[9],
                                "outsideBaseline": row[10],
                                "autoClose": row[11],
                                "predict": row[12],
                                "minSampleWindow": row[13] if row[13] != "" else None,
                                "baselineType": row[14],
                                "absoluteDeviation": row[15] if row[15] != "" else None,
                                "deviation": row[16],
                                "suppressEvents": row[17],
                                "thresholdType": row[18].lower()
                            })
                        except:
                            logger.error(f"An error occrued while processing row {rowno} of file {filename}. Skipping rest of file.")
                            break

                        rowno = rowno + 1