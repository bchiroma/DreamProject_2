import simpy
from Globals import G 

from Operator import Operator
from OperatorManagedJob import OperatorManagedJob
from OperatorPool import OperatorPool
from OperatedPoolBroker import Broker

from Job import Job
from OrderComponent import OrderComponent
from Order import Order
from OrderDesign import OrderDesign
from Mould import Mould
from OrderDecomposition import OrderDecomposition
from ConditionalBuffer import ConditionalBuffer
from MouldAssemblyBuffer import MouldAssemblyBuffer
from MachineManagedJob import MachineManagedJob
from QueueManagedJob import QueueManagedJob
from MachineJobShop import MachineJobShop
from QueueJobShop import QueueJobShop
from ExitJobShop import ExitJobShop
from Machine import Machine
from Queue import Queue

import ExcelHandler
import time
import json
from random import Random
import sys
import os.path
import Globals
import ast

class WIPreadError(Exception):
    """Exception raised for errors in the WIP.
    """
    def __init__(self, msg):
        Exception.__init__(self, msg)
        
class EntityIDError(Exception):
    """Exception raised for errors in entities' ids.
    """
    def __init__(self, msg):
        Exception.__init__(self, msg) 

SOURCE_TYPE_SET=set(['Dream.Source', 'Dream.BatchSource'])
def checkWIP():
    '''checks if there is WIP given, if there is no WIP given returns False'''
    # XXX have to check whether it is a JOBSHOP that must have WIP or something else
    # if there is source in the model then return true
    json_data = G.JSONData
    totalWip=[]
    #Read the json data
    nodes = json_data['nodes']                      # read from the dictionary the dicts with key 'nodes'
    sourcePresent=False
    for (element_id, element) in nodes.iteritems():
        
        type=element.get('_class')
        if type in SOURCE_TYPE_SET:
            sourcePresent=True
        wip=element.get('wip', [])
        if wip:
            totalWip.append(wip)
    if not sourcePresent:
        return len(totalWip)>0
    return True
        
def findFile(seekName, path, implicitExt=''):
    """ Given a pathsep-delimited path string, find seekName. 
    Returns path to seekName if found, otherwise None.
    >>> findFile('ls', '/usr/bin:/bin', implicit='.exe')
    'bin/ls.exe'
    """
    for file in os.listdir(path):
        if file.endswith(os.extsep+implicitExt) and file.startswith(seekName):
            full_path=os.path.join(path,file)
            if os.path.isfile(full_path):
                return full_path
    return None

def GetOSPath():
    immediate = os.curdir + os.pathsep + os.pardir + os.pathsep
    ospath = os.getenv('PATH', os.defpath)
    path = immediate + ospath
    return path.split(os.pathsep)

def requestWIP():
    ''' connects to the DB and gets the dictionary of the WIP
        if the database is not accessible then fetch the WIP data from a mock-up json file
    '''
    from routeQuery import connectDB
    file=connectDB()
    if not file:
        # added for testing purposes
        # XXXXX change that to a test file containing the wip, ADDED FOR TESTING
        file=findFile('testJSON',os.path.dirname(os.path.abspath(sys.argv[0])), 'json' )
    return file

def getOrders(input_data):
    ''' run the method from KEtool to read the orders'''
    ''' dict={
                'orders':
                    [
                        {
                            'orderName':'name1',
                            'orderID':'ID1',
                            'manager':'manager1',
                            'orderDate':'orderDate1',
                            'dueDate':'dueDate1',
                            'componentsList':
                                [
                                    {
                                        'componentName':'componenet1order1',
                                        'componentID':'C1O1',
                                        'route':
                                            [
                                                {
                                                    'technology':'CAD',
                                                    'sequence':'1',
                                                    'processingTime':{'distribution':'Fixed','mean':'1'}
                                                },
                                                {
                                                    'technology':'INJM',
                                                    'sequence':'3',
                                                    'numberOfParts':'200',
                                                    'processingTime':{'distribution':'Fixed','mean':'2'}
                                                }
                                            ]
                                    },
                                    {
                                        'componentName':'component2order1',
                                        'componentID':'C2O1',
                                        'route':
                                            [
                                                {
                                                    'technology':'CAM',
                                                    'sequence':'1',
                                                    'processingTime':{'distribution':'Fixed','mean':'1'}
                                                },
                                                {
                                                    'technology':'MILL',
                                                    'sequence':'2',
                                                    'processingTime':{'distribution':'Fixed','mean':'1'}
                                                }
                                            ]
                                    }
                                ]
                        },
                        { 
                            'orderName':'name2',
                            'ordeerID':'ID1',
                            'manager':'manager1',
                            'orderDate':'orderDate2':
                            'dueDate':'dueDate2',
                            'componentsList':
                                [
                                    {
                                        'componentName':'component1order2',
                                        'componentID':'C1O2',
                                        'route':[]
                                    },
                                    {
                                        'componentName':'component1order2',
                                        'componentID':'C1O2',
                                        'route':[]
                                    }
                                ]
                        }
                    ],
                'WIP':
                    {
                        'C2O1':
                            {
                                'station':'MILL1',
                                'entry':1234,
                                'exit':1235
                            },
                        'C3O6':
                            {
                                'station':'EDM1',
                                'entry':235,
                                'exit':259
                            }
                    }
             }
    '''   

    G.MouldList=[]
    G.OrderComponentList=[]
    G.DesignList=[]
    G.WipList=[]
    G.EntityList=[]
    G.JobList=[]    
    
    G.inputWIP=''
    if input_data is None:
        raise WIPreadError('There are no Orders to be read')
    else:
        G.inputWIP = input_data
    #read the input from the JSON file and create the line
    if type(G.inputWIP) is dict:
        G.wip_Data=G.inputWIP
    else:
        G.wip_Data=json.loads(open(G.inputWIP).read())              # create the dictionary wip_Data
    #===========================================================================
