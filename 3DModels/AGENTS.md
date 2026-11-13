# 3D asset workflow

- Every high-poly revision must be presented to the user for visual approval before starting any mesh reduction or game LOD production.
- Do not infer high-poly approval from a continue request during high-poly revision. Obtain explicit approval of the shown high-poly version.
- High-poly delivery includes an actual render and an interactive model or local model file. Report triangle count and remaining fidelity issues honestly.
- Use additional polygons for visible structural and surface detail, not arbitrary global subdivision to reach a count.
- Store models, reference images and provenance under 3DModels/<EnglishAssetName>/.

- For every model and every generation, revision, high render, texture bake and LOD stage, record start/end or measured duration, model calls, input/output/cache/reasoning tokens when supplied, and USD cost with provenance. Distinguish ledger-calculated estimates from provider charges. Unknown imagegen usage or cost is null, never zero. Local Blender-only work has zero model calls/API tokens/API dollars, with compute cost excluded. Failed or rejected stages remain in the cost ledger.
