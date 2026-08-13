# Release Notes — v12.7.1

## Fixes

- Initialize optional KB hierarchy thresholds safely when `test_hierarchy_stats` is absent.
- Run the post-migration executor directly from the main migration workflow instead of nesting a workflow result that can be normalized as a plain dict.
- Normalize post-migration status exclusively through `StepOutput.success` / `StepOutput.stop`.
- Add regression coverage for both failure modes.
