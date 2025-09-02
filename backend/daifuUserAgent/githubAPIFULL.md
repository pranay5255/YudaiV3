search
search.code(q, sort, order, per_page, page): Search code
search.commits(q, sort, order, per_page, page): Search commits
search.issues_and_pull_requests(q, sort, order, per_page, page): Search issues and pull requests
search.labels(repository_id, q, sort, order, per_page, page): Search labels
search.repos(q, sort, order, per_page, page): Search repositories
search.topics(q, per_page, page): Search topics
search.users(q, sort, order, per_page, page): Search users


repos
repos.list_for_org(org, type, sort, direction, per_page, page): List organization repositories
repos.create_in_org(org, name, description, homepage, private, visibility, has_issues, has_projects, has_wiki, is_template, team_id, auto_init, gitignore_template, license_template, allow_squash_merge, allow_merge_commit, allow_rebase_merge, allow_auto_merge, delete_branch_on_merge, use_squash_pr_title_as_default): Create an organization repository
repos.get(owner, repo): Get a repository
repos.update(owner, repo, name, description, homepage, private, visibility, security_and_analysis, has_issues, has_projects, has_wiki, is_template, default_branch, allow_squash_merge, allow_merge_commit, allow_rebase_merge, allow_auto_merge, delete_branch_on_merge, allow_update_branch, use_squash_pr_title_as_default, archived, allow_forking): Update a repository
repos.delete(owner, repo): Delete a repository
repos.list_autolinks(owner, repo, page): List all autolinks of a repository
repos.create_autolink(owner, repo, key_prefix, url_template): Create an autolink reference for a repository
repos.get_autolink(owner, repo, autolink_id): Get an autolink reference of a repository
repos.delete_autolink(owner, repo, autolink_id): Delete an autolink reference from a repository
repos.enable_automated_security_fixes(owner, repo): Enable automated security fixes
repos.disable_automated_security_fixes(owner, repo): Disable automated security fixes
repos.list_branches(owner, repo, protected, per_page, page): List branches
repos.get_branch(owner, repo, branch): Get a branch
repos.get_branch_protection(owner, repo, branch): Get branch protection
repos.update_branch_protection(owner, repo, branch, required_status_checks, enforce_admins, required_pull_request_reviews, restrictions, required_linear_history, allow_force_pushes, allow_deletions, block_creations, required_conversation_resolution): Update branch protection
repos.delete_branch_protection(owner, repo, branch): Delete branch protection
repos.get_admin_branch_protection(owner, repo, branch): Get admin branch protection
repos.set_admin_branch_protection(owner, repo, branch): Set admin branch protection
repos.delete_admin_branch_protection(owner, repo, branch): Delete admin branch protection
repos.get_pull_request_review_protection(owner, repo, branch): Get pull request review protection
repos.update_pull_request_review_protection(owner, repo, branch, dismissal_restrictions, dismiss_stale_reviews, require_code_owner_reviews, required_approving_review_count, bypass_pull_request_allowances): Update pull request review protection
repos.delete_pull_request_review_protection(owner, repo, branch): Delete pull request review protection
repos.get_commit_signature_protection(owner, repo, branch): Get commit signature protection
repos.create_commit_signature_protection(owner, repo, branch): Create commit signature protection
repos.delete_commit_signature_protection(owner, repo, branch): Delete commit signature protection
repos.get_status_checks_protection(owner, repo, branch): Get status checks protection
repos.update_status_check_protection(owner, repo, branch, strict, contexts, checks): Update status check protection
repos.remove_status_check_protection(owner, repo, branch): Remove status check protection
repos.get_all_status_check_contexts(owner, repo, branch): Get all status check contexts
repos.add_status_check_contexts(owner, repo, branch, contexts): Add status check contexts
repos.set_status_check_contexts(owner, repo, branch, contexts): Set status check contexts
repos.remove_status_check_contexts(owner, repo, branch, contexts): Remove status check contexts
repos.get_access_restrictions(owner, repo, branch): Get access restrictions
repos.delete_access_restrictions(owner, repo, branch): Delete access restrictions
repos.get_apps_with_access_to_protected_branch(owner, repo, branch): Get apps with access to the protected branch
repos.add_app_access_restrictions(owner, repo, branch, apps): Add app access restrictions
repos.set_app_access_restrictions(owner, repo, branch, apps): Set app access restrictions
repos.remove_app_access_restrictions(owner, repo, branch, apps): Remove app access restrictions
repos.get_teams_with_access_to_protected_branch(owner, repo, branch): Get teams with access to the protected branch
repos.add_team_access_restrictions(owner, repo, branch, teams): Add team access restrictions
repos.set_team_access_restrictions(owner, repo, branch, teams): Set team access restrictions
repos.remove_team_access_restrictions(owner, repo, branch, teams): Remove team access restrictions
repos.get_users_with_access_to_protected_branch(owner, repo, branch): Get users with access to the protected branch
repos.add_user_access_restrictions(owner, repo, branch, users): Add user access restrictions
repos.set_user_access_restrictions(owner, repo, branch, users): Set user access restrictions
repos.remove_user_access_restrictions(owner, repo, branch, users): Remove user access restrictions
repos.rename_branch(owner, repo, branch, new_name): Rename a branch
repos.codeowners_errors(owner, repo, ref): List CODEOWNERS errors
repos.list_collaborators(owner, repo, affiliation, per_page, page): List repository collaborators
repos.check_collaborator(owner, repo, username): Check if a user is a repository collaborator
repos.add_collaborator(owner, repo, username, permission): Add a repository collaborator
repos.remove_collaborator(owner, repo, username): Remove a repository collaborator
repos.get_collaborator_permission_level(owner, repo, username): Get repository permissions for a user
repos.list_commit_comments_for_repo(owner, repo, per_page, page): List commit comments for a repository
repos.get_commit_comment(owner, repo, comment_id): Get a commit comment
repos.update_commit_comment(owner, repo, comment_id, body): Update a commit comment
repos.delete_commit_comment(owner, repo, comment_id): Delete a commit comment
repos.list_commits(owner, repo, sha, path, author, since, until, per_page, page): List commits
repos.list_branches_for_head_commit(owner, repo, commit_sha): List branches for HEAD commit
repos.list_comments_for_commit(owner, repo, commit_sha, per_page, page): List commit comments
repos.create_commit_comment(owner, repo, commit_sha, body, path, position, line): Create a commit comment
repos.list_pull_requests_associated_with_commit(owner, repo, commit_sha, per_page, page): List pull requests associated with a commit
repos.get_commit(owner, repo, ref, page, per_page): Get a commit
repos.get_combined_status_for_ref(owner, repo, ref, per_page, page): Get the combined status for a specific reference
repos.list_commit_statuses_for_ref(owner, repo, ref, per_page, page): List commit statuses for a reference
repos.get_community_profile_metrics(owner, repo): Get community profile metrics
repos.compare_commits(owner, repo, basehead, page, per_page): Compare two commits
repos.get_content(owner, repo, path, ref): Get repository content
repos.create_or_update_file_contents(owner, repo, path, message, content, sha, branch, committer, author): Create or update file contents
repos.delete_file(owner, repo, path, message, sha, branch, committer, author): Delete a file
repos.list_contributors(owner, repo, anon, per_page, page): List repository contributors
repos.list_deployments(owner, repo, sha, ref, task, environment, per_page, page): List deployments
repos.create_deployment(owner, repo, ref, task, auto_merge, required_contexts, payload, environment, description, transient_environment, production_environment): Create a deployment
repos.get_deployment(owner, repo, deployment_id): Get a deployment
repos.delete_deployment(owner, repo, deployment_id): Delete a deployment
repos.list_deployment_statuses(owner, repo, deployment_id, per_page, page): List deployment statuses
repos.create_deployment_status(owner, repo, deployment_id, state, target_url, log_url, description, environment, environment_url, auto_inactive): Create a deployment status
repos.get_deployment_status(owner, repo, deployment_id, status_id): Get a deployment status
repos.create_dispatch_event(owner, repo, event_type, client_payload): Create a repository dispatch event
repos.get_all_environments(owner, repo, per_page, page): Get all environments
repos.get_environment(owner, repo, environment_name): Get an environment
repos.create_or_update_environment(owner, repo, environment_name, wait_timer, reviewers, deployment_branch_policy): Create or update an environment
repos.delete_an_environment(owner, repo, environment_name): Delete an environment
repos.list_forks(owner, repo, sort, per_page, page): List forks
repos.create_fork(owner, repo, organization, name): Create a fork
repos.list_webhooks(owner, repo, per_page, page): List repository webhooks
repos.create_webhook(owner, repo, name, config, events, active): Create a repository webhook
repos.get_webhook(owner, repo, hook_id): Get a repository webhook
repos.update_webhook(owner, repo, hook_id, config, events, add_events, remove_events, active): Update a repository webhook
repos.delete_webhook(owner, repo, hook_id): Delete a repository webhook
repos.get_webhook_config_for_repo(owner, repo, hook_id): Get a webhook configuration for a repository
repos.update_webhook_config_for_repo(owner, repo, hook_id, url, content_type, secret, insecure_ssl): Update a webhook configuration for a repository
repos.list_webhook_deliveries(owner, repo, hook_id, per_page, cursor): List deliveries for a repository webhook
repos.get_webhook_delivery(owner, repo, hook_id, delivery_id): Get a delivery for a repository webhook
repos.redeliver_webhook_delivery(owner, repo, hook_id, delivery_id): Redeliver a delivery for a repository webhook
repos.ping_webhook(owner, repo, hook_id): Ping a repository webhook
repos.test_push_webhook(owner, repo, hook_id): Test the push repository webhook
repos.list_invitations(owner, repo, per_page, page): List repository invitations
repos.update_invitation(owner, repo, invitation_id, permissions): Update a repository invitation
repos.delete_invitation(owner, repo, invitation_id): Delete a repository invitation
repos.list_deploy_keys(owner, repo, per_page, page): List deploy keys
repos.create_deploy_key(owner, repo, title, key, read_only): Create a deploy key
repos.get_deploy_key(owner, repo, key_id): Get a deploy key
repos.delete_deploy_key(owner, repo, key_id): Delete a deploy key
repos.list_languages(owner, repo): List repository languages
repos.enable_lfs_for_repo(owner, repo): Enable Git LFS for a repository
repos.disable_lfs_for_repo(owner, repo): Disable Git LFS for a repository
repos.merge_upstream(owner, repo, branch): Sync a fork branch with the upstream repository
repos.merge(owner, repo, base, head, commit_message): Merge a branch
repos.get_pages(owner, repo): Get a GitHub Pages site
repos.create_pages_site(owner, repo, source): Create a GitHub Pages site
repos.update_information_about_pages_site(owner, repo, cname, https_enforced, public, source): Update information about a GitHub Pages site
repos.delete_pages_site(owner, repo): Delete a GitHub Pages site
repos.list_pages_builds(owner, repo, per_page, page): List GitHub Pages builds
repos.request_pages_build(owner, repo): Request a GitHub Pages build
repos.get_latest_pages_build(owner, repo): Get latest Pages build
repos.get_pages_build(owner, repo, build_id): Get GitHub Pages build
repos.get_pages_health_check(owner, repo): Get a DNS health check for GitHub Pages
repos.get_readme(owner, repo, ref): Get a repository README
repos.get_readme_in_directory(owner, repo, dir, ref): Get a repository README for a directory
repos.list_releases(owner, repo, per_page, page): List releases
repos.create_release(owner, repo, tag_name, target_commitish, name, body, draft, prerelease, discussion_category_name, generate_release_notes): Create a release
repos.get_release_asset(owner, repo, asset_id): Get a release asset
repos.update_release_asset(owner, repo, asset_id, name, label, state): Update a release asset
repos.delete_release_asset(owner, repo, asset_id): Delete a release asset
repos.generate_release_notes(owner, repo, tag_name, target_commitish, previous_tag_name, configuration_file_path): Generate release notes content for a release
repos.get_latest_release(owner, repo): Get the latest release
repos.get_release_by_tag(owner, repo, tag): Get a release by tag name
repos.get_release(owner, repo, release_id): Get a release
repos.update_release(owner, repo, release_id, tag_name, target_commitish, name, body, draft, prerelease, discussion_category_name): Update a release
repos.delete_release(owner, repo, release_id): Delete a release
repos.list_release_assets(owner, repo, release_id, per_page, page): List release assets
repos.upload_release_asset(owner, repo, release_id, name, label): Upload a release asset
repos.get_code_frequency_stats(owner, repo): Get the weekly commit activity
repos.get_commit_activity_stats(owner, repo): Get the last year of commit activity
repos.get_contributors_stats(owner, repo): Get all contributor commit activity
repos.get_participation_stats(owner, repo): Get the weekly commit count
repos.get_punch_card_stats(owner, repo): Get the hourly commit count for each day
repos.create_commit_status(owner, repo, sha, state, target_url, description, context): Create a commit status
repos.list_tags(owner, repo, per_page, page): List repository tags
repos.list_tag_protection(owner, repo): List tag protection states for a repository
repos.create_tag_protection(owner, repo, pattern): Create a tag protection state for a repository
repos.delete_tag_protection(owner, repo, tag_protection_id): Delete a tag protection state for a repository
repos.download_tarball_archive(owner, repo, ref): Download a repository archive (tar)
repos.list_teams(owner, repo, per_page, page): List repository teams
repos.get_all_topics(owner, repo, page, per_page): Get all repository topics
repos.replace_all_topics(owner, repo, names): Replace all repository topics
repos.get_clones(owner, repo, per): Get repository clones
repos.get_top_paths(owner, repo): Get top referral paths
repos.get_top_referrers(owner, repo): Get top referral sources
repos.get_views(owner, repo, per): Get page views
repos.transfer(owner, repo, new_owner, team_ids): Transfer a repository
repos.check_vulnerability_alerts(owner, repo): Check if vulnerability alerts are enabled for a repository
repos.enable_vulnerability_alerts(owner, repo): Enable vulnerability alerts
repos.disable_vulnerability_alerts(owner, repo): Disable vulnerability alerts
repos.download_zipball_archive(owner, repo, ref): Download a repository archive (zip)
repos.create_using_template(template_owner, template_repo, owner, name, description, include_all_branches, private): Create a repository using a template
repos.list_public(since): List public repositories
repos.list_for_authenticated_user(visibility, affiliation, type, sort, direction, per_page, page, since, before): List repositories for the authenticated user
repos.create_for_authenticated_user(name, description, homepage, private, has_issues, has_projects, has_wiki, team_id, auto_init, gitignore_template, license_template, allow_squash_merge, allow_merge_commit, allow_rebase_merge, allow_auto_merge, delete_branch_on_merge, has_downloads, is_template): Create a repository for the authenticated user
repos.list_invitations_for_authenticated_user(per_page, page): List repository invitations for the authenticated user
repos.accept_invitation_for_authenticated_user(invitation_id): Accept a repository invitation
repos.decline_invitation_for_authenticated_user(invitation_id): Decline a repository invitation
repos.list_for_user(username, type, sort, direction, per_page, page): List repositories for a user


