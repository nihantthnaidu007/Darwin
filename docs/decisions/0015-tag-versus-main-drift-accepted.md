# 0015 Tag-versus-main drift: accept it, do not re-point the tag

Decision: The v0.3.0 tag points to commit d1f7123 while main has advanced two commits ahead (6a6a820, 6bdec83). Accept the drift. Do not re-point, move, or force-update the tag. The applied action is documentation only (this record); no git tag operation is performed.

Context: The v0.3.0 tag correctly marks the released 0.3.0 content at d1f7123. The two extra commits on main are no-op merge commits that changed nothing: git diff v0.3.0..main is empty, so main's tree is byte-identical to the tagged commit (6a6a820 is the merge of PR #2 and 6bdec83 is the merge of PR #3; their net content change relative to the tag is zero). Re-pointing a published tag to the current main tip would require a force-update of an already-published tag, which this project forbids (CONTEXT.md conventions; decision 0005 on honest version tags).

Alternatives rejected:
- Force-update the v0.3.0 tag to the main tip: forbidden by the project's never-force-push-tags rule, and pointless because the trees are identical.
- Cut a new patch tag (v0.3.1) to absorb the two merges: the merges changed no content, so a new tag would advertise a release that is byte-identical to 0.3.0, adding noise without signal.

Consequences: The published v0.3.0 tag stays exactly where it is. The drift is now recorded rather than silently carried, so a fresh session or audit can confirm at a glance that the tag-to-main gap is two no-op merges and not unreleased content. Future releases continue to tag from main with no force-update of existing tags.
