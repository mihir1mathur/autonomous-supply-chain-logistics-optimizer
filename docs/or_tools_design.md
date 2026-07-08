# OR-Tools Design (Week 5)

This document explains **why** the project uses Google OR-Tools and the
optimization ideas behind the Week 5 solvers: linear programming (LP), integer
programming (IP), constraint programming (CP), and the Vehicle Routing Problem
(VRP) at a high level. It then shows how the two CP-SAT solvers in this project
are actually modelled.

For the package layout see
[`optimization_architecture.md`](optimization_architecture.md); for the runtime
data flow see [`optimization_flow.md`](optimization_flow.md).

---

## Why OR-Tools

**OR-Tools** is Google's open-source toolkit for **operations research** — the
branch of applied mathematics that finds the best decision among a huge number
of possibilities, subject to rules. It is a strong fit here for several reasons:

- **The problems are combinatorial.** "Which vehicle carries which shipment?"
  has an astronomical number of possible answers. A hand-written loop cannot
  search that space well; a dedicated solver can, and can even *prove* a plan is
  optimal.
- **It separates the model from the search.** We describe *what* a valid, good
  plan looks like (variables, constraints, an objective) and OR-Tools does the
  searching. We never write the search algorithm ourselves.
- **One toolkit, many techniques.** OR-Tools includes a CP-SAT solver
  (constraint programming), LP/MIP solvers (linear and mixed-integer
  programming), and a dedicated routing library for the VRP. Week 5 uses CP-SAT;
  the same toolkit covers the future routing work.
- **Production-grade and free.** It is fast, well-documented, battle-tested at
  Google scale, and carries no licensing cost.

---

## Operations research vocabulary

Every optimization model has three parts:

| Part | Meaning | Example (shipment assignment) |
|------|---------|-------------------------------|
| **Decision variables** | The choices the solver may set | `x[s,v] = 1` if shipment *s* rides on vehicle *v* |
| **Constraints** | Rules a valid plan must obey | a vehicle's load ≤ its capacity |
| **Objective** | The single number to maximize or minimize | carry the most packages, using the fewest vehicles |

Optimization = **find the setting of the variables that gives the best
objective while satisfying every constraint.**

---

## Linear Programming (LP)

**Linear programming** optimizes a linear objective subject to linear
constraints, where the variables are **continuous** (they can take fractional
values). "Linear" means every term is just a variable times a constant, added
up — no multiplying two variables together, no curves.

- *Example:* "Ship as cheaply as possible, where cost = distance × rate and no
  warehouse ships more than it stocks." If quantities can be fractional, this is
  an LP, and it is solved very efficiently.
