# precompute.py — fill results/game_cache.json and results/pareto.json
import json, time
from core.game import Game, LEVELS, pareto_front

game = Game()
pareto = {}
for level in LEVELS:
    t = time.time()
    points, pool = game.explore(level, n_samples=60)
    front = pareto_front(points)
    best = min(points, key=lambda p: p["estimation_error"])
    pareto[level] = {
        "points": [{"F": p["F_postselected"], "keep": p["keep_fraction"],
                    "n_checks": p["ancillas"], "error": p["estimation_error"]} for p in points],
        "front": [{"F": p["F_postselected"], "keep": p["keep_fraction"]} for p in front],
        "best_error_N1000": best["estimation_error"],
        "valid_placements": pool,
    }
    print(f"level {level}: {len(points)} configs, {pool} valid placements, "
          f"best error {best['estimation_error']:.3f}, {time.time()-t:.1f}s")
game.save()
with open("results/pareto.json", "w") as f:
    json.dump(pareto, f)
print("Saved results/game_cache.json and results/pareto.json")