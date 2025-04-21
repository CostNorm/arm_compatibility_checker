# **Refined JS Checker Enhancement Plan**

This plan outlines the steps to significantly improve the ARM64 compatibility analysis for JavaScript dependencies (`js_checker.py`), aiming for greater accuracy by checking specific versions and analyzing more detailed metadata.

**Phase 1: Preparation & Foundation (Prerequisites)**

1. **Dependency Setup:**

   - [x] **Confirm & Install `semver`:** Add the Python `semver` library (`pip install semver`) to your project's dependencies (`requirements.txt` or Lambda Layer configuration). Verify it can be packaged and deployed correctly in the Lambda environment.
   - [x] **Confirm Requests:** Ensure the `requests` library is available and correctly configured for network calls.

2. **Caching Strategy Definition:**

   - [x] **Define Cache Keys:**
     - Success: `f"{package_name}@{resolved_version}"` (Stores result for the specific version satisfying the spec).
     - Failure/Fallback: `f"{package_name}@{version_spec}"` (Stores result if spec resolution fails or leads to fallback; the cached data _must_ include the reason for failure/fallback).
   - [x] **Review Cache Scope:** Ensure `_NPM_CACHE` is appropriately managed (global within the module, potentially cleared per invocation if memory is a concern, though less likely needed).

3. **API & Timeout Considerations:**

   - [x] **Rate Limiting:** Be mindful that increased analysis depth might lead to more NPM registry calls. While NPM is generally permissive, excessive calls could theoretically be throttled. Caching is key.
   - [x] **Timeout Strategy:** Implement explicit timeouts for `requests.get` calls to the NPM registry (e.g., 10-15 seconds) to prevent long hangs on network issues.
   - [x] **Overall Lambda Timeout:** Keep the overall Lambda execution time limit in mind, especially if implementing recursive checks.

4. **Code Structure Review:**
   - [x] **`js_checker.py`:** Confirm the `_check_npm_package_compatibility` function structure allows for adding version resolution logic and more detailed checks.
   - [x] **`manager.py` / `parse_dependencies`:** Ensure the parser (`JSDependencyChecker.parse_dependencies`) can distinguish between `dependencies`, `devDependencies`, and `optionalDependencies`, passing this information (e.g., an `is_optional: bool` flag) along in the `dependency_info` dict. (Note: `optionalDependencies` parsing deferred to Phase 3 if needed).

---

**Phase 2: Core Implementation - Specific Version & Enhanced Metadata Analysis**