pulls
pulls.list(owner, repo, state, head, base, sort, direction, per_page, page): List pull requests
pulls.create(owner, repo, title, head, base, body, maintainer_can_modify, draft, issue): Create a pull request
pulls.list_review_comments_for_repo(owner, repo, sort, direction, since, per_page, page): List review comments in a repository
pulls.get_review_comment(owner, repo, comment_id): Get a review comment for a pull request
pulls.update_review_comment(owner, repo, comment_id, body): Update a review comment for a pull request
pulls.delete_review_comment(owner, repo, comment_id): Delete a review comment for a pull request
pulls.get(owner, repo, pull_number): Get a pull request
pulls.update(owner, repo, pull_number, title, body, state, base, maintainer_can_modify): Update a pull request
pulls.list_review_comments(owner, repo, pull_number, sort, direction, since, per_page, page): List review comments on a pull request
pulls.create_review_comment(owner, repo, pull_number, body, commit_id, path, position, side, line, start_line, start_side, in_reply_to): Create a review comment for a pull request
pulls.create_reply_for_review_comment(owner, repo, pull_number, comment_id, body): Create a reply for a review comment
pulls.list_commits(owner, repo, pull_number, per_page, page): List commits on a pull request
pulls.list_files(owner, repo, pull_number, per_page, page): List pull requests files
pulls.check_if_merged(owner, repo, pull_number): Check if a pull request has been merged
pulls.merge(owner, repo, pull_number, commit_title, commit_message, sha, merge_method): Merge a pull request
pulls.list_requested_reviewers(owner, repo, pull_number, per_page, page): List requested reviewers for a pull request
pulls.request_reviewers(owner, repo, pull_number, reviewers, team_reviewers): Request reviewers for a pull request
pulls.remove_requested_reviewers(owner, repo, pull_number, reviewers, team_reviewers): Remove requested reviewers from a pull request
pulls.list_reviews(owner, repo, pull_number, per_page, page): List reviews for a pull request
pulls.create_review(owner, repo, pull_number, commit_id, body, event, comments): Create a review for a pull request
pulls.get_review(owner, repo, pull_number, review_id): Get a review for a pull request
pulls.update_review(owner, repo, pull_number, review_id, body): Update a review for a pull request
pulls.delete_pending_review(owner, repo, pull_number, review_id): Delete a pending review for a pull request
pulls.list_comments_for_review(owner, repo, pull_number, review_id, per_page, page): List comments for a pull request review
pulls.dismiss_review(owner, repo, pull_number, review_id, message, event): Dismiss a review for a pull request
pulls.submit_review(owner, repo, pull_number, review_id, body, event): Submit a review for a pull request
pulls.update_branch(owner, repo, pull_number, expected_head_sha): Update a pull request branch


