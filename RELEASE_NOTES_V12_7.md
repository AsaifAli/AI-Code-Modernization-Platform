# v12.7.0

## Post-migration autonomous repair

The post-migration stage now owns one bounded repair/revalidation loop for both deterministic and semantic failures. Each completed Agno repair pass is followed by a fresh quality-gate run and fresh semantic/behavioral verification against the changed target tree.

Release packaging is allowed only after both deterministic checks and semantic verification are green.

## API behavior

Attempting to download a migration that has been produced but is blocked by the release gate now returns HTTP 409 with structured release-gate information instead of a misleading 404.