#     print G.wip_Data
    #===========================================================================
    G.OrderList=[]
    
    json_data = G.wip_Data
    # find the IDs of the entities that are in the wip list and should be created
    getWipID()
    
    #Read the json data
    orders = json_data['orders']                                    # read from the dictionary the list with key 'orders'
    # each order is a dictionary
    for orderDict in orders:
        id=orderDict.get('orderID', 'not found')
        name=orderDict.get('orderName', 'not found')
        priority=int(orderDict.get('priority', '0'))
        dueDate=float(orderDict.get('dueDate', '0'))
        orderDate=float(orderDict.get('orderDate', '0'))
        isCritical=bool(int(orderDict.get('isCritical', '0')))
        basicsEnded=bool(int(orderDict.get('basicsEnded', '0')))
        componentsReadyForAssembly=bool((orderDict.get('componentsReadyForAssembly', '0')))
        manager=orderDict.get('manager', None)                          # read the manager ID
        # if a manager ID is assigned then search for the operator with the corresponding ID
        # and assign it as the manager of the order 
        if manager:
            for operator in G.OperatorsList:
                if manager==operator.id:
                    manager=operator
                    break
        # keep a reference of all extra properties passed to the job
        extraPropertyDict = {}
        for key, value in orderDict.items():
            if key not in ('_class', 'id'):
                extraPropertyDict[key] = value
        # initiate the Order (the order has no route any more)
        O=Order(id, name, priority=priority, dueDate=dueDate,orderDate=orderDate,
                isCritical=isCritical, basicsEnded=basicsEnded, manager=manager, componentsList=[],
                componentsReadyForAssembly=componentsReadyForAssembly, extraPropertyDict=extraPropertyDict)
        #=======================================================================
        # print 'created ORDER', ' >'*20, O.id
        #=======================================================================
        G.OrderList.append(O)
        # call the method that finds the components of each order and initiates them 
        getComponets(orderDict,O)
        
def getMachineNameSet(technology):
    """
    Give list of machines given a particular step name. For example
    if step_name is "CAM", it will return ["CAM1", "CAM2"]
    """
    from Globals import G
    machine_name_set = set()
    for machine in G.MachineList:
        machine_name=machine.id
        if machine_name.startswith(technology):
            machine_name_set.add(machine_name)
    return machine_name_set

MACHINE_TYPE_SET = set(["Dream.MachineManagedJob", "Dream.MouldAssembly"])
def getNotMachineNodePredecessorList(technology):
    """
    Give the list of all predecessors that are not of type machine
    For example, for technology "CAM", it may return "QCAM"
    """
    predecessor_list = []
    machine_name_set = getMachineNameSet(technology)
    for edge in G.JSONData["edges"].values():
        if edge[1] in machine_name_set:
            predecessor_step = edge[0]
            if predecessor_step in predecessor_list:
                continue
            if not G.JSONData["nodes"][predecessor_step]["_class"] in MACHINE_TYPE_SET:
                predecessor_list = [predecessor_step] + predecessor_list
                predecessor_list = [x for x in getNotMachineNodePredecessorList(predecessor_step) \
                                    if x not in predecessor_list] + predecessor_list
    return predecessor_list

def getNotMachineNodeSuccessorList(technology):
    """
    Give the list of all successors that are not of type machine
    For example, for technology "CAM", it may return "Decomposition"
                 for technology "INJM-MAN" or "INJM" it may return "Exit"
    """
    successor_list = []
    machine_name_set = getMachineNameSet(technology)
    for edge in G.JSONData["edges"].values():
        if edge[0] in machine_name_set:
            successor_step = edge[1]
            if successor_step in successor_list:
                continue
            if not G.JSONData["nodes"][successor_step]["_class"] in MACHINE_TYPE_SET:
                successor_list = [successor_step] + successor_list
                successor_list = [x for x in getNotMachineNodeSuccessorList(successor_step) \
                                    if x not in successor_list] + successor_list
    return successor_list
        
