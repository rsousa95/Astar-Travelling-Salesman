import search


class ASARProblem(search.Problem):

    def __init__(self):
        self.initial = State()

    def load(self, fh):
        # Reads the lines of the file and stores the information as the initial state

        lines = fh.readlines()

        airclass = []

        for ln in lines:
            line_list = ln.split()
            if len(line_list) > 0:
                if line_list[0] == 'A':  # name open_time close_time
                    airport = Airport(line_list[1], hhmm2minutes(line_list[2]), hhmm2minutes(line_list[3]))
                    self.initial.Airports.append(airport)

                elif line_list[0] == 'C':  # class rot_time
                    airclass.append((line_list[1], hhmm2minutes(line_list[2])))

                elif line_list[0] == 'P':  # name class
                    airplane = Plane(line_list[1], line_list[2])
                    self.initial.Planes.append(airplane)

                elif line_list[0] == 'L':  # dep arriv duration airclass1 profit1 airclass2 profit2...
                    leg = Leg(line_list[1], line_list[2], hhmm2minutes(line_list[3]))
                    for i in range(4, len(line_list) - 1, 2):
                        leg.insert_plane_and_profit(line_list[i], int(line_list[i + 1]))
                    self.initial.Legs.append(leg)

        for plane in self.initial.Planes:  # assigns class and rotation time to the planes
            for classes in airclass:
                if plane.air_class == classes[0]:
                    plane.rot_time = classes[1]

        self.initial.time = earliest_airport_open_time(self.initial.Airports)

    def save(self, fh, state):
        # Writes the solution in the output file

        for plane in state.Planes:
            if len(plane.schedule) > 0:
                string = "S "
                string = string + plane.id
                for sch in plane.schedule:
                    string = string + " " + sch[0] + " " + sch[1] + " " + sch[2]
                string = string + '\n'
                fh.writelines(string)

        fh.writelines("P " + str(state.profit) + '\n')

    def actions(self, state):
        # Returns a list of the actions applicable to the given state

        # checks which planes are available
        planes_available = [plane for plane in state.Planes
                            if (plane.is_available() and plane.has_an_available_leg(state.Legs, state.Airports, state.time))]

        # for the planes available, checks if they have a valid leg available
        actions = [(plane, leg) for plane in planes_available for leg in state.Legs
                   if valid_leg(plane, leg, state.Airports, state.time)]

        # if a plane is in the starting airport and at least one other plane is active we can order the plane to suspend activity
        for plane in planes_available:
            if plane.is_in_start_airport() is True and state.at_least_one_other_plane_working(plane) is True:
                actions.append((plane, None))

        return actions

    def result(self, state, action):
        # Receives the current state and the action to apply. Returns the new state resulting from applying the action
        # The actions are assigning a leg to an airplane or suspending an airplane's activity

        sub = my_copy(state)
        plane = find_equivalent_plane(sub, action[0])

        if action[1] is not None:
            # puts a plane on a leg
            leg = action[1]
            land_time, available_time = plane.put_plane_on_leg(leg, state.Airports, state.time)
            sub.event_log.append(land_time)
            sub.event_log.append(available_time)
            sub.profit = state.profit + leg_profit(plane, leg)
            remove_equivalent_leg(sub, leg)

        else:
            # puts a plane on standby
            plane.state = "On standby"
            plane.available = False
            plane.available_time = None

        sub.update_time()
        return sub

    def goal_test(self, state):
        # Checks if the state is the goal
        # The goal is:  all legs done and each plane in its starting airport

        if len(state.Legs) > 0:
            return False

        for plane in state.Planes:
            if plane.is_in_start_airport() is False:
                return False

        return True

    def path_cost(self, c, state1, action, state2):
        # Returns the path cost.
        # The path cost is the negative of the profit of the leg chosen (or zero, if the action was to suspend a plane)

        profit = 0

        if action[1] is not None:
            plane = action[0]
            leg = action[1]

            for pp in leg.plane_and_profit:
                if plane.air_class == pp[0]:
                    profit = -pp[1]

        return c + profit

    def heuristic(self, node):
        # Returns the heuristic of the node
        # The heuristic is the negative of the sum of the highest profits for all legs not done

        if len(node.state.Legs) > 0:
            return -sum([max(leg.all_profits()) for leg in node.state.Legs])

        else:
            return 0


class State:
    def __init__(self):
        self.Airports = []
        self.Planes = []
        self.Legs = []
        self.time = 0
        self.profit = 0.0
        self.event_log = []

    def __lt__(self, other):
        return False

    def display(self):
        print("Time:", minutes2hhmm(self.time))
        # print("Events: ", [minutes2hhmm(t) for t in self.event_log])
        # for airport in self.Airports:
        #    airport.display()
        for airplane in self.Planes:
            airplane.display()
        for leg in self.Legs:
            leg.display()

    def update_time(self):
        # Advances time until a plane is available again

        # If there are planes already available no time passes
        for plane in self.Planes:
            if plane.is_available():
                return

        there_are_planes_available = False

        while there_are_planes_available is False:
            self.time = min(self.event_log)

            for plane in self.Planes:
                if plane.landing_time == self.time:
                    # Lands the plane and it starts the rotation process
                    plane.location = plane.schedule[-1][-1]
                    plane.state = "Rotating"
                    plane.landing_time = None
                    self.event_log.remove(self.time)

                if plane.available_time == self.time:
                    there_are_planes_available = True

                    if plane.has_an_available_leg(self.Legs, self.Airports, self.time):
                        # The plane finishes rotating and becomes available again
                        plane.available = True
                        plane.available_time = None
                        plane.state = "Ready"
                        self.event_log.remove(self.time)

                    else:
                        # The plane has finished rotating but has no available legs, so it's put on standby
                        plane.available = False
                        plane.available_time = None
                        plane.state = "On standby"
                        self.event_log.remove(self.time)

                        if len(self.Legs) == 0:
                            return

    def at_least_one_other_plane_working(self, current_plane):
        for plane in self.Planes:
            if current_plane != plane:
                if plane.state != "On standby":
                    return True
        return False


class Airport:

    def __init__(self, code=None, open_t=0, close_t=0):
        self.code = code
        self.open_t = open_t
        self.close_t = close_t
        self.schedule = []

    def display(self):
        print("Airport: [", self.code, minutes2hhmm(self.open_t), minutes2hhmm(self.close_t), "]")


class Plane:

    def __init__(self, code="", air_class=""):
        self.id = code
        self.air_class = air_class
        self.schedule = []
        self.available = True
        self.state = "Ready"
        self.location = None
        self.rot_time = None
        self.landing_time = None
        self.available_time = None

    def put_plane_on_leg(self, leg, airports, time):
        # Assigns the leg to the airplane's schedule
        # Returns the landing and available times

        dep, arriv = find_airports_of_leg(leg, airports)

        # When the arrival airport isn't open yet the plane departs later
        if time + leg.duration < arriv.open_t:
            self.schedule.append([minutes2hhmm(arriv.open_t - leg.duration), leg.depart, leg.arrival])
            self.landing_time = arriv.open_t

        # when the departure airport isn't open yet the plane departs later
        elif time < dep.open_t:
            self.schedule.append([minutes2hhmm(dep.open_t), leg.depart, leg.arrival])
            self.landing_time = dep.open_t + leg.duration

        # normal situations
        else:
            self.schedule.append([minutes2hhmm(time), leg.depart, leg.arrival])
            self.landing_time = time + leg.duration

        self.available_time = self.landing_time + self.rot_time
        self.location = "Airborne"
        self.state = "En route"
        self.available = False

        return self.landing_time, self.available_time

    def display(self):
        print("Airplane: [", self.air_class, "Available:", self.available, "Available time:", self.available_time, "Location:", self.location, " State:", self.state, "]")
        print("     schedule:", [(sched[0], sched[1], sched[2]) for sched in self.schedule])

    def is_available(self):
        if self.state == "Ready":
            return True
        else:
            return False

    def has_an_available_leg(self, legs, airports, time):
        # Returns True if the plane has at least one available leg

        for leg in legs:
            if valid_leg(self, leg, airports, time):
                return True
        return False

    def is_in_start_airport(self):
        # Returns True if the plane is in its starting airport (or if it hasn't even flown yet)

        if len(self.schedule) == 0:
            # len == 0 means the plane didn't even fly
            return True
        elif self.schedule[0][1] == self.schedule[-1][2]:
            return True
        else:
            return False


