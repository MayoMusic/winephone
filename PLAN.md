# WinePhone plan

## Status

FP0 complete. FP1 base/top-level pins and selected build-source map recorded. FP2 static audit and source adaptation are in progress. No build or device test has passed.

## Next five actions

1. Finish the remaining reference/source study and rank unresolved technical gaps; retain the local audit hash.
2. Review workflow syntax and resolve any clean-checkout issues found on the first macOS run.
3. User runs `gh auth login`; then create public `winephone`, push the pinned tree, and start the macOS workflow.
4. Diagnose and fix CI failures until a validated unsigned IPA artifact exists, or record a precise blocker.
5. User signs/installs on iPhone 17/iOS 27 and supplies device logs plus the DRM-free test game's name.

## Track A milestones

- **A0 Study:** In progress; pinned sources and audit exist, but reference studies, full catalog, game profile, and gap ranking remain.
- **A1 IPA CI:** Workflow and scripts drafted; acceptance requires a successful macOS build and validated artifact.
- **A2 Device boot:** Not started; requires user installation and device logs.
- **A3-A6:** Not started; depend on A2 and measurements.

## Track B

Research only; not started. No static recompiler or interpreter performance claim is made.

## Publication update (2026-10-14)

- GitHub authentication is active; `MayoMusic/winephone` is created as a public repository.
- Source publication and CI are authorized. Binary distribution remains gated: the source snapshot has conflicting Wine licensing statements and no demonstrated LGPL relink/re-sign/install route.
- Next: push `main`, run the macOS workflow, diagnose failures, and record the exact CI result. The iPhone install/game test remains user-side.
