"""
api/routers/ package  (Week 4)
Project: Supply Chain & Logistics Optimizer

WHAT LIVES HERE: the ROUTERS - the actual URL endpoints, one file per entity:

  customers.py   warehouses.py   inventory.py   vehicles.py
  routes.py      orders.py       disruptions.py

WHAT IS A ROUTER?
  A router is a group of related endpoints under a common URL prefix. e.g.
  routers/customers.py owns everything under /customers:
      GET    /customers            list (with filter/search/sort/pagination)
      GET    /customers/{id}       one by id
      POST   /customers           create
      PUT    /customers/{id}       full update
      PATCH  /customers/{id}       partial update
      DELETE /customers/{id}       delete
  main.py includes all seven routers, which is how the whole API is assembled.

THE GOLDEN RULE: ROUTERS ARE THIN
  A router only ever: (1) receives the HTTP request and its parameters,
  (2) calls a SERVICE function, (3) returns the result. It NEVER touches the
  database directly and holds NO business logic. That lives in services/. This
  is what keeps the API easy to test and lets later weeks reuse the services
  without going through HTTP. See docs/rest_api_design.md.

WHAT ARE HTTP METHODS? (zero-knowledge version)
  The "verb" of a request says what you want to do with a thing (a "resource"):
    GET    = read (never changes anything)
    POST   = create a new thing
    PUT    = replace an existing thing
    PATCH  = change part of an existing thing
    DELETE = remove a thing
  REST maps these verbs onto nouns (URLs like /customers/{id}).
"""

from api.routers import (
    customers,
    warehouses,
    inventory,
    vehicles,
    routes,
    orders,
    disruptions,
    optimization,
    execution,
    agents,
)

# The ordered list main.py registers. One APIRouter per module (named `router`).
# The optimization router (Week 5) exposes the /optimize/* endpoints (the raw,
# stateless solvers). The execution router (Week 6) exposes the /optimization/*
# endpoints (the execution layer: run, measure, evaluate, and STORE runs). The
# agents router (Week 7) exposes the /agents/* endpoints (the AI orchestration
# layer that drives the execution layer to make autonomous decisions).
all_routers = [
    customers.router,
    warehouses.router,
    inventory.router,
    vehicles.router,
    routes.router,
    orders.router,
    disruptions.router,
    optimization.router,
    execution.router,
    agents.router,
]
