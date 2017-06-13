import math
import random
import time
import sys

stopPenalty = 12 # sec
timeSteps = 100000

floorHeight = 11

debug = False

def getRequestDirection(request):
    if request[0] > request[1]:
        return 'down'
    else:
        return 'up'

class Floor(object):

    def __init__(self):
        self.downQueue = []
        self.upQueue = []

        self.sourceCount = 0
        self.sourceWait = 0
        self.sourceTravel = 0

        self.destCount = 0
        self.destWait = 0
        self.destTravel = 0

    def addRequest(self, request, direction):
        if direction == 'up':
            self.upQueue.append(request)
        else:
            self.downQueue.append(request)

        if debug:
            print "%s: P%s wants to go from %s to %s" % (request[2], request[2], request[0], request[1])

    def hasRequest(self, direction):
        if direction == 'up':
            return bool(self.upQueue)
        else:
            return bool(self.downQueue)

    def stat(self, source, waitTime, travelTime):
        if source:
            self.sourceCount += 1
            self.sourceWait += waitTime
            self.sourceTravel += travelTime
        else:
            self.destCount += 1
            self.destWait += waitTime
            self.destTravel += travelTime

class ElevatorState(object):

    def __init__(self, floorCount, elevators):
        self.elevators = elevators

        self.elevatorDestinations = {}
        for elevator in elevators:
            self.elevatorDestinations[elevator.uid] = None
        
        self.floors = []
        self.floorCount = floorCount
        for floor in range(0, floorCount):
            self.floors.append(Floor())

        self.upCalls = set()
        self.downCalls = set()

        self.satisfiedPassengers = 0
        self.totalRequests = 0
        self.totalWaitTime = 0
        self.totalTravelTime = 0

    def addSatisfiedPassenger(self, request):
        self.satisfiedPassengers += 1
        waitTime = request[3] - request[2]
        travelTime = request[4] - request[3]
        self.totalWaitTime += waitTime
        self.totalTravelTime += travelTime
        self.floors[request[0]].stat(True, waitTime, travelTime)
        self.floors[request[1]].stat(False, waitTime, travelTime)

    def getExtremes(self):
        if self.downCalls:
            highDown = sorted(self.downCalls)[-1]
        else:
            highDown = None

        if self.upCalls:
            lowUp = sorted(self.upCalls)[0]
        else:
            lowUp = None

        return lowUp, highDown

    def timeIncrement(self, t):
        for elevator in self.elevators:
            elevator.timeIncrement(t, self)

    def submitRequest(self, request):
        self.totalRequests += 1
        direction = getRequestDirection(request)
        self.floors[request[0]].addRequest(request, direction)
        if direction == 'up':
            self.upCalls.add(request[0])
        else:
            self.downCalls.add(request[0])

    def swapPassengers(self, elevator, floor, t):
        for request in list(elevator.passengers):
            if request[1] == elevator.floor:
                elevator.passengers.remove(request)
                request[4] = t
                self.addSatisfiedPassenger(request)
                if debug:
                    print "%s: P%s got off at %s" % (t, request[2], elevator.floor)

        if elevator.passengers:
            direction = getRequestDirection(elevator.passengers[0])
        elif floor.downQueue:
            # todo: this is a preference, should be randomized or use time
            direction = 'down'
        elif floor.upQueue:
            direction = 'up'
        else:
            return # fuck it

        if direction == 'up' and floor.upQueue:
            queue = floor.upQueue
            self.upCalls.remove(elevator.floor)
        elif direction == 'down' and floor.downQueue:
            queue = floor.downQueue
            self.downCalls.remove(elevator.floor)
        else:
            return # really, fuck it

        for request in list(queue):
            request[3] = t
            queue.remove(request)
            elevator.addPassenger(request)
            if debug:
                print "%s: P%s got on at %s" % (t, request[2], elevator.floor)

