from copy import copy
import json
import time
import random
import operator

from dream.simulation.GUI.Shifts import Simulation as ShiftsSimulation
from dream.simulation.GUI.Default import schema

class Simulation(ShiftsSimulation):
  def getConfigurationDict(self):
    conf = ShiftsSimulation.getConfigurationDict(self)
    conf['Dream-LineClearance'] = {
      "_class": "Dream.LineClearance",
      "name": "Clearance",
      "property_list": conf['Dream-Queue']['property_list']}
    conf['Dream-BatchSource'] = {
        "_class": "Dream.BatchSource",
        "name": "Source",
        "property_list": conf['Dream-Source']['property_list']\
          + [schema['batchNumberOfUnits']]
    }
    conf['Dream-BatchDecompositionStartTime'] = {
      "_class": "Dream.BatchDecompositionStartTime",
      "name": "Decomposition",
      "property_list": [schema['processingTime'], schema['numberOfSubBatches'] ]
      }
    conf['Dream-BatchReassembly'] = {
      "_class": "Dream.BatchReassembly",
      "name": "Reassembly",
      "property_list": [schema['processingTime'], schema['numberOfSubBatches'] ]
      }
    conf['Dream-BatchScrapMachine'] = {
      "_class": "Dream.BatchScrapMachine",
      "name": "Station",
      "property_list": conf['Dream-Machine']['property_list']
      }
    conf['Dream-EventGenerator'] = {
      "_class": "Dream.EventGenerator",
      "name": "Attainment",
      "property_list": [schema['start'], schema['stop'], schema['duration'],
          schema['interval'], schema['method'], schema['argumentDict']]
      }
    conf["Dream-Configuration"]["gui"]["exit_stat"] = 1
    conf["Dream-Configuration"]["gui"]["debug_json"] = 1
    conf["Dream-Configuration"]["gui"]["shift_spreadsheet"] = 1
    # some more global properties
    conf["Dream-Configuration"]["property_list"].append( {
      "id": "throughputTarget",
      "type": "string",
      "_class": "Dream.Property",
      "_default": "10" })
    conf["Dream-Configuration"]["property_list"].append( {
      "id": "desiredPercentageOfSuccess",
      "type": "string",
      "_class": "Dream.Property",
      "_default": "0.85" })

    # remove tools that does not make sense here
    conf.pop('Dream-Machine')
    conf.pop('Dream-Repairman')
    conf.pop('Dream-Source')
    return conf