def getRouteList(steps_list):
    ''' step_list is a list of tuples (technology, sequence, processing_time, parts_needed)
        use to record which predecessor has been already done, used to avoid doing
        two times Decomposition
    '''
    technology_list=[]
    step_sequence_list=[]
    processing_time_list=[]
    prerequisite_list=[]
    for step in steps_list:
        technology_list.append(step[0])
        step_sequence_list.append(step[1])
        processing_time_list.append(step[2])
        prerequisite_list.append(step[3])
    predecessor_set = set()
    successor_set = set()
    route_list = []
    setup_step=None             # a step that is of type SETUP
    next_step=None        # the next step of the last SETUP step
    for j, sequence_step in enumerate(technology_list):
#         print j, sequence_step
        #=======================================================================
        #             check whether the current step is SETUP-step
        #=======================================================================
        # if so, keep the step and append the processing time to the following step of the sequence
        if sequence_step.endswith('SET'):
            setup_step=(sequence_step,step_sequence_list[j],processing_time_list[j],prerequisite_list[j])
            next_step=step_sequence_list[j+1]
            continue
        #=======================================================================
        #        check whether the operation defined must be manual or not
        #=======================================================================
        # XXX e.g. MILL-MAN and MILL are the same technology, the difference is that the first requires manual operation while the latter is automatic
        # the machine should be able to read the operationType from the entity just received and accordingly request an operator or not (manual or automatic)
        operation_type='automatic'              # variable that can take two values, automatic and manual
        if sequence_step.endswith('MAN'):
            operation_type='manual'
            sequence_step=sequence_step.split('-')[0]
        #=======================================================================
        #                         append the predecessors
        #=======================================================================
        for predecessor_step in getNotMachineNodePredecessorList(sequence_step):
            # do no attempt to add AssemblyBuffers in the route of moulds
            if sequence_step.startswith('ASSM'):
                break
            # before the QCAM must an order decomposition come
            if predecessor_step=='QCAM': #XXX hard coded logic to add DECOMPOSITION in the route of components
                for pre_predecessor_step in getNotMachineNodePredecessorList(predecessor_step):
                    predecessor_set.add(pre_predecessor_step)
                    route={"stationIdsList": [pre_predecessor_step],}
                    route_list.append(route)
            predecessor_set.add(predecessor_step)
            route = {"stationIdsList": [predecessor_step],}
            route_list.append(route)
        #=======================================================================
        #                        append the current step
        #=======================================================================
        # if there is a pending step (SETUP-setup_step) for this step (next_step), 
        # add the processing time as setup_time to the current step
        setup_time=0
        setup_distribution='Fixed'
        if step_sequence_list[j]==next_step:
            setup_time=setup_step[2]
            setup_distribution=setup_step[2]['distributionType']
            setup_time=float(setup_step[2]['mean'])
            #reset the dummy variables
            setup_step=None
            next_step=None
        # XXX somehow the machines must be informed if the processing is manual or automatic (INJM-MAN or INJM (automatic)
        route = {"stationIdsList": list(getMachineNameSet(sequence_step)),
                 "processingTime": {"distributionType": processing_time_list[j]['distributionType'],
                                    "mean": float(processing_time_list[j]['mean']),
                                    "operationType":operation_type},# XXX key that can take two values, automatic or manual
                 "setupTime": {"distributionType": setup_distribution,
                               "mean": setup_time},
                 "stepNumber": str(step_sequence_list[j]),
                 }
        if prerequisite_list:
            route["prerequisites"] = prerequisite_list[j]
        route_list.append(route)
        #=======================================================================
        #                     append successors if needed
        #=======================================================================
        # treat the case of design (add order DECOMPOSITION)
        if "CAD" in sequence_step and j==len(technology_list)-1:
            for successor_step in getNotMachineNodeSuccessorList(sequence_step):
                successor_set.add(successor_step)
                route = {"stationIdsList": [successor_step],}
                route_list.append(route)
        # treat the case of mould (add EXIT)
        elif sequence_step=="INJM" or sequence_step=='INJM-MAN' and j==len(technology_list)-1:
            for successor_step in getNotMachineNodeSuccessorList(sequence_step):
                successor_set.add(successor_step)
                route = {"stationIdsList": [successor_step],}
                route_list.append(route)
        # treat the case of normal components (add ASSM buffer and ASSM after MAN operations 
        elif j==len(technology_list)-1:
            #Below it is to assign an exit if it was not assigned in JSON
            #have to talk about it with NEX
            exitAssigned=False
            for elementId in list(getMachineNameSet(sequence_step)):
                for obj in G.ObjList:
                    type=obj.__class__.__name__
                    if obj.id==elementId and (type=='MouldAssembly' or type=='MouldAssemblyBuffer'):
                        exitAssigned=True
            # Below it is to assign assemblers if there are any in the corresponding Global list
            if not exitAssigned:                    
                if len(G.MouldAssemblyList)!=0:
                    # append the assembly buffers
                    bufferIDlist = []
                    for assemblyBuffer in G.MouldAssemblyBufferList:
                        bufferIDlist.append(str(assemblyBuffer.id))
                    route = {"stationIdsList": bufferIDlist,}
                    route_list.append(route)
                    # append the assemblers
                    assemblerIDlist = []
                    for assembler in G.MouldAssemblyList:
                        assemblerIDlist.append(str(assembler.id))
                    route = {"stationIdsList": assemblerIDlist,}
                    route_list.append(route)
        # XXX INJM-MAN/INJM+INJM-SET must be set as one step of the route, the same stands for the other ***-SET steps
    #===========================================================================