1. **Task: Implement Specific Version Resolution:**

   - [x] Modify `_check_npm_package_compatibility` to accept `version_spec` as a key argument.
   - [x] Inside the function (after cache check):
     - Fetch full package data: `response = requests.get(f"https://registry.npmjs.org/{package_name}", timeout=15)`. Handle 404s and other HTTP errors.
     - Extract `versions_dict = data.get("versions", {})`.
     - Extract available version strings: `available_versions = list(versions_dict.keys())`.
     - **Find Target Version:**
       - Use `target_version_str = semver.max_satisfying(available_versions, version_spec, loose=True)` (handle potential `ValueError` from invalid `version_spec`).
       - **Handle No Match:** If `target_version_str` is `None`:
         - Log a warning: `f"No version found for {package_name} satisfying spec '{version_spec}'. Falling back to latest."`
         - Determine `latest_version_str = data.get("dist-tags", {}).get("latest")`.
         - Set `target_version_str = latest_version_str`.
         - Mark analysis as potentially inaccurate: `is_fallback = True`.
       - Else (`target_version_str` found): `is_fallback = False`.
     - **Get Version Metadata:** `version_metadata = versions_dict.get(target_version_str)` if `target_version_str` exists, otherwise handle error (shouldn't happen if logic is correct).
   - [x] **Cache Result:** Store the final compatibility result using the appropriate key (Phase 1.2). Include `checked_version: target_version_str` and `spec_satisfied: not is_fallback` in the cached data.

2. **Task: Enhance Metadata Checks (using `version_metadata`):**
   - [x] **Refine `cpu`/`os` Checks:**
     - Get `cpu = version_metadata.get("cpu", [])`, `os = version_metadata.get("os", [])`.
     - Implement stricter logic:
       - `cpu`: If `cpu` exists and _only_ contains non-ARM arches (e.g., `['x64']`, `['ia32']`), set `compatible = False`, `reason = "CPU field excludes ARM64"`. If `arm` or `arm64` is present, `compatible = True` (or `partial` for `arm`). If ambiguous (`['any']` or `!x64`), treat as `unknown` or `partial`.
       - `os`: If `os` exists and explicitly excludes `linux` (e.g., `['!linux']`, `['darwin', 'win32']`), set `compatible = False`, `reason = "OS field excludes Linux"`. If `linux` is present, good sign. If ambiguous (`['any']`), `unknown`.
   - [x] **Check `binary` Field:** If `version_metadata.get("binary")` exists, set `compatible = 'partial'`, `reason = "Contains 'binary' field, may download pre-compiled native code"`.
   - [x] **Check `scripts` for Build Steps:** If `scripts = version_metadata.get("scripts", {})` contains `node-gyp` or `node-pre-gyp` in `install`, `preinstall`, or `postinstall` commands, set `compatible = 'partial'`, `reason = "Uses node-gyp/node-pre-gyp, likely involves native compilation"`.
   - [x] **Consolidate Reasons:** Combine reasons if multiple flags trigger (`partial` takes precedence over `True`, `False` takes precedence over `partial`).

---

## Future Works (Not today)

---

**Phase 3: Advanced Implementation - Transitive Dependency Check (Optional but Recommended)**

- **Warning:** This significantly increases complexity and potential execution time. Implement carefully and monitor performance. Start with `MAX_DEPTH = 1`.

1. **Task: Implement Recursive Check:**

   - [ ] Add `depth=0` parameter to `_check_npm_package_compatibility`. Add `MAX_DEPTH = 1` (or 2, configurable).
   - [ ] Add base case: `if depth >= MAX_DEPTH: return {'compatible': 'unknown', 'reason': 'Max recursion depth reached'}` (or return cached result if available).
   - [ ] **Inside the check (after analyzing the current package):**
     - Identify dependencies to check: `deps_to_check = version_metadata.get('dependencies', {})`. _(Consider adding `optionalDependencies` here if deep checking is desired for them)_.
     - Initialize parent status based on _itself_.
     - Iterate through `deps_to_check.items()`:
       - `dep_name`, `dep_spec = item`.
       - **Check Cache First:** Look for `f"{dep_name}@{dep_spec}"` (or resolved version if you resolve specs recursively, which adds complexity).
       - If not cached or cache incomplete: `dep_result = _check_npm_package_compatibility(dep_name, dep_spec, depth + 1)`.
       - **Propagate Status:**
         - If `dep_result['compatible'] is False`: Parent package `compatible = False`, update parent `reason` (e.g., `"...due to incompatible dependency '{dep_name}'"`). Break loop (one False is enough).
         - If `dep_result['compatible'] == 'partial'` and parent is not `False`: Parent package `compatible = 'partial'`, update parent `reason`.
   - [ ] Ensure results from recursive calls are added to the main cache to avoid re-computation.

2. **Task: Handle `optionalDependencies` (Requires Parser Update):**
   - [ ] Modify the recursive check: If the dependency being checked was marked `is_optional`:
     - If `dep_result['compatible']` is `False` or `partial`: Do _not_ automatically make the parent `False`/`partial`. Instead, add a note/warning to the parent's `reason` (e.g., `"Optional dependency '{dep_name}' may have issues..."`) and potentially add a specific `recommendation`.

---

**Phase 4: Refinement, QA & Testing**

1. **Task: Improve `reason` and `recommendations`:**

   - [ ] Ensure `reason` strings clearly state _why_ a package is flagged (`cpu`, `os`, `binary`, `node-gyp`, `transitive dep X`, `version spec fallback`, etc.).
   - [ ] Generate actionable `recommendations` based on the findings (e.g., "Investigate ARM64 build for X", "Consider alternative for Y due to OS incompatibility", "Verify optional dependency Z").

2. **Task: Comprehensive Unit Testing:**

   - [ ] Test `semver.max_satisfying` logic with various specs (`^ ~ > < = * latest`).
   - [ ] Test fallback logic when no version satisfies the spec.
   - [ ] Test `cpu`, `os`, `binary`, `scripts` detection logic individually and in combination.
   - [ ] Test status propagation (`True`, `partial`, `False`, `unknown`).
   - [ ] Mock `requests` and test cache hit/miss scenarios.
   - [ ] Test recursive check (depth 1) status propagation.
   - [ ] Test `optionalDependencies` logic (if implemented).

3. **Task: Integration Testing:**

   - [ ] Test the full flow: `AnalysisOrchestrator` -> `DependencyManager` -> `JSDependencyChecker` -> `check_compatibility` (with recursion if enabled).
   - [ ] Use sample `package.json` files representing diverse real-world scenarios.

4. **Task: Performance & Stress Testing:**
   - [ ] Analyze repositories with large numbers of JS dependencies.
   - [ ] Monitor execution time in CloudWatch Logs. Ensure it stays well within the Lambda timeout.
   - [ ] Measure cache effectiveness (log cache hits/misses).

---

**Phase 5: Deployment & Monitoring**

1. **Task: Code Review & Merge:**

   - [ ] Submit changes via Pull Requests for review.
   - [ ] Ensure code quality, clarity, and adherence to standards.
   - [ ] Run CI checks (linting, unit tests).

2. **Task: Deployment:**

   - [ ] Update the Lambda function code and dependencies (including the `semver` library).
   - [ ] Consider phased rollout (e.g., canary deployment) if your infrastructure supports it.

3. **Task: Post-Deployment Monitoring:**
   - [ ] Closely monitor CloudWatch Logs for errors, warnings, and execution times after deployment.
   - [ ] Monitor Slack bot interactions for user feedback and analysis result quality. Are the new `partial`/`incompatible` flags accurate and helpful?
   - [ ] Be prepared to rollback if critical issues arise.

---

By following this refined plan, the JS checker will become significantly more accurate, providing developers with much more reliable insights into the potential ARM64 compatibility challenges within their Node.js dependencies. Remember to prioritize Phase 2, as checking the correct version's metadata is the most crucial improvement. Phase 3 (recursion) adds significant value but also risk, so implement and test it cautiously.