class Elevator(object):

    def __init__(self, uid, speed):
        self.uid = uid
        self.travelCost = int(math.ceil(floorHeight  / speed))
        
        self.floor = 0
        self.passengers = []
        self.destination = None

        self.action = 'idle'
        self.actionCounter = 0

    def addPassenger(self, request):
        self.passengers.append(request)

    def hasPassengersForFloor(self, floor):
        for request in self.passengers:
            if request[1] == floor:
                return True
        return False

    def timeIncrement(self, t, state):
        if self.actionCounter > 0:
            self.actionCounter -= 1
        else:
            # state-changing
            if self.action == 'down':
                self.floor -= 1
                if debug:
                    print "%s: E%s %s->%s" % (t, self.uid, self.floor+1, self.floor)
            elif self.action == 'up':
                self.floor += 1
                if debug:
                    print "%s: E%s %s->%s" % (t, self.uid, self.floor-1, self.floor)
            self.action = 'idle'

            if self.passengers:
                # if you have passengers, you can only open the door for
                # passengers on this floor going the same direction, or keep
                # going towards your destination

                direction = getRequestDirection(self.passengers[0])

                floor = state.floors[self.floor]
                if floor.hasRequest(direction):
                    self.action = 'open-door'
                elif self.hasPassengersForFloor(self.floor):
                    self.action = 'open-door'
                else:
                    self.action = direction
            elif self.destination is not None:
                # we might cancel this destination if there's nobody there
                floor = state.floors[self.destination]
                if not floor.upQueue and not floor.downQueue:
                    self.destination = None
                else:
                    if self.destination == self.floor:
                        self.destination = None
                        floor = state.floors[self.floor]
                        if floor.upQueue or floor.downQueue:
                            self.action = 'open-door'
                    elif self.destination < self.floor:
                        self.action = 'down'
                    else:
                        self.action = 'up'

            # if we still don't have an action, let's choose some new destination
            if self.action == 'idle':
                lowUp, highDown = state.getExtremes()

                # if only one, choose it, otherwise, pick random
                if highDown is not None and lowUp is not None:
                    if random.random() < 0.5:
                        self.destination = highDown
                    else:
                        self.destination = lowUp
                elif highDown is not None:
                    self.destination = highDown
                elif lowUp is not None:
                    self.destination = lowUp

                if self.destination is not None:
                    if self.destination < self.floor:
                        self.action = 'down'
                    else:
                        self.action = 'up'

                    if debug:
                        print "%s: E%s is destined for %s" % (t, self.uid, self.destination)

            if self.action == 'open-door':
                floor = state.floors[self.floor]
                state.swapPassengers(self, floor, t)

            if self.action in ['up', 'down']:
                self.actionCounter = self.travelCost
            elif self.action == 'open-door':
                self.actionCounter = stopPenalty
            else:
                self.actionCounter = 0
 
def simulateElevators(load, numberFloors, elevatorSpeedFpm, numberElevators, peakMode):
    elevators = []
    for i in range(0, numberElevators):
        elevators.append(Elevator(i, elevatorSpeedFpm / 60.))

    state = ElevatorState(numberFloors, elevators)

    for t in xrange(0, timeSteps):
        if random.random() < 1.0 / load:
            floor = random.randint(1, numberFloors-1)
            direction = peakMode
            if direction == 'up':
                startFloor, endFloor = 0, floor
            else:
                startFloor, endFloor = floor, 0
            passenger = [startFloor, endFloor, t, None, None]
            state.submitRequest(passenger)
        
        state.timeIncrement(t)

    return state

def statResults(load, numberFloors, elevatorSpeedFpm, numberElevators, peakMode, state):
    if state.satisfiedPassengers:
        print "\t".join([
            str(numberFloors),
            str(numberElevators),
            str(load),
            str(elevatorSpeedFpm),
            str(peakMode),
            str(state.totalWaitTime / state.satisfiedPassengers), 
            str(state.totalTravelTime / state.satisfiedPassengers), 
            str(state.satisfiedPassengers / float(state.totalRequests))
        ])
    else:
        print "\t".join([
            str(numberFloors),
            str(numberElevators),
            str(load),
            str(elevatorSpeedFpm),
            str(peakMode),
        ])

def statFloorResults(state, source):
    floors = []
    for (i, floor) in enumerate(state.floors):
        if source and floor.sourceCount:
            row = [
                floor.sourceWait / floor.sourceCount, 
                floor.sourceTravel / floor.sourceCount
            ]
        elif (not source) and floor.destCount:
            row = [
                floor.destWait / floor.destCount, 
                floor.destTravel / floor.destCount
            ]
        else:
            row = [0, 0]

        floors.append(row)

    return floors

def getElevatorTimes(floorCount, elevatorSpeed, unitCount, elevatorCount):
    load = 10800 / (1.0 * unitCount)

    return {
        'up': statFloorResults(
            simulateElevators(load, floorCount, elevatorSpeed, elevatorCount, 'up'),
            False
        ),
        'down': statFloorResults(
            simulateElevators(load, floorCount, elevatorSpeed, elevatorCount, 'down'),
            True
        ),
    }