#     print '='*90
#     print route_list
#     print '='*90
    #===========================================================================
    return route_list
        
def getListFromString(self, my_string):
    """ turn a string with delimiters '-' into a list"""
    my_list = []
    if not my_string in (None, ''):
      my_list = my_string.split('-')
    return my_list

ROUTE_STEPS_SET=set(["ENG", "CAD","CAM","MILL", "MILL-SET","TURN", "DRILL", "QUAL","EDM", "EDM-SET","ASSM", "MAN","INJM", "INJM-MAN", "INJM-SET"])
DESIGN_ROUTE_STEPS_SET=set(["ENG", "CAD"])
ASSEMBLY_ROUTE_STEPS_SET=set(["QASSM"])
MOULD_ROUTE_STEPS_SET=set(["ASSM","INJM","INJM-MAN","INJM-SET"])
def getComponets(orderDict,Order):
    """ get the components of each order, and construct them.
    """
    json_data = G.wip_Data
    #Read the json data
    WIP = json_data['WIP']                             # read from the dictionary the dict with key 'WIP'
    
    isCritical=Order.isCritical                        # XXX have to figure out the isCritical flag
    
    # get the componentsList
    components=orderDict.get('componentsList',[])
    # for all the components in the componentsList of the Order
    for component in components:
        id=component.get('componentID','')
        name=component.get('componentName','')
        #=======================================================================
#         print '* '*50
#         print name, '- '*45
#         print '* '*50
        #=======================================================================
        dictRoute=component.get('route',[])
        route = [x for x in dictRoute]       #    copy dictRoute
        # keep a reference of all extra properties passed to the job
        extraPropertyDict = {}
        for key, value in component.items():
            if key not in ('_class', 'id'):
                extraPropertyDict[key] = value
        
        # if there is an exit assigned to the component
        #    update the corresponding local flag
        # TODO: have to talk about it with NEX
        mould_step_list=[]  # list of all the info needed for the each step of the part's route if it is mould
        design_step_list=[] # list of all the info needed for the each step of the part's route if it is design
        step_list=[]        # list of all the info needed for the each step of the part's route
        exitAssigned=False
        for step in route:
            stepTechnology = step.get('technology',[])
            assert stepTechnology in ROUTE_STEPS_SET, 'the technology provided does not exist'
            stepSequence=step.get('sequence','0')
            parts_needed=step.get('parts_needed',[])
            processingTime=step.get('processingTime',{})
            # if the technology step is in the DESIGN_ROUTE_STEPS_SET
            if stepTechnology in DESIGN_ROUTE_STEPS_SET:
                design_step_list.append((stepTechnology,stepSequence,processingTime,parts_needed))
            # if the technology step is in the MOULD_ROUTE_STEPS_SET
            elif stepTechnology in MOULD_ROUTE_STEPS_SET:
                mould_step_list.append((stepTechnology,stepSequence,processingTime,parts_needed))
            step_list.append((stepTechnology,stepSequence,processingTime,parts_needed))
            
            # XXX componentType needed
            # XXX the components should not be created if the are not in the WIP or not designs
            # append to the entity list only those entities that are in the current WIP and not those to be created
            # later on, that the entities should be created by the order decomposition or the mould assembly
            #     the assembler or the decomposer must check if they are already created
        
        # find the new route of the component if it is no design or mould
        if not mould_step_list and not design_step_list:
            #===================================================================
#             print '/^\\'*30
#             print 'normal component'
            #===================================================================
            route_list=getRouteList(step_list)
            componentType='Basic'               # XXX have to figure out the component type
            readyForAssembly=0                  # XXX have to figure out the readyForAssembly flag
            # XXX if the component is not in the WipIDList then do not create it but append it the componentsList of the Order O
            # XXX if an other normal component of the same order is in the WIP (but not a mould) then create it 
            # check whether the mould of the order is created
            assembled=False
            for entity in G.MouldList:
                if entity.order==Order:
                    assembled=True
                    break
            # check if at list one of the Order's normal components is created
            decomposed=False
            if len(Order.basicComponentsList+Order.secondaryComponentsList+Order.auxiliaryComponentsList)>0:
                decomposed=True
            if ((id in G.WipIDList) or decomposed) and not assembled:
                # initiate the job
                OC=OrderComponent(id, name, route_list, priority=Order.priority, dueDate=Order.dueDate,orderDate=Order.orderDate,
                                  componentType=componentType, order=Order, readyForAssembly=readyForAssembly,
                                  isCritical=Order.isCritical, extraPropertyDict=extraPropertyDict)
                #===============================================================