class Leg:

    def __init__(self, depart="", arrival="", duration=0, plane_and_profit=None):
        if plane_and_profit is None:
            plane_and_profit = []
        self.depart = depart
        self.arrival = arrival
        self.duration = duration
        self.plane_and_profit = []

    def insert_plane_and_profit(self, plane, profit):
        self.plane_and_profit.append((plane, profit))

    def display(self):
        print("Leg: [", self.depart, self.arrival, self.duration, self.plane_and_profit, "]")

    def all_profits(self):
        # Returns a list with all the profits possible for the leg
        return [pp[1] for pp in self.plane_and_profit]


def valid_leg(plane, leg, airports, time):
    # Receives a plane and a leg. Returns True if the plane can fly the leg

    # checks if the plane is in the airport where a leg departs
    # if the plane doesn't have a location is because it's the starting situation and every leg is available
    # also has the airports' close times in consideration
    if plane.location == leg.depart or plane.location is None:
        airport_dep, airport_arriv = find_airports_of_leg(leg, airports)
        if time + leg.duration <= airport_arriv.close_t and time <= airport_dep.close_t:
            return True

    return False


def find_airports_of_leg(leg, airports):
    dep, arriv = (None, None)

    for airport in airports:
        if airport.code == leg.depart:
            dep = airport
        if airport.code == leg.arrival:
            arriv = airport
    return dep, arriv


def hhmm2minutes(time):
    # Converts hhmm (in string) format to minutes (int)

    hours = int(time[:len(time)//2])
    minutes = int(time[len(time)//2:])
    return hours*60 + minutes


def minutes2hhmm(time):
    # Converts a time in minutes (in int) to hhmm format (in string)
    return '%02d' % (time//60) + '%02d' % (time % 60)


def earliest_airport_open_time(airports):
    return min([airport.open_t for airport in airports])


def earliest_plane_available_time(planes):
    return min([plane.available_time for plane in planes])


def leg_profit(plane, leg):
    # Returns the profit of the leg when a plane of a certain class flies it

    for (air_class, profit) in leg.plane_and_profit:
        if plane.air_class == air_class:
            return profit


def find_equivalent_plane(state, plane_to_find):
    for plane in state.Planes:
        if plane_to_find.id == plane.id:
            return plane


def remove_equivalent_leg(state, leg_to_remove):
    for leg in state.Legs:
        if leg.depart == leg_to_remove.depart and leg.arrival == leg_to_remove.arrival and leg.duration == leg_to_remove.duration:
            state.Legs.remove(leg)
            return


def my_copy(state):
    new = State()

    for airport in state.Airports:
        new_airport = Airport()
        new_airport.code = airport.code
        new_airport.open_t = airport.open_t
        new_airport.close_t = airport.close_t

        new.Airports.append(new_airport)

    for leg in state.Legs:
        new_leg = Leg()
        new_leg.depart = leg.depart
        new_leg.arrival = leg.arrival
        new_leg.duration = leg.duration
        new_leg.plane_and_profit = leg.plane_and_profit[:]

        new.Legs.append(new_leg)

    for plane in state.Planes:
        new_plane = Plane()

        new_plane.id = plane.id
        new_plane.air_class = plane.air_class
        new_plane.schedule = plane.schedule[:]
        new_plane.available = plane.available
        new_plane.state = plane.state
        new_plane.location = plane.location
        new_plane.rot_time = plane.rot_time
        new_plane.landing_time = plane.landing_time
        new_plane.available_time = plane.available_time

        new.Planes.append(new_plane)

    new.time = state.time
    new.profit = state.profit
    new.event_log = state.event_log[:]

    return new


def my_copy_plane(plane):
    new_plane = Plane()

    new_plane.id = plane.id
    new_plane.air_class = plane.air_class
    new_plane.schedule = plane.schedule[:]
    new_plane.available = plane.available
    new_plane.state = plane.state
    new_plane.location = plane.location
    new_plane.rot_time = plane.rot_time
    new_plane.landing_time = plane.landing_time
    new_plane.available_time = plane.available_time

    return new_plane
