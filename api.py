# api.py — run with:  uvicorn api:app --reload
import json, os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from core.game import Game, LEVELS, grid

app = FastAPI(title="Checkpoint API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

game = Game()
PARETO = {}
if os.path.exists("results/pareto.json"):
    with open("results/pareto.json") as f:
        PARETO = json.load(f)


class CheckSpec(BaseModel):
    qubit: int
    pauli: str
    start_layer: int
    end_layer: int


class RunRequest(BaseModel):
    checks: list[CheckSpec] = []
    shot_budget: int = 1000


def _level(level_id):
    if level_id not in LEVELS:
        raise HTTPException(404, "unknown level")
    return LEVELS[level_id]


@app.get("/levels")
def levels():
    return [{"id": lv, **cfg, "t_gates": 2 * cfg["t_inserts"],
             "best_error": PARETO.get(str(lv), {}).get("best_error_N1000")}
            for lv, cfg in LEVELS.items()]


@app.get("/levels/{level_id}")
def level(level_id: int):
    cfg = _level(level_id)
    return {"id": level_id, **cfg, "grid": grid(game.payloads[level_id]),
            "baseline": game.evaluate(level_id, [])}


@app.post("/levels/{level_id}/validate")
def validate(level_id: int, spec: CheckSpec):
    _level(level_id)
    check, reason = game.build_check(level_id, spec.qubit, spec.pauli,
                                     spec.start_layer, spec.end_layer)
    return {"valid": bool(check and check.valid), "reason": reason,
            "pauli_out": check.pauli_out if check and check.valid else None}


@app.post("/levels/{level_id}/run")
def run(level_id: int, req: RunRequest):
    _level(level_id)
    result = game.evaluate(level_id, [c.model_dump() for c in req.checks], req.shot_budget)
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    best = PARETO.get(str(level_id), {}).get("best_error_N1000")
    if best and req.shot_budget == 1000:
        result["stars"] = 3 if result["estimation_error"] <= best * 1.02 else \
                          2 if result["estimation_error"] <= best * 1.15 else 1
    game.save()
    return result


@app.get("/levels/{level_id}/pareto")
def pareto(level_id: int):
    _level(level_id)
    return PARETO.get(str(level_id), {"points": [], "front": []})