#                 print '_'*90,'>', OC.id, 'created'
                #===============================================================
                G.OrderComponentList.append(OC)
                G.JobList.append(OC)   
                G.WipList.append(OC)  
                G.EntityList.append(OC)
                # check the componentType of the component and accordingly add to the corresponding list of the parent order
                if OC.componentType == 'Basic':
                    Order.basicComponentsList.append(OC)
                elif OC.componentType == 'Secondary':
                    Order.secondaryComponentsList.append(OC)
                else:
                    Order.auxiliaryComponentsList.append(OC)
            else:
                componentDict={"_class": "Dream.OrderComponent",
                               "id": id,"name": name,"componentType": componentType,"route": route_list,}
                Order.componentsList.append(componentDict)
            continue
        # create to different routes for the design and for the mould (and different entities)
        if mould_step_list:
            #===================================================================
#             print '/^\\'*30
#             print 'mould'
            #===================================================================
            route_list=getRouteList(mould_step_list)
            # XXX if the component is not in the WipIDList then do not create it but append it the componentsList of the Order O
            # XXX it may be that the order is already processed so there is nothing in the WIP from that order
            doCreate=False
            if id in G.WipIDList:
                # XXX avoid creating moulds wile the id of the part in the keys of WIP but regarding the design and not the mould
                doCreate=True
                import re
                nam=WIP[id]['station']
                name_parts=re.split(r'(\d+)', nam)
                for name_part in name_parts:
                    if name_part in DESIGN_ROUTE_STEPS_SET:
                        doCreate=False
                        break
            if doCreate:
                # initiate the job
                M=Mould(id, name, route_list, priority=Order.priority, dueDate=Order.dueDate,orderDate=Order.orderDate,
                                    isCritical=Order.isCritical, extraPropertyDict=extraPropertyDict, order=Order)
                #===============================================================
#                 print '_'*90,'>', M.id, 'created'
                #===============================================================
                G.MouldList.append(M)
                G.JobList.append(M)
                G.WipList.append(M)
                G.EntityList.append(M)
            else:
                componentDict={"_class": "Dream.Mould",
                               "id": id, "name": name, "route": route_list,}
                Order.componentsList.append(componentDict)
        if design_step_list:
            #===================================================================
#             print '/^\\'*30
#             print 'design'
            #===================================================================
            route_list=getRouteList(design_step_list)
            # XXX if the design is not in the WipIDList then do create if the Order is not being processed at the moment
            #     if the Order is being processed there may be a need to create the design if the design is in the WIP
            #     otherwise the design has already been decomposed and it must not be added to the compononetsList of the order
            if (id in G.WipIDList) or\
                (not id in G.WipIDList and len(Order.auxiliaryComponentsList+Order.secondaryComponentsList+Order.basicComponentsList)==0):
                # initiate the job
                OD=OrderDesign(id+'-D', name+' design',route_list,priority=Order.priority,dueDate=Order.dueDate,orderDate=Order.orderDate,
                                  isCritical=Order.isCritical, order=Order,extraPropertyDict=extraPropertyDict)
                #===============================================================
#                 print '_'*90,'>', OD.id, 'created'
                #===============================================================
                G.OrderComponentList.append(OD)
                G.DesignList.append(OD)
                G.JobList.append(OD)
                G.WipList.append(OD)
                G.EntityList.append(OD)

def findEntityById(entityID):
    for entity in G.EntityList:
        try:
            if entity.id==entityID:
                return entity
            else:
                return None
        except:
            raise EntityIDError('There is no Entity to be found')# pass the contents of the input file to the global var InputData

def getWipID():
    ''' create a list with the ids of the entities in the WIP
        the entities that are not in the wip should not be created
    '''
    json_data = G.wip_Data
    G.WipIDList=[]              # list that holds the IDs of the entities that are in the WIP
    #Read the json data
    WIP = json_data['WIP']                                    # read from the dictionary the dict with key 'WIP'
    for work_id in WIP.iterkeys():
        G.WipIDList.append(work_id)
        
def difference(list1,list2):
    ''' get the difference between two lists
    '''
    templist1=set(list1).union(set(list2))
    templist2=set(list1).intersection(set(list2))
    return list(templist1-templist2)

def setStartWip():
    ''' find the current station from the WIP, if not in a station, then place the entity in a queue
        then remove the previous stations from the remaining_route
    '''
    '''
        XXX if an entity is not in the WIP list then it is not created yet, or is in the starting Queue
        *    XXX OrderDesign, if not in the WIP then in the startingQueue (QCAM or QENG)
                 if their last station is CAM and probably already decomposed
                 if the components then should be placed in the QCAM if not already in the WIP
        *    XXX OrderComponent, if not in the WIP then they are not created yet, do nothing
                 if their last station is MAN or XXX the last station of their route, then are already processed and should not be placed in the WIP
        *    xxx Mould, if not in the WIP -> not created yet
                 if their last station is INJM-MAN or INJM then they are already processed
    '''
    from Globals import SetWipTypeError, setWIP
    from Globals import findObjectById
    json_data = G.wip_Data
    #Read the json data
    WIP = json_data['WIP']                                    # read from the dictionary the dict with key 'WIP'
    #===========================================================================
    # print '/'*200
    # print 'SETTING THE WIP'
    # print '\\'*200
    #===========================================================================
    #===========================================================================
    # OrderDesign type