issues
issues.list(filter, state, labels, sort, direction, since, collab, orgs, owned, pulls, per_page, page): List issues assigned to the authenticated user
issues.list_for_org(org, filter, state, labels, sort, direction, since, per_page, page): List organization issues assigned to the authenticated user
issues.list_assignees(owner, repo, per_page, page): List assignees
issues.check_user_can_be_assigned(owner, repo, assignee): Check if a user can be assigned
issues.list_for_repo(owner, repo, milestone, state, assignee, creator, mentioned, labels, sort, direction, since, per_page, page): List repository issues
issues.create(owner, repo, title, body, assignee, milestone, labels, assignees): Create an issue
issues.list_comments_for_repo(owner, repo, sort, direction, since, per_page, page): List issue comments for a repository
issues.get_comment(owner, repo, comment_id): Get an issue comment
issues.update_comment(owner, repo, comment_id, body): Update an issue comment
issues.delete_comment(owner, repo, comment_id): Delete an issue comment
issues.list_events_for_repo(owner, repo, per_page, page): List issue events for a repository
issues.get_event(owner, repo, event_id): Get an issue event
issues.get(owner, repo, issue_number): Get an issue
issues.update(owner, repo, issue_number, title, body, assignee, state, milestone, labels, assignees): Update an issue
issues.add_assignees(owner, repo, issue_number, assignees): Add assignees to an issue
issues.remove_assignees(owner, repo, issue_number, assignees): Remove assignees from an issue
issues.list_comments(owner, repo, issue_number, since, per_page, page): List issue comments
issues.create_comment(owner, repo, issue_number, body): Create an issue comment
issues.list_events(owner, repo, issue_number, per_page, page): List issue events
issues.list_labels_on_issue(owner, repo, issue_number, per_page, page): List labels for an issue
issues.add_labels(owner, repo, issue_number, labels): Add labels to an issue
issues.set_labels(owner, repo, issue_number, labels): Set labels for an issue
issues.remove_all_labels(owner, repo, issue_number): Remove all labels from an issue
issues.remove_label(owner, repo, issue_number, name): Remove a label from an issue
issues.lock(owner, repo, issue_number, lock_reason): Lock an issue
issues.unlock(owner, repo, issue_number): Unlock an issue
issues.list_events_for_timeline(owner, repo, issue_number, per_page, page): List timeline events for an issue
issues.list_labels_for_repo(owner, repo, per_page, page): List labels for a repository
issues.create_label(owner, repo, name, color, description): Create a label
issues.get_label(owner, repo, name): Get a label
issues.update_label(owner, repo, name, new_name, color, description): Update a label
issues.delete_label(owner, repo, name): Delete a label
issues.list_milestones(owner, repo, state, sort, direction, per_page, page): List milestones
issues.create_milestone(owner, repo, title, state, description, due_on): Create a milestone
issues.get_milestone(owner, repo, milestone_number): Get a milestone
issues.update_milestone(owner, repo, milestone_number, title, state, description, due_on): Update a milestone
issues.delete_milestone(owner, repo, milestone_number): Delete a milestone
issues.list_labels_for_milestone(owner, repo, milestone_number, per_page, page): List labels for issues in a milestone
issues.list_for_authenticated_user(filter, state, labels, sort, direction, since, per_page, page): List user account issues assigned to the authenticated user


dependency_graph
dependency-graph.diff_range(owner, repo, basehead, name): Get a diff of the dependencies between commits
dependency-graph.create_repository_snapshot(owner, repo, version, job, sha, ref, detector, metadata, manifests, scanned): Create a snapshot of dependencies for a repository