- *Limitation for us:* many logistics decisions are **yes/no** ("does this
  shipment go on this vehicle?"). You cannot put *half* a shipment on a vehicle.
  Fractional answers are meaningless, which is where integers come in.

---

## Integer Programming (IP)

**Integer programming** is LP with the extra rule that some or all variables
must be **whole numbers** — often just `0` or `1` (a "binary" variable meaning
no/yes). This captures indivisible, all-or-nothing decisions exactly.

- *Example:* `x[s,v] ∈ {0, 1}` — shipment *s* is either fully on vehicle *v* or
  not at all. `used[v] ∈ {0, 1}` — a vehicle is either opened or not.
- *Why it is harder:* forcing whole numbers makes the problem much harder to
  solve than LP (you cannot simply round an LP answer and stay optimal). Solvers
  use clever search ("branch and bound") to handle it.
- **Both Week 5 CP-SAT models are integer programs**: the shipment-assignment
  and vehicle-utilization solvers use binary assignment variables.

---

## Constraint Programming (CP) and CP-SAT

**Constraint programming** describes a problem as variables over finite domains
plus constraints, and searches for a satisfying (and, with an objective, best)
assignment. **CP-SAT** is OR-Tools' modern solver that combines constraint
programming with SAT ("boolean satisfiability") techniques. It is excellent at
problems built from **integer and boolean variables with linear constraints** —
exactly the shape of our assignment and balancing problems.

Week 5 uses CP-SAT because our decisions are naturally boolean ("on this
vehicle or not") and our rules are linear ("total load ≤ capacity"). CP-SAT
models these directly, works purely in integers (so we scale fractions like
utilization into whole numbers), and returns a status — `OPTIMAL` (proven best)
or `FEASIBLE` (a valid plan found within the time limit).

---

## Model 1 — Shipment assignment (CP-SAT)

*Goal: respect capacity, carry as much as possible, and minimize unused
capacity by consolidating onto as few vehicles as possible.* Solved per
warehouse (a vehicle only carries its own site's shipments).

```
Variables
  x[s, v] in {0,1}   shipment s is carried by vehicle v
  used[v] in {0,1}   vehicle v carries at least one shipment

Constraints
  (1) each shipment on at most one vehicle:   sum over v of x[s,v] <= 1
  (2) capacity:  sum over s of demand[s]*x[s,v] <= capacity[v]     (for each v)
  (3) link used: used[v] >= x[s,v]                        (for each s, v)

Objective
  maximize   W * (packages carried)  -  (vehicles used)
  where W = (number of vehicles) + 1, so carrying one more package always
  outranks opening one more vehicle. Carrying wins first; among equally-full
  plans, fewer vehicles wins — and fewer, fuller vehicles is exactly what
  "minimize unused capacity" means.
```

---

## Model 2 — Vehicle utilization / balancing (CP-SAT)

*Goal: carry as much as possible, then spread the load evenly so no vehicle is
slammed while others sit idle.* Same variables and capacity rule as Model 1,
different objective.

```
Variables
  x[s, v] in {0,1}       shipment s on vehicle v
  assigned[s] in {0,1}   shipment s is carried by some vehicle
  peak in 0..1000        the highest utilization reached, in per-mille

Constraints
  (1) sum over v of x[s,v] == assigned[s]
  (2) capacity:  load[v] = sum over s of demand[s]*x[s,v] <= capacity[v]
  (3) peak bounds every vehicle:  load[v] * 1000 <= peak * capacity[v]

Objective
  minimize   BIG * (packages left unassigned)  +  peak
  Carrying dominates (BIG is huge); among plans that carry the same amount, the
  one with the lowest peak — the most balanced — wins.
```

The `* 1000` trick turns the fractional constraint `load/capacity ≤ peak` into
an all-integer inequality, which CP-SAT handles cleanly (it works in integers).

---

## The Vehicle Routing Problem (VRP) — high level

The **Vehicle Routing Problem** asks: given a depot, a set of delivery
locations, and a fleet of vehicles, find the set of routes (one per vehicle)
that serves every location at the lowest total distance/cost — usually with
extra rules like vehicle capacities and delivery time windows. It generalises
the classic Travelling Salesman Problem (one vehicle, visit everyone once) to
many vehicles with constraints.

Week 5 does **not** solve the full VRP. It implements the **nearest-neighbour
heuristic** — start at the warehouse, always drive to the closest unvisited
stop — which is fast, easy to explain, and typically far shorter than a random
order. It is a strong baseline and a natural first optimizer.

To stay ready for the real thing, routing is written behind a
`RoutingStrategy` interface with the nearest-neighbour strategy implemented and
a `VehicleRoutingProblem` strategy reserved (it raises `NotImplementedError`
today). A later week can drop in OR-Tools' dedicated routing library
(`RoutingModel`, which handles multiple vehicles, capacities, and time windows)
behind that same interface, with no change to the service or the API.

---

## Why a solver time limit

Integer and constraint problems can be hard, so CP-SAT is given a wall-clock
**time limit** (`OPT_SOLVER_TIME_LIMIT_SECONDS`, default 5s). Within the limit
it returns the best plan it has found and a status of `OPTIMAL` (proven best) or
`FEASIBLE` (valid, possibly improvable). This guarantees an endpoint always
responds promptly, even on a large, hard instance.