#     print 'setting desings as wip'
    #===========================================================================
    # for all the entities in the entityList
    for entity in G.DesignList:
        # if the entity is not in the WIP dict then move it to the starting station.
        #=======================================================================
        # print entity.id
        #=======================================================================
        # the id of the entity without the -D ending added when creating the orderDesign
        simple_id=entity.id.split('-')[0]
        if not simple_id in WIP.keys():
            # perform the default action
            setWIP([entity])
        # if the entity is in the WIP dict then move it to the station defined.
        elif simple_id in WIP.keys():
            objectID=WIP[simple_id]["station"]
            #===================================================================
            # print objectID
            #===================================================================
            assert objectID!='', 'there must be a stationID given to set the WIP'
            object=Globals.findObjectById(objectID)
            assert object!=None, 'the station defined in the WIP is not a valid Station'
            # find the station by its id, if there is no station then place it 
            # in the starting queue (QCAD), (QENG)
            entry_time=float(WIP[simple_id]["entry"])
            exit_time=float(WIP[simple_id]["exit"])
            # XXX  alreadyProcessedFor=currentTime-entry_time
            # XXX if the exit time is no grater than the entry then raise an exception as for machines is not yet implemented
            try:
                if not exit_time>entry_time:
                    raise SetWipTypeError('WIP for machines is not implemented yet')
            except SetWipTypeError as setWipError:
                print 'WIP definition error: {0}'.format(setWipError)
            # find which step of the route is the current station-object and update the remainingRoute
            # removing the previous stations from the remaining_route
            for j,step in enumerate(entity.remainingRoute):
                if object.id in step["stationIdsList"]:
                    # XXX the station (object.id) must be removed from the remainingRoute as the entity has already exited (Reconsider) 
                    entity.remainingRoute=entity.remainingRoute[j+1:]
            # find the stations that come after the machine that the entity last exited
            currentObjectIds=entity.remainingRoute[0].get('stationIdsList',[])
            # pick one at random
            currentObjectId=next(id for id in currentObjectIds)
            currentObject=Globals.findObjectById(currentObjectId)
            # then break down the OrderDesing and design the OrderComponents
            if currentObject.type=='OrderDecomposition':
                orderToDecompose=entity.order
                if len(orderToDecompose.auxiliaryComponentsList+orderToDecompose.secondaryComponentsList+orderToDecompose.basicComponentsList)==0:
                    breakOrderDesing(entity)
                # if the orderDesign is already broken down do not break it down again
                else:
                    continue
            # if the current station is not of type orderDecomposition
            else:
                # append the entity to its internal queue
                currentObject.getActiveObjectQueue().append(entity)        # append the entity to its Queue
                # read the IDs of the possible successors of the object
                nextObjectIds=entity.remainingRoute[1].get('stationIdsList',[])
                # for each objectId in the nextObjects find the corresponding object and populate the object's next list
                nextObjects=[]
                for nextObjectId in nextObjectIds:
                    nextObject=Globals.findObjectById(nextObjectId)
                    nextObjects.append(nextObject)
                # update the next list of the object
                for nextObject in nextObjects:
                    # append only if not already in the list
                    if nextObject not in currentObject.next:
                        currentObject.next.append(nextObject)
                entity.remainingRoute.pop(0)                        # remove data from the remaining route.
                entity.schedule.append([currentObject,G.env.now])   #append the time to schedule so that it can be read in the result
                entity.currentStation=currentObject                 # update the current station of the entity
            
                # if the currentStation of the entity is of type Machine then the entity must be processed first and then added to the pendingEntities list
                if not (entity.currentStation in G.MachineList):    
                    # add the entity to the pendingEntities list
                    G.pendingEntities.append(entity)
    #===========================================================================
    # OrderComponent type
#     print 'setting normal components as wip'
    #===========================================================================
    # for all the entities of Type orderComponent
    for entity in [x for x in G.OrderComponentList if not x in (G.DesignList+G.MouldList)]:
        #=======================================================================
        # print entity.id
        #=======================================================================
        # XXX if there are already Mould parts in the WIP then the components are already assembled, do not set the entity
        # check whether the mould of the same order is created
        assembled=False
        for mould in G.MouldList:
            if mould.order.id==entity.order.id:
                assembled=True
        # check whether there are other normal components from the same order in the WIP, thus the component must be created
        decomposed=False
        if len(entity.order.basicComponentsList+entity.order.secondaryComponentsList+entity.order.auxiliaryComponentsList)>0:
            decomposed=True
        # if already assembled then break to the next OrderComponent
        if assembled:
            break
        # if the entity is not in the WIP dict then they should be set by OrderDecomposition or they have already been set by createOrderComponent.
        # XXX if they are not in the WIP the it is possible that the must be set because only an other part of the same order is in the WIP (but no mould)
        if not entity.id in WIP.keys() and not decomposed:
            pass
        if not entity.id in WIP.keys() and decomposed:
            # perform the default action
            setWIP([entity])
        # if the entity is in the WIP dict then move it to the station defined.
        elif entity.id in WIP.keys() :
            objectID=WIP[entity.id]["station"]
            #===================================================================
