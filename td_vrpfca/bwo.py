import random
import copy
from typing import List, Dict, Tuple
from .loader import Instance
from .evaluator import evaluate_routes

class BWOSolution:
    def __init__(self, chromosome: List[int], fitness: float = float('inf')):
        self.chromosome = chromosome
        self.fitness = fitness

class BWOOptimizer:
    def __init__(
        self,
        instance: Instance,
        npop: int = 20,
        procreation_rate: float = 0.40,
        cannibalism_rate: float = 0.50,
        mutation_rate: float = 0.05,
        seed: int = None
    ):
        self.inst = instance
        self.npop = npop
        self.procreation_rate = procreation_rate
        self.cannibalism_rate = cannibalism_rate
        self.mutation_rate = mutation_rate
        self.seed = seed
        
        self.n = len(self.inst.customers)
        self.k = len(self.inst.vehicles)
        self.d = len(self.inst.crew)
        
        self.corte_cadena = self.n + self.k + 1
        self.nr = max(1, int(self.npop * self.procreation_rate))
        self.nm = max(1, int(self.npop * self.mutation_rate))
        
        if self.seed is not None:
            random.seed(self.seed)
            
    def decode_chromosome(self, chromosome: List[int]) -> Tuple[Dict[int, List[int]], Dict[int, int], Dict[int, int]]:
        route_segment = chromosome[:self.corte_cadena]
        crew_segment = chromosome[self.corte_cadena:self.corte_cadena + self.d]
        time_segment = chromosome[-1]
        
        routes = {i: [] for i in range(1, self.k + 1)}
        vehicle_idx = 1
        
        for node in route_segment[1:]:
            if node == 0:
                vehicle_idx += 1
                if vehicle_idx > self.k:
                    break
            else:
                if vehicle_idx <= self.k:
                    routes[vehicle_idx].append(node)
                
        crew = {}
        v_idx = 1
        for l in range(self.d):
            count = crew_segment[l]
            while count > 0 and v_idx <= self.k:
                crew[v_idx] = l + 1
                v_idx += 1
                count -= 1
                
        while v_idx <= self.k:
            crew[v_idx] = 1
            v_idx += 1
            
        start_intervals = {i: time_segment for i in range(1, self.k + 1)}
        
        return routes, crew, start_intervals
        
    def evaluate(self, chromosome: List[int]) -> float:
        routes, crew, start_intervals = self.decode_chromosome(chromosome)
        result = evaluate_routes(self.inst, routes, crew, start_intervals)
        if not result["feasible"]:
            return float('inf')
        return result["T_MAX"]

    def is_route_feasible(self, route_segment: List[int]) -> bool:
        current_demand = 0.0
        vehicle_idx = 1
        for node in route_segment[1:]:
            if node == 0:
                if vehicle_idx <= self.k:
                    if current_demand > self.inst.vehicles[vehicle_idx].capacity:
                        return False
                vehicle_idx += 1
                current_demand = 0.0
            else:
                current_demand += self.inst.demand.get(node, 0.0)
        return True

    def create_random_route(self) -> List[int]:
        while True:
            customers = list(self.inst.customers)
            random.shuffle(customers)
            zeros = [0] * (self.k - 1)
            inner = customers + zeros
            random.shuffle(inner)
            route = [0] + inner + [0]
            if self.is_route_feasible(route):
                return route

    def create_random_crew(self) -> List[int]:
        while True:
            crew = [0] * self.d
            for _ in range(self.k):
                crew[random.randint(0, self.d - 1)] += 1
                
            cap_fact = True
            for wt, avail in self.inst.worker_availability.items():
                required = sum(self.inst.crew[c_id].get(wt, 0) * crew[c_id - 1] for c_id in self.inst.crew)
                if required > avail:
                    cap_fact = False
                    break
                    
            if cap_fact:
                v_idx = 1
                crew_fact = True
                for c_id, count in enumerate(crew, 1):
                    c_size = sum(self.inst.crew[c_id].values())
                    for _ in range(count):
                        if v_idx <= self.k:
                            if c_size > self.inst.vehicles[v_idx].max_crew:
                                crew_fact = False
                                break
                            v_idx += 1
                    if not crew_fact:
                        break
                        
                if crew_fact:
                    return crew

    def initialize_population(self) -> List[BWOSolution]:
        population = []
        for _ in range(self.npop):
            route = self.create_random_route()
            crew = self.create_random_crew()
            interval = random.choice(self.inst.intervals)
            chromosome = route + crew + [interval]
            sol = BWOSolution(chromosome)
            sol.fitness = self.evaluate(chromosome)
            population.append(sol)
        return sorted(population, key=lambda x: x.fitness)

    def breed(self, parent1: List[int], parent2: List[int]) -> Tuple[List[int], List[int]]:
        route_p1 = parent1[:self.corte_cadena]
        route_p2 = parent2[:self.corte_cadena]
        assign1 = parent1[self.corte_cadena:]
        assign2 = parent2[self.corte_cadena:]
        
        if len(route_p1) > 1:
            a = random.randint(0, len(route_p1) - 1)
            b = random.randint(0, len(route_p1) - 1)
            start = min(a, b)
            end = max(a, b)
        else:
            start, end = 0, 1
            
        child_p1 = route_p1[start:end]
        child_p2 = [x for x in route_p2 if x == 0 or x not in child_p1]
        
        child = child_p1 + child_p2
        if len(child) > 0 and child[0] != 0:
            child = [0] + child
            
        while len(child) > self.corte_cadena:
            found_zero = False
            for i in range(1, len(child)):
                if child[i] == 0 and not found_zero:
                    del child[i]
                    found_zero = True
                    break
                    
        while len(child) < self.corte_cadena:
            child.append(0)
            
        if not self.is_route_feasible(child):
            child = self.create_random_route()
            
        child1 = child + assign1
        child2 = child + assign2
        
        return child1, child2

    def procreate_and_cannibalize(self, pop: List[BWOSolution]) -> List[BWOSolution]:
        survivors = list(pop)
        
        for _ in range(self.nr // 2):
            if len(survivors) < 2:
                break
                
            p1_idx = random.randint(0, len(survivors) - 1)
            p2_idx = random.randint(0, len(survivors) - 1)
            while p1_idx == p2_idx:
                p2_idx = random.randint(0, len(survivors) - 1)
                
            mother = survivors[p1_idx]
            father = survivors[p2_idx]
            
            c1_chrom, c2_chrom = self.breed(mother.chromosome, father.chromosome)
            
            sol1 = BWOSolution(c1_chrom)
            sol1.fitness = self.evaluate(c1_chrom)
            sol2 = BWOSolution(c2_chrom)
            sol2.fitness = self.evaluate(c2_chrom)
            
            # Sexual Cannibalism (Reconstructed): weaker parent (father) is destroyed
            if mother.fitness <= father.fitness:
                if father in survivors:
                    survivors.remove(father)
            else:
                if mother in survivors:
                    survivors.remove(mother)
                # Swap mother role to the stronger one for parental cannibalism logic
                mother = father
                
            # Sibling Cannibalism: stronger sibling eats weaker
            children = sorted([sol1, sol2], key=lambda x: x.fitness)
            if self.cannibalism_rate > 0 and len(children) > 1:
                # keep cr% of children. Since we only have 2, cr=0.5 means keep 1.
                surviving_count = max(1, int(len(children) * self.cannibalism_rate))
                children = children[:surviving_count]
                
            # Parental Cannibalism (Reconstructed from paper concept):
            # Best child compares with mother. If child is better, mother is eaten.
            if len(children) > 0 and children[0].fitness < mother.fitness:
                if mother in survivors:
                    survivors.remove(mother)
                    
            survivors.extend(children)
            
        return survivors

    def mutate(self, pop: List[BWOSolution]) -> List[BWOSolution]:
        mutants = []
        for _ in range(self.nm):
            if not pop:
                break
            parent = random.choice(pop).chromosome
            route = list(parent[:self.corte_cadena])
            assign = list(parent[self.corte_cadena:])
            
            if len(route) > 2:
                m1 = random.randint(1, len(route) - 1)
                m2 = random.randint(1, len(route) - 1)
                route[m1], route[m2] = route[m2], route[m1]
                
            if route[0] != 0:
                route = [0] + route
                if len(route) > self.corte_cadena:
                    for i in range(1, len(route)):
                        if route[i] == 0:
                            del route[i]
                            break
                            
            while len(route) < self.corte_cadena:
                route.append(0)
                
            if not self.is_route_feasible(route):
                route = self.create_random_route()
                
            mutant_chrom = route + assign
            sol = BWOSolution(mutant_chrom)
            sol.fitness = self.evaluate(mutant_chrom)
            mutants.append(sol)
            
        return mutants

    def run(self, max_iter: int = 100):
        import time
        start_time = time.time()
        
        pop = self.initialize_population()
        gbest = copy.deepcopy(pop[0])
        hist = []
        
        for iteration in range(max_iter):
            pop = self.procreate_and_cannibalize(pop)
            mutants = self.mutate(pop)
            pop.extend(mutants)
            
            pop = sorted(pop, key=lambda x: x.fitness)
            pop = pop[:self.npop]
            
            if pop[0].fitness < gbest.fitness:
                gbest = copy.deepcopy(pop[0])
                
            hist.append(gbest.fitness)
            
        total_time = time.time() - start_time
        return gbest, hist, total_time

