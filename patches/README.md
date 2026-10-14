# WinePhone patch series

The checkout is the Madeira base commit recorded in `DECISIONS.md`. Text source
changes are mirrored here as reviewable diffs and are already applied in the
working tree. Binary payload exclusions are represented by tree deletions, not
duplicated as a large binary patch. Regenerate a patch after changing source:

```sh
git diff <base-commit> -- <paths> > patches/NNNN-topic.patch
```

Do not apply these patches to upstream Wine/FEX/DXMT without checking each
component's contribution policy. AI-authored changes stay in this project.