#             print objectID, '((0))    '*10
            #===================================================================
            assert objectID!='', 'there must be a stationID given to set the WIP'
            object=Globals.findObjectById(objectID)
            assert object!=None, 'the station defined in the WIP is not a valid Station'
            # find the station by its id, if there is no station then place it 
            # in the starting queue (QCAD), (QENG)
            entry_time=float(WIP[entity.id]["entry"])
            exit_time=float(WIP[entity.id]["exit"])
            # XXX  alreadyProcessedFor=currentTime-entry_time
            # XXX if the exit time is no grater than the entry then raise an exception as for machines is not yet implemented
            try:
                if not exit_time>entry_time:
                    raise SetWipTypeError('WIP for machines is not implemented yet')
            except SetWipTypeError as setWipError:
                print 'WIP definition error: {0}'.format(setWipError)
            # find which step of the route is the current station-object and update the remainingRoute
            # removing the previous stations from the remaining_route
            for j,step in enumerate(entity.remainingRoute):
                if object.id in step["stationIdsList"]:
                    # XXX the station (object.id) must be removed from the remainingRoute as the entity has already exited (Reconsider) 
                    entity.remainingRoute=entity.remainingRoute[j+1:]
            # find the stations that come after the machine that the entity last exited
            currentObjectIds=entity.remainingRoute[0].get('stationIdsList',[])
            # pick one at random
            currentObjectId=next(id for id in currentObjectIds)
            currentObject=Globals.findObjectById(currentObjectId)
            # append the entity to its internal queue
            currentObject.getActiveObjectQueue().append(entity)        # append the entity to its Queue
            # read the IDs of the possible successors of the object
            nextObjectIds=entity.remainingRoute[1].get('stationIdsList',[])
            # for each objectId in the nextObjects find the corresponding object and populate the object's next list
            nextObjects=[]
            for nextObjectId in nextObjectIds:
                nextObject=Globals.findObjectById(nextObjectId)
                nextObjects.append(nextObject)
            # update the next list of the object
            for nextObject in nextObjects:
                # append only if not already in the list
                if nextObject not in currentObject.next:
                    currentObject.next.append(nextObject)
            entity.remainingRoute.pop(0)                        # remove data from the remaining route.
            entity.schedule.append([currentObject,G.env.now])   #append the time to schedule so that it can be read in the result
            entity.currentStation=currentObject                 # update the current station of the entity
            
            # if the currentStation of the entity is of type Machine then the entity must be processed first and then added to the pendingEntities list
            if not (entity.currentStation in G.MachineList):    
                # add the entity to the pendingEntities list
                G.pendingEntities.append(entity)
    #===========================================================================
    # Mould type
#     print 'setting mould as wip'
    #===========================================================================
    # for all the entities in the entityList
    for entity in G.MouldList:
        #=======================================================================
        # print entity.id
        #=======================================================================
        # if the entity is not in the WIP dict then it will be set by MouldAssembly on time.
        if not entity.id in WIP.keys():
            break
        # if the entity is in the WIP dict then move it to the station defined.
        elif entity.id in WIP.keys():
            objectID=WIP[entity.id]["station"]
            assert objectID!='', 'there must be a stationID given to set the WIP'
            object=Globals.findObjectById(objectID)
            assert object!=None, 'the station defined in the WIP is not a valid Station'
            # find the station by its id, if there is no station then place it 
            # in the starting queue (QCAD), (QENG)
            entry_time=float(WIP[entity.id]["entry"])
            exit_time=float(WIP[entity.id]["exit"])
            # XXX  alreadyProcessedFor=currentTime-entry_time
            # XXX if the exit time is no grater than the entry then raise an exception as for machines is not yet implemented
            try:
                if not exit_time>entry_time:
                    raise SetWipTypeError('WIP for machines is not implemented yet')
            except SetWipTypeError as setWipError:
                print 'WIP definition error: {0}'.format(setWipError)
            # find which step of the route is the current station-object and update the remainingRoute
            # removing the previous stations from the remaining_route
            for j,step in enumerate(entity.remainingRoute):
                if object.id in step["stationIdsList"]:
                    # XXX the station (object.id) must be removed from the remainingRoute as the entity has already exited (Reconsider) 
                    entity.remainingRoute=entity.remainingRoute[j+1:]
            # find the stations that come after the machine that the entity last exited
            currentObjectIds=entity.remainingRoute[0].get('stationIdsList',[])
            # pick one at random
            currentObjectId=next(id for id in currentObjectIds)
            currentObject=Globals.findObjectById(currentObjectId)
            # XXX consider reconfiguring the controls by using the length of the route
            #     or just avoid using it as the entity will be placed in the Exit
            # if the entity has already exited the Injection molding station then break, the entity should not be set 
            if currentObject.id.startswith('INJM'):
                break
            # append the entity to its internal queue
            currentObject.getActiveObjectQueue().append(entity)        # append the entity to its Queue
            # read the IDs of the possible successors of the object
            nextObjectIds=entity.remainingRoute[1].get('stationIdsList',[])
            # for each objectId in the nextObjects find the corresponding object and populate the object's next list
            nextObjects=[]
            for nextObjectId in nextObjectIds:
                nextObject=Globals.findObjectById(nextObjectId)
                nextObjects.append(nextObject)
            # update the next list of the object
            for nextObject in nextObjects:
                # append only if not already in the list
                if nextObject not in currentObject.next:
                    currentObject.next.append(nextObject)
            entity.remainingRoute.pop(0)                        # remove data from the remaining route.
            entity.schedule.append([currentObject,G.env.now])   #append the time to schedule so that it can be read in the result
            entity.currentStation=currentObject                 # update the current station of the entity
            
            # if the currentStation of the entity is of type Machine then the entity must be processed first and then added to the pendingEntities list
            if not (entity.currentStation in G.MachineList):    
                # add the entity to the pendingEntities list
                G.pendingEntities.append(entity)
            
def breakOrderDesing(orderDesign):
    '''break down the orderDesign into OrderComponents
    '''
    #===========================================================================
    # print 'breaking down','< '*20, orderDesign.id
    #===========================================================================
    G.newlyCreatedComponents=[]
    G.orderToBeDecomposed=None
    #loop in the internal Queue. Decompose only if an Entity is of type order
    # XXX now instead of Order we have OrderDesign
    assert orderDesign.type=='OrderDesign', 'cannot break down entity other than OrderDesign'
    G.orderToBeDecomposed=orderDesign.order
    #append the components in the internal queue
    for component in G.orderToBeDecomposed.componentsList:
        # XXX if the component has class Dream.Mould then avoid creating it
        if component['_class']=='Dream.Mould':
            continue
        createOrderComponent(component)
    # after the creation of the order's components update each components auxiliary list
    # if there are auxiliary components
    if len(G.orderToBeDecomposed.auxiliaryComponentsList):
        # for every auxiliary component
        for auxComponent in G.orderToBeDecomposed.auxiliaryComponentsList:
            # run through the componentsList of the order
            for reqComponent in G.orderToBeDecomposed.componentsList:
                # to find the requestingComponent of the auxiliary component
                if auxComponent.requestingComponent==reqComponent.id:
                    # and add the auxiliary to the requestingComponent auxiliaryList
                    reqComponent.auxiliaryList.append(auxComponent)
    #if there is an order for decomposition
    if G.orderToBeDecomposed:
        from Globals import setWIP
        setWIP(G.newlyCreatedComponents)     #set the new components as wip
        # TODO: consider signalling the receivers if any WIP is set now
        #reset attributes
        G.orderToBeDecomposed=None
        G.newlyCreatedComponents=[]


def createOrderComponent(component):
    '''create each OrderComponent of the componentsList of the Order
    '''
    #read attributes from the json or from the orderToBeDecomposed
    id=component.get('id', 'not found')
    name=component.get('name', 'not found')
    try:
        # there is the case were the component of the componentsList of the parent Order
        # is of type Mould and therefore has no argument componentType
        # in this case no Mould object should be initiated
        if component.get('_class', 'not found')=='Dream.Mould':
            raise MouldComponentException('there is a mould in the componentList')
        # variable that holds the componentType which can be Basic/Secondary/Auxiliary
        componentType=component.get('componentType', 'Basic') 
        # the component that needs the auxiliary (if the componentType is "Auxiliary") during its processing
        requestingComponent = component.get('requestingComponent', 'not found') 
        # dummy variable that holds the routes of the jobs the route from the JSON file is a sequence of dictionaries
        JSONRoute=component.get('route', [])
        # variable that holds the argument used in the Job initiation hold None for each entry in the 'route' list
        route = [x for x in JSONRoute]
        # keep a reference of all extra properties passed to the job
        extraPropertyDict = {}
        for key, value in component.items():
            if key not in ('_class', 'id'):
                extraPropertyDict[key] = value
        
        # initiate the OrderComponent
        OC=OrderComponent(id, name, route, \
                            priority=G.orderToBeDecomposed.priority, \
                            dueDate=G.orderToBeDecomposed.dueDate, \
                            componentType=componentType,\
                            requestingComponent = requestingComponent, \
                            order=G.orderToBeDecomposed,\
                            orderDate=G.orderToBeDecomposed.orderDate, \
                            extraPropertyDict=extraPropertyDict,\
                            isCritical=G.orderToBeDecomposed.isCritical)
        #=======================================================================
        # print 'created component', '< '*10, OC.id
        #=======================================================================
            
        # check the componentType of the component and accordingly add to the corresponding list of the parent order
        if OC.componentType == 'Basic':
            G.orderToBeDecomposed.basicComponentsList.append(OC)
        elif OC.componentType == 'Secondary':
            G.orderToBeDecomposed.secondaryComponentsList.append(OC)
        else:
            G.orderToBeDecomposed.auxiliaryComponentsList.append(OC)
                
        G.OrderComponentList.append(OC)
        G.JobList.append(OC)   
        G.WipList.append(OC)  
        G.EntityList.append(OC)
        G.newlyCreatedComponents.append(OC)              #keep these to pass them to setWIP
    except MouldComponentException as mouldException:
        